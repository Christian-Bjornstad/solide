# LVMS/report notation

The copyable report line and visible protein columns use the reviewed identity.
Confirmed corrected nucleotide HGVS retains its complete reference, including
`NC_(NM_)` genomic/transcript context. An imported transcript must not replace the
reference explicitly attached to the corrected coding description.

An updated protein prediction requires current verified Mutalyzer evidence (or
current verified annotation-resolution proof), independent same-event confirmation,
the exact corrected nucleotide description, matching gene and genomic alleles, and
the matching transcript/reference. Mutalyzer's genomic-context `NC_(NP_):p.…`
spelling is accepted only with the exact `NC_` accession and version already
confirmed for the corrected `NC_(NM_):c.…` description. Bare `NP_:p.…` predictions
do not establish a transcript association and are omitted.

For manually registered interpretations, the corresponding proof records that
genomic alleles were derived from the entered HGVS and public reference sequence.
This confirms the reference mapping, not sample-level phase or observation. Manual
inputs, source-row links and that distinction remain in the hidden Kilder sheet,
also when the Mutalyzer screenshot source was not selected.

The laboratory presentation removes only an outer protein prediction wrapper,
for example `p.(Arg1516Ter)` becomes `p.Arg1516Ter`. Imported annotations and raw
API evidence retain their original spelling. If no matching confirmed prediction
exists for a corrected identity, the report omits the protein instead of reusing
the imported protein. Existing exported workbooks are snapshots; generating a
new report applies the current formatting and confirmation checks.
