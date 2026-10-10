import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PyQt6.QtGui import QPalette,QColor
from PyQt6.QtWidgets import QApplication,QDialog,QFormLayout,QScrollArea
from solide.gui import MainWindow
from solide.assessment import AssessmentDialog
from solide.models import Variant


def test_dialog_and_popup_keep_readable_palette_on_dark_windows_theme():
    app=QApplication.instance() or QApplication([])
    before=app.palette();dark=QPalette(before)
    for role in (QPalette.ColorRole.Window,QPalette.ColorRole.Base,QPalette.ColorRole.Button):
        dark.setColor(role,QColor('#252525'))
    dark.setColor(QPalette.ColorRole.Text,QColor('white'));app.setPalette(dark)
    window=MainWindow();dialog=AssessmentDialog(Variant(gene='EGFR'),window)
    try:
        for widget in (window,dialog,window.login_source.view(),dialog.classification.view()):
            palette=widget.palette()
            assert palette.color(QPalette.ColorRole.Window).lightness()>200
            assert palette.color(QPalette.ColorRole.Text).lightness()<100
        assert window.detail.font().pixelSize()>=16
    finally:
        window.dirty=False;window.close();app.setPalette(before)


def test_text_size_setting_applies_without_clipping_progress(tmp_path):
    app=QApplication.instance() or QApplication([]);window=MainWindow()
    window.config_path=tmp_path/'settings.json'
    window.text_size.setCurrentText('Large (18 px)');window.save_settings()
    window.show();app.processEvents()
    try:
        assert window.config['text_size']==18
        assert window.detail.font().pixelSize()==18
        assert window.variant_table.verticalHeader().defaultSectionSize()>=42
        window.progress.setTextVisible(True);window.progress.setFormat('%v / %m');window.progress.setRange(0,20)
        window.nav.setCurrentRow(1)
        assert window.progress.height()>=window.progress.fontMetrics().height()+10
        def luminance(colour):
            channels=[channel/255 for channel in (colour.red(),colour.green(),colour.blue())]
            linear=[value/12.92 if value<=.04045 else ((value+.055)/1.055)**2.4 for value in channels]
            return sum(value*weight for value,weight in zip(linear,(.2126,.7152,.0722)))
        foreground=luminance(window.progress.palette().color(QPalette.ColorRole.WindowText))
        for value in (0,20):
            window.progress.setValue(value);app.processEvents()
            rendered=window.progress.grab().toImage()
            background=luminance(rendered.pixelColor(12,rendered.height()//2))
            assert (max(foreground,background)+.05)/(min(foreground,background)+.05)>=4.5
    finally:
        window.dirty=False;window.close()


def test_settings_status_and_forms_remain_readable_at_large_text():
    app=QApplication.instance() or QApplication([]);window=MainWindow()
    try:
        window.config['login_checks']={'Franklin':{'state':'Last sign-in confirmed','time':'2026-10-09T15:18:14'}}
        window.login_source.setCurrentText('Franklin');window.show_account()
        assert '\n' in window.account_status.text()
        window.text_size.setCurrentIndex(window.text_size.findData(20))
        window.resize(1050,700);window.nav.setCurrentRow(3);window.show();app.processEvents()
        scroll=window.pages.currentWidget().findChild(QScrollArea)
        assert scroll.horizontalScrollBar().maximum()==0
        forms=scroll.findChildren(QFormLayout)
        assert all(form.fieldGrowthPolicy()==QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow for form in forms)
        assert window.account_status.height()>=2*window.account_status.fontMetrics().height()
    finally:
        window.dirty=False;window.close()
