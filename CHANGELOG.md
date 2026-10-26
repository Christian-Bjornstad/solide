# Changelog

## 0.8.10 — 26 October 2026

- Search COSMIC by gene/cDNA when no COSM/COSV identifier is supplied. Select
  only one exact native syntax result and check its gene, CDS and GRCh37 span;
  ambiguous, mismatching and unfinished searches remain explicit outcomes.
- Add a quoted HGVS ClinVar query for aliases missing from the VARNAME index.
  Every candidate still requires the exact GRCh37 position and both alleles.
- Stabilize source capture against animation/scrollbar reflow and subpixel DPI
  jitter, with a padded crop and layout checks before and after the screenshot.
- Show copyable Rapporttekst in the overview and every variant sheet, using
  the reviewed identity and available matching COSMIC identifier.
- Mark selected, distinct same-gene events within 100 bp in orange and show an
  IGV reminder before database searches. This is a phasing prompt, not a cis/trans
  conclusion; overlapping annotations retain their existing purple colour.
- Distinguish ClinVar browser verification from no-hit/layout failures and retain
  independently verified API classifications when the website image is blocked.

## 0.8.9 — 22 October 2026

- Extend the ClinVar source image to include its expanded Variant Details panel
  with identifiers, location, timeline and HGVS table alongside the complete
  germline/somatic summary. Open collapsed details using the native control.
- Label the Excel image Klassifikasjon og variantdetaljer and retain the detail
  text and captured panel metadata without changing source classifications.

## 0.8.8 — 22 October 2026

- Capture rendered OncoKB and ClinVar result panels without waiting for unrelated
  document resources or fonts. Required source labels and stable panel geometry
  are still checked before and after capture.
- Retain the matched OncoKB answer when only its screenshot fails, keep that
  search eligible for retry, and record layout diagnostics. Discard the image
  and old classification if the returned variant changes during capture.
- Shorten the missing COSMIC identifier message to `COSMIC-ID mangler` in the
  provider response and Excel cells.

## 0.8.7 — 22 October 2026

- Accept OncoKB's canonical splice/protein labels when its returned genomic
  breadcrumb independently matches the requested GRCh37 event and gene. Keep
  mismatching genes, alleles, assemblies and URL-only claims rejected.
- Read ClinVar's variant-level aggregate classifications rather than the first
  condition/submission assertion. Keep germline, somatic clinical impact and
  oncogenicity separate in the report cell when several are available.
- Replace vague report checks with specific Norwegian access, network, profile,
  identity and capture messages. Retain independently verified classifications
  when only capture failed. Document all report texts in docs/RAPPORTSVAR.md.
- Treat COSMIC's exact-ID empty-search response as no hit instead of a rendering
  timeout. Keep unrelated fuzzy results excluded.
- Capture the complete OncoKB overview/effect panels and ClinVar summary after
  fonts and layout settle; retry crops if page geometry moves during capture.

## 0.8.6 — 21 October 2026

- Capture only explicitly annotated MANE Select transcript scores, together with
  Pangolin scores and Predicted Splicing Consequences in one native source image.
  Keep the query/settings image and full API evidence; scoring settings are unchanged.
- Verify Pangolin's allele/settings and every visible MANE score row. Missing
  sections, failed consequence predictions and canonical fallbacks require retry.
  Older SpliceAI-only images are eligible for Retry failed.

## 0.8.5 — 21 October 2026

- Show all database checkboxes directly in Searches, with Select all/Clear all
  controls and an explicit run-selected-databases button. Keep the search page
  scrollable on smaller windows so controls do not overlap or disappear.
- Shorten the Excel creation label to Opprettet, retaining Norwegian local time
  and the existing date format.

## 0.8.4 — 21 October 2026

- Match Archer Prosess's 60-second wait after MTBP credential submission.
- Follow a newly committed main document during SSO redirects instead of waiting
  for the first document's loader forever. Continue rejecting the previous
  document, another frame and browser error pages.

