# Verification — Solide

Local Windows / Python 3.12. Verification runs are dated below.

## OncoKB genomic identity and explicit report cells — 22 October 2026, v0.8.7

Inspected the supplied workbook read-only: seven selected variant sheets, 42
recorded source responses and 13 embedded images. NF1's OncoKB result had been
discarded as a canonical-transcript mismatch. All seven Franklin searches were
blocked by a busy dedicated Edge profile. COSMIC's TERT lookup reported an
explicit empty search but had been classified as a rendering failure. These
conditions previously shared the vague Kontroller resultat cell text.

A live NF1 lookup reproduced the exact failure before the fix: OncoKB's rendered
header said GRCh37, 17:g.29663493T>A, NF1 X2028_splice. Strict comparison to the
source transcript's c.6147+2T>A rejected that canonical label despite the explicit
returned genomic identity. The corrected parser accepts that independent proof,
retains the source label and imports the actual Likely Oncogenic assertion.
Wrong returned assembly, gene, position, alternate allele and URL-only claims
remain rejected. Raw fallback results are retained for unresolved cases.

Live ClinVar VCV 1299388 reproduced a separate error: the first unrestricted
GermlineClassification/Description was Pathogenic from a condition record;
the variant-level aggregate was Conflicting classifications of pathogenicity.
The corrected parser returns that aggregate, Tier I - Strong somatic impact and
Oncogenic oncogenicity as separate source assertions. Missing aggregate data
does not promote an individual submission. Explicit legacy RCV aggregates remain
supported. API responses and source screenshots are preserved in the audit.

**178 targeted tests passed**, covering source parsing, genomic identity,
normalization/report preservation, status text, failed captures, retry, COSMIC
no-hits, SpliceAI and layout stability, including 23 relevant Archer-parity checks.
The final checks include the multi-line heading-height change and HTTP access/
rate-limit messages. The full suite was not rerun.

Fresh background Edge captures and a production two-control Excel export show
NF1's OncoKB assertion/image and all three TERT ClinVar aggregate classifications.
Images extracted from the workbook were visually inspected; layout stability
fixes prevent late CSS/notices from cropping out classification panels. Native
Excel opened the report read-only without repair and confirmed both images.
Native Excel PDFs were used only for local visual verification, including cell
wrapping. A separate Excel process was verified before automation so existing
user workbooks were untouched. The supplied workbook was never written to.

MTBP was not queried, as requested. The busy Franklin profile on the reporting
workstation was not forcibly closed; the report now identifies that actual
failure. A fresh isolated OncoKB login attempt was not accepted; verification
continued using the authenticated test profile created during the initial live
reproduction. This does not establish successful sign-in on another workstation.

## MANE Select SpliceAI capture — 21 October 2026, v0.8.6

**71 targeted tests passed** for source capture, search/retry behavior, report
source order, SpliceAI visibility and clean Excel export. Regressions reject
wrong allele/assembly/settings, altered MANE annotations, non-finite Pangolin
scores, extra/missing transcript rows, missing panels, prediction errors and
canonical fallback. Multiple MANE transcripts remain visible. Earlier captures
without Pangolin/consequences enter Retry failed without losing API evidence.
The full suite was not rerun, following the user's earlier instruction.

A live managed Edge run used the public NF1 example NM_001042492.3:c.6147+2T>A
(hg19 chr17:29663493 T>A) from the supplied reference image. The full six-row
SpliceAI API response matched the page before filtering. The resulting native
image contains exactly four SpliceAI and two Pangolin score rows for MANE Select
ENST00000358273.9_12, followed by its SAI-10k-calc consequence. Other transcripts
and unrelated predictor sections are excluded. Existing masked/500 bp/REF-ALT
settings remain unchanged; predictions are not edited to match a reference image.

The production Excel export has two embedded images: the verified query/settings
and the combined three-section panel. The image extracted from the workbook was
visually inspected, including the last consequence row. Native Microsoft Excel
opened the report read-only without repair and confirmed both images; its file
hash was unchanged. Tests used isolated background Edge profiles and Qt offscreen.
MTBP was not queried during this change because the user reported it unavailable.

## Visible database selection and Excel label — 21 October 2026, v0.8.5

