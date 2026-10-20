# Analysis report contract — v0.7.1

One original source is one OPA or Ion Torrent analysis in the current session. Sample IDs do
not merge separate sources. Selection, tissue, queries and export use the active
analysis. Assay identifies the panel, for example Childhood or BRCA/HRR.

## Archer/VPM workbook

The default export is one versioned Excel workbook, following the pinned Archer
patient writer's layout, colours, source order and original image placement:

- **Oversikt**: navy title rows 1–2, sample/date rows 3–4, section row 6 and
  filterable findings from row 8. The merged D3:M4 box and Comment cells are
  blank for manual Excel notes. Gene names are plain text, with no worksheet links.
- Source columns show the actual source content: MTBP functional relevance and
  evidence level, Franklin/ClinVar classifications, OncoKB oncogenicity, COSMIC
  identifiers and BRCA expert classification. Only current usable source records
  get an external link. Not-found results and unavailable/outdated evidence remain
  distinguishable; operational Review match / Verified match labels stay in the app.
- **MTBP**, when available: one copy of each combined report after Oversikt.
- **Variant sheets**: identity header followed by source screenshot sections.
  No repeated source-detail tables or laboratory-assessment appendix after the images.
  Unqueried/inapplicable sources add no empty sections. No internal navigation links.
- No **Quality** worksheet in either report profile. All-row QC remains in the app.
- Hidden **Kilder** and **Rådata** retain full responses, metadata and original
  ordered cells. They use literal ranges, without Excel structured tables or
  local capture links. Right-click a tab and choose Unhide to inspect them.
  Large JSON uses exact literal chunks, not truncation.

App-owned headings, captions and statuses are Norwegian. Original classifications
(including Benign), MTBP text, source screenshots, raw JSON and imported cells
remain verbatim. Missing OUM identifiers require manual entry in the import
dialog; valid typed identifiers are uppercased. Supported exports represent one
sample per file, and multiple supplied sample identifiers are rejected.

One genomic source row may expose multiple purple transcript choices. Displayed
source associations are provisional until exact-version NCBI gene lookup and an
independent Mutalyzer comparison with the source REF/ALT confirm the selected
annotation. Qualified HGVS references override source list positions; unqualified
names are candidates and must match the same genomic event. Missing names can be
recovered only from exact transcript equivalents and independently rechecked.
When a genomic-context response omits its gene, the exact NCBI reference proof
can supply it; a contradictory returned gene is always rejected. Temporary lookup
or identity-check outages remain retryable through Retry failed.
Proteins are retained only from a matching NM/NP prediction, never ambiguous list
positions. Unresolved selected choices block database requests and finding exports;
MTBP requires a complete valid selected batch. Each chosen annotation has independent identity/evidence. Rådata retains
the physical source row once, with all child IDs and any-choice selection; Kilder
retains the annotation mapping, checked identity and choices. Imported row counts
remain source counts. Changed identity, approval or source binding invalidates proof
and prior evidence. Reversed column repairs never modify the original cells.

Source columns and per-variant screenshots follow Mutalyzer, SpliceAI,
BRCA Exchange, OncoKB, COSMIC, ClinVar, MTBP and Franklin. Mutalyzer appears
above the screenshots only for a verified name change from the imported variant;
SpliceAI and BRCA sections require verified hits. Other source responses remain
in Kilder, including skipped/unsuccessful optional-source searches. Franklin
captures Predictions, Population Frequencies and expanded Clinical evidence.

Original screenshots are embedded intact at up to 1120 px width without shrinking
long captures to a fixed height. Valid MTBP geometry crops only the display copy;
its original PNG remains unchanged. Shared full reports are not repeated under
variants. Stale, conflicting, incomplete or unreadable captures are excluded with
an explicit state. The source assertions never become laboratory classifications. App assessments
remain in the current in-memory app session until close; only source content is presented in the attachment.

