# Changelog

## 0.7.0 — 15 October 2026

- Check Mutalyzer normalization against independently validated hg19 source
  REF/ALT, including padding, and canonical genomic sequence events. Offer an
  explicit source/MANE transcript only after gene/version/event verification;
  never choose the first equivalent transcript. Checked names still require
  manual approval in Identity review. Conflicts block downstream searches.
- Capture the actual SpliceAI query/settings and all basic-annotation transcript
  scores. Compare the page response with validated API alleles, settings and
  scores. Missing captures retain predictions and remain retryable. Preserve
  the original intronic ±100 bp triage after genomic HGVS normalization.
- Export the Archer/VPM single-workbook layout: Overview, a shared MTBP report,
  source-ordered variant sheets, all-row Quality and hidden complete source data.
  Include only Solide's databases. Keep source PNGs intact at readable width.
- Port selected provider and Edge updates from Archer workstation c12a1b8,
  including MTBP hidden identities/shared rows/recovery, provider capture
  diagnostics, Franklin onboarding, COSMIC cache identity and strict ClinVar
  allele-cache validation. Legacy uncertain MTBP gene matches require recheck.

## 0.6.0 — 14 October 2026

- Keep each imported source in an independent, persistent analysis. OPA and Ion
  Torrent profiles have their own assay, tissue, selection, quality, searches and
  export, including when a sample ID is shared. Older sessions migrate without
  losing rows, assessments or evidence; unconfirmed profiles require review.
- Replace the combined Excel layout with a compact Findings / Quality / Sources
  report and a separate VPM-style evidence attachment. Preserve every original
  row in hidden Raw data and retain source assertions apart from app assessments.
- Use profile-specific all-row quality sections. Absent CNV/RNA/run-level data
  remains Not supplied; missing values remain Unknown.
- Isolate MTBP batch freshness and capture folders by analysis. A rerun expands
  only its analysis's selected rows; legacy combined evidence remains outdated
  until rerun. Publish versioned Excel bundles together, with actionable save errors.

## 0.5.1 — 13 October 2026

- Keep Genotype when an Ion Reporter export has a present but empty Call cell.
  Preserve both original columns and explicit PRESENT, ABSENT and NO CALL states.
- When Mutalyzer rejects intronic HGVS on an mRNA reference, retain that error
  and offer a separate genomic hg19 candidate only if the supplied alleles and
  returned chromosome/transcript context agree. Candidates require manual review.
- Trim redundant shared VCF bases at the browser-query boundary, retaining indel
  anchors and the original source identity. Equivalent padded SNVs no longer
  produce false identity conflicts or missed exact genomic searches.
- Verify twelve additional raw TSV exports individually through the app import
  flow, preserving all 76 rows and detecting both row-level coverage failures.

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
