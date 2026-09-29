"use strict";

const state = { token: sessionStorage.getItem("paeToken"), project: null, revision: 0, profile: null, rows: [], proposal: null, artifact: null, pendingWorkbook: null };
const $ = (id) => document.getElementById(id);
const toast = (message) => { $("toast").textContent = message; $("toast").classList.add("show"); setTimeout(() => $("toast").classList.remove("show"), 5000); };
const busy = (button, value, label = "กำลังทำงาน…") => { button.disabled = value; if (value) { button.dataset.label = button.textContent; button.textContent = label; } else if (button.dataset.label) button.textContent = button.dataset.label; };

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (state.token) headers.set("Authorization", `Bearer ${state.token}`);
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(`/api/v1${path}`, { ...options, headers });
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try { message = (await response.json()).error.message; } catch (_) { /* safe fallback */ }
    if (response.status === 401) endSession(false);
    throw new Error(message);
  }
  if (response.status === 204) return null;
  return response.headers.get("content-type")?.includes("json") ? response.json() : response;
}

function showStep(step) {
  document.querySelectorAll("[data-panel]").forEach((panel) => { panel.hidden = Number(panel.dataset.panel) !== step; });
  document.querySelectorAll("[data-step]").forEach((button) => button.classList.toggle("active", Number(button.dataset.step) === step));
  document.querySelector(`[data-panel="${step}"]`)?.querySelector("h2")?.focus?.();
}

function parseLocalCsv(file) {
  if (!file.name.toLowerCase().endsWith(".csv")) return Promise.resolve([]);
  return file.text().then((text) => {
    const lines = text.split(/\r?\n/).filter(Boolean).slice(0, 51);
    if (lines.length < 2) return [];
    const delimiter = lines[0].includes(";") ? ";" : ",";
    const headers = lines[0].split(delimiter).map((value) => value.trim());
    return lines.slice(1).map((line) => Object.fromEntries(headers.map((name, index) => [name, line.split(delimiter)[index] ?? ""])));
  });
}

async function loadProjects() {
  const list = await api("/projects");
  $("project-list").replaceChildren(...list.map((project) => {
    const item = document.createElement("li"); const button = document.createElement("button");
    button.textContent = `${project.name} · r${project.current_revision}`; button.addEventListener("click", () => openProject(project)); item.append(button); return item;
  }));
  $("project-empty").hidden = list.length > 0;
}

async function openProject(project) {
  state.pendingWorkbook = null; $("source-result").replaceChildren();
  state.project = project; state.revision = project.current_revision; $("project-title").textContent = project.name;
  $("revision-state").textContent = `Revision ${project.current_revision} · ${project.specification_confirmed ? "Specification confirmed" : "รอการยืนยัน"}`;
  sessionStorage.setItem("paeProject", project.project_id); await loadArtifacts();
  const recoverJob = sessionStorage.getItem(`paeJob:${project.project_id}`); if (recoverJob) pollJob(recoverJob);
  showStep(1);
}

function renderSchema(profile) {
  $("schema-fields").replaceChildren(...profile.fields.map((field, index) => {
    const row = document.createElement("div"); row.className = "field-row";
    row.innerHTML = `<label><input type="checkbox" data-select checked> <strong></strong></label><span class="badge">Inferred</span><label>ชนิด<select data-type>${["string","integer","decimal","boolean","date","datetime","json"].map((type) => `<option ${type === field.inferred_type ? "selected" : ""}>${type}</option>`).join("")}</select></label><small></small>`;
    row.querySelector("strong").textContent = field.name; row.querySelector("small").textContent = `confidence ${Math.round(field.confidence * 100)}% · null ${field.null_percentage}% · ${field.samples_masked.join(", ")}`; row.dataset.index = index; return row;
  }));
}

