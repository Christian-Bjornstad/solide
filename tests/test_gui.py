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


def test_english_navigation_and_identity_review_tab():
    from PyQt6.QtWidgets import QTabWidget
    app=QApplication.instance() or QApplication([])
    window=MainWindow()
    assert [window.nav.item(i).text() for i in range(window.nav.count())]==[
        'Import','Quality','Variants','Sources','Reports','Settings']
    window.session=Session(variants=[Variant(patient='DEMO',gene='EGFR',coverage=499,source_row=8)])
    window.refresh();window.nav.setCurrentRow(2);window.show();app.processEvents()
    window.variant_table.selectRow(0);app.processEvents()
    assert 'Source:' in window.detail.toPlainText()
    assert window.qc_model.item(0,3).text()=='Failed'
    assert 'on row 8' in window.qc_model.item(0,4).text()
    tabs=window.findChild(QTabWidget)
    assert tabs.tabText(2)=='Identity review'
    tabs.setCurrentIndex(2);app.processEvents()
    assert window.hgvs_edit.isVisible()
    window.close()
