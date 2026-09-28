# Pilot Plan and Training Checklist

Candidate users: one data analyst and one data engineer who can use synthetic/de-identified data.
Use cases: CSV customer transactions to Python, JSON Lines cleanup to JavaScript, and disposable
PostgreSQL read-only exploration. No production credentials or regulated data are permitted.

Training walkthrough (45 minutes): sign-in/security, read-profile-confirm flow, clarification and
rule review, masked preview, job recovery/cancel, ZIP inspection, folder repeat-run, stale revision,
and support/incident reporting. Each pilot must complete the workflow without developer actions.

Capture: completion time, errors, unclear text, number of clarifications, incorrect rule proposals,
download/run success, severity, and suggested change. A Critical/High security/correctness issue or
inability to complete the critical journey is a release blocker. Product Owner records participant,
date, result, and approval in `docs/PILOT_RESULTS.md`.

This plan is ready, but real participant training and feedback cannot be claimed until users perform
it. Synthetic automated E2E tests are supporting evidence, not a substitute for the pilot.

Facilitator package: `PILOT_TRAINING.md`, `PILOT_FEEDBACK_FORM.md`,
`PILOT_HANDOFF_CHECKLIST.md`, `USER_GUIDE.md`, and the three synthetic use cases above.
