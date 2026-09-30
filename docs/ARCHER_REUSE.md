# Archer reuse

Pinned source: https://github.com/Christian-Bjornstad/Archer-prosess
Revision: 4fda67a43d8002fb2928d60211327b73943967fd

Included under src/solide/_vendor/archer: evidence browser runtime and its
direct dependencies, original model types. Imports namespaced to Solide.
Default profile/config paths isolated; MTBP defaults to Other. COSMIC sample
filter cleared to cover all tissues. No Archer artifact rules are applied.
User explicitly requested using their reference project; original repository
has no LICENSE file. Distribution beyond the repository owner's authorized
use needs a license decision. Upstream tests are used for selected runtime
regressions. No data files or browser profiles are copied.

Further adaptations: SOLIDE- portal report prefix; previous portal reports are
never deleted automatically; result and screenshot keys include genomic alleles
and protein to avoid collisions when HGVS is absent. Patient batch selection
participates in MTBP freshness. Solide checkpoints provisional audit captures
as partial results until the provider returns its final result. Provider screenshots
are written to separate per-run directories to preserve older source captures.
