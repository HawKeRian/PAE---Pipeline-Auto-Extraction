# MVP Acceptance Thresholds

สถานะ: **Approved MVP baseline — 2026-09-26**

| Area | Metric | Proposed threshold |
|---|---|---|
| Schema inference | Correct field type on curated representative fixtures | ≥ 95% |
| AI structured output | Schema-valid output on benchmark | ≥ 98% |
| AI semantic correctness | Exact/approved-equivalent rules on benchmark | ≥ 90% overall และ 100% สำหรับ safety-critical rejection cases |
| Field references | Unknown/ambiguous fields rejected before generation | 100% |
| Generated syntax | Syntax validation for supported language/dialect | 100% |
| Cross-generator parity | Output matches shared expected fixtures | 100% สำหรับ MVP rules/edge cases |
| Profiling latency | 100 MB หรือ 100,000-row sample บน reference machine | p95 ≤ 60 seconds |
| Preview latency | Standard 10,000-row sample | p95 ≤ 5 seconds |
| Code generation latency | Excluding model cold-start/download | p95 ≤ 60 seconds |
| API health | Local reference environment | p95 ≤ 1 second |
| Reliability | Duplicate submission produces at most one effective job | 100% in test suite |
| Recovery | Interrupted job becomes failed/cancelled and cleans temporary resources | 100% in recovery suite |
| Security | Critical/High findings before release | 0 open |
| Secret handling | Secrets in logs/artifacts/tests | 0 occurrences |
| Retention | Expired temporary samples removed | 100% in retention tests |
| Folder discovery | Matching files are processed once in deterministic order | 100% in batch fixture suite |
| Schema compatibility | Missing required/incompatible fields follow confirmed failure policy | 100% in compatibility suite |
| Repeat execution | Re-running with unchanged files/state produces no duplicate effective output | 100% in idempotency suite |
| Test coverage | Core domain/specification/generator modules | ≥ 90% line coverage; project overall ≥ 80% |

## Reference Machine

Hardware profile, operating system, storage and Local Llama model must be recorded with every benchmark report. Thresholds are not comparable without this context.

## Concurrency Proposal

- Development baseline: 2 simultaneous generation/validation jobs
- Queue excess jobs rather than oversubscribing the Local Llama runtime
- Final concurrency threshold will be set after Phase 3 model/hardware evaluation
