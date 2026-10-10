# Report and assessment contract — v0.4.0

The laboratory reference files were inspected locally for structure and useful
workflow patterns. No patient source content was added to the repository.
The review templates informed the app's manual categories and assessment fields;
their clinical scoring formulas are not an automatic classifier in Solide.

Manual assessment lives in the session. Each change records previous and updated
classification, decision, reviewer, notes and UTC review time. Older sessions load
with blank classification and `Pending` decision. Database assertions remain
separate. Identity and tissue changes invalidate evidence; assessment text does
not change a biological search fingerprint.

The Excel report is an immutable export version, not an input for assessment
readback. Selected variants appear in Overview with their explicit decision,
including Pending and Exclude. Quality includes all imported patient rows.
Only current, readable image captures are embedded. Full MTBP captures are shared
within the workbook; long images are split into consecutive segments without
changing the original capture files.

Source provenance includes file hash, sheet and physical row. Raw data retains
source column order, blank-header values and literal text safely. Mixed source
schemas form an ordered union beginning with the first imported source schema;
the source sheet/hash/row resolve each record. Full originals remain in the
session. Formula characters are not executable spreadsheet formulas.

Original raw tables are accepted after their preamble. Duplicate header names,
multiple competing tables and generated presentation copies are rejected.
Reviewed child templates and target/gene coverage are intentionally different
source types: they must not be interpreted as sequence variants. Row Coverage
does not establish whole-gene coverage. No PDF output is created.

BRCA Exchange runs for exact canonical BRCA1/BRCA2 gene labels. A found result
requires an exact versioned HGVS or explicit hg37 allele match, one unambiguous
candidate and a matching detail version. The source assertion, accession and
release remain visible; they never populate manual classification automatically.
Unknown assembly, unresolved nomenclature, conflicting identities and incomplete
API pages remain review/error states. API use follows its
[official documentation](https://brcaexchange.org/about/api) and
[current server implementation](https://github.com/BRCAChallenge/brca-exchange/blob/master/django/data/views.py).

MTBP checkpoints its analysis ID before click dispatch and cancellable waits.
Retries of a current batch pass retained report evidence for reconciliation.
Changed variant identity, tissue or selection creates a different batch; older
evidence remains in history. The account owner requested an empty MTBP portal:
all existing reports are deleted before submission, and each new report is
deleted after local audit/capture. Deletion is verified with up to three delayed
server checks. A failed cleanup blocks the next submission. This policy includes
reports created outside Solide; the configured account should be dedicated to
this workflow. Failed or incomplete captures remain explicit local statuses.
