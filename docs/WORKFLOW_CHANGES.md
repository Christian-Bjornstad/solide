# Search workflow and account controls — v0.4.0

The user requested fewer destinations, Settings login details, a shared log,
visible running status and explicit ways to retry failed or completed searches.

Workspace combines import actions, variant selection and row-level QC. Searches
owns results and queue actions. Reports and Settings remain separate. Original
source data is available on demand rather than another permanent tab.

Search plans are explicit sets of variant/source pairs. They are computed before
starting a worker so progress has a stable denominator. MTBP expands any targeted
pair to the complete selected patient batch. No selection is silently changed.
Provider results checkpoint into the session; provisional captures are retained
without counting as completed jobs. Old evidence is archived once per pair per
run before the first replacement.

Found results require separate assessment. Genomic verification is reported only
when the provider supplies accepted matching genomic identities, a matched GRCh37
location, an exact SpliceAI request/response echo, or exact versioned HGVS from
BRCA Exchange. BRCA Exchange jobs are restricted to BRCA1 and BRCA2. Screenshots must pass the
existing capture validator. Gene/protein-only results remain reviewable. This
checks search identity and capture integrity, not clinical classification.

Account usernames and last sign-in timestamps are local UI configuration. Only
Windows WinVault is accepted for password persistence; no plaintext fallback.
Vault lookup failures fall back to browser authentication, while save failures
remain explicit. Passwords are passed to the browser service in memory and
registered for log redaction. Logs rotate locally (2 MB, three backups).

Independent review identified ambiguous MTBP retries and blocked manual sign-in
on vault failure. Both were fixed with regression tests. Live provider login and
work-PC policies remain part of the laboratory pilot.

Manual clinical fields are edited through Assess variant and persisted with
change history. Excel is a new export version per patient; it does not become
another place to maintain assessments. Source classifications remain separate.

MTBP submission IDs are stored before click dispatch. Interim submissions and
captures do not count as finished work. A current uncertain report is reconciled
on retry; an interrupted provider cannot erase that report ID. Lost click
acknowledgements and cancellation during report polling are covered by regression
tests. OncoKB and Franklin returned identity conflicts cannot import classifications
just because the requested URL or bare coding description matches.
