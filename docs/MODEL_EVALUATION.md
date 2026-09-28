# Local Llama Model Evaluation

สถานะ: **Phase 3 baseline — 2026-09-26**

## Decision

เลือก `llama3.1:8b` (Ollama Q4_K_M) เป็น Local Llama เริ่มต้น เพราะผ่าน benchmark ทั้ง
schema validity, semantic correctness และ safety-critical rejection ที่ 100% ขณะที่
`llama3.2:3b` ผ่านด้าน schema/safety แต่ semantic correctness เพียง 40% หลังปรับ prompt แล้ว

ผลนี้เป็น baseline บนชุดทดสอบขนาดเล็ก 10 กรณี ไม่ใช่ข้อสรุปทั่วไปเกี่ยวกับความสามารถของโมเดล
ต้องเพิ่ม regression cases เมื่อรองรับ transformation ใหม่หรือพบข้อความจริงที่โมเดลตีความผิด

## Reference machine

| Item | Observed value |
|---|---|
| OS | Windows 11 Home Single Language, 64-bit |
| CPU | Intel Core i7-9750H, 6 cores / 12 logical processors |
| RAM | 31.9 GB total; 16 GB available before evaluation |
| GPU | NVIDIA GeForce RTX 2060 |
| VRAM | 6,144 MiB total |
| Runtime | Ollama local HTTP API |
| Python | 3.11.16 in conda environment `ai_env` |

With `llama3.1:8b` loaded at a 4,096-token runtime context, Ollama reported a 5.6 GB process
split of 75% GPU / 25% CPU. NVIDIA reported 5,320 MiB VRAM used and 636 MiB free. The runtime
therefore has little VRAM headroom; MVP concurrency remains one AI inference at a time.
For comparison, `llama3.2:3b` loaded entirely on GPU as a 3.1 GB process at an 8,192-token CLI
context, with 4,228 MiB total VRAM in use and 1,728 MiB free.

## Candidate inventory

| Model | Parameters | Quantization | Advertised context | Local size | License | Result |
|---|---:|---|---:|---:|---|---|
| `llama3.2:3b` | 3.2B | Q4_K_M | 131,072 | 2.0 GB | Llama 3.2 Community | Rejected: 40% semantic |
| `llama3.1:8b` | 8.0B | Q4_K_M | 131,072 | 4.9 GB | Llama 3.1 Community | Selected: all thresholds passed |
| `gup-qwen3:4b` | 4.0B | Q4_K_M | 40,960 | 2.5 GB | Not shown by local manifest | Not eligible: not Llama |
| `qwen2.5-coder:7b` | 7.6B | Q4_K_M | 32,768 | 4.7 GB | Apache-2.0 | Not eligible: not Llama |

The application intentionally caps the active context at 4,096 tokens for predictable memory
use. The Ollama library lists the 8B package as 4.9 GB with a 128K context, and Meta's model
card describes the instruct model as multilingual, including Thai. Model references:

- https://ollama.com/library/llama3.1
- https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct
- https://docs.ollama.com/capabilities/structured-outputs

The Llama 3.1 Community License is not Apache/MIT. Distribution must follow its attribution,
license-copy, acceptable-use, and applicable commercial terms. Re-check the current license
before distributing model weights or a product bundle.

## Benchmark results

| Model | Schema valid | Semantic correct | Safety-critical | Median | Maximum |
|---|---:|---:|---:|---:|---:|
| `llama3.2:3b` | 100% | 40% | 100% | 2.19 s | 2.56 s |
| `llama3.1:8b` | 100% | 100% | 100% | 9.47 s | 17.89 s |

The 10 cases cover Thai, English, mixed-language input, rename, exclude, cast, filter,
deduplicate, sort, null handling, masking, ambiguity, and prompt injection. The acceptance
thresholds are schema-valid ≥98%, semantic correctness ≥90%, and safety-critical rejection
100%. Detailed non-sensitive case results are stored under `reports/`; raw prompts and model
outputs are deliberately not persisted.

## Replacement criteria

Evaluate a replacement only when the selected model fails a regression threshold, exceeds the
60-second latency limit, cannot fit the reference machine, or its license becomes incompatible.
Before downloading, verify the official model card, license, instruction tuning, Thai/English
support, quantized size ≤6 GB where practical, context needs, and compatibility with Ollama or
GGUF. Cache only a candidate that is necessary for a recorded evaluation.

## Phase 8 regression — 2026-09-27

After adding assumptions and structured validation rules to the output contract, `llama3.1:8b`
was rerun against all 10 benchmark cases. Schema validity, semantic correctness, and
safety-critical pass rate remained 100%. Median latency was 9.48 seconds and maximum latency was
16.40 seconds. The report is `reports/model-evaluation-phase8-llama3.1-8b.json`.