**Include source screenshots** controls images in the same workbook. Saving a new
version preserves earlier exports; retry a save error without rerunning searches.
The older compact exporter remains an internal compatibility API, not the default.
No PDF is produced and Excel edits are not read back into the app. Frozen worksheet
views are normalized once before save, removing obsolete/duplicate pane selections.

## Mutalyzer normalization

A normalizer result checks a name on its stated reference. It does not establish
that an arbitrary equivalent transcript is the reporting transcript. The app
independently normalizes the source hg19 REF/ALT including its VCF anchor, checks
reference sequence, and compares canonical delins event models. It never uses the
first returned equivalent as a transcript choice.

Explicit source/MANE candidates require matching gene, exact accession version
and genomic event. With no source transcript, offer only the verified genomic
name. Retain reference errors and mapper failures. Intronic mRNA EINTRONIC errors
remain visible; a separate exact NC(source NM):c context may yield a checked name
only after its returned hg19 reference and full genomic event agree.

Identity review shows Unchanged, Normalized, Conflict or Review required.
Independently confirmed new nomenclature is applied automatically to subsequent
queries, the variant view and the workbook. It requires the same explicit source
alleles, checked GRCh37 event and an accepted source/MANE candidate. It never
chooses an arbitrary equivalent transcript. Original imported fields remain
unchanged in Rådata. A current Conflict or unapproved manual change blocks
downstream queries. **Use checked name** remains available for manual review. Original
source fields and previous results remain intact. Conflicting green normalizer
panels cannot be embedded as accepted evidence.

## SpliceAI

Selected intronic candidates within ±100 bp trigger lookup, including when a
reviewed genomic name no longer displays an intron offset. The scoring request
uses hg19, basic annotations, distance 500 and masked scores. The 500 bp prediction
window is distinct from the candidate-selection rule. Exonic variants are not
implicitly assigned an intronic consequence by a different transcript.

Capture the actual website query/settings and every basic transcript's score rows,
including REF/ALT columns. The page's returned allele, genome, mask, distance,
transcripts and DS/DP scores must agree with the API response before capture.
Missing or incompatible images retain the API prediction and expose Missing
capture for retry. A verified identity is not a clinical splicing classification.

When SpliceAI is not indicated, Oversikt states **Ikke kjørt**. The ±100 bp
intronic selection rule is unchanged. The app shows the number of
selected candidates before running.

BRCA Exchange captures the current Variant Names and Clinical Significance
(ENIGMA) panels. The visible gene, versioned cDNA, GRCh37 HGVS, source assertion
and evaluation date must match the verified API record, including after a
canonical allele redirect. Historical versions are excluded from the capture.
A failed capture retains the API response and becomes Missing capture for retry.

All displayed export and capture dates use Europe/Oslo, including automatic DST.
Excel stores local dates as native date cells, with `dd.mm.yyyy hh:mm:ss` format;
report filenames use the same local clock. Original ISO source stamps stay intact.

## Data and MTBP preservation

Schema migration preserves original IDs, rows, evidence and assessments. Repeat
imports of the same source hash/sample/profile/assay reuse the analysis; assembly
conflicts require review. Apparent source formulas stay literal text. Raw fields
that cannot fit losslessly in Excel cause explicit export errors.

Coverage <500 describes the exported row, not whole-gene coverage. Missing values
are Unknown and missing categories Not supplied. CNV=1 requires review;
RNAExonVariant ABSENT is a reportable status rather than a positive finding.
Clinical review remains in the app and database assertions remain separate.

MTBP freshness includes the selected analysis batch and tissue. Legacy uncertain
gene matches require recheck. The account owner's policy deletes all portal reports
before submission and each new report after local capture/audit. An explicit
rendered report count and list headings are required to confirm an empty account;
a loading/error page with zero buttons is insufficient. Delete failures block a
new batch, and uncertain submissions retain their exact report ID for recovery.

Reference: [Archer writer at c12a1b8](https://github.com/Christian-Bjornstad/Archer-prosess/blob/c12a1b8bb840e33a41216148bc13be1e5c69682a/src/archer_processor/reports/patient_excel.py).
Actual laboratory data and account material remain local and Git-ignored.
