"""Install Solide in-process in Python FELLES; adapted from MolStat."""
from pathlib import Path
import ensurepip
import importlib
import os
import site
import sys
import traceback

PROJECT_DIR=Path(__file__).resolve().parent


def add_path(path):
    value=str(path)
    while value in sys.path:sys.path.remove(value)
    sys.path.insert(0,value)


def activate_user_site():
    if sys.version_info < (3,11):raise RuntimeError('Solide requires Python 3.11 or later.')
    path=Path(site.getusersitepackages());path.mkdir(parents=True,exist_ok=True)
    site.addsitedir(str(path));add_path(path);return path


def record_failure(stage,error):
    logs=Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData'/'Local'))/'Solide'/'logs'
    logs.mkdir(parents=True,exist_ok=True)
    path=logs/'bootstrap.log'
    with path.open('a',encoding='utf8') as f:
        f.write(f'\n{stage}: {error}\n');traceback.print_exception(type(error),error,error.__traceback__,file=f)
    print(f'Error: {error}\nDetails: {path}')


def install(*,project_dir=PROJECT_DIR,user_site=None,pip_main=None,importer=importlib.import_module):
    project=Path(project_dir).resolve()
    if not (project/'pyproject.toml').is_file() or not (project/'src'/'solide').is_dir():
        raise RuntimeError('Cannot find the Solide project in this folder.')
    package_site=Path(user_site or site.getusersitepackages());package_site.mkdir(parents=True,exist_ok=True)
    add_path(package_site)
    if pip_main is None:
        try:import pip
        except ImportError:ensurepip.bootstrap(user=True,upgrade=True)
        from pip._internal.cli.main import main as pip_main
    result=pip_main(['install','--user','--disable-pip-version-check','-e',str(project)]) or 0
    if result:raise RuntimeError(f'Installation exited with code {result}.')
    add_path(project/'src');importlib.invalidate_caches()
    for name in ('PyQt6','openpyxl','requests','websocket','solide.gui'):importer(name)
    print('Solide installed. Close Python FELLES and run SOLIDE_START.cmd.')
    return 0


def main(*,project_dir=PROJECT_DIR):
    try:activate_user_site();return install(project_dir=project_dir)
    except Exception as exc:record_failure('install',exc);return 1


if __name__=='__main__':raise SystemExit(main())
