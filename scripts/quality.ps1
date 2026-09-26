$ErrorActionPreference = "Stop"

conda run -n ai_env ruff check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

conda run -n ai_env ruff format --check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

conda run -n ai_env mypy
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

conda run -n ai_env pytest
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

conda run -n ai_env detect-secrets scan --all-files --exclude-files '^\.git/' | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

conda run -n ai_env pip-audit -r requirements.txt
exit $LASTEXITCODE