async function loadArtifacts() {
  if (!state.project) return;
  const artifacts = await api(`/projects/${state.project.project_id}/artifacts`);
  if (!artifacts.length) return;
  $("artifact-list").classList.remove("empty");
  $("artifact-list").replaceChildren(...artifacts.map((artifact) => {
    const row = document.createElement("div"); row.className = "artifact-row";
    const files = artifact.manifest.files?.map((file) => file.path).join(", ") || "legacy manifest";
    row.innerHTML = `<strong>Revision ${artifact.revision}</strong><span class="badge"></span><small></small><button>ดาวน์โหลด ZIP</button>`;
    row.querySelector(".badge").textContent = artifact.stale ? "Historical · stale" : artifact.artifact_status;
    row.querySelector("small").textContent = files; const button = row.querySelector("button"); button.disabled = !artifact.download_available; button.addEventListener("click", () => downloadArtifact(artifact)); return row;
  }));
}

async function downloadArtifact(artifact) {
  const response = await api(`/projects/${state.project.project_id}/artifacts/${artifact.artifact_id}/download`);
  const blob = await response.blob(); const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = `pae-${artifact.artifact_id}.zip`; link.click(); URL.revokeObjectURL(link.href);
}

async function endSession(callApi = true) {
  if (callApi && state.token) { try { await api("/auth/logout", { method: "POST" }); } catch (_) { /* local cleanup still required */ } }
  state.token = null; state.project = null; sessionStorage.removeItem("paeToken"); sessionStorage.removeItem("paeProject"); $("app").hidden = true; $("login-card").hidden = false; $("logout").hidden = true; $("connection-state").textContent = "ออกจากระบบแล้ว";
}

$("login-form").addEventListener("submit", async (event) => { event.preventDefault(); state.token = $("token").value; sessionStorage.setItem("paeToken", state.token); try { await loadProjects(); $("login-card").hidden = true; $("app").hidden = false; $("logout").hidden = false; $("connection-state").textContent = "เชื่อมต่อ API แล้ว"; } catch (error) { endSession(false); toast(error.message); } });
$("logout").addEventListener("click", () => endSession(true)); $("refresh-projects").addEventListener("click", () => loadProjects().catch((error) => toast(error.message)));
document.querySelectorAll("[data-step]").forEach((button) => button.addEventListener("click", () => showStep(Number(button.dataset.step))));

$("project-form").addEventListener("submit", async (event) => { event.preventDefault(); try { const project = await api("/projects", { method: "POST", body: JSON.stringify({ name: $("project-name").value }) }); await loadProjects(); await openProject(project); } catch (error) { toast(error.message); } });

function applyFileAnalysis(result, rows = []) {
  state.pendingWorkbook = null; state.profile = result.profile; state.rows = rows; state.revision = result.revision;
  const sheet = result.analysis.metadata.sheet_name ? ` · Sheet ${result.analysis.metadata.sheet_name}` : "";
  $("source-result").className = "result";
  $("source-result").textContent = `อ่านสำเร็จ ${result.profile.sampled_rows} แถว · พบ ${result.profile.fields.length} columns${sheet}`;
  renderSchema(result.profile); showStep(2);
}

