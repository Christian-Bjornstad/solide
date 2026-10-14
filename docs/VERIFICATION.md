# Verification — Solide v0.6.0

Dates: 9–14 October 2026. Local Windows / Python 3.12.

## Analysis reports — 14 October 2026

- **418 tests passed** in 30.54 seconds; compileall and diff checks passed.
  New checks cover source/analysis isolation even with shared sample IDs,
  schema migration, selection/tissue/rerun scope, full response retention,
  rejected capture identities and paired export failure recovery.
- The actual GUI imported the twelve raw TSVs individually again: twelve
  independent analyses, all 76 rows, 70 sequence candidates, six CNV rows,
  both row-level coverage failures and all source hashes retained.
- Generated twelve compact reports and seven separate evidence attachments,
  plus a complete OPA report retaining another 3,204 source rows. Independent
  audit verified all **3,280 report raw rows**, every laboratory QC exception,
  source metadata and literal API-response round trips.
- **48 embedded image segments** match the analysis's current original pixels;
  MTBP display crops preserve original PNGs. **83 local links** resolve to the
  correct evidence or workbook target. Main reports contain no images.
- Read-only artifact rendering produced 83 view ranges across report and
  attachment roles. Actual OPA/Ion findings, full OPA CNV/RNA exceptions, filtered
  export warnings, source ledgers, VPM-style captures and API evidence were
  visually checked. Fixed clipped assay metadata and identity-check descriptions;
  complete machine metadata remains available in hidden literal storage.
- At 1050×700 with 18 px text, duplicate workspace spacing/counts are removed;
  detail tabs and assessment actions remain below the visible variant rows.
- Two independent authenticated MTBP batches completed six variant results:
  five Review matches and one No match. Every capture path is in its own analysis
  folder; every remote report was deleted. A separate authenticated portal check
  confirmed **zero reports**. Other 13 October source captures retain their real
  capture dates; they were not relabeled as newly captured.
- Actual records still have blank laboratory classifications and Pending decisions.
  No clinical assessment was invented. Migrated source sessions preserve their
  original rows, clinical fields, IDs and evidence, and originals stay unchanged.
- Independent code and visual reviews reproduced and verified fixes for missing
  RNA status, rejected-identity captures, long API JSON and corrected HGVS labels.
  Public previews contain synthetic data only; actual material stays Git-ignored.

## Automated and runtime checks

- v0.5.1: **348 tests passed** in 23.87 seconds; compileall passed.
- v0.5.0: `python -m pytest -q` passed **304 tests** in 21.86 seconds; compileall
  passed. Publishable paths and Git history contained no input/report files,
  private identifiers or keys. Saved passwords remain in the Windows vault.

- The v0.4.2 baseline had **247 passing tests**. Fixtures are synthetic; the optional
  local reference test reads ignored laboratory files without external lookups.
- Compileall passed for source, scripts and the Python FELLES install/start helpers.
- Assessment/identity edits notify changed model values, preserving the selected
  variant when the sorted proxy moves its row. An intermittent native Qt crash
  during assessment saving led to removal of bare layout-change notifications.
- Native GUI checks cover import/selection/filtering, sessions, English navigation,
  all-row QC, identity review, assessment saving, gene-scoped BRCA result rows,
  account handling, retries, retained capture history and run progress.
- Four destinations were rendered and inspected at full and 1050×700 sizes.
  Variant rows remain visible; identity forms and Settings scroll when needed.
- Windows dark palettes were reproduced independently. Dialogs and dropdowns
  retain light surfaces and dark text; text sizes 14–20 px fit the compact view.
  Progress text contrast on the filled bar is 8.76:1. Table headers fit their
  labels and sorting arrows. Failed imports remain visible in the common Log.
- Excel checks cover patient separation, versioned filenames, typed dates/numbers,
  app assessment fields, native filter tables, original source order and literal
  text, unnamed-column collisions, all-row QC and safe formula handling.
- Generated synthetic Excel was imported read-only into artifact-tool and all
  report roles were rendered and visually checked, including linked variant
  evidence and a shared MTBP attachment. Tall-capture segmentation was verified.
- Stale images and full reports are omitted. Missing/unreadable captures stay
  visible as retryable states. Source assertions do not set app classification.
- Import guards reject competing tables, duplicate headers and generated reports;
  repeated header rows are not imported as records. Ion/Genexus preambles work.
