# Solide

Local Windows desktop app for solid tumour variant review. Import Ion Reporter
and Genexus exports, review row-level quality, select variants, collect database
evidence through Edge, and export one Excel workbook per patient.

![Solide workspace with synthetic data](docs/images/solide.png)

## Install and start

Python 3.11+ and Microsoft Edge are required.

```powershell
python -m pip install -e ".[dev]"
python start_python_felles.py
```

After installation, `SOLIDE_START.cmd` also starts the app.

For the laboratory's **Python FELLES** environment:

1. Save the project in a permanent folder.
2. Run `SOLIDE_INSTALL.cmd`, paste the copied command into Python FELLES and press Enter.
3. Close Python FELLES, run `SOLIDE_START.cmd` and paste its start command.
4. Choose an approved local workspace folder in **Settings**.

The shared-interpreter bootstrap follows
[MolStat](https://github.com/Christian-Bjornstad/MolStat). Ivanti app ID 15694
and Python FELLES compatibility must be checked on the work PC. Installation
uses the user's site-packages without administrator rights. Failure logs are
written to `%LOCALAPPDATA%\Solide\logs\bootstrap.log`.

## Workflow

1. **Import** TSV or Genexus XLSX; confirm patient / sample ID and assembly.
2. **Quality** shows flags from every imported row, including unselected rows.
3. **Variants** lets you filter, select, comment and review variant identity.
4. **Sources** selects databases and MTBP tissue (default **Other**). Save the
   session, sign in through Edge where needed, then run searches.
5. Review source status and screenshots before exporting **Reports**.

Sessions preserve source data, comments, reviewed HGVS and search history locally.
Comments edited directly in an exported Excel file are not imported back.
Pause and stop take effect at checkpoints; active browser or HTTP requests may
need to finish first. Provisional captures remain marked as partial evidence.

## Quality and nomenclature

| Check | Result |
|---|---|
| Coverage <500 on a row | Failed coverage |
| CNV Copy Number <1 | Failed CNV |
| CNV Copy Number =1 | Review boundary value |
| RNAExonTiles NO CALL | Failed expression imbalance |
| RNAExonVariant ABSENT | Included as a status, not a positive finding |
| Intronic HGVS offset 1–100 bp | SpliceAI candidate |

Missing numeric QC values are unknown. Coverage describes exported rows, not
whole-gene coverage. Assay / gene-package selection currently follows the imported
export; the laboratory must define any additional panel rules.

Delins / complex variants require Mutalyzer review. Known FGFR1 and MET transcript
differences require mapped, reviewed HGVS on the target transcript:

| Gene | Exported transcript | Target transcript |
|---|---|---|
| FGFR1 | NM_001127500.3 | NM_023110.3 |
| MET | NM_001174067.1 | NM_000245.4 |

Mutalyzer returns suggestions for manual approval in **Identity review**.
Corrected HGVS never silently reuses original genomic alleles. Enter matching
reviewed hg19 `chr-pos-REF-ALT` when a genomic lookup is needed after correction.

## Database evidence

ClinVar, Franklin, COSMIC, OncoKB and MTBP use the pinned
[Archer Edge/CDP runtime](docs/ARCHER_REUSE.md). Sign-in uses visible Edge;
automated windows are minimised by default. Edge remote debugging must be allowed.
Mutalyzer and SpliceAI use HTTP adapters. SpliceAI requires confirmed GRCh37 and
explicit REF/ALT, uses `distance=500`, `mask=1`, and runs at least 30 seconds apart.
Genexus XLSX may omit REF/ALT; these must be reviewed before genomic searches.

Gene / protein or identifier-only lookups are explicitly labelled. Multiple
genes / transcripts require identity review. Record HSMD results manually in
the variant comment.

Changing variant identity or tissue marks older evidence as outdated. Changing
the selected patient batch also invalidates the MTBP full report. A resumed MTBP
search reruns the whole selected batch when needed. Existing portal reports are
not automatically deleted; the newly generated report may be removed after local
capture. Errors and partial captures remain distinct from **Not found**.

Patient IDs, local filenames, comments and raw worksheets are not sent to providers.
Adapters receive variant data and pseudonymous search IDs. Authenticated profiles
stay under `%USERPROFILE%\.solide\browser_profiles`. Source files, sessions,
reports, credentials and browser profiles are excluded from Git.

Live authenticated provider flows, MTBP **Other**, institutional access and the
work-PC environment still require a laboratory pilot. No patient variants were
sent to external services during development. Reports require professional review
before clinical use.

## Development

```powershell
python -m pytest -q
python -m compileall -q src install_python_felles.py start_python_felles.py
python scripts/render_preview.py
```

Tests use synthetic fixtures. The optional local reference-file test is skipped
when the laboratory's untracked input files are absent. The UI preview is synthetic.
See [verification](docs/VERIFICATION.md) for tested scope and remaining checks.
