# Changelog

## 0.5.0 — 10 October 2026

- Reduce Excel to four visible worksheets: compact Overview, all-row Quality,
  indexed Evidence and ordered Raw data. Keep the complete Searches audit hidden
  by default. Link findings, source results and raw rows directly; put shared
  full MTBP reports once in Evidence, preserve lossless capture segments and split
  long assessment notes into readable rows without discarding text.
- Warn when source metadata describes a filtered export; row QC does not imply
  complete assay coverage. Reject generated Solide workbooks explicitly as input.
- Correct FGFR1/MET transcript assignments using NCBI gene records. Preserve
  successful Mutalyzer normalization if optional mapping fails and support
  explicit genomic GRCh37 normalization when a transcript is unavailable.
- Display current SpliceAI gene/transcript fields and validate assembly, query
  parameters, returned alleles and prediction score ranges before a verified match.

## 0.4.2 — 10 October 2026

- Empty MTBP reports before each submission and remove each new report after
  local audit, including No match outcomes. The account owner requested cleanup
  of all reports, including manual reports. Follow the latest Archer branch's
  five-second settling and three server verification checks; cleanup failures
  block submission. Fix report-page/list URL comparison so deletion actually
  reaches the report list.

- Notify Qt of edited row values instead of emitting a bare layout change that
  could invalidate selection indexes during assessment saving.
- Match equivalent one-letter/three-letter protein notation for MTBP indels
  without conflating deletion and delins. Use English gene-context captions.
- Put Settings headings inside their cards and wrap account status onto two lines.
- Preserve the complete Franklin classification panel when parent elements clip
  expanded content at Windows display scaling.
- Wait for populated, stable MTBP report tables before matching variants or
  capturing screenshots. Incomplete reports retain their ID for recovery.
- Wait for the requested Edge navigation's document loader rather than the
  previous page's ready state.
- Search Franklin by source gene/cDNA when transcript is absent, clearly marking
  these results for transcript review. Enable exact-allele ClinVar genomic queries.
- Mark missing transcript or genomic inputs as review requirements rather than
  retryable network failures.
- Recover MTBP links that open a new tab and reconcile expired, absent submissions
  before permitting a new analysis.

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
