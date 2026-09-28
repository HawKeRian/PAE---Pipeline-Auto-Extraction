"""Generate a standalone Node.js batch pipeline and validate it with Node permissions."""

# ruff: noqa: E501 -- generated JavaScript is intentionally kept in auditable complete statements.

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from pae.domain.enums import ArtifactStatus, OutputFormat, TargetLanguage, TransformationKind
from pae.domain.models import PipelineSpecification
from pae.generation.models import GeneratedPackage, PackageValidation
from pae.persistence.errors import SandboxExecutionFailed, SandboxTimeout, UnsupportedCapability
from pae.runtime_core import execute

JAVASCRIPT_RUNTIME = r"""import crypto from "node:crypto";

const clone = value => structuredClone(value);
const jsonEqual = (a, b) => JSON.stringify(a) === JSON.stringify(b);

function decimalParts(value) {
  const text = String(value);
  if (!/^[+-]?\d+(\.\d+)?$/.test(text)) throw new Error("decimal value is invalid");
  const negative = text.startsWith("-");
  const unsigned = text.replace(/^[+-]/, "");
  const [whole, fraction = ""] = unsigned.split(".");
  const integer = BigInt((negative ? "-" : "") + whole + fraction);
  return { integer, scale: fraction.length };
}

function formatDecimal(integer, scale) {
  const negative = integer < 0n;
  let digits = (negative ? -integer : integer).toString().padStart(scale + 1, "0");
  const text = scale ? `${digits.slice(0, -scale)}.${digits.slice(-scale)}` : digits;
  return negative ? `-${text}` : text;
}

function decimalAdd(left, right) {
  const a = decimalParts(left); const b = decimalParts(right); const scale = Math.max(a.scale, b.scale);
  return formatDecimal(a.integer * 10n ** BigInt(scale - a.scale) + b.integer * 10n ** BigInt(scale - b.scale), scale);
}

function decimalDivideByInteger(value, divisor) {
  const decimal = decimalParts(value); const extra = 18; const quotient = decimal.integer * 10n ** BigInt(extra) / BigInt(divisor);
  let result = formatDecimal(quotient, decimal.scale + extra);
  if (result.includes(".")) result = result.replace(/0+$/u, "").replace(/\.$/u, "");
  return result;
}

function castValue(value, target, parameters) {
  if (value === null || value === undefined) return null;
  if (target === "string") return String(value);
  if (target === "integer") {
    if (!/^[+-]?\d+$/.test(String(value))) throw new Error("integer value is invalid");
    return Number.parseInt(String(value), 10);
  }
  if (target === "decimal") {
    let text = String(value);
    if (parameters.thousands_separator) text = text.split(String(parameters.thousands_separator)).join("");
    if ((parameters.decimal_separator ?? ".") !== ".") text = text.replace(String(parameters.decimal_separator), ".");
    decimalParts(text); return text;
  }
  if (target === "boolean") {
    if (typeof value === "boolean") return value;
    const text = String(value).trim().toLowerCase();
    if (["true", "1", "yes", "y"].includes(text)) return true;
    if (["false", "0", "no", "n"].includes(text)) return false;
    throw new Error("boolean value is invalid");
  }
  if (target === "date") {
    const text = String(value); if (!/^\d{4}-\d{2}-\d{2}$/.test(text)) throw new Error("date value is invalid"); return text;
  }
  if (target === "datetime") {
    const text = String(value).replace(/Z$/, "+00:00"); if (Number.isNaN(Date.parse(text))) throw new Error("datetime value is invalid"); return text;
  }
  if (target === "json") return typeof value === "string" ? JSON.parse(value) : value;
  throw new Error(`unsupported cast target: ${target}`);
}

function compare(value, operator, expected) {
  if (operator === "is_null") return value === null || value === undefined;
  if (operator === "not_null") return value !== null && value !== undefined;
  if (operator === "eq") return jsonEqual(value, expected);
  if (operator === "ne") return !jsonEqual(value, expected);
  if (value === null || value === undefined) return false;
  if (operator === "gt") return value > expected; if (operator === "gte") return value >= expected;
  if (operator === "lt") return value < expected; if (operator === "lte") return value <= expected;
  if (operator === "contains") return String(value).includes(String(expected));
  if (operator === "in") return expected.some(item => jsonEqual(item, value));
  throw new Error(`unsupported filter operator: ${operator}`);
}

function mask(value, strategy) {
  if (value === null || value === undefined) return null; const text = String(value);
  if (strategy === "redact") return "***";
  if (strategy === "last4") return `***${text.slice(-4)}`;
  if (strategy === "hash") return crypto.createHash("sha256").update(text, "utf8").digest("hex");
  if (strategy === "email") { if (!text.includes("@")) return "***"; const [local, domain] = text.split("@", 2); return `${local.slice(0, 1)}***@${domain}`; }
  throw new Error(`unsupported masking strategy: ${strategy}`);
}

function derive(row, inputs, parameters) {
  const values = inputs.map(name => row[name]); const operation = parameters.operation;
  if (operation === "concat") return values.map(value => value ?? "").join(String(parameters.separator ?? ""));
  if (operation === "coalesce") return values.find(value => value !== null && value !== undefined) ?? parameters.default ?? null;
  if (values.length !== 2 || values.some(value => value === null || value === undefined)) throw new Error("arithmetic derive requires two non-null inputs");
  const [left, right] = values;
  if (operation === "add") return typeof left === "string" && /^[-+]?\d/.test(left) ? decimalAdd(left, right) : left + right;
  if (operation === "subtract") return left - right; if (operation === "multiply") return left * right; if (operation === "divide") return left / right;
  throw new Error(`unsupported derive operation: ${operation}`);
}

function aggregate(rows, rule) {
  const parameters = rule.parameters; const groups = parameters.group_by ?? []; const input = rule.inputs[0];
  const output = rule.output ?? `${parameters.function}_${input}`; const grouped = new Map();
  for (const row of rows) { const key = JSON.stringify(groups.map(name => row[name] ?? null)); if (!grouped.has(key)) grouped.set(key, []); grouped.get(key).push(row); }
  return [...grouped.entries()].map(([key, members]) => {
    const groupValues = JSON.parse(key); const values = members.map(row => row[input]).filter(value => value !== null && value !== undefined);
    let result; if (parameters.function === "count") result = parameters.count_all ? members.length : values.length;
    else if (parameters.function === "sum") result = values.reduce((total, value) => decimalAdd(total, value), "0");
    else if (parameters.function === "min") result = values.length ? values.reduce((a, b) => a < b ? a : b) : null;
    else if (parameters.function === "max") result = values.length ? values.reduce((a, b) => a > b ? a : b) : null;
    else if (parameters.function === "avg") result = values.length ? decimalDivideByInteger(values.reduce((total, value) => decimalAdd(total, value), "0"), values.length) : null;
    else throw new Error(`unsupported aggregate function: ${parameters.function}`);
    return Object.assign(Object.fromEntries(groups.map((name, index) => [name, groupValues[index]])), { [output]: result });
  });
}

function validate(rule, rows) {
  const issues = []; const seen = new Set();
  rows.forEach((row, row_index) => { const value = row[rule.field]; let valid = true; const p = rule.parameters ?? {};
    if (rule.kind === "not_null") valid = value !== null && value !== undefined;
    else if (rule.kind === "unique") { const key = JSON.stringify(value); valid = value == null || !seen.has(key); seen.add(key); }
    else if (rule.kind === "range") valid = value == null || ((p.minimum == null || value >= p.minimum) && (p.maximum == null || value <= p.maximum));
    else if (rule.kind === "regex") valid = value == null || new RegExp(`^(?:${p.pattern})$`, "u").test(String(value));
    else if (rule.kind === "allowed_values") valid = value == null || (p.values ?? []).some(item => jsonEqual(item, value));
    if (!valid) issues.push({ rule_id: rule.rule_id, row_index, field: rule.field, severity: rule.severity ?? "error", message: `${rule.kind} validation failed for ${rule.field}` });
  }); return issues;
}

export function execute(specification, sourceRows) {
  let rows = clone(sourceRows); const rejected = []; const rule_impacts = [];
  for (const rule of [...(specification.transformations ?? [])].sort((a, b) => a.order - b.order)) {
    if (rule.enabled === false) continue; const beforeRows = clone(rows); const before = rows.length; const p = rule.parameters ?? {}; const inputs = rule.inputs;
    try {
      if (rule.kind === "include") rows = rows.map(row => Object.fromEntries(inputs.filter(name => name in row).map(name => [name, row[name]])));
      else if (rule.kind === "exclude") rows = rows.map(row => Object.fromEntries(Object.entries(row).filter(([name]) => !inputs.includes(name))));
      else if (rule.kind === "rename") rows = rows.map(row => Object.fromEntries(Object.entries(row).map(([name, value]) => [name === inputs[0] ? rule.output : name, value])));
      else if (rule.kind === "cast") { const kept = []; rows.forEach((row, row_index) => { try { row[inputs[0]] = castValue(row[inputs[0]], p.type, p); kept.push(row); } catch (error) { rejected.push({ row_index, rule_id: rule.rule_id, reason: error.message, row }); } }); rows = kept; }
      else if (rule.kind === "filter") rows = rows.filter(row => compare(row[inputs[0]], p.operator, p.value));
      else if (rule.kind === "sort") { const direction = p.direction === "descending" ? -1 : 1; rows.sort((a, b) => { for (const name of inputs) { const left = a[name], right = b[name]; if (left == null || right == null) { if (left == null && right == null) continue; return (left == null ? (p.nulls === "first" ? -1 : 1) : (p.nulls === "first" ? 1 : -1)); } if (left < right) return -direction; if (left > right) return direction; } return 0; }); }
      else if (rule.kind === "deduplicate") { const keys = p.keys ?? inputs; const source = p.survivor === "last" ? [...rows].reverse() : rows; const seen = new Set(); const unique = []; for (const row of source) { const key = JSON.stringify(keys.map(name => row[name] ?? null)); if (!seen.has(key)) { seen.add(key); unique.push(row); } } rows = p.survivor === "last" ? unique.reverse() : unique; }
      else if (rule.kind === "replace") rows.forEach(row => { if (jsonEqual(row[inputs[0]], p.old)) row[inputs[0]] = p.new; });
      else if (rule.kind === "handle_null") rows.forEach(row => { if (row[inputs[0]] == null) row[inputs[0]] = p.value; });
      else if (rule.kind === "derive") rows.forEach(row => { row[rule.output] = derive(row, inputs, p); });
      else if (rule.kind === "aggregate") rows = aggregate(rows, rule);
      else if (rule.kind === "mask") rows.forEach(row => { row[inputs[0]] = mask(row[inputs[0]], p.strategy ?? "redact"); });
      else if (rule.kind === "join") throw new Error("multi-source join is deferred"); else throw new Error(`unsupported transformation kind: ${rule.kind}`);
    } catch (error) { throw new Error(`rule ${rule.rule_id} failed: ${error.message}`); }
    const changed_count = before !== rows.length ? Math.abs(before - rows.length) : rows.filter((row, index) => !jsonEqual(row, beforeRows[index])).length;
    rule_impacts.push({ rule_id: rule.rule_id, kind: rule.kind, before_count: before, after_count: rows.length, changed_count });
  }
  const issues = (specification.validations ?? []).flatMap(rule => validate(rule, rows)); const rejectedIndexes = new Set(issues.filter(issue => issue.severity === "error").map(issue => issue.row_index));
  if (rejectedIndexes.size && specification.error_policy === "fail_job") throw new Error("validation failed and error_policy is fail_job");
  rows.forEach((row, row_index) => { if (rejectedIndexes.has(row_index)) { const failed = issues.filter(issue => issue.severity === "error" && issue.row_index === row_index); rejected.push({ row_index, rule_id: failed[0].rule_id, reason: failed.map(issue => issue.message).join("; "), row }); } });
  const sensitive = new Set((specification.fields ?? []).filter(field => field.pii_classification !== "none").flatMap(field => [field.source_name, field.target_name]));
  rejected.forEach(item => { item.row = Object.fromEntries(Object.entries(item.row).map(([name, value]) => [name, sensitive.has(name) && value != null ? "***" : value])); });
  const output_rows = rows.filter((_, index) => !rejectedIndexes.has(index));
  return { output_rows, rejected_rows: rejected, issues, rule_impacts, input_count: sourceRows.length, output_count: output_rows.length, rejected_count: rejected.length };
}
"""


