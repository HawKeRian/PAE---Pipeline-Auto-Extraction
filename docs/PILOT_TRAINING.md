# Pilot Training Script

Duration: 45 minutes. Use only synthetic or de-identified data. The facilitator may explain the
goal and safety rules, but must not operate the product during the scored journey.

## Walkthrough

1. Sign in, create a project, and upload the supplied CSV example.
2. Review suggested columns, inferred types, PII flags, and required/optional choices; confirm the
   schema only after correcting any mismatch.
3. Describe the desired output in Thai, English, or mixed language; review clarifications and never
   accept a suggested rule without checking its field references and intent.
4. Edit mapping/transformation/validation rules, run the masked preview, and inspect rejected rows.
5. Select Python, generate the package, download the ZIP, and verify README, specification,
   manifest, script, configuration example, sample output, and tests.
6. Run the exported script against two matching files in a folder; repeat the run and confirm files
   are not duplicated. Modify one file and confirm only that file is processed again.
7. Return to an earlier workflow step, change a rule, and confirm old preview/export results become
   stale. Recover the generation job after a page reload and demonstrate cancellation.
8. Sign out and confirm project APIs no longer accept the session token.

## Scored Journey

The participant repeats the agreed use case without developer actions. Record start/end time,
completion, deviations, clarification count, incorrect suggestions, preview correctness,
download/run result, repeat-run result, and every usability/security finding in
`docs/PILOT_FEEDBACK_FORM.md`.

Release blocker: any Critical/High security or correctness issue, an incorrect generated result not
caught before export, inability to finish a critical step, or need for a developer to manipulate
data/state on the participant's behalf.
