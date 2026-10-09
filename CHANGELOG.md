# Changelog

## 0.4.1 — 9 October 2026

- Make dialog and popup colours readable with Windows dark themes.
- Use 16 px default text and add 14–20 px text sizes in Settings.
- Fit table headers and show readable progress counts on a light moss bar.
- Group rerun actions in one menu and show import failures in the common Log.
- Allow opening a saved local session with `--session`.
- Fix stale Edge profile detection on Windows, where connection refusal can
  take over two seconds; active and uncertain profiles remain protected.

## 0.4.0 — 9 October 2026

- Save classification, report decision, reviewer and assessment notes in the app.
- Create versioned Excel reports with source annotations, assessments, evidence
  links, all-row QC and original ordered data. Prior exports remain available.
- Add exact-identity BRCA Exchange evidence for BRCA1 and BRCA2 only.
- Segment tall screenshots at readable width and omit stale captures.
- Reject ambiguous reviewed-table imports and retain unnamed source columns.
- Update selected Archer Edge and provider fixes from the October branch,
  including MTBP uncertain-submission recovery and cancellation checkpoints.
- Keep variant rows visible at compact window sizes; database choices use two rows.

## 0.3.0 — 30 September 2026

- Consolidated English navigation, Settings accounts, local activity log,
  progress, match assessments and explicit retry/rerun controls.