function renderWorkbookSelection(result) {
  state.pendingWorkbook = result;
  const projectId = state.project.project_id;
  const container = $("source-result"); container.className = "result"; container.replaceChildren();
  const title = document.createElement("h3"); title.textContent = `พบ ${result.inspection.sheets.length} Sheets — เลือก Sheet ที่ต้องการวิเคราะห์`;
  const note = document.createElement("p"); note.textContent = "ระบบอ่านเฉพาะ header และตัวอย่างแบบจำกัด ยังไม่สร้าง revision จนกว่าคุณจะเลือก";
  const options = document.createElement("div"); options.className = "sheet-picker";
  let firstReady = true;
  result.inspection.sheets.forEach((sheet) => {
    const label = document.createElement("label"); label.className = `sheet-option ${sheet.status}`;
    const radio = document.createElement("input"); radio.type = "radio"; radio.name = "workbook-sheet"; radio.value = sheet.name; radio.disabled = sheet.status !== "ready" || sheet.visibility !== "visible"; radio.checked = !radio.disabled && firstReady; if (radio.checked) firstReady = false;
    const content = document.createElement("span"); const heading = document.createElement("strong"); heading.textContent = sheet.name;
    const details = document.createElement("small"); details.textContent = sheet.status === "ready" ? `${sheet.total_rows} rows · ${sheet.column_count} columns · ${sheet.columns.join(", ")}` : `${sheet.status} · ${sheet.warning || "ไม่มีตารางข้อมูลที่พร้อมวิเคราะห์"}`;
    if (sheet.visibility !== "visible") details.textContent += ` · ${sheet.visibility} (ไม่สามารถเลือกได้)`;
    content.append(heading, details); label.append(radio, content); options.append(label);
  });
  const choose = document.createElement("button"); choose.type = "button"; choose.textContent = "วิเคราะห์ Sheet ที่เลือก"; choose.disabled = firstReady;
  choose.addEventListener("click", async () => {
    if (state.project?.project_id !== projectId || state.pendingWorkbook !== result) return;
    const selected = container.querySelector('input[name="workbook-sheet"]:checked'); if (!selected) return;
    busy(choose, true, "กำลังวิเคราะห์ Sheet…");
    try {
      const analyzed = await api(`/projects/${projectId}/file-sources/${result.upload_id}/select-sheet`, { method: "POST", body: JSON.stringify({ original_name: result.inspection.original_name, sheet_name: selected.value, filename_pattern: $("filename-pattern").value, sample_row_limit: 10000 }) });
      if (state.project?.project_id === projectId && state.pendingWorkbook === result) applyFileAnalysis(analyzed);
    } catch (error) { toast(error.message); } finally { busy(choose, false); }
  });
  container.append(title, note, options, choose);
}

$("upload-form").addEventListener("submit", async (event) => { event.preventDefault(); if (!state.project) return toast("เลือก Project ก่อน"); const button = event.submitter; busy(button, true, "กำลังอ่านและ profile…"); try { const file = $("source-file").files[0]; const form = new FormData(); form.append("file", file); form.append("filename_pattern", $("filename-pattern").value); const [result, rows] = await Promise.all([api(`/projects/${state.project.project_id}/file-sources`, { method: "POST", body: form }), parseLocalCsv(file)]); if (result.status === "sheet_selection_required") { renderWorkbookSelection(result); return; } applyFileAnalysis(result, rows); } catch (error) { $("source-result").textContent = `ผิดพลาด: ${error.message}`; toast(error.message); } finally { busy(button, false); } });

$("database-form").addEventListener("submit", async (event) => { event.preventDefault(); if (!state.project) return toast("เลือก Project ก่อน"); const body = { database_type: $("db-type").value, host: $("db-host").value, port: Number($("db-port").value), database: $("db-name").value, username: $("db-user").value, connection_ref: $("db-ref").value, tls_mode: "verify_identity" }; try { await api(`/projects/${state.project.project_id}/database-sources/test`, { method: "POST", body: JSON.stringify(body) }); toast("เชื่อมต่อฐานข้อมูลสำเร็จ"); } catch (error) { toast(error.message); } });

$("schema-form").addEventListener("submit", async (event) => { event.preventDefault(); const fields = [...document.querySelectorAll(".field-row")].map((row) => { const field = state.profile.fields[Number(row.dataset.index)]; return { name: field.name, inferred_type: field.inferred_type, confirmed_type: row.querySelector("[data-type]").value, nullable: field.nullable, required: field.required, selected: row.querySelector("[data-select]").checked, confidence: field.confidence, null_percentage: field.null_percentage, distinct_count: field.distinct_count, pii_classification: field.pii_classification, samples_masked: field.samples_masked }; }); try { await api(`/projects/${state.project.project_id}/schema/confirm`, { method: "POST", body: JSON.stringify({ fields }) }); showStep(3); } catch (error) { toast(error.message); } });

$("requirement-form").addEventListener("submit", async (event) => { event.preventDefault(); const button = event.submitter; busy(button, true, "Local Llama กำลังวิเคราะห์…"); try { const result = await api(`/projects/${state.project.project_id}/requirement-proposals`, { method: "POST", body: JSON.stringify({ requirement: $("requirement").value, language_hint: "auto" }) }); state.proposal = result; $("proposal-result").className = "result"; $("proposal-result").textContent = result.analysis.status === "ready" ? `Suggested ${result.analysis.transformations.length} rules · confidence ${Math.round(result.analysis.confidence * 100)}%` : `ต้องการข้อมูลเพิ่ม: ${result.analysis.clarification_questions.join(" ")}`; if (result.analysis.status === "ready") { $("rules-json").value = JSON.stringify(result.analysis.transformations, null, 2); showStep(4); } } catch (error) { toast(error.message); } finally { busy(button, false); } });

