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
    assert m.start(project_dir=ROOT,user_site=tmp_path,app_main=lambda:calls.append('started') or 0)==0
    assert calls==['started']