- BRCA Exchange: 35 mocked tests and two live lookups of a public example variant
  passed (exact hg37 allele and complete versioned HGVS). Exact gene, reference,
  variant/detail version and dataset release are retained. Non-BRCA genes make
  no request; incomplete/ambiguous/conflicting responses cannot become Found.
- Archer October ports and additional regression checks passed. Coverage includes Edge local
  transport, profile ownership, policy diagnostics, timeouts, source readiness,
  identity conflicts, per-variant checkpoints, MTBP uncertain dispatch, retained
  recovery, lost acknowledgements and cancellation during report polling.
- Local Edge smoke checks passed on synthetic HTML with a fresh temporary profile:
  zoom 1 / 1.25 / 0.8, nested scrolling, exact MTBP row crop and Franklin header.
  A nested clipping regression also verifies the complete right edge and restoration
  of original overflow styles. The Franklin fix was checked against a live report
  at Windows 150% display scaling.
- Settings cards now contain their headings. Account status occupies separate
  storage and sign-in lines. Compact renders at 18 and 20 px were inspected.
- MTBP report navigation exposed a loading race in the real-data run. The adapter
  now requires report metadata, populated stable tables and no visible loader
  before parsing or capture. Incomplete content preserves a recoverable report ID;
  it cannot establish absence of a variant. Recovery uses the same readiness guard.
- Missing transcript / genomic input is a review requirement rather than a
  retryable HTTP failure. A clinical interpretation is still entered in the app.
- Edge navigation checks the requested document loader before reading ready state;
  the previous complete document cannot satisfy the new navigation. A regression
  covers delayed commits and redirected URLs.
- Franklin gene/cDNA queries retain the supplied cDNA without inventing a
  transcript. Their results always require transcript review. ClinVar genomic-only
  queries retain strict GRCh37 position, REF and ALT verification.
- MTBP Reports List links are opened in the controlled tab, including links whose
  browser target is a new tab. Real retained-report recovery returned four matches.
  A lost submission acknowledgement can be retried only after the analysis
  deadline and two populated Reports List checks confirm its ID is absent. A
  pending row without a report link prevents duplicate submission.
- Independent reviews replayed reported identity/cancellation failures after fixes
  and found no remaining blocking issue in the reviewed report and provider code.
- Public-content audit found no input TSV/XLSX/ZIP, sessions, reports, logs,
  browser profiles, private keys, tokens or patient identifiers in publishable
  files/history. Published UI screenshots use synthetic data only.

## Reference inspection

All five supplied inputs were read locally, including archive inventories.
The inspected structures include 15 workbooks / 95 sheets, raw variant exports,
review and classification templates, target/gene coverage and sample QC.
Only sanitized structural conclusions are documented publicly. Patient content,
source filenames within archives, raw formulas and reviewed clinical narratives
remain local. Source files were not modified.

Private checks independently compared all **16,024 raw rows** from the direct
inputs and four archived raw workbooks with source columns, values, physical
row numbers, quality rules and stable row IDs. Six actual Excel exports and
session reloads passed. Ten reviewed workbooks were correctly rejected, and
five PDF attachments were excluded from variant import. Original input hashes
were unchanged. An input without sample metadata was left unbound.

The actual GUI imported two supplied sources (3,212 rows across two samples),
confirmed hg19, filtered and selected rows, saved/reloaded the review, and
exported separate patient workbooks. The actual Excel overview, assessment
columns and quality sheets were rendered read-only and visually checked.
No app classifications, report decisions or assessment notes were invented.

The earlier v0.4.1 small real Edge batches returned two ClinVar and one Franklin **Verified match**,
plus COSMIC and OncoKB **Review match**, with stored source captures. The first
three searches exposed a stale-profile probe timeout on Windows. A real reserved,
unlistening TCP-port regression reproduced the problem. With the bounded
three-second probe, **Retry failed** completed all three earlier failures and
retained their prior evidence in history. Active or uncertain profiles remain
blocked; ordinary Edge windows and profiles were not closed or cleared.

Mutalyzer returned a suggestion requiring review. SpliceAI correctly marked an
exonic variant outside the intronic rule as not applicable; this batch did not
exercise an intronic HTTP request. MTBP returned **Sign-in required** for both
selected variants and remains retryable. Local sessions and generated Excel
retain these different outcomes. No MTBP report was submitted in this batch.
Real BRCA patient lookups were not part of this batch.

All actual data, sessions, source captures and reports remain Git-ignored.
Public documentation screenshots are isolated synthetic previews.

