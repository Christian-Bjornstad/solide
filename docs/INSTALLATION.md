# Install and start Solide

Keep the complete Solide project in a permanent folder. The CMD and Python files
must stay beside pyproject.toml and the src folder. Original data and saved
reviews are not part of the installation package.

## Updating an existing installation

Extract the complete new package into a separate folder and run its
**SOLIDE_START.cmd**. The bootstrap selects that folder's source code before any
older editable installation. Version 0.8.4 adds no dependencies; when the existing
installation already works, reinstalling packages is unnecessary. Check the
version in the window title. Use SOLIDE_INSTALL.cmd only for a first installation
or missing dependencies.

## Work PC — Python FELLES / Ivanti

1. Double-click **SOLIDE_INSTALL.cmd** once.
2. Python FELLES opens through Ivanti. Paste the copied command with Ctrl+V and
   press Enter. The installer uses that interpreter and the user's site-packages;
   administrator permissions are not required.
3. When installation finishes, close Python FELLES.
4. Double-click **SOLIDE_START.cmd**. Paste the copied command into Python FELLES
   and press Enter to open Solide.

SOLIDE_INSTALLER.cmd is an alternative name for the install launcher. Installation
and startup follow MolStat's in-process bootstrap pattern. The default Ivanti
executable is C:\Program Files (x86)\Ivanti\Workspace Control\pwrgate.exe and
its Python FELLES application ID is 15694. Solide requires Python 3.11 or newer;
MolStat's stricter interpreter-version requirement is not copied.

The pasted startup command intentionally ignores Python FELLES' own launch flags.
Encoded paths support spaces, apostrophes, ampersands and Norwegian characters.
Clipboard failure stops before opening Ivanti. Keep the entire folder in place:
editable installation and startup both reference its source code.

## Ordinary Windows PC

Without Ivanti, the same CMD files use a local Python interpreter: py.exe -3,
then python.exe. Install first with SOLIDE_INSTALL.cmd; start with SOLIDE_START.cmd.
Errors stay visible in the CMD window. Optionally set SOLIDE_PYTHON to the full
path of a specific Python executable for both launchers. SOLIDE_IVANTI can
specify a different Ivanti executable location.

The equivalent terminal commands are:

```powershell
python install_python_felles.py
python start_python_felles.py
```

Startup does not install packages automatically. Rerun SOLIDE_INSTALL.cmd if
application dependencies are missing. Bootstrap errors are recorded in
%LOCALAPPDATA%\Solide\logs\bootstrap.log.

## Verification

Windows integration tests run both CMD local routes against harmless Python
stand-ins, check exit-code/argument forwarding and execute the copied FELLES
command against a stand-in. They include special-character directory names.
They do not install packages, launch Ivanti or change the system clipboard.
Actual Ivanti availability and institutional installation access still depend
on the work PC.
