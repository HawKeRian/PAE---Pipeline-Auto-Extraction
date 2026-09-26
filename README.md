# Pipeline Auto Extraction (PAE)

PAE generates validated data-pipeline code from source samples and a user-confirmed Pipeline Specification. The repository currently contains the Phase 0 product baseline and Phase 1 application foundation.

## Prerequisites

- Miniconda or Anaconda
- Conda environment name: `ai_env`
- Python 3.11

## Setup

Create the environment when it does not exist:

```powershell
conda env create -f environment.yml
```

If `ai_env` already exists, install Python and dependencies into that environment:

```powershell
conda install -n ai_env -c conda-forge python=3.11 pip
conda run -n ai_env python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` only for local settings. Never commit `.env` or secrets.

## Run

```powershell
conda run -n ai_env uvicorn pae.main:app --app-dir src --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs` for the generated API documentation or call `GET /health`.

## Quality Checks

```powershell
conda run -n ai_env ruff check .
conda run -n ai_env ruff format --check .
conda run -n ai_env mypy
conda run -n ai_env pytest
conda run -n ai_env detect-secrets scan --all-files --exclude-files '^\.git/'
conda run -n ai_env pip-audit -r requirements.txt
```

Install local pre-commit hooks with:

```powershell
conda run -n ai_env pre-commit install
```

## Project Layout

```text
src/pae/        Application source
tests/          Automated tests
docs/           Product scope, decisions and traceability
configs/        Non-secret configuration templates
samples/        Synthetic/de-identified fixtures only
generated/      Local generated artifacts; ignored by Git
```

See `Progress.md` for the implementation plan and current status.