The reviewed child templates are design references rather than importable raw
variant tables. Their target/gene coverage is not treated as variant Coverage.
Clinical scoring formulas were not copied into an automatic classifier.

## Fresh authenticated run — 9–10 October 2026

The supplied raw files were imported again into a new local session: **3,214
rows, three independent datasets and 27 selected variants**. The two-row export
without sample metadata received an explicit source-dataset alias; it was not
joined to another patient. Three new Excel reports retain all raw rows and QC,
with manual classifications blank and report decisions Pending.

The run used actual saved accounts, GRCh37 and MTBP tissue Other. Source captures
were newly generated in the run directory. **378 capture references** passed
image validity, freshness and path checks. **374 embedded Excel image segments**
were compared pixel-for-pixel with current source images for the same dataset.
Actual overview, assessment and quality sheets were rendered read-only and
visually checked. No patient captures or workbooks are published.

ClinVar returned three verified matches and Franklin six. Other results include
matches requiring transcript/identity review, no matches, missing-input review
requirements and two Franklin identity mismatches. These remain distinct from
successful verified matches. Missing transcript or genomic alleles were not
invented. Three intronic entries lack inputs needed for SpliceAI, and none of
the selected variants are BRCA1/BRCA2; this does not constitute a real intronic
SpliceAI or patient BRCA Exchange test.