JAVASCRIPT_RUNNER = r"""import fs from "node:fs";
import { execute } from "./runtime.mjs";
const request = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
fs.writeFileSync(process.argv[3], JSON.stringify(execute(request.specification, request.rows)));
"""


JAVASCRIPT_PIPELINE = r"""import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { execute } from "./runtime.mjs";

function args() { const values = Object.fromEntries(process.argv.slice(2).reduce((all, value, index, array) => { if (value.startsWith("--")) all.push([value.slice(2), array[index + 1]]); return all; }, [])); for (const name of ["input-dir", "output-dir", "quarantine-dir", "state-file"]) if (!values[name]) throw new Error(`missing --${name}`); return values; }
function csv(text, delimiter = ",") { const records = []; let record = [], field = "", quoted = false; for (let index = 0; index < text.length; index++) { const char = text[index]; if (quoted && char === '"' && text[index + 1] === '"') { field += '"'; index++; } else if (char === '"') quoted = !quoted; else if (char === delimiter && !quoted) { record.push(field); field = ""; } else if ((char === "\n" || char === "\r") && !quoted) { if (char === "\r" && text[index + 1] === "\n") index++; record.push(field); if (record.some(value => value !== "")) records.push(record); record = []; field = ""; } else field += char; } if (field || record.length) { record.push(field); records.push(record); } const headers = records.shift() ?? []; return records.map(values => Object.fromEntries(headers.map((name, index) => [name, values[index] ?? ""]))); }
async function read(file, source) { const textFormats = ["csv", "json", "json_lines"]; if (textFormats.includes(source.file_format)) { const text = fs.readFileSync(file, source.encoding ?? "utf8"); if (source.file_format === "csv") return csv(text, source.delimiter ?? ","); if (source.file_format === "json") { const value = JSON.parse(text); return Array.isArray(value) ? value : [value]; } return text.split(/\r?\n/u).filter(Boolean).map(JSON.parse); } if (source.file_format === "excel") { const ExcelJS = (await import("exceljs")).default; const book = new ExcelJS.Workbook(); await book.xlsx.readFile(file); const sheet = source.sheet_name ? book.getWorksheet(source.sheet_name) : book.worksheets[0]; const headers = sheet.getRow(1).values.slice(1).map(String); return sheet.getRows(2, sheet.rowCount - 1).map(row => Object.fromEntries(headers.map((name, index) => [name, row.getCell(index + 1).value]))); } if (source.file_format === "parquet") { const { ParquetReader } = await import("parquetjs-lite"); const reader = await ParquetReader.openFile(file); const cursor = reader.getCursor(); const rows = []; let row; while ((row = await cursor.next())) rows.push(row); await reader.close(); return rows; } throw new Error(`Unsupported file format ${source.file_format}`); }
async function readDatabase(source) { const config = JSON.parse(process.env[source.connection_ref]); const query = source.read_only_query ?? `SELECT * FROM ${source.schema_name ? `${source.schema_name}.` : ""}${source.object_name}`; if (source.database_type === "postgresql") { const { Client } = await import("pg"); const client = new Client(config); await client.connect(); try { return (await client.query(query)).rows.slice(0, source.sample_limit); } finally { await client.end(); } } if (source.database_type === "mysql") { const mysql = await import("mysql2/promise"); const connection = await mysql.createConnection(config); try { const [rows] = await connection.query(query); return rows.slice(0, source.sample_limit); } finally { await connection.end(); } } if (source.database_type === "sql_server") { const sql = await import("mssql"); const pool = await sql.connect(config); try { return (await pool.request().query(query)).recordset.slice(0, source.sample_limit); } finally { await pool.close(); } } throw new Error(`Unsupported database ${source.database_type}`); }
function encode(rows, format) { if (format === "json_lines") return rows.map(row => JSON.stringify(row)).join("\n") + "\n"; const fields = rows.length ? Object.keys(rows[0]) : []; return [fields.join(","), ...rows.map(row => fields.map(name => row[name] ?? "").join(","))].join("\n") + "\n"; }
function atomicWrite(file, content, append) { fs.mkdirSync(path.dirname(file), { recursive: true }); const temporary = `${file}.${process.pid}.tmp`; const prior = append && fs.existsSync(file) ? fs.readFileSync(file, "utf8") : ""; try { fs.writeFileSync(temporary, prior + content); fs.renameSync(temporary, file); } catch (error) { fs.rmSync(temporary, { force: true }); throw error; } }
function validate(rows, spec, source) { const actual = new Set(rows.flatMap(Object.keys)); const selected = spec.fields.filter(field => field.selected); const missing = selected.filter(field => field.required && !actual.has(field.source_name)).map(field => field.source_name); const extra = [...actual].filter(name => !selected.some(field => field.source_name === name)); if (missing.length || (extra.length && source.runtime.schema_policy === "strict")) throw new Error(`schema incompatible; missing=${missing}, extra=${extra}`); }
function discover(root, pattern, recursive) { const escaped = pattern.replace(/[.+^${}()|[\]\\]/gu, "\\$&").replaceAll("**", "§§").replaceAll("*", "[^/]*").replaceAll("§§", ".*"); const matcher = new RegExp(`^${escaped}$`, "u"); const found = []; function visit(directory) { for (const entry of fs.readdirSync(directory, { withFileTypes: true })) { const absolute = path.join(directory, entry.name); if (entry.isDirectory() && recursive) visit(absolute); else if (entry.isFile()) { const relative = path.relative(root, absolute).split(path.sep).join("/"); if (matcher.test(relative)) found.push(relative); } } } visit(root); return found.sort(); }
function outputFile(root, inputName, output, extension) { const stem = path.parse(inputName).name; const template = output.path_template ?? "output/result"; const hasToken = template.includes("{stem}") || template.includes("{name}"); const rendered = template.replaceAll("{stem}", stem).replaceAll("{name}", path.basename(inputName)); const relative = `${hasToken ? rendered : `${rendered}-${stem}`}${extension}`; if (path.isAbsolute(relative) || relative.split(/[\\/]/u).includes("..")) throw new Error("output path escaped output directory"); return path.join(root, relative); }
async function main() { const options = args(); const spec = JSON.parse(fs.readFileSync(new URL("./pipeline_spec.json", import.meta.url))); const source = spec.sources[0]; const extension = spec.output.format === "csv" ? ".csv" : ".jsonl"; if (source.kind === "database") { const rows = await readDatabase(source); const result = execute(spec, rows); atomicWrite(outputFile(options["output-dir"], "database", spec.output, extension), encode(result.output_rows, spec.output.format), spec.output.write_mode === "append"); console.log(JSON.stringify({ discovered: 1, processed: 1, skipped: 0, failed: 0, rejected: result.rejected_count })); return 0; } const state = fs.existsSync(options["state-file"]) ? JSON.parse(fs.readFileSync(options["state-file"], "utf8")) : { processed: {} }; const files = discover(options["input-dir"], source.runtime.filename_pattern, source.runtime.recursive); const summary = { discovered: files.length, processed: 0, skipped: 0, failed: 0, rejected: 0 }; for (const name of files) { const file = path.join(options["input-dir"], name); const digest = crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex"); if (state.processed[name] === digest) { summary.skipped++; continue; } try { const rows = await read(file, source); validate(rows, spec, source); const result = execute(spec, rows); const output = outputFile(options["output-dir"], name, spec.output, extension); atomicWrite(output, encode(result.output_rows, spec.output.format), spec.output.write_mode === "append"); if (result.rejected_rows.length) atomicWrite(path.join(options["quarantine-dir"], `${name}.rejected.jsonl`), result.rejected_rows.map(row => JSON.stringify(row)).join("\n") + "\n", false); state.processed[name] = digest; atomicWrite(options["state-file"], JSON.stringify(state, null, 2), false); summary.processed++; summary.rejected += result.rejected_count; } catch (error) { summary.failed++; if (source.runtime.failure_policy === "quarantine") { const target = path.join(options["quarantine-dir"], name); fs.mkdirSync(path.dirname(target), { recursive: true }); fs.copyFileSync(file, target); fs.writeFileSync(`${target}.error.json`, JSON.stringify({ error: error.message })); } if (source.runtime.failure_policy === "fail_batch") break; } } console.log(JSON.stringify(summary)); return summary.failed ? 1 : 0; }
try { process.exitCode = await main(); } catch (error) { console.error(error.message); process.exitCode = 2; }
"""


