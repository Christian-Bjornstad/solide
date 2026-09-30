# Verification — Solide v0.2.0

Date: 30 September 2026.

## Verified

- `python -m pytest -q`: 48 tests passed on Windows / Python 3.12.
- `python -m compileall -q src install_python_felles.py start_python_felles.py`: passed.
- Local input formats: 8 Ion rows, 2 Genexus TSV rows and 3204 Genexus XLSX
  rows. Quality rules reproduce 4 failed CNVs, 5 NO CALL tiles and 4
  RNAExonVariant ABSENT statuses. Input files remain untracked.
- Native GUI: filtering, selection, QC, session saving, English navigation,
  detail labels and identity review. All six pages fit at 1050×700; synthetic
  previews inspected at full and compact sizes.
- Legacy sessions with Norwegian unknown-assembly labels load correctly;
  comments and raw source data are preserved.
- Excel: patient separation, all-row QC, percentages, formula protection,
  assembly provenance, outdated evidence, embedded variant images and MTBP
  full report. Workbook headings and statuses are English.
- Queue: pseudonymous external records, separate patient batches, missing
  responses as errors, partial capture on interruption and complete selected
  MTBP batch on resume.
- Nomenclature: reviewed HGVS does not reuse old alleles; reviewed intronic
  offsets control SpliceAI; multiple genes, MANE differences and delins block
  ordinary searches until reviewed.
- Pinned Edge / genomic runtime regression tests pass.
- Previous local Edge capture verification used synthetic HTML only:
  zoom 1 / 1.25 / 0.8, nested scrolling, exact MTBP variant row and Franklin
  gene header. These runtime paths were unchanged by the UI update.
- Independent code review found no important regressions. Minor copy issues
  were corrected.
- Public-content audit: Git history contains no input TSV/XLSX files, sessions,
  browser profiles or embedded credentials. Targeted sample-ID and private-key /
  token checks passed. The published UI image contains synthetic data only.

## Still requires a laboratory pilot

Authenticated live database pages, MTBP Other, institutional access, proxy,
Edge policies, Python FELLES and Ivanti app ID 15694 require testing on the work PC.
No patient variants were sent to external providers during development.

Mutalyzer mapping is a suggestion requiring manual approval. Transcript choices
and nomenclature require professional validation. QC covers exported rows;
whole-gene coverage, panel membership and the final CNV =1 rule must be defined
by the laboratory. Exported Excel edits are not imported back.

For a pilot, compare a known sample's import, QC and selection with the manual
worksheet, then check a small database batch and its screenshots. Verify identity,
tissue, generated Excel and stop / resume behaviour before clinical use.