**34 targeted tests passed** for database selection, report language/local time,
the everyday workflow, analysis isolation, SpliceAI visibility and readability.
The source controls are permanently visible and can select/clear all databases.
Worker-boundary checks confirm that normal and rerun-all searches receive only
the checked databases; empty selection launches no worker.

Offscreen Qt screenshots were inspected at 1440×940 and 1050×700. All eight
checkboxes retain their full geometry; the compact-window page scrolls instead
of overlapping controls. A fresh production Excel export contains Opprettet
in A4 and the unchanged local-time date value/format in C4.

## Archer login comparison — 21 October 2026, v0.8.4

Compared the latest Archer Prosess main (249b823) with Solide. Both use the same
MTBP analysis URL and Keycloak username/password/submit controls. Archer allows
60 seconds after credential submission; Solide now uses at least that budget
while retaining cancellable waits and positive authentication checks.

A reproduced Solide-only navigation defect required the initial loader ID even
after a new SSO document had committed. Navigation now remembers the previous
document and accepts a new document in the requested main frame. The old page,
another/missing frame and Chromium error documents remain rejected.

**60 targeted tests passed** for CDP navigation, MTBP login, cancellation and Qt
worker cleanup/retry. The full suite was not rerun, as requested. A real managed
Edge comparison passed for both applications against a local synthetic login
fixture: immediate JavaScript redirect, a delayed navigation acknowledgement,
visible login form, synthetic credential submission and arrival at the analysis
input. No real credentials were used in that fixture.

The latest Archer login code was also run against real MTBP in a separate
background profile on this PC. It returned the same ERR_CONNECTION_TIMED_OUT
as Solide. The user clarified that Archer had worked on a different PC. These
are different environments; positive live MTBP login on this PC is still
unconfirmed. No network/proxy settings or existing browser profiles were changed.

## MTBP login navigation — 21 October 2026, v0.8.3

The reported failure was reproduced with the unmodified application against
the real MTBP site: Page.navigate timed out after exactly 15 seconds, before
credentials could be entered. A separate Edge navigation with a 45-second
budget ended with net::ERR_CONNECTION_TIMED_OUT. Independent curl access to
the same HTTPS endpoint also timed out; the system DNS and a separate public
resolver returned the same address. These checks establish a connection failure
from this PC, not a bad password or proof of a worldwide MTBP outage.

The login now uses the configured 45-second navigation/authentication budget,
waits for the actual visible Keycloak form or positively authenticated MTBP
input, and inspects a usable redirected document after navigation timeout.
Only HTTPS on the exact MTBP origin is accepted for this recovery. One retry
is limited to opening the login page; credential submissions are not replayed.
The dedicated browser profile is always released and readiness waits can be
cancelled.

The production live login rerun returned an unconfirmed Norwegian connection
message after two unsuccessful navigations, retaining ERR_CONNECTION_TIMED_OUT.
No credentials were submitted or marked verified. Actual positive MTBP login
could not be confirmed while the endpoint remained unreachable from this PC.

**956 tests passed**, including thirteen provider regressions for slow
navigation, delayed forms, timed-out but usable pages, transient recovery,
unreachable service, rejected origins, cancellation and slow authentication.
A real Qt LoginWorker test verifies failure cleanup and a subsequent successful
retry against controlled browser responses. Inverting the trusted-origin guard
was detected by the new tests, and source bytes were restored afterwards.

## Workstation API recovery — 20 October 2026, v0.8.2

**898 tests passed** in 69.43 seconds. Source compilation and diff checks passed.

### Actual-input rerun — 20 October 2026

- **942 tests passed** in 70.36 seconds after the additional provider and
  genomic-only input fixes. Source compilation and diff checks passed.
- The full production GUI workflow also completed on the supplied 20-row HRR
  input with 20 selected interpretations and 146 source jobs. All 20 Mutalyzer
  identities were verified. Franklin returned 20 verified matches, OncoKB 20
  source results, ClinVar 16 matches/four explicit no-hits, SpliceAI one verified
  intronic result, and BRCA Exchange four verified matches/one no-hit. Sources
  without applicable input were not queried. Excel opened normally with 20 raw
  rows, 20 selected findings and 394 embedded images. The overlapping unselected
  interpretation was not added to findings or the submitted MTBP group.
