import importlib.util
from pathlib import Path
ROOT=Path(__file__).parents[1]

def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/f'{name}.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def test_install_inprocess(tmp_path):
    m=module('install_python_felles');calls=[]
    assert m.install(project_dir=ROOT,user_site=tmp_path,pip_main=lambda args:calls.append(args) or 0,
                     importer=lambda name:None)==0
    assert '--user' in calls[0] and '-e' in calls[0]

def test_start_inprocess(tmp_path):
    m=module('start_python_felles');calls=[]
    assert m.start(project_dir=ROOT,user_site=tmp_path,app_main=lambda args:calls.append(args) or 0)==0
    assert calls==[[]]


def test_start_passes_explicit_args_without_using_shared_interpreter_flags(tmp_path,monkeypatch):
    import sys
    m=module('start_python_felles');calls=[]
    monkeypatch.setattr(sys,'argv',['python.exe','--shared-interpreter-flag'])
    m.start(project_dir=ROOT,user_site=tmp_path,app_main=lambda args:calls.append(args))
    args=['--session',str(tmp_path/'review with spaces.solide.json')]
    m.start(project_dir=ROOT,user_site=tmp_path,app_main=lambda args:calls.append(args),argv=args)
    assert calls==[[],args]


def test_install_failure_and_start_failure_are_reported(tmp_path):
    import pytest
    installer=module('install_python_felles');starter=module('start_python_felles')
    with pytest.raises(RuntimeError,match='code 7'):
        installer.install(project_dir=ROOT,user_site=tmp_path,pip_main=lambda args:7)
    with pytest.raises(RuntimeError,match='code 8'):
        starter.start(project_dir=ROOT,user_site=tmp_path,app_main=lambda args:8)