## 0.8.3 — 21 October 2026

- Give MTBP navigation and post-submission authentication the full configured
  timeout instead of stopping after 15 seconds. Wait for the visible trusted
  login form or a positively authenticated application before proceeding.
- Recover a navigation timeout when the redirected MTBP document is already
  usable. Retry a failed login-page GET once without replaying credentials.
- Return a concise Norwegian connection failure without marking login verified;
  release the dedicated Edge profile and keep form waits cancellable.

## 0.8.2 — 20 October 2026

- Use independently verified genomic names for complex OPA variants without
  transcripts. Submit chromosome-qualified genomic queries to MTBP and allele
  queries to Franklin rather than gene-qualified genomic positions.
- Match MTBP's assembly-labelled VCF popup against the complete source event,
  trimming shared padding and checking chromosome, position and both alleles.
  Reject conflicting assemblies/DNA even if the protein matches; recheck older
  no-hit results that contained gene rows.
- Distinguish a completed COSMIC search with zero exact legacy matches from a
  rendering timeout. Unrelated fuzzy search results never establish a match.
- Include short update instructions for running from a fresh extracted folder
  without reinstalling dependencies on an existing working installation.
- Verify filtered RefSeq/assembly mappings in exact genomic transcript context
  when reference sequences differ elsewhere (ATRX, ATM and KRAS inputs).
- Validate promoter positions outside the mRNA sequence against the explicit
  GRCh37 source allele and exact transcript, retaining the original rejection.
- Complete verified genomic-only OPA normalizations without repeatedly marking
  them for review. Extend public API recovery to BRCA Exchange.
- Recover public Mutalyzer and SpliceAI API reads through managed Edge when
  Python cannot connect or a proxy rejects access. Reuse one isolated temporary
  connection per search run and retain the same response/identity checks.
- Resolve exact human transcript identity through Mutalyzer's RefSeq model when
  NCBI is unreachable. Reject reference-version, gene, organism and CDS conflicts.
- Identify the annotation and original row blocking Excel or the combined MTBP
  batch. Include the actual failure cause in activity logs and allow Retry failed
  to recover the whole batch after a temporary annotation outage.
- Mark independently checked unchanged Mutalyzer names as complete without
  taking an unused screenshot. Show a verified normalized protein prediction
  with corrected DNA names while retaining original imported protein text.
- Show the application version in the window and startup log.

## Unreleased — 19 October 2026

- Recover from cancelled/failed login without leaving Edge profiles or active
  threads behind. Save verified login details automatically; show confirmed
  per-provider and all-provider states, and invalidate expired authentication.
- Start imported files with no variants checked. Apply highlighted rows as an
  explicit choice, show the checked count and clear hidden choices as well.
- Split multiple transcript annotations into independent purple choices. Resolve
  selected choices through exact-version NCBI gene identity and Mutalyzer genomic
  event proof before every provider, including when Mutalyzer is unchecked.
  Handle reordered/unequal lists, duplicate references and compound HGVS; retain
  one original raw Excel row and stop unconfirmed findings or incomplete MTBP batches.
- Repair unequivocally reversed gene/transcript cells with retained provenance;
  validate repeated headers and preserve their original column/cell order.
- Use independently confirmed new nomenclature automatically while preserving
  original cells. Reorder Excel sources to Mutalyzer, SpliceAI, BRCA Exchange,
  OncoKB, COSMIC, ClinVar, MTBP and Franklin; omit inapplicable optional panels.
- Capture expanded Franklin Clinical evidence alongside predictions and
  population frequencies, with identity and complete-layout checks.
- Preserve COSV, lowercase and multiple COSMIC identifiers. Distinguish network,
  certificate, proxy, timeout and rate-limit failures from invalid variant input.

## Unreleased — 18 October 2026

- Stress-test synthetic OPA/Ion files, malformed data, random GUI actions,
  interrupted workers, export failures and 5,000-row inputs with an opt-in script.