- A two-variant KIT OPA run exposed a genomic-only complex variant that was
  unnecessarily blocked after successful normalization. It now adopts only the
  independently checked genomic name, retaining original cells and without
  inferring a transcript or protein. Live MTBP rerun matched both distinct KIT
  rows and exported normally. Its More popup reports VCF alleles with a padding
  base; the shared event normalizer now compares complete, explicitly GRCh37
  DNA events. Wrong assembly, coordinate, REF/ALT or protein remains rejected.
  A genomic-only query cannot fall back to an unidentified gene-only row.
- A fresh full Mutalyzer/MTBP rerun of the 20 selected HRR variants then matched
  **20/20 MTBP rows**, including PTEN c.254-1G>A, which the old cDNA-only reader
  missed. Its Excel export completed without errors with 20 selected findings,
  20 original raw rows and 22 images. Only the test-created portal report was
  removed after capture; all source-file hashes remained unchanged.
- The HRR COSMIC identifier COSM937333 returned zero Legacy Mutations and 15
  unrelated fuzzy results on the fully loaded website. A fresh live rerun now
  records no exact legacy match instead of a transient rendering failure;
  unrelated records are not used. Other exact COSMIC lookups still succeed.
- Native Excel additionally opened the full HRR report and both KIT reports
  without repair (394, 41 and four images). Franklin's expanded Clinical evidence
  image was read back from an exported workbook and visually checked.
- An isolated inversion of the new genomic-event comparison was detected by
  its regression tests; the source was restored byte-for-byte afterwards.
- **914 tests passed** in 72.82 seconds after the actual-input regressions below.
- Imported fourteen supplied TSVs (the twelve archived exports plus the two
  original local inputs): 86 original source rows and 81 selected sequence
  interpretations. All original hashes were preserved. Technical test sample
  bindings were used; original patient identifiers were not sent to providers.
- Live Mutalyzer checks initially exposed six unnecessarily blocked cases:
  ATRX, three ATM variants, a TERT promoter variant and KRAS. RefSeq/assembly
  sequence differences elsewhere now require independent normalization of the
  filtered mapping in the exact genomic transcript context, followed by the
  existing source-event comparison. Missing context, changed gene/version,
  different events and malformed responses still fail closed.
- Promoter EOUTOFBOUNDARY responses can now be checked against explicit GRCh37
  source alleles using the exact genomic transcript. The original transcript
  rejection remains retained; no coordinate is inferred from a gene name.
- Rechecking all six yielded **81 confirmed identities: 71 unchanged and ten
  normalized**. All fourteen reports opened normally in native Microsoft Excel
  without repair, retaining the 86 original rows and 81 selected findings.
- A real single-variant OPA input completed the production Qt import, selection,
  search and export workers with live ClinVar, Franklin, COSMIC, OncoKB and MTBP
  results and 25 embedded images. It completed again with Python API access
  deliberately failing through a proxy, using managed Edge recovery.
- Additional live forced-proxy checks returned the expected BRCA Exchange
  record and six SpliceAI transcript score rows. BRCA Exchange now shares the
  restricted public-API transport; authenticated providers remain browser based.
- Live validation uses separate browser profiles and refuses to delete any
  pre-existing MTBP reports. Only reports created by the validation run are
  removed after local capture. User applications and normal profiles are kept.

The supplied activity logs showed immediate Mutalyzer/SpliceAI failures while
browser-based ClinVar and Franklin searches completed. The logs did not retain
the underlying API exception, so they cannot establish the exact workstation
network cause. The export error came from one unresolved selected annotation;
that same annotation correctly prevented submission of an incomplete MTBP batch.

- Public API transport now tries managed Edge after a Python connection/TLS
  failure, proxy HTTP 403/407 response, or HTML access page. One isolated
  temporary browser session is reused within the worker and closed afterwards.
  Destination allowlists, HTTPS, response status, exact request identity and
  all existing genomic-event validation remain enforced. No credentials,
  patient IDs, filenames or raw source rows are passed to the transport.
- If NCBI is unreachable, exact transcript identity can be checked against
  Mutalyzer's RefSeq model, including organism, accession/version, unique gene
  and CDS/protein hierarchy. A substantive NCBI reference conflict does not
  trigger this fallback. NM and NR cases, malformed/conflicting references,
  cooldown, reuse and cleanup have regression coverage.
