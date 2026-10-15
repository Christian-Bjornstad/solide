# Understanding the supplied raw data

The normal workflow is one original TSV from one sample and one analysis. OPA
and Ion Torrent are separate analysis profiles in this app. A sample need not
have both; matching gene names never establish that two files belong together.

## What was inspected

The recent archive contains twelve TSV exports:

| Export layout | Files | Total rows | Available sample information |
| --- | ---: | ---: | --- |
| Ion Reporter | 7 | 69 | Sample names and hg19 in metadata; Childhood or BRCA/HRR workflows |
| Genexus / OPA | 5 | 7 | No OUM number or reference genome in these small TSVs |

The seven Ion files include six CNV rows alongside sequence variants. The five
OPA TSVs are short variant exports, not complete sample quality worksheets.
Their small row counts do not show how many variants were originally analysed.
Without sample metadata the app cannot establish who those files belong to.
Enter the correct OUM when available; do not borrow an ID from another file.

The full supplied Genexus workbook has 3,204 rows for its sample, including
absent calls and CNV/RNA rows. It is a different source structure from a short
TSV of reported variants. The older OPA and Childhood ZIPs contain Excel files
(and OPA PDFs), rather than more original TSVs. Reviewed workbooks/templates
must not be mistaken for a fresh raw variant export. No PDF import is required.

## Detection and identity

- Genes + Transcript columns identify the Ion Reporter export layout. Workflow
  metadata supplies labels such as Childhood or BRCA/HRR.
- Gene + Nuc Change / Nucleotide Change identifies the supplied Genexus/OPA
  layout. This is an OPA profile suggestion, not proof that every possible
  Genexus export uses that assay. Import details permits correction.
- Explicit Oncomine Precision Assay metadata takes precedence over a Reporter
  column layout. Generic Type/Gene tables alone do not establish an assay.
- OUM numbers are read from sample metadata, a source preamble or the filename.
  Run suffixes do not become part of the OUM. Conflicts leave the field empty;
  metadata naming multiple samples is rejected for this single-sample workflow.
- Missing reference metadata remains missing in the original source. The import
  dialog explicitly displays the user-specified hg19 workspace default.

## Selecting rows

A filtered TSV can legitimately contain only one or two variants. Ion metadata
may explicitly describe thousands of source variants omitted by filtering. The
app retains that warning; it cannot reconstruct omitted rows or whole-gene QC.

Variants shows candidate rows for the active file. Unselected absent Genexus
calls and CNV/RNA quality rows are initially hidden, but never deleted. Use Show
all rows or Quality to inspect the complete supplied source. Existing selected
rows always remain visible in the candidate view. A checkbox selects a database
query candidate; it is not a clinical classification or final approval.

Source data and app assessments stay local. The clean Excel attachment contains
source findings and screenshots; complete source responses remain in hidden
storage, and quality review remains in the app.
