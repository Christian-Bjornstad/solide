"""Run the real CMD routing using harmless stand-ins, never pip or the GUI."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import pytest

ROOT=Path(__file__).parents[1]
pytestmark=pytest.mark.skipif(os.name!='nt',reason='Windows CMD / PowerShell integration')


def setup_launcher(tmp_path,mode):
    folder=tmp_path/"Lab O'Neil & test Å";folder.mkdir()
    (folder/'src'/'solide').mkdir(parents=True)
    (folder/'pyproject.toml').write_text('[project]\nname="test"')
    shutil.copyfile(ROOT/f'SOLIDE_{mode.upper()}.cmd',folder/f'SOLIDE_{mode.upper()}.cmd')
    script=folder/f'{mode}_python_felles.py'
    script.write_text("import json,os,sys\nfrom pathlib import Path\nPath(os.environ['SOLIDE_TEST_RESULT']).write_text(json.dumps(sys.argv[1:]))\nsys.exit(7)\n")
    env=dict(os.environ,SOLIDE_IVANTI=str(folder/'no-ivanti.exe'),SOLIDE_PYTHON=sys.executable,
             SOLIDE_TEST_RESULT=str(folder/'result.json'))
    return folder,script,env


@pytest.mark.parametrize('mode',['start','install'])
def test_cmd_local_path_with_spaces_and_forwarded_arguments(tmp_path,mode):
    folder,script,env=setup_launcher(tmp_path,mode)
    command=f'cmd.exe /d /s /c ""{folder / ("SOLIDE_"+mode.upper()+".cmd")}" --session "a review.solide.json""'
    result=subprocess.run(command,env=env,input='',text=True,capture_output=True,timeout=20)
    assert result.returncode==7,result.stdout+result.stderr
    assert json.loads((folder/'result.json').read_text())==['--session','a review.solide.json']


@pytest.mark.parametrize('mode',['start','install'])
def test_felles_clipboard_payload_survives_special_path_without_opening_ivanti(tmp_path,mode):
    folder,script,env=setup_launcher(tmp_path,mode)
    env.update(SOLIDE_SCRIPT=str(script),SOLIDE_TEST_CLIP=str(folder/'clipboard.txt'))
    line=next(line for line in (folder/f'SOLIDE_{mode.upper()}.cmd').read_text().splitlines() if line.startswith('powershell.exe'))
    code=line.split('-Command "',1)[1].rsplit('"',1)[0]
    override="function Set-Clipboard { [CmdletBinding()] param([string]$Value) [IO.File]::WriteAllText($env:SOLIDE_TEST_CLIP,$Value) }; "
    completed=subprocess.run(['powershell.exe','-NoProfile','-Command',override+code],env=env,capture_output=True,text=True,timeout=20)
    assert completed.returncode==0,completed.stderr
    payload=(folder/'clipboard.txt').read_text(encoding='utf-8-sig')
    compile(payload,'<clipboard>','exec')
    import base64,re
    encoded=re.search(r"b64decode\('([^']+)'\)",payload)[1]
    assert base64.b64decode(encoded).decode('utf8')==str(script)
    assert "['main']()" in payload
    script.write_text("import os\nfrom pathlib import Path\ndef main():\n    Path(os.environ['SOLIDE_TEST_RESULT']).write_text('pasted command ran')\n    return 0\n")
    pasted=subprocess.run([sys.executable,'-c',payload],env=env,capture_output=True,text=True,timeout=20)
    assert pasted.returncode==0,pasted.stderr
    assert (folder/'result.json').read_text()=='pasted command ran'