- Live testing forced Python TLS failure for every API read and separately
  blocked NCBI. The two KIT examples and NF1 example normalized to the expected
  delins/dup names and predicted proteins. Reordered KLLN/PTEN candidates
  resolved to PTEN c.19G>A, then four selected findings exported successfully.
  Native Microsoft Excel opened the report normally without repair and retained
  all four original source rows, including the old KIT spelling.
- Live checks also resolved the supplied H3-3A/H3P6, TET2/TET2-AS1 and reordered
  CSDE1/NRAS examples. NRAS resolved to NM_002524.5:c.34G>T / p.(Gly12Cys).
- A deliberately wrong PTEN reference base returned HTTP 422 through Edge and
  stayed a sequence conflict. The intronic PTEN c.254-1G>A example was verified
  in its explicit GRCh37 context; SpliceAI returned six transcript score rows
  for chr10-89692769-G-A.
- MTBP query generation retained normalized HGVS and its allele-equivalent
  genomic fallback for all four selected examples. A regression test recovers
  the entire selected batch after a temporary annotation outage. No authenticated
  MTBP submission was performed in this verification run.
- The synthetic stress run passed 51 checks with 1,500 random GUI actions and
  a 5,000-row input. Original fixture hashes were unchanged. A mutation of the
  fallback organism guard was detected by its regression test.

Workstation-specific proxy/Edge access and authenticated MTBP submission still
need verification on the affected work PC. Export continues to reject unresolved
selected identities; it now identifies the transcript/source row and explains
retrying or explicitly deselecting the row, without silently omitting findings.
All supplied logs, workbook notes and generated verification artifacts stay
local and Git-ignored.

## Windows install/start launchers — 16 October 2026

- **581 tests passed** in 72.45 seconds on Windows. Eight bootstrap/launcher
  checks cover in-process install/start, failure exit codes, isolated shared-host
  arguments, local CMD argument forwarding, special-character paths and actual
  execution of the encoded pasted Python command against harmless stand-ins.
- Reused MolStat's Python FELLES / Ivanti startup pattern after reading its
  current tracked launchers and confirming its remote branch revision. Solide
  keeps its own Python minimum and local profile/configuration paths.
- Both CMD launchers check the complete project layout, prefer Ivanti app 15694
  when available, and otherwise use the same local interpreter selection. Paths
  are absolute and encoded for clipboard transfer. Added the installer alias.
- No packages were installed, no Ivanti process was opened, and the real clipboard
  was not changed by the tests. Institutional Ivanti/access still needs the work
  PC. Source compilation, diff checks and the public-data audit passed.

## Sample-based import and separate workflow pages — 15 October 2026

- **575 tests passed** in 36.71 seconds. New tests cover analysis detection,
  explicit-assay precedence, filename/metadata OUM extraction and conflicts,
  missing-ID validation, rejection of multiple named samples, isolated sample
  switching/selection, lossless candidate filtering, sample renaming and the
  separate Import/Variants/Searches/Settings navigation and clearing a previous
  sample's gene filter when a new file is imported.
- The actual GUI imported all twelve supplied TSVs separately again: seven
  Ion Reporter exports (69 rows) and five Genexus/OPA exports (seven rows).
  All 76 rows and original hashes are retained. Seven files provided detectable
  OUM metadata; five did not. For technical testing only, missing bindings use
  explicit Unbound aliases, not fabricated OUM identifiers or inferred patients.
- Every import dialog preselected the expected profile. Missing sample IDs had
  disabled Add sample actions; import details remain available on demand.
  Selection and active sample IDs were verified through the persistent sample list.
- The full 3,204-row OPA source shows 25 candidate rows in the default view.
  Show all rows restores exactly 3,204 rows, without changing the source model.
  Original all-row QC remains available separately from candidate selection.
- Reviewed compact 1050×700 and full-size GUI captures for Import, Variants,
  Searches and Settings, plus actual missing-OUM and populated import dialogs.
  File actions live on Import; source/tissue configuration folds out on Searches,
  leaving readable result rows and Excel export together. Public previews are
  synthetic; actual records and captures remain local and ignored by Git.
- Confirmed Archer's workstation branch still resolves to c12a1b8 and examined
  its current navigation. Reused its staged workflow approach while retaining
  Solide's per-file variant selection and the requested separate Import page.