The account owner requested an empty MTBP portal on 10 October. The newest
[Archer workstation branch](https://github.com/Christian-Bjornstad/Archer-prosess/tree/feat/workstation-improvements-2026-10-07)
was inspected at commit `c6744f98`. Its delayed server verification was adapted
and broadened to every report under the owner's instruction. Preflight now
requires zero reports; final cleanup follows local audit even for No match.
Two existing portal reports were removed and zero remaining reports verified.
A report-page/list URL bug that previously skipped deletion was fixed. Cleanup
failures remain visible and retryable and block new submissions.

After cleanup, the two previously uncertain submissions completed. Inspection
of the actual deletion capture exposed a protein-notation comparison bug;
normalization now handles indel ranges and inserted residues without equating
deletion and delins. A new authenticated batch confirmed both variant matches
with fresh captures, local Excel and verified remote deletion. An independent
subsequent visit confirmed zero reports. The final MTBP outcomes are nine
Review match, one No match, five Review required and twelve Review query.
There are no remaining uncertain submissions in this session.

## Excel format 3 and public services — 10 October 2026

Both raw workflows were rechecked: the Ion TSV metadata identifies the
Childhood/Oncomine workflow; Genexus/OPA raw XLSX and the separate SNV/indel TSV
are accepted. The Childhood TSV is filtered: 8 exported rows out of 3,385 total
variants, with 3,377 filtered out upstream. Source counts now accompany each row
and produce an explicit import warning and report scope note. Reviewed Childhood
workbooks remain design references and are not accepted as raw variant exports.

Three new actual workbooks use four visible worksheets: Overview, Quality,
Evidence and Raw data, with a hidden Searches audit. Independent read-only
verification checked 3,214 unchanged raw rows, 27 selected findings, 189 source
records, 408 valid internal links, 374 pixel-exact image segments and four unique
full MTBP reports. All 13 Genexus flags remain: four Failed CNV, five Failed
expression imbalance and four Report RNAExonVariant. All original source hashes
were unchanged. No clinical assessments were invented or read back from Excel.

Actual overview, QC, evidence index, raw data and first/middle/last variant
sections were rendered read-only and inspected. Long multiline notes retain all
text in readable rows; final image segments are included in the print area.
Generated reports have an explicit document marker, with a legacy recognition
fallback, and cannot be reimported as raw data.

Mutalyzer normalized all ten actual selected variants with sufficiently explicit
HGVS or hg19 alleles. Two deletion positions shift after HGVS normalization;
these remain review candidates. HTTP 422 HGVS validation reasons are preserved
as review evidence. An optional mapping failure does not discard normalization.
The source accessions in the original requirements were swapped between genes:
[FGFR1 NM_001174067.1](https://www.ncbi.nlm.nih.gov/nuccore/NM_001174067.1) and
[MET NM_001127500.3](https://www.ncbi.nlm.nih.gov/nuccore/NM_001127500.3) are now
associated correctly. Both mappings to the requested target transcripts succeeded
on public reference controls; this does not automatically approve patient HGVS.

SpliceAI returned 19 transcript predictions on a published intronic TP53 control
(maximum delta score 0.998), and valid predictions on two supplied exonic service
controls. The three selected intronic rows still lack REF/ALT and remain review
requirements. No alleles or transcripts were guessed. Assembly, request settings,
returned/trimmed alleles and numeric scores are checked; request spacing also
applies after validation rejections. Current gene/transcript fields are displayed.
[Official API and server documentation](https://github.com/broadinstitute/SpliceAI-lookup).

BRCA Exchange matched published BRCA1 and BRCA2 controls through both exact hg19
genomic and full versioned HGVS searches. ENIGMA assertions, exact identity and
dataset release were retained. The actual selected rows contain no BRCA1/2
variant, so these are reference tests rather than patient BRCA results.
[Official BRCA Exchange API](https://brcaexchange.org/about/api).

## Additional raw TSV validation — 13 October 2026

A new delivery archive was inspected recursively without executing attachments.
It contained seven Ion Reporter TSVs (69 rows) and five nested Genexus/OPA TSVs
(seven rows). Each of the twelve original TSVs was imported separately through
the production GUI. All 76 physical source rows, their original 62/63/25-column
schemas, sample separation and file hashes were independently verified. The
archive contains 70 sequence rows and six CNV rows; it contains no RNA assay rows.
Seven Ion exports declare hg19 and upstream filtering. The five OPA exports lack
sample/transcript/reference metadata; technical validation uses separate dataset
aliases and the user's prior explicit hg19 instruction, without inventing a
clinical patient association. Clinical assessments remain blank and Pending.

Two Ion formats have an empty Call column but populated Genotype. A reproduced
importer defect discarded the genotype in 38 sequence rows; the fix retains the
first nonempty Call/Genotype while preserving both original cells. Explicit
ABSENT, NO CALL and PRESENT precedence is covered by regression tests. These
negative/no-call values are not present in this new archive; earlier all-row
Genexus checks cover actual RNA ABSENT/NO CALL cases. Ion rows still require
manual selection; selecting all 70 sequence rows here is a technical test choice.

Fresh public-service checks used actual variants: seven successful transcript or
genomic Mutalyzer normalizations plus one PTEN intronic genomic candidate; one
verified PTEN SpliceAI result; and two verified BRCA Exchange matches. BRCA
source classifications remain separate from app assessments. PTEN's original
EINTRONIC error is retained alongside the confirmed hg19 genomic suggestion.
No transcript, allele or nomenclature approval was invented.

A fresh authenticated Edge batch recorded 14 source outcomes across two input
datasets, including two complete MTBP reports and current provider screenshots.
An OPA EGFR record describes a padded CT-to-CG change. Strict matching rejected
the database's equivalent T-to-G description one base downstream. The query
boundary now trims shared padding without shifting repeats or removing indel
anchors. Rerunning the two affected ClinVar/Franklin results returned a Verified
match and Review match respectively; both previous outcomes remain in history.
Source fields and fingerprints were unchanged. MTBP cleanup was verified after
both reports, and an independent portal visit confirmed zero remaining reports.

Twelve actual Excel exports passed independent source/session/workbook checks:
76 unchanged raw rows, 70 selected technical review candidates, both Failed
row-coverage flags, 25 current source results, 537 valid internal links and 49
pixel-exact image segments. Two full MTBP reports are embedded once each. Every
workbook retains four visible worksheets and the hidden Searches audit. Unsearched
rows remain explicitly Not run. Current image provenance, source-file separation,
first/middle/last links and final image print boundaries passed. Actual source
files, sessions, provider responses, captures and workbooks remain Git-ignored.

## Work-PC pilot remains

Franklin, COSMIC and OncoKB small-batch capture passed on this local PC.
The v0.4.2 real-data run uses locally saved credentials and MTBP tissue Other.
Institutional access, proxy and Edge policies
require testing on the work PC. Python FELLES and Ivanti app ID 15694 need the
same check. Provider adapters received variant data and pseudonymous search
IDs; original patient IDs, filenames and app notes were not sent.

Compare a known sample's import, row QC, selection and app assessments with the
manual workflow, then check a small authenticated source batch, identity, tissue,
captures, generated Excel and stop/retry behaviour before clinical use.

Mutalyzer mapping remains a suggestion requiring manual approval. Panel
membership, whole-gene coverage and the CNV =1 boundary need laboratory rules.
Excel edits are not read back; the app is the assessment source of truth.
