# Export Package Guide

Phase 13 exports the confirmed revision through `POST /api/v1/projects/{project_id}/exports` with
an `Idempotency-Key`. Generation, syntax validation, optional sample parity validation, persistence,
and ZIP storage are one user operation. Reusing the same key returns the completed artifact.

Every ZIP contains executable source/runtime files, generated tests where supported, `README.md`,
`.env.example`, `pipeline-spec.json`, a bounded masked `sample-output.json`, dependency configuration,
and `artifact-manifest.json`. The manifest records revision identity, generator/model version,
validation evidence, per-file hashes, and explicit assertions that source samples and credentials
are absent. A secret scan runs before storage.

The README documents schemas, rules, prerequisites, variable names, commands, folder pattern,
schema/failure/quarantine policy, repeat-run behavior, Task Scheduler/cron invocation, security,
limitations, troubleshooting, and downstream integration. Python packages use scan-on-run plus a
processed checksum manifest, so future matching files are handled while unchanged files are skipped.

`GET /api/v1/projects/{project_id}/artifacts` shows files and validation status before download.
When the project revision advances, old packages are marked `stale` and `historical`. Project
deletion removes stored ZIPs and samples immediately.
