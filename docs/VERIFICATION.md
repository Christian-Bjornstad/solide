# Verification — Solide v0.4.1

Date: 9 October 2026. Local Windows / Python 3.12.

## Automated and runtime checks

- `python -m pytest -q`: **211 tests passed**. Fixtures are synthetic; the optional
  local reference test reads ignored laboratory files without external lookups.
- Compileall passed for source, scripts and the Python FELLES install/start helpers.
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
- Archer October ports: 98 vendor tests passed. Coverage includes Edge local
  transport, profile ownership, policy diagnostics, timeouts, source readiness,
  identity conflicts, per-variant checkpoints, MTBP uncertain dispatch, retained
  recovery, lost acknowledgements and cancellation during report polling.
- Local Edge smoke checks passed on synthetic HTML with a fresh temporary profile:
  zoom 1 / 1.25 / 0.8, nested scrolling, exact MTBP row crop and Franklin header.
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

Small real Edge batches returned two ClinVar and one Franklin **Verified match**,
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

## Work-PC pilot remains

Franklin, COSMIC and OncoKB small-batch capture passed on this local PC.
MTBP requires a fresh sign-in before submission, Other, full-report capture and
retry/recovery can be checked live. Institutional access, proxy and Edge policies
require testing on the work PC. Python FELLES and Ivanti app ID 15694 need the
same check. Provider adapters received variant data and pseudonymous search
IDs; original patient IDs, filenames and app notes were not sent.

Compare a known sample's import, row QC, selection and app assessments with the
manual workflow, then check a small authenticated source batch, identity, tissue,
captures, generated Excel and stop/retry behaviour before clinical use.

Mutalyzer mapping remains a suggestion requiring manual approval. Panel
membership, whole-gene coverage and the CNV =1 boundary need laboratory rules.
Excel edits are not read back; the app is the assessment source of truth.
