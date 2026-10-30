# Manual variants and selection implementation plan

**Goal:** Enter a new sequence variant or a manual interpretation of highlighted
rows, run the normal searches, and report the checked Mutalyzer identity.

**Execution:** User requested immediate execution ("Kjør på"). Keep the current
PyQt application and analysis model. Original rows remain unchanged. Coverage
and LVMS evidence audits run independently while the main implementation proceeds.

## Review focus

- A new interpretation must never inherit source evidence, COSMIC ID, REF/ALT,
  coverage or AF from a different event.
- Missing locus must not prevent entry; derive genomic identity from exact HGVS
  and public references at search time, retaining its manual provenance.
- Cancelled/failed validation must not partially replace a row's identity.
- Select-all must use a snapshot of visible rows and stay within one analysis.
- Report text must use confirmed current corrections, including protein names
  from chromosomal NP references, without outer prediction parentheses.

## 1. Domain entry and validation

Create `manual_variants.py` with `add_manual_variant(session, analysis_id, *,
transcript, coding, protein='', gene='', locus='', parent_ids=()) -> Variant`.
Require a versioned NM/NR and a single c./n. description. Gene and locus are
optional. Bind to an existing analysis; preserve manual inputs/parent IDs and
timestamp. Start selected without imported evidence or measurements.

Test missing/invalid fields, foreign parent IDs, source preservation, independent
IDs, JSON session roundtrip, and export provenance in `test_manual_variants.py`.
Run the tests red, implement, run green.

## 2. Selection header

Create a checkbox header for the Valgt column and connect it to visible-row
selection in `gui.py`. Checked means all visible rows are selected; partial
means some; clicking partial selects all; clicking checked deselects visible.
Use a row snapshot to prevent proxy re-filtering during changes. Disable while
a search is active. Test filtering, multiple analyses, empty views and reruns.

## 3. Manual entry UI

Create `manual_variant_dialog.py` with transcript, nucleotide, protein, optional
gene and locus inputs. New-from-row prefills only an unambiguous transcript/gene
and current coding/protein; no inherited genomic event. Keep the popup open with
inline validation errors. Add two buttons to a separate toolbar in Variants.
Selecting multiple rows records all parent IDs for a combined interpretation.
After entry select and scroll to the new row, clearing the text filter as needed.

## 4. Search integration

Create `manual_resolution.py` and dispatch manual rows from annotation resolution.
Confirm transcript/gene and map its HGVS to GRCh37 before provider searches, even
when the Mutalyzer screenshot source is unchecked. Record sequence derivation
explicitly. Optional locus constrains the mapping. Existing row evidence remains
bound to the resolved identity. Emit manual genomic changes to the GUI only for
unchanged manual input/provenance. Test cancellation, conflict, failed services,
combined delins, missing locus and exact reference checks.

## 5. Audit and verification

Inspect supplied coverage metadata for an explicit OUM↔barcode crosswalk; document
the missing fields if absent, with no automatic assignment based on column order.
Check old LVMS report outputs against retained Mutalyzer data; add regression
tests for confirmed corrections. Recheck existing OPA 45-reference and 10 bp tests.
Run `python -m pytest -q`, compileall and diff checks. Render the Qt popup and
selection header with synthetic data and inspect screenshots. Commit cohesive
changes after verification. No source workbooks or TSVs are modified.

## Completed verification

- Final suite: 1,163 passed, 6 existing optional integration tests skipped.
- Independent review findings reproduced and fixed: re-enable the header after
  worker completion, verify unchanged manual Mutalyzer names on first/repeated
  lookup, and enforce a known exact NP version in all protein consumers.
- Queue-to-report tests cover manual entry without locus, provider queries with
  Mutalyzer screenshots unchecked, LVMS corrections and hidden provenance.
- Qt screenshots inspected at standard size and 1050×700 with 18 px text; dialog,
  header checkbox and existing detail actions fit without overlap.
- Compilation and whitespace checks pass. Source attachments remain unchanged.
