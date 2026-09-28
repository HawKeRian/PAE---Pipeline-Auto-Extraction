# Local Llama Usage Guide

## Runtime

PAE uses Ollama through its local HTTP API. No cloud inference or API key is required. The
Python application uses the already-pinned `httpx` package, so no heavyweight PyTorch or
Transformers dependency is added to `ai_env`.

Install or verify the selected model:

```powershell
ollama pull llama3.1:8b
ollama show llama3.1:8b
ollama list
```

Run the reproducible benchmark:

```powershell
conda run -n ai_env python scripts/benchmark_local_ai.py `
  --model llama3.1:8b `
  --output reports/model-evaluation-llama3.1-8b.json
```

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `PAE_AI_PROVIDER` | `ollama` | Runtime adapter selector |
| `PAE_AI_MODEL` | `llama3.1:8b` | Ollama model/tag; no path is hard-coded |
| `PAE_OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Local-only runtime endpoint |
| `PAE_AI_TIMEOUT_SECONDS` | `120` | Request timeout including cold load |
| `PAE_MODEL_PATH` | empty | Reserved for a future direct GGUF adapter |

## Trust and validation flow

1. The caller creates a `RequirementRequest` containing the user's requirement plus confirmed
   field names and types. Source row values and credentials are not accepted by this contract.
2. `OllamaProvider` sends an explicit system prompt and the JSON Schema from
   `RequirementAnalysis` with temperature zero.
3. Pydantic validates every response. Unknown properties and inconsistent status/confidence
   combinations are rejected.
4. `RequirementInterpreter` rejects references to fields outside the confirmed field set.
5. Any runtime, JSON, schema, or reference failure activates `ClarificationFallbackProvider`.
   It proposes no transformations and asks the user to clarify instead of guessing.
6. Valid AI output is still a draft; the user must confirm it before it becomes a Pipeline
   Specification.

Keep Ollama bound to localhost for MVP. Do not log prompt bodies, model output bodies, source
samples, credentials, or connection strings. Metrics and benchmark reports may record model
name, timing, token counts, case IDs, and pass/fail status only.

## Troubleshooting

- If Ollama is unavailable, start the local Ollama service and verify `ollama list`.
- If the model is missing, run `ollama pull llama3.1:8b` once; runtime code never downloads it.
- If VRAM pressure causes slowdowns, close other GPU workloads. Do not increase concurrency;
  this reference machine supports one AI inference at a time.
- If a response falls back to clarification, make the operation, exact fields, and criteria
  explicit. Never bypass schema or field-reference validation to accept a model response.