class JavaScriptGenerator:
    """Render and validate a Node.js package without embedding local secrets or paths."""

    def generate(self, specification: PipelineSpecification) -> GeneratedPackage:
        if specification.target.language is not TargetLanguage.JAVASCRIPT:
            raise UnsupportedCapability("The JavaScript generator requires target javascript.")
        if specification.output.format not in {OutputFormat.CSV, OutputFormat.JSON_LINES}:
            raise UnsupportedCapability("JavaScript output supports CSV and JSON Lines only.")
        if specification.joins or any(
            rule.kind is TransformationKind.JOIN for rule in specification.transformations
        ):
            raise UnsupportedCapability("Multi-source Join is Deferred for JavaScript generation.")
        if len(specification.sources) != 1:
            raise UnsupportedCapability("JavaScript generation supports one source in the MVP.")
        source = specification.sources[0]
        if source.kind == "file" and (
            Path(source.original_name).name != source.original_name or ":" in source.original_name
        ):
            raise UnsupportedCapability("Sample paths cannot be embedded in generated packages.")
        if source.kind == "database" and any(
            marker in source.connection_ref for marker in ("://", "=", ";")
        ):
            raise UnsupportedCapability("connection_ref must name an environment variable.")
        dependencies: dict[str, str] = {}
        if source.kind == "file" and source.file_format == "excel":
            dependencies["exceljs"] = "4.4.0"
        elif source.kind == "file" and source.file_format == "parquet":
            dependencies["parquetjs-lite"] = "0.8.7"
        elif source.kind == "database":
            dependencies[
                {"postgresql": "pg", "mysql": "mysql2", "sql_server": "mssql"}[source.database_type]
            ] = {"postgresql": "8.16.3", "mysql": "3.15.1", "sql_server": "12.0.0"}[
                source.database_type
            ]
        files = {
            "pipeline.mjs": JAVASCRIPT_PIPELINE,
            "runtime.mjs": JAVASCRIPT_RUNTIME,
            "sample_runner.mjs": JAVASCRIPT_RUNNER,
            "pipeline_spec.json": json.dumps(
                specification.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True
            )
            + "\n",
            "package.json": json.dumps(
                {
                    "name": specification.name,
                    "private": True,
                    "type": "module",
                    "engines": {"node": ">=20"},
                    "scripts": {"start": "node pipeline.mjs", "test": "node --test"},
                    "dependencies": dependencies,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            "config.example.env": "PAE_LOG_LEVEL=info\n# Database connection JSON is supplied through connection_ref when applicable.\n",
            "tests/runtime.test.mjs": "import test from 'node:test';\nimport assert from 'node:assert/strict';\nimport { execute } from '../runtime.mjs';\ntest('runtime executes', () => assert.equal(execute({transformations: []}, [{}]).input_count, 1));\n",
            "README.md": f"# {specification.name}\n\nRun with Node.js 20+ using `node pipeline.mjs --input-dir INPUT --output-dir OUTPUT --quarantine-dir QUARANTINE --state-file state.json`. Database credentials are resolved only from the environment variable named by `connection_ref`.\n",
        }
        payload = "".join(f"{name}\0{files[name]}\0" for name in sorted(files))
        return GeneratedPackage(files=files, checksum=hashlib.sha256(payload.encode()).hexdigest())

    @staticmethod
    def syntax_validate(package: GeneratedPackage) -> PackageValidation:
        node = shutil.which("node")
        if node is None:
            raise SandboxExecutionFailed("Node.js is required to validate generated JavaScript.")
        checked = tuple(sorted(name for name in package.files if name.endswith(".mjs")))
        with tempfile.TemporaryDirectory(prefix="pae-js-syntax-") as directory:
            root = Path(directory)
            for name, content in package.files.items():
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            for name in checked:
                completed = subprocess.run(
                    [node, "--check", str(root / name)],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                if completed.returncode:
                    raise SandboxExecutionFailed("Generated JavaScript failed syntax validation.")
        return PackageValidation(
            status=ArtifactStatus.SYNTAX_VALIDATED,
            syntax_valid=True,
            sample_matches_preview=False,
            checked_files=checked,
        )

    @staticmethod
    def sample_validate(
        package: GeneratedPackage,
        specification: PipelineSpecification,
        rows: tuple[dict[str, Any], ...],
        *,
        timeout_seconds: float = 10,
    ) -> PackageValidation:
        JavaScriptGenerator.syntax_validate(package)
        node = shutil.which("node")
        assert node is not None
        with tempfile.TemporaryDirectory(prefix="pae-js-sandbox-") as directory:
            root = Path(directory).resolve()
            for name in ("runtime.mjs", "sample_runner.mjs"):
                (root / name).write_text(package.files[name], encoding="utf-8")
            request = root / "request.json"
            output = root / "output.json"
            request.write_text(
                json.dumps(
                    {
                        "specification": specification.model_dump(mode="json"),
                        "rows": list(rows),
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            command = [
                node,
                "--permission",
                f"--allow-fs-read={root}",
                f"--allow-fs-write={root}",
                "--max-old-space-size=128",
                "--disallow-code-generation-from-strings",
                str(root / "sample_runner.mjs"),
                str(request),
                str(output),
            ]
            try:
                completed = subprocess.run(
                    command,
                    cwd=root,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    check=False,
                    env={
                        "PATH": str(Path(node).parent),
                        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
                        "TEMP": str(root),
                        "TMP": str(root),
                        "NODE_NO_WARNINGS": "1",
                    },
                )
            except subprocess.TimeoutExpired as exc:
                raise SandboxTimeout("JavaScript sample execution timed out.") from exc
            if completed.returncode or not output.exists():
                raise SandboxExecutionFailed("JavaScript sample execution failed in the sandbox.")
            actual = json.loads(output.read_text(encoding="utf-8"))
        expected = execute(specification.model_dump(mode="json"), list(rows))
        matches = actual == expected
        return PackageValidation(
            status=ArtifactStatus.SAMPLE_TESTED if matches else ArtifactStatus.SYNTAX_VALIDATED,
            syntax_valid=True,
            sample_matches_preview=matches,
            checked_files=("runtime.mjs", "sample_runner.mjs"),
        )
