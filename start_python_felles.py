"""Start Solide in the shared Python interpreter without launching python.exe."""
from pathlib import Path
import importlib
import site
import runpy
import sys

PROJECT_DIR=Path(__file__).resolve().parent
_helpers=runpy.run_path(str(PROJECT_DIR/'install_python_felles.py'),run_name='solide_bootstrap')
add_path=_helpers['add_path']
activate_user_site=_helpers['activate_user_site']
record_failure=_helpers['record_failure']


def start(*,project_dir=PROJECT_DIR,user_site=None,app_main=None,argv=None):
    project=Path(project_dir).resolve()
    if not (project/'src'/'solide').is_dir():raise RuntimeError('Cannot find src\\solide.')
    package_site=Path(user_site or site.getusersitepackages())
    site.addsitedir(str(package_site));add_path(package_site);add_path(project/'src')
    importlib.invalidate_caches()
    if app_main is None:
        from solide.__main__ import main as app_main
    # A pasted FELLES command must not inherit the host launcher's sys.argv.
    # Direct CLI starts explicitly forward their own arguments below.
    result=app_main(list(argv or [])) or 0
    if result:raise RuntimeError(f'Solide exited with code {result}.')
    return 0


def main(*,project_dir=PROJECT_DIR,argv=None):
    try:activate_user_site();return start(project_dir=project_dir,argv=argv)
    except Exception as exc:
        record_failure('start',exc)
        print('Run SOLIDE_INSTALL.cmd to install or repair the application dependencies.')
        return 1


if __name__=='__main__':raise SystemExit(main(argv=sys.argv[1:]))
