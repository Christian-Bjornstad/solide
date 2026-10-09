# Archer reuse

Pinned source: https://github.com/Christian-Bjornstad/Archer-prosess
Revision: 4fda67a43d8002fb2928d60211327b73943967fd

Focused follow-up source: branch `feat/workstation-improvements-2026-10-07`,
revision `c6744f98c919fd2ee89b5c8c6ebc57578edf1d0e`, checked 9 October 2026.
Upstream `main` still points at the base revision above. This is a selective
port from the later branch, not a replacement of the vendor tree.

Included under src/solide/_vendor/archer: evidence browser runtime and its
direct dependencies, original model types. Imports namespaced to Solide.
Default profile/config paths isolated; MTBP defaults to Other. COSMIC sample
filter cleared to cover all tissues. No Archer artifact rules are applied.
The repository owner explicitly authorized this reuse and publication of Solide.
The original repository has no LICENSE file; this repository does not add a
third-party redistribution license. Upstream tests are used for selected runtime
regressions. No data files or browser profiles are copied.

Further adaptations: SOLIDE- portal report prefix; previous portal reports are
never deleted automatically; result and screenshot keys include genomic alleles
and protein to avoid collisions when HGVS is absent. Patient batch selection
participates in MTBP freshness. Solide checkpoints provisional audit captures
as partial results until the provider returns its final result. Provider screenshots
are written to separate per-run directories to preserve older source captures.

The October follow-up imports local Edge policy diagnostics, exclusive profile
leases, checks that an existing DevTools profile is idle, local-only HTTP with
redirect rejection, bounded retries for Windows socket collisions, and CDP
timeout handling. Policy checks are read-only; neither ordinary Edge windows nor
other evidence sessions are closed to make a profile available. No runtime
dependencies were added.

Provider fixes include OncoKB page identity checks and GRCh37 genomic fallback,
explicit terminal-page detection, diagnostic captures on rendering timeouts,
independent COSMIC cache results, COSMIC GRCh37 selection and terminal-page
readiness, Franklin mode/render readiness and failure
stages, and final per-variant evidence checkpoints before the next lookup.
Checkpoint payloads retain the existing dictionary API and are copied so later
provider work cannot mutate earlier results. Unknown provider statuses remain
unfinished. MTBP checks the submission button and preserves an uncertain click's
exact SOLIDE report ID for reconciliation before resubmission. The report ID is
durably audited and checkpointed before click dispatch; lost acknowledgements
and cancellation during report polling therefore retain recovery information.
That interim checkpoint is marked provisional until the provider call finishes,
so waiting for a report does not count as a completed review job.
MTBP variant
captures fall back to a direct capture if a frozen-report crop is incomplete;
full-report geometry also records `content_top` for report presentation.

Solide retains its isolated `.solide` paths, `Other` cancer default, all-tissue
COSMIC samples, SOLIDE report IDs, genomic-aware result/screenshot keys, and
manual removal of old portal reports. The selected variant list is controlled
by Solide; upstream germline/artifact skipping and the workstation UI/catalog
rules were not imported. Default pacing remains 10–20 seconds. The strict
ClinVar API verification of chromosome, GRCh37 position, REF, and ALT remains:
the branch's website-only HGVS/protein matcher was not substituted. MTBP gene
context warnings remain visible in the capture pixels.

Solide review also tightened two identity boundaries beyond the upstream port.
OncoKB's documented [HGVS URL](https://faq.oncokb.org/technical) is a request
route, not proof of returned genomic identity: a visible gene/protein or cDNA
match is required and a conflicting variant heading is rejected. A different
canonical protein mapping remains for manual review unless independently
verified. Franklin calls a transcript match exact only when the full accession,
version, and cDNA agree; an older displayed accession version is rejected when
matching returned genomic alleles are unavailable. Gene/cDNA-only matching is
recorded separately from exact transcript or genomic verification.

Verification uses synthetic provider doubles, local DevTools HTTP fixtures,
profile-lock subprocesses, cancellation/checkpoint regressions, and local HTML
pages in a fresh temporary Edge profile. No patient files or signed-in provider
profiles are needed for these checks.