$("spec-form").addEventListener("submit", async (event) => { event.preventDefault(); try { const language = $("target-language").value; const output = language === "sql" ? "sql_result" : $("output-format").value; const body = { proposal_id: state.proposal.proposal_id, name: $("pipeline-name").value, transformations: JSON.parse($("rules-json").value), validations: state.proposal.analysis.validations, output: { format: output, destination: "artifact", output_directory_parameter: "output_dir", path_template: "output/{stem}", encoding: "utf-8", null_representation: "", write_mode: "overwrite", atomic_write: true }, target: { language, ...(language === "sql" ? { sql_dialect: $("sql-dialect").value } : {}) }, assumptions_acknowledged: $("acknowledge").checked }; await api(`/projects/${state.project.project_id}/specification/confirm-from-proposal`, { method: "POST", body: JSON.stringify(body) }); showStep(5); } catch (error) { toast(error.message); } });

$("run-preview").addEventListener("click", async (event) => { const button = event.currentTarget; busy(button, true); try { const result = await api(`/projects/${state.project.project_id}/preview`, { method: "POST", body: JSON.stringify({ rows: state.rows.slice(0, 50), timeout_seconds: 5 }) }); $("preview-result").textContent = JSON.stringify(result, null, 2); showStep(6); } catch (error) { toast(error.message); } finally { busy(button, false); } });

async function pollJob(jobId) { if (!state.project) return; try { const job = await api(`/projects/${state.project.project_id}/jobs/${jobId}`); $("job-state").textContent = `${job.status} · ${job.progress_percentage}%`; if (["queued", "running", "cancelling"].includes(job.status)) { $("cancel-export").hidden = false; setTimeout(() => pollJob(jobId), 1000); return; } sessionStorage.removeItem(`paeJob:${state.project.project_id}`); $("cancel-export").hidden = true; if (job.status === "succeeded") { $("retry-export").hidden = true; await loadArtifacts(); } else { $("retry-export").hidden = false; } } catch (error) { $("job-state").textContent = `กู้คืน Job ไม่สำเร็จ: ${error.message}`; $("retry-export").hidden = false; } }
async function createExport() { const button = $("create-export"); busy(button, true, "กำลังส่ง Job…"); $("job-state").textContent = "กำลังสร้าง package จาก confirmed revision"; const key = crypto.randomUUID(); try { const result = await api(`/projects/${state.project.project_id}/exports`, { method: "POST", headers: { "Idempotency-Key": key }, body: JSON.stringify({ sample_rows: state.rows.slice(0, 50) }) }); if (result.artifact_id) { await loadArtifacts(); return; } sessionStorage.setItem(`paeJob:${state.project.project_id}`, result.job_id); $("cancel-export").dataset.jobId = result.job_id; pollJob(result.job_id); } catch (error) { $("job-state").textContent = `ไม่สำเร็จ: ${error.message}`; $("retry-export").hidden = false; toast(error.message); } finally { busy(button, false); } }
$("create-export").addEventListener("click", createExport); $("retry-export").addEventListener("click", createExport);
$("cancel-export").addEventListener("click", async () => { const jobId = $("cancel-export").dataset.jobId || sessionStorage.getItem(`paeJob:${state.project.project_id}`); if (!jobId) return; try { await api(`/projects/${state.project.project_id}/jobs/${jobId}/cancel`, { method: "POST" }); pollJob(jobId); } catch (error) { toast(error.message); } });

if (state.token) { loadProjects().then(() => { $("login-card").hidden = true; $("app").hidden = false; $("logout").hidden = false; $("connection-state").textContent = "กู้คืน session แล้ว"; }).catch(() => endSession(false)); }
