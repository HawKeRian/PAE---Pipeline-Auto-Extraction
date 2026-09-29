# File Source Ingestion

Phase 5 accepts a representative source file, inspects its structure, and returns a reusable
folder-processing contract for the user to confirm. The sample filename is metadata only; it is
never embedded as the future runtime input path.

## Supported formats

| Format | Extensions | Options |
| --- | --- | --- |
| CSV | `.csv` | `encoding`, `delimiter` |
| JSON array/object | `.json` | `encoding` |
| JSON Lines | `.jsonl`, `.ndjson` | `encoding` |
| Excel | `.xlsx` | inspect ทุก Sheet แบบ bounded แล้วเลือก `sheet_name` |
| Parquet | `.parquet` | None |

CSV encoding is detected from UTF-8 (with or without BOM), CP874, and Windows-1252 unless the
caller provides an explicit encoding. CSV delimiters are detected from comma, semicolon, tab,
and pipe unless explicitly supplied.

## API workflow

Send `multipart/form-data` to:

```text
POST /api/v1/projects/{project_id}/file-sources
Authorization: Bearer <local token>
```

The multipart field `file` is required. Optional form fields are `encoding`, `delimiter`,
`sheet_name`, `filename_pattern`, `recursive`, and `sample_row_limit`.

เมื่อ XLSX มีหลาย Sheet การอัปโหลดครั้งแรกตอบ `202 sheet_selection_required` พร้อมชื่อ Sheet,
visibility, จำนวนแถว/columns และรายชื่อ header โดยไม่ส่งค่าจากเซลล์กลับไป UI ไฟล์ถูกเก็บชั่วคราว
เพียงครั้งเดียวและยังไม่สร้าง revision ผู้ใช้เลือก Sheet ผ่าน
`POST /projects/{project_id}/file-sources/{upload_id}/select-sheet`; จากนั้นระบบจึง profile,
สร้าง revision และลบ pending object เดิม Sheet ว่าง, hidden หรือ header ไม่ถูกต้องจะแสดงเหตุผลและ
ไม่สามารถเลือกได้ใน UI

The selection request uses a JSON body, for example:

```json
{"original_name": "business.xlsx", "sheet_name": "Orders", "filename_pattern": "*.xlsx"}
```

It also accepts `recursive` and `sample_row_limit`. Successful selection returns `201` with
the analysis below. Pending uploads expire under the sample retention policy; expired or
already consumed upload IDs return `404`. Selection consumes the pending reference atomically
with creation of the revision, so retries cannot create duplicate revisions. An explicit
`sheet_name` on the initial upload still supports direct ingestion.

The response contains:

- normalized metadata (format, hash, size, encoding/sheet details, and column profiles);
- a suggested filename glob such as `*.csv`, never the uploaded sample's exact path;
- suggested required and optional columns plus strict schema compatibility;
- a project revision and opaque sample ID;
- the sample expiry timestamp.

Raw row values and the server-side storage reference are not returned. Uploading a new source
increments the project revision and invalidates any previously confirmed specification.

## Reusable runtime contract

The default suggestion uses `folder_batch` mode and a glob derived from the file extension. A
user may replace it with a relative glob such as `incoming-*.csv` and choose recursive folder
discovery. Generated pipelines in later phases use this contract to discover every matching
future file, rather than referring to the uploaded sample name or location.

Column presence across sampled records determines the initial required/optional suggestions.
The default compatibility policy is `strict`; the user confirms or edits these suggestions in a
later workflow step.

## Limits and security

Defaults can be changed through `.env`:

- `PAE_MAX_UPLOAD_BYTES=52428800`
- `PAE_MAX_SAMPLE_ROWS=100000`
- `PAE_MAX_SAMPLE_COLUMNS=1000`
- `PAE_SAMPLE_RETENTION_HOURS=24`

The service authorizes project edit access before reading or storing the upload. It validates
the filename, extension, declared MIME type, and available file signatures. XLSX archives are
checked for unsafe paths, excessive entries, expanded size, and suspicious compression ratios.
Readers bound the number of rows and columns used for analysis.

Samples are copied into `PAE_DATA_DIR/samples` under random names, are never modified in place,
and are removed after the retention period. Cleanup runs at application startup, periodically
while the application is running, and opportunistically before an upload. If persistence fails,
the newly stored sample is discarded.

Error responses use the standard safe error envelope and include corrective guidance where it
is useful. Common causes include an unsupported extension, mismatched MIME/signature, invalid
encoding, corrupt content, a missing Excel sheet choice, or configured size/shape limits.