- The two older supplied archives contain workbooks/PDFs rather than additional
  raw TSVs. docs/RAW_DATA.md records what can and cannot be inferred from them.

## Clean attachments and Excel repair regression — 15 October 2026

- **565 tests passed** in 39.95 seconds. New regressions cover both report
  profiles, blank manual-note areas, source labels/IDs/links, stale-source
  exclusion, absence of Quality/details/internal links/tables, and canonical
  worksheet pane selections after repeated freeze changes.
- Reproduced the duplicate obsolete selection records in a previously exported
  worksheet view. The save path now rebuilds exactly the valid frozen-pane
  selections. Default exports use no structured-table parts; hidden raw/source
  data remain complete literal ranges.
- Regenerated thirteen actual attachments. Opened all thirteen read-only with
  Microsoft Excel automation using normal load and no requested repair/recovery;
  every workbook opened and retained Overview with no Quality sheet. Existing
  user workbooks and earlier exports were not modified.
- Independent audit retained all 3,280 original rows, complete response/metadata
  round trips and all 272 pixel-exact source images. No internal/local navigation
  links remain. Read-only artifact rendering produced 140 worksheet ranges plus
  three full-width header views; source classifications, images and the blank
  Overview note box were visually checked.
- Source assertions are presented without Review match / Verified match prefixes;
  no laboratory assessment/source-detail appendix follows screenshots. App
  classifications, original rows and checks remain unchanged in the saved session.

## Normalization and Archer/VPM reports — 15 October 2026

- **560 tests passed** in 39.90 seconds. Source compilation and diff checks
  passed. Tests cover full anchored source alleles, canonical genomic delins
  identity, exact transcript versions, intronic genomic context, rejected
  normalization conflicts, SpliceAI settings/score/capture agreement and legacy
  MTBP identity rechecks. Provider regression tests exercise the selected
  c12a1b8 Archer ports; local Edge DOM smoke checks passed separately.
- Live Mutalyzer checks confirmed that the two supplied EGFR screenshot names
  describe the same GRCh37 sequence event. The short-transcript UTR name is
  not automatically an error. The app never selects the first equivalent
  transcript. Actual EGFR deletion, KIT delins, BRCA1 and intronic PTEN queries
  retain their original source fields and complete validation responses.
- PTEN c.254-1G>A initially produces the mRNA-reference EINTRONIC response.
  A separate exact NC(source NM):c request validates the genomic event; the
  original error remains in the evidence. Its checked candidate is offered
  for manual approval, not applied automatically.
- Actual SpliceAI capture shows hg19, basic annotations, masked predictions,
  distance 500, REF/ALT and all six transcript score groups. The page response,
  DOM settings, coordinates, transcripts and DS/DP values match the separately
  validated API response. Two real PNGs are retained; missing capture is retryable.
- Fresh authenticated browser batches covered two supplied analysis formats:
  14 source results across ClinVar, Franklin, COSMIC, OncoKB and MTBP. Six MTBP
  variant results completed as five Review matches and one No match. Remote
  reports were deleted and a separate authenticated rendered-list check
  confirmed zero reports. An unavailable/error list cannot be treated as empty.
- Generated **13 actual version-5 workbooks**: twelve separate TSV analyses
  plus the complete 3,204-row OPA worksheet. Independent read-only audit passed
  all **3,280 original rows**, selected order, QC exceptions, full metadata and
  JSON round trips, **272 pixel-exact embedded images** and **426 local links**.
  Existing valid source captures retain their actual dates; this image total
  includes earlier captures and does not represent 272 fresh database requests.
- Read-only artifact rendering produced **155 worksheet ranges**, with further
  full-width header checks. OPA/Ion overviews, QC exceptions, source statuses,
  source images and normalization details were visually inspected. Default
  export is now one Archer/VPM workbook; separate evidence attachments belong
  to the older compatibility exporter.
- Actual GUI renders at 1050×700 / 18 px and 1440×940 verify readable Settings
  and a scrolling Identity review with the checked PTEN candidate. Laboratory
  classifications, reviewers and approvals remain unfilled. Technical source
  checks do not constitute laboratory validation or a clinical interpretation.
- Public-path/history and vault checks found no raw inputs, sessions, generated
  reports, private identifiers, keys or passwords in publishable paths. Actual
  data, screenshots and audit artifacts stay local and Git-ignored.

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