- Preserve quoted multiline TSV cells and physical source row numbers. Reject
  broken quoting, extra nonempty fields and concatenated export metadata rather
  than silently discarding cells or binding multiple exports to one sample.
- Recover from invalid saved UI setting types and handle extreme intron offsets
  without crashing. Resolve each source path once and avoid rebuilding the
  results table twice after import.
- Remove repeated workflow/storage explanations and the unused SAMPLES heading.
  Keep file switching in the sidebar. Replace native dark control details with
  matching green controls and add an editable SVG/Windows app icon.
- Use concise Norwegian workbook labels and statuses; preserve source
  classifications, MTBP text, screenshots and original imported cells verbatim.
- Require a valid OUM number when import cannot detect one; uppercase typed
  identifiers automatically. Reject multiple sample IDs in row-level sample fields.
- Shorten skipped SpliceAI report cells to “Ikke kjørt” and remove repeated
  workflow explanations from the app.
- Use Europe/Oslo for displayed timestamps, Excel dates and report filenames,
  including daylight saving changes; keep original source timestamps intact.
- Show SpliceAI candidate counts. Live PTEN captures include the query/settings and all
  transcript scores.
- Capture BRCA Exchange's current variant and ENIGMA panels automatically after
  exact API identity verification. Check the displayed gene, versioned HGVS,
  GRCh37 name, classification and evaluation date before including the image.
  Keep API evidence and expose Retry failed when the screenshot cannot be verified.

- Simplify the four-tab flow to TSV import, variant selection, database searches
  and explicit Excel export. Open recognised files directly when the sample ID
  is unambiguous; keep confirmation for missing or conflicting identifiers.
- Remove saved-review actions and the mandatory workspace folder. Search
  captures and activity logs use a temporary workspace, cleared on normal close
  or Clear files. Review state is not autosaved, including legacy reviews.
- Ask for an export destination only when Export Excel is clicked; preserve
  existing Excel files and embed screenshots in the workbook.
- Give the variant grid cell selection, row numbers and Ctrl+C for Excel.
  Collapse optional details and organise Settings into two readable sections.

## 0.8.1 — 16 October 2026

- Complete the MolStat-style install/start launchers for Python FELLES via Ivanti
  and ordinary Windows Python. Check the project layout, preserve special paths,
  forward local startup arguments and retain actionable error messages/exit codes.
- Isolate pasted FELLES startup from the host interpreter's command-line flags.
  Add SOLIDE_INSTALLER.cmd as an installer alias and concise installation docs.
- Test actual CMD routes and encoded clipboard commands with harmless stand-ins;
  verification does not install packages or launch institutional applications.

## 0.8.0 — 15 October 2026

- Split file import from variant review: Import, Variants, Searches and Settings.
  Add a persistent per-file sample list and a concise imported-file overview.
  Keep source configuration collapsible and Excel export beside search results.
- Detect the supplied Ion Reporter and Genexus/OPA layouts, respect explicit OPA
  metadata, and identify Childhood/BRCA panels. Unknown formats require a choice.
- Extract OUM numbers from metadata or filenames. Missing or conflicting IDs
  require input; reject exports naming multiple samples. Correct sample bindings
  without changing source rows, evidence or other imported analyses.
- Default the variant view to candidates while retaining all raw rows and all-row
  quality checks. Absent Genexus calls and quality rows can be shown on demand.

## 0.7.1 — 15 October 2026

- Simplify both attachment profiles to Overview and source screenshots; remove
  the Quality worksheet, source-detail and laboratory-assessment appendices,
  internal navigation links and default text in the Overview note/comment areas.
- Show concise source findings and classifications; COSMIC displays linked IDs.
  Keep source identity checks and retry states in the app without match-status
  prefixes in Excel. Preserve unavailable/outdated distinctions.
- Retain complete hidden provenance as plain literal ranges without Excel
  structured tables. Normalize saved view selections so repeated freezes do not
  produce invalid duplicate panes. Native Excel normal-load checks passed for
  all thirteen actual regenerated workbooks.

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
