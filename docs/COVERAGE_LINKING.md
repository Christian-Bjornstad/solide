# Coverage linking investigation

Read-only local inspection on 2026-10-29. No source workbooks or TSVs were changed. This note records file structure and provenance checks, without patient measurements.

## Conclusion

The supplied files do **not** establish a safe automatic link from an OUM sample to a coverage-matrix column. Defer automatic coverage assignment until a run-specific barcode-to-sample crosswalk is supplied or explicitly confirmed. Dates, row order, column order, and similar coverage values are insufficient evidence.

## Evidence

| Source | Observed structure |
| --- | --- |
| `D:/Dekning/Auto_2026_10_21_HRR_torrent-server_2350.bcmatrix.xls` | Plain tab-delimited text despite the `.xls` suffix. Header is `Gene`, `Target`, then `IonCode_0101` through `IonCode_0132`. 1,481 target rows, each with 34 fields. |
| `D:/Dekning/Coverage_20260923.xls` | Plain tab-delimited text. Header is `Gene`, `Target`, then `IonCode_0101` through `IonCode_0124`. 1,481 target rows, each with 26 fields. |
| Three supplied Ion Reporter TSV exports dated 2026-10-26 | Metadata includes `analysisDate`, `exportDate`, `analysisName`, `sampleNames`, `workflowName`, and `reference=hg19`. Neither metadata nor the variant table has a barcode or sequencing-run field. |
| Corresponding report workbooks, including the supplied additional report sample | `Kilder` retains the TSV metadata. `Rådata` retains source filename, reference genome, application analysis ID, and source SHA256. These identify the imported TSV, but do not add the missing run/barcode mapping. |

Both matrices contain the same ordered set of 1,481 unique target IDs. No OUM identifiers occur in either matrix. There are no additional metadata rows, embedded sample names, genomic coordinate columns, reference-genome fields, or metric-definition fields. All matrix measurement cells parse as numeric values; their units and processing definition cannot be established from these files alone.

Target IDs are assay identifiers, for example `RAD54L_1.33418`, rather than genomic positions. Mapping targets to variant loci or genomic/exon intervals would additionally require the matching assay target definition, such as a versioned BED/manifest.

All eight inspected versions of the relevant report workbooks had no `IonCode_*`, `barcode`, `torrent-server`, or `runId` token in their workbook XML. The three 2026-10-26 reports' metadata cells are `Kilder!K41`, `Kilder!K93`, and `Kilder!K69`; the additional sample's 2026-10-26 report uses `Kilder!K593`. The reports' `Rådata!BO1:BS1` headers identify the provenance columns. The `Analyse-ID` here belongs to the application import and must not be treated as a Torrent run identifier.

The source hashes in all four 2026-10-26 reports match their corresponding local TSVs. Hashes in the inspected 2026-10-27 report versions also match. One older report dated 2026-10-22 names a different TSV export that is absent from `D:/`, so that older report's source hash cannot be checked against the supplied files. This is not evidence of a hash mismatch.

The three fresh TSVs have an analysis date of 2026-10-23, while their export date is 2026-10-26. The additional sample's retained analysis date is 2026-10-09. Report creation/export dates therefore cannot establish which coverage run applies. The run-like string in the first matrix filename is only a filename hint until corroborated by a run export.

## Missing crosswalk

A trusted export or explicit user confirmation must connect these fields in the same record:

- Coverage source file, preferably with its SHA256, and the actual sequencing run/result identifier.
- Exact matrix barcode, such as `IonCode_0101`.
- Exact source sample/library identifier, preserving version suffixes and repeat/library distinctions, linked to the intended TSV/import.
- Reference genome and assay/target-definition version where interval or locus mapping is needed.

A Torrent Suite sample/barcode table, run plan, BAM filename/header metadata, or equivalent laboratory sample sheet may supply this information. Its contents must be checked rather than inferred from its name. Barcode labels recur in both matrices, so barcode alone is not a global key.

## Safe implementation boundary

An eventual importer can recognize the tab-delimited matrix by its content, retain it as an **unlinked** dataset, and show its source/run, barcode columns, and target count. It must not attach measurements to a sample automatically without an unambiguous confirmed crosswalk. Persist the chosen matrix hash, run identity, exact barcode, sample/library identity, mapping origin, and confirmation state; reject missing/ambiguous mappings and preserve repeat imports separately.

Keep variant-table `Coverage` and `Raw Coverage` distinct from coverage-matrix target measurements. These filtered TSVs do not supply coverage for targets absent from the variant table. A matrix cannot by itself establish base-level coverage, unsequenced loci, or a validated clinical coverage threshold.
