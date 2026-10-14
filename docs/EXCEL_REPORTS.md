# Analysis report contract — v0.6.0

One imported source is one analysis. OPA and Ion Torrent are explicit report
profiles; assay describes the panel (such as Childhood or BRCA/HRR). Matching
sample IDs never join separate sources. Each analysis has a persistent local ID,
its own tissue and complete source metadata. Analysis IDs are not sent to databases.
The active analysis controls rows, searches and export across the app.

Schema 1 sessions migrate by source, sample and assembly without changing row
IDs, evidence, clinical fields or source cells. Unknown Genexus profiles are
Unassigned until confirmed. Repeat imports with the same source hash, sample,
profile and assay reuse the existing analysis. Different confirmation creates
a distinct analysis; assembly conflicts require review.

## Compact report

Each version has three visible worksheets:

- **Findings**: selected variants, source transcript, variant, protein, AF, row
  coverage, laboratory classification and decision. Full assessment notes,
  reviewer and review date follow the table when recorded in the app.
- **Quality**: all analysis rows, including unselected rows. OPA separates row
  coverage, CNV, RNA expression imbalance and RNA exon variants. Ion includes
  row coverage, supplied CNV, identity checks and coverage limitations.
- **Sources**: variant/source match assessment, separate source assertion,
  capture date and attachment link. Hidden columns retain response and provenance.

Complete original columns and every row remain in hidden **Raw data**. To read
these, right-click a worksheet tab and choose **Unhide → Raw data**. Source order,
blank values and literal text are preserved; apparent formulas are stored as text.
Fields that Excel cannot store losslessly cause an explicit export error.
Source file/hash/physical row identify each record. Source files remain intact.

Coverage <500 applies to the exported row, not a whole gene. Missing numeric
values remain Unknown. Missing categories are Not supplied, rather than passing
QC. CNV=1 requires review. RNAExonVariant ABSENT is a reportable status, not a
positive variant. Filtered exports state that QC covers supplied rows only.
Source metadata does not establish missing run/chip metrics.

## Separate VPM-style attachment

**Include Excel attachment** creates another workbook when current source
evidence exists. Its **Index** links to variant sheets, with sources ordered:
MTBP, Franklin, ClinVar, OncoKB, COSMIC, BRCA Exchange, Mutalyzer and SpliceAI.
Unsearched variants do not get empty evidence sheets. Each combined MTBP report
is included once per original capture in its own sheet, linked from the variants.

Only current, readable, eligible images are embedded. Outdated or conflicting
results remain explicit source states. Tall captures are split into consecutive
lossless segments and displayed at a readable width. Valid MTBP geometry can
crop introductory material from the displayed copy; its original PNG stays
unchanged and remains linked. Private, deleted MTBP portal links are omitted.

Reports and attachments have versioned, paired names. Relative links work while
the two Excel files stay together. Stage both files, publish the attachment first
and the main report last. Failed publication removes its new orphan attachment;
prior exports are preserved. Retry save errors without repeating searches.
Clearing the attachment option still exports the compact report and source ledger.

## Assessment and evidence

Classification, decision, reviewer and comments are edited in the app. Each
change records prior values and review time. Excel is a snapshot; workbook edits
are not read back. Database assertions never fill laboratory classification.
No PDF output is created.

Identity and tissue changes invalidate evidence. MTBP freshness additionally
includes the local analysis context and complete selected analysis batch. Rerunning
one MTBP result expands only that analysis. Old combined batches remain outdated
until rerun, with evidence retained. Capture folders separate analyses and runs.

BRCA Exchange applies only to BRCA1/BRCA2. Mutalyzer suggestions and SpliceAI
predictions require review. A found record alone does not prove an exact variant
match. Unknown assemblies, conflicting alleles and incomplete responses cannot
become verified evidence.

The account owner's MTBP policy remains: delete all existing reports before
submission and delete each new report after local audit/capture. Verify deletion
with delayed server checks; failed cleanup blocks a new submission. This includes
reports created outside Solide. Uncertain submissions retain their exact remote
report ID for reconciliation before resubmission.

Laboratory files informed structure and preservation checks. Clinical source
content is not published. VPM attachment concepts were checked against the
[pinned Archer writer](https://github.com/Christian-Bjornstad/Archer-prosess/blob/b5f50c6e031ad9cfe8374e99d7e47b92c22872d1/src/archer_processor/reports/patient_excel.py).
