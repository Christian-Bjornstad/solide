"""Malformed saved settings must never prevent starting the app."""
import os,json
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from unittest.mock import patch
import pytest
from PyQt6.QtWidgets import QApplication
from solide.gui import MainWindow

@pytest.mark.parametrize('payload',[
    [],None,42,{'sources':None},{'background':'false'},{'accounts':[]},
    {'accounts':{'Franklin':False}},{'login_checks':[]},
    {'login_checks':{'Franklin':[]}},
    {'login_checks':{'Franklin':{'state':42,'time':[]}}},{'text_size':float('inf')},
])
def test_startup_recovers_from_wrong_setting_types(tmp_path,payload):
    settings=tmp_path/'.solide'/'ui_config.json';settings.parent.mkdir()
    settings.write_text(json.dumps(payload),encoding='utf8')
    original=settings.read_bytes()
    app=QApplication.instance() or QApplication([])
    with patch('solide.gui.Path.home',return_value=tmp_path),patch('solide.gui.read_password',return_value=''):
        view=MainWindow()
        try:
            assert view.nav.count()==4
            assert view.account_username.text()==''
            assert settings.read_bytes()==original,'Startup rewrote a damaged settings file'
        finally:view.close()
