# Analysis report contract — v0.7.0

One original source is one persistent OPA or Ion Torrent analysis. Sample IDs do
not merge separate sources. Selection, tissue, queries and export use the active
analysis. Assay identifies the panel, for example Childhood or BRCA/HRR.

## Archer/VPM workbook

The default export is one versioned Excel workbook, following the pinned Archer
patient writer's layout, colours, source order and original image placement:

- **Overview**: navy title rows 1–2, sample/date rows 3–4, section row 6 and
  filterable findings from row 8. Columns are Gene, HGVSc, HGVSp, Short evidence,
  Comment, then MTBP, Franklin, ClinVar, OncoKB, COSMIC, BRCA Exchange, Mutalyzer
  and SpliceAI. Solide's analysis context replaces Archer's app comment heading.
- **MTBP**, when current evidence is available: one copy of each combined report,
  linked from variant sheets. It follows Overview.
- **Variant sheets**: compact source statuses/links, source screenshots, recorded
  laboratory assessment and complete relevant source details. Only selected rows
  get variant sheets; no Archer germline/artifact exclusion rules are applied.
- **Quality**: all imported analysis rows, including unselected rows; OPA and Ion
  retain their own coverage/CNV/RNA/identity sections and missing-data warnings.
- Hidden **Sources** and **Raw data** retain all responses, metadata, original
  ordered cells, source hashes and physical rows. Right-click a tab and choose
  Unhide to inspect them. Large JSON uses exact literal chunks, not truncation.

Original screenshots are embedded intact at up to 1120 px width without shrinking
long captures to a fixed height. Valid MTBP geometry crops only the display copy;
its original PNG remains unchanged. Shared full reports are not repeated under
variants. Stale, conflicting, incomplete or unreadable captures are excluded with
an explicit state. The source assertions never become laboratory classifications.

**Include source screenshots** controls images in the same workbook. Saving a new
version preserves earlier exports; retry a save error without rerunning searches.
The older compact exporter remains an internal compatibility API, not the default.
No PDF is produced and Excel edits are not read back into the app.

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
**Use checked name** copies a verified candidate and alleles into the form; it does
not save or approve. Review, tick HGVS / mapping reviewed, and save. A current
Conflict or unapproved changed name blocks downstream database queries. Original
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
