# PAE User Guide

## Start and sign in

Start PAE, open `/ui`, and enter the bearer token supplied by the administrator. The token remains
in browser session storage and is revoked when you choose **ออกจากระบบ**.

## Build a pipeline

1. Create a Project.
2. Upload a bounded sample file. PAE reads it, profiles columns, masks sensitive examples, and
   suggests the filename pattern used for future files. Database users first test a TLS/read-only
   connection that refers to a secret; passwords are never entered into the project.
3. Review every inferred column, type, nullability, and PII flag. Select the fields you need and
   confirm the schema.
4. Describe the desired result in Thai, English, or mixed language. Local Llama proposes rules; if
   it asks a clarification question, refine the requirement. Suggested rules never become active
   until you confirm them.
5. Review/edit rules, choose Python, JavaScript, or a supported SQL dialect and output format, then
   confirm the Specification.
6. Run the masked sandbox preview. Go back if the result is not correct; a change creates a new
   revision and older preview/artifacts become stale.
7. Generate the package. The job can be monitored, cancelled, retried, or recovered after reload.
   Review its file list and validation status, then download the ZIP.

## Use the exported package

Read its `README.md`. For a Python folder pipeline, place future files matching the confirmed
pattern under the input directory and run the documented scan-on-run command. Unchanged files are
skipped using checksums. Invalid files/rows follow the confirmed quarantine/error policy. Schedule
the command with Task Scheduler or cron; do not run overlapping scans.

## Common problems

- **401**: sign in again; logout or administrator deactivation revokes the old token.
- **Schema changed**: confirm whether incoming required/extra columns are acceptable, then create a
  new revision/package.
- **Local model unavailable**: start Ollama and verify the configured Llama model.
- **Database rejected**: verify the hostname allowlist, TLS identity, read-only account, and
  `secret://` environment mapping.
- **Stale package**: it belongs to an older revision. Download only for historical reproduction or
  generate again from the current confirmed revision.
