import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PyQt6.QtWidgets import QApplication
from solide.gui import MainWindow
from solide.models import Variant, Session

def test_variant_selection_filter_and_session(tmp_path):
    app=QApplication.instance() or QApplication([])
    window=MainWindow()
    window.session=Session(variants=[Variant(patient='DEMO',gene='EGFR',selected=True,coverage=400),
                                     Variant(patient='DEMO',gene='MET',selected=False,coverage=500)])
    window.refresh()
    assert window.variant_model.rowCount()==2
    assert window.qc_model.rowCount()==1
    window.search.setText('MET')
    assert window.proxy.rowCount()==1
    window.select_visible(True)
    assert all(v.selected for v in window.session.variants)
    window.save_to(tmp_path/'demo.solide.json')
    assert (tmp_path/'demo.solide.json').exists()
    window.close()
