from __future__ import annotations
import copy
from datetime import datetime
import json
from pathlib import Path
import re
import time
import uuid
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl, QSize, QByteArray, QTimer
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QDesktopServices, QFontDatabase, QIcon, QPixmap, QPainter
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QListWidget, QStackedWidget, QFileDialog, QMessageBox, QLineEdit,
    QComboBox, QTableView, QHeaderView, QTextEdit, QCheckBox, QFormLayout, QSplitter,
    QDialog, QDialogButtonBox, QGroupBox, QAbstractItemView, QProgressBar,QTabWidget,QPlainTextEdit,QListWidgetItem,QScrollArea,QLayout,QFrame)
from .models import Session, Variant
from .importing import load_file
from .quality import qc_flags, review_reasons
from .session import save_session, load_session, atomic_write
from .table_model import VariantTableModel, VariantProxy
from .reporting import export_patient, STATUS
from .evidence import SOURCES, QueueControl, run_queue, evidence_is_current
from .evidence import build_search_plan, assess_evidence
from .accounts import ACCOUNT_PROVIDERS, browser_credentials, read_password, write_password, remove_password
from .activity import ActivityLog
from ._vendor.archer.services.browser_review import BrowserReviewService, BrowserReviewCancelled

STYLE='''
QWidget { font-family: "Segoe UI"; font-size: 14px; color: #243128; }
QMainWindow, QStackedWidget { background: #F5F7F4; }
QWidget#rail { background: white; border-right: 1px solid #E1E7DE; }
QLabel#brand { color: #425B3D; font-size: 25px; font-weight: 700; letter-spacing: 2px; }
QLabel#railNote { color: #596454; font-size: 12px; }
QLabel#title { font-size: 28px; font-weight: 600; }
QLabel#subtitle { color: #53634D; background: #EAF0E6; padding: 9px 14px; border-radius: 8px; }
QLabel#status { color: #596454; font-size: 12px; padding-top: 8px; }
QListWidget#nav { background: transparent; border: 0; outline: 0; }
QListWidget#nav::item { padding: 13px 10px; margin: 4px 0; border-radius: 8px; }
QListWidget#nav::item:selected { background: #425B3D; color: white; font-weight: 600; }
QListWidget#nav::item:hover:!selected { background: #EDF3E8; }
QPushButton { background: white; border: 1px solid #CBD5C5; border-radius: 8px; padding: 10px 16px; min-height: 22px; }
QPushButton:hover { background: #EAF0E6; border-color: #425B3D; }
QPushButton:focus, QLineEdit:focus, QComboBox:focus, QTableView:focus { border: 2px solid #425B3D; }
QPushButton#primary { background: #425B3D; color: white; border-color: #425B3D; font-weight: 600; }
QPushButton#primary:hover { background: #34492F; }
QPushButton:disabled { background: #E8ECE5; color: #667260; border-color: #D6DED2; }
QLineEdit, QComboBox { background: white; border: 1px solid #CBD5C5; padding: 10px; border-radius: 8px; min-height: 20px; }
QTextEdit, QPlainTextEdit, QTableView { background: white; border: 1px solid #DEE5DA; border-radius: 8px; selection-background-color: #DCE8D5; selection-color: #1F2A22; }
QTextEdit, QPlainTextEdit { padding: 10px; }
QTableView { alternate-background-color: #FAFBF9; gridline-color: #EEF1EB; }
QHeaderView::section { background: #EDF2E9; padding: 10px; border: 0; border-bottom: 1px solid #DEE5DA; font-weight: 600; }
QGroupBox { background: white; border: 1px solid #DEE5DA; border-radius: 10px; margin-top: 12px; padding: 20px; }
QGroupBox::title { subcontrol-origin: margin; left: 18px; padding: 0 6px; font-weight: 600; }
QTabWidget::pane { background: white; border: 1px solid #DEE5DA; border-radius: 8px; }
QTabBar::tab { background: transparent; color: #596454; padding: 10px 18px; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: #425B3D; border-bottom: 2px solid #425B3D; font-weight: 600; }
QTabBar::tab:hover { background: #EAF0E6; }
QSplitter::handle { background: #E1E7DE; }
QToolTip { background: #243128; color: white; border: 0; padding: 8px; }
QCheckBox { spacing: 8px; padding: 5px; }
QCheckBox::indicator { width: 17px; height: 17px; }
QProgressBar { border: 1px solid #D6DED2; background: white; height: 8px; border-radius: 4px; }
QProgressBar::chunk { background: #425B3D; }
'''


def navigation_icon(path):
    icon=QIcon()
    for mode,color in ((QIcon.Mode.Normal,'#53634D'),(QIcon.Mode.Selected,'#FFFFFF')):
        svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><g fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{path}</g></svg>'
        pixmap=QPixmap(24,24);pixmap.fill(Qt.GlobalColor.transparent)
        painter=QPainter(pixmap);QSvgRenderer(QByteArray(svg.encode())).render(painter);painter.end()
        icon.addPixmap(pixmap,mode)
    return icon


class Worker(QThread):
    result=pyqtSignal(object)
    error=pyqtSignal(str)
    def __init__(self,fn):
        super().__init__();self.fn=fn
    def run(self):
        try:self.result.emit(self.fn())
        except Exception as exc:self.error.emit(str(exc))


class EvidenceWorker(QThread):
    evidence=pyqtSignal(str,str,object)
    progress=pyqtSignal(str)
    error=pyqtSignal(str)
    outcome=pyqtSignal(str)
    def __init__(self,session,sources,root,control,background,plan=None,credentials=None):
        super().__init__();self.session=copy.deepcopy(session);self.sources=sources
        self.root=root;self.control=control;self.background=background
        self.plan=plan;self.credentials=credentials or {}
    def run(self):
        try:
            run_queue(self.session,self.sources,self.root,self.control,self.evidence.emit,
                      self.progress.emit,self.background,plan=self.plan,credentials=self.credentials)
            self.outcome.emit('Search complete. Review source status before reporting.')
        except BrowserReviewCancelled:self.outcome.emit('Stopped. Completed results retained.')
        except Exception as exc:self.error.emit(str(exc))


def table(model):
    widget=QTableView();widget.setModel(model);widget.setSortingEnabled(True)
    widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    widget.setAlternatingRowColors(True);widget.setShowGrid(False);widget.verticalHeader().setDefaultSectionSize(36)
    widget.verticalHeader().hide();widget.horizontalHeader().setStretchLastSection(True)
    return widget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Offscreen Qt on Windows has an empty font database; register system fonts
        # so test renders use the same readable typeface as the desktop app.
        if 'Segoe UI' not in QFontDatabase.families():
            for font in ('segoeui.ttf','segoeuib.ttf'):
                path=Path('C:/Windows/Fonts')/font
                if path.is_file():QFontDatabase.addApplicationFont(str(path))
        self.session=Session();self.session_path=None;self.dirty=False
        self.active=None;self.workers=[];self.control=None;self.current_variant=None
        self.run_plan=set();self.run_done=set();self.run_id=None;self.run_started=0;self.run_state='Idle'
        self.run_history_saved=set()
        try:self.activity=ActivityLog()
        except OSError:self.activity=None
        self.config_path=Path.home()/'.solide'/'ui_config.json'
        try:self.config=json.loads(self.config_path.read_text(encoding='utf8'))
        except (OSError,ValueError):self.config={}
        self.setWindowTitle('Solide | Variant review');self.resize(1440,940)
        self.setMinimumSize(1050,700);self.setStyleSheet(STYLE)
        central=QWidget();self.setCentralWidget(central)
        horizontal=QHBoxLayout(central);horizontal.setContentsMargins(0,0,0,0);horizontal.setSpacing(0)
        rail=QWidget();rail.setObjectName('rail');rail.setFixedWidth(190)
        rail_layout=QVBoxLayout(rail);rail_layout.setContentsMargins(16,30,16,24);rail_layout.setSpacing(12)
        brand=QLabel('SOLIDE');brand.setObjectName('brand');rail_layout.addWidget(brand)
        self.nav=QListWidget();self.nav.setObjectName('nav')
        icons=[
            '<path d="M12 3v12m-4-4 4 4 4-4M4 15v5h16v-5"/>',
            '<path d="M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6zM8 12l3 3 5-6"/>',
            '<path d="M8 3c12 4-4 14 8 18M16 3C4 7 20 17 8 21M8 6h8M8 12h8M8 18h8"/>',
            '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0"/>',
            '<path d="M6 3h9l4 4v14H6zM14 3v5h5M9 12h7M9 16h7"/>',
            '<circle cx="12" cy="12" r="4"/><path d="M12 2v3m0 14v3M2 12h3m14 0h3M5 5l2 2m10 10 2 2M5 19l2-2M17 7l2-2"/>']
        self.nav.setIconSize(QSize(20,20))
        for label,path in zip(['Workspace','Searches','Reports','Settings'],[icons[i] for i in (2,3,4,5)]):
            self.nav.addItem(QListWidgetItem(navigation_icon(path),label))
        rail_layout.addWidget(self.nav,1)
        footer=QLabel('LOCAL WORKSPACE\nGRCh37 / hg19');footer.setObjectName('railNote');rail_layout.addWidget(footer)
        horizontal.addWidget(rail)
        body=QWidget();vertical=QVBoxLayout(body);vertical.setContentsMargins(28,25,28,18)
        header=QHBoxLayout()
        self.title=QLabel('Import');self.title.setObjectName('title');header.addWidget(self.title);header.addStretch()
        self.summary=QLabel('No files imported');self.summary.setObjectName('subtitle');header.addWidget(self.summary)
        vertical.addLayout(header)
        self.pages=QStackedWidget();vertical.addWidget(self.pages,1)
        self.banner=QLabel('Ready');self.banner.setObjectName('status');self.banner.setWordWrap(True)
        vertical.addWidget(self.banner);horizontal.addWidget(body,1)
        self.build_import();self.build_quality();self.build_variants();self.build_evidence();self.build_report();self.build_settings()
        self.consolidate_workspace()
        status_row=QHBoxLayout()
        self.live_status=QLabel('Idle');self.live_status.setWordWrap(True);status_row.addWidget(self.live_status,1)
        self.log_toggle=self.button('Log',lambda:None);self.log_toggle.setCheckable(True);status_row.addWidget(self.log_toggle)
        vertical.insertLayout(vertical.count()-1,status_row)
        self.queue_log=QPlainTextEdit();self.queue_log.setReadOnly(True);self.queue_log.setMaximumBlockCount(2000)
        if self.activity:self.queue_log.setPlainText(self.activity.tail())
        self.queue_log.setMaximumHeight(145);self.queue_log.setPlaceholderText('Activity log')
        vertical.insertWidget(vertical.count()-1,self.queue_log);self.queue_log.hide()
        self.log_toggle.toggled.connect(self.queue_log.setVisible)
        self.run_timer=QTimer(self);self.run_timer.setInterval(1000);self.run_timer.timeout.connect(self.update_run_status)
        self.nav.currentRowChanged.connect(self.navigate);self.nav.setCurrentRow(0)
        self.refresh()
        self.record_activity('Application started')

    def consolidate_workspace(self):
        original=[self.pages.widget(i) for i in range(self.pages.count())]
        for page in original:self.pages.removeWidget(page)
        workspace=QWidget();layout=QVBoxLayout(workspace);layout.setContentsMargins(0,18,0,0)
        row=QHBoxLayout()
        for button in (self.import_btn,self.open_btn,self.save_btn):row.addWidget(button)
        row.addStretch();self.workspace_view=QComboBox();self.workspace_view.addItems(['Variants','Quality'])
        self.workspace_view.setAccessibleName('Workspace view');row.addWidget(self.workspace_view);layout.addLayout(row)
        self.workspace_pages=QStackedWidget();self.workspace_pages.addWidget(original[2]);self.workspace_pages.addWidget(original[1])
        self.workspace_view.currentIndexChanged.connect(self.workspace_pages.setCurrentIndex)
        layout.addWidget(self.workspace_pages,1);self.pages.addWidget(workspace)
        for page in original[3:]:self.pages.addWidget(page)
        # Import history is recorded in the common log; retain the widget for the
        # existing import summary handler, without another navigation destination.
        self.import_log.setParent(workspace);self.import_log.hide();original[0].deleteLater()

    def page(self):
        w=QWidget();layout=QVBoxLayout(w);layout.setContentsMargins(0,18,0,0)
        layout.setSpacing(14);self.pages.addWidget(w);return layout

    def button(self,label,fn,primary=False):
        b=QPushButton(label);b.clicked.connect(fn)
        if primary:b.setObjectName('primary')
        return b

    def build_import(self):
        layout=self.page()
        box=QGroupBox('Import files');content=QVBoxLayout(box)
        info=QLabel('Ion Reporter or Genexus · TSV / XLSX');info.setWordWrap(True)
        content.addWidget(info)
        row=QHBoxLayout()
        self.import_btn=self.button('Import files…',self.import_files,True);row.addWidget(self.import_btn)
        self.open_btn=self.button('Open session…',self.open_session);row.addWidget(self.open_btn)
        self.save_btn=self.button('Save session…',self.save_dialog);row.addWidget(self.save_btn);row.addStretch()
        content.addLayout(row);layout.addWidget(box)
        self.import_log=QPlainTextEdit();self.import_log.setReadOnly(True)
        self.import_log.setPlaceholderText('Import history');layout.addWidget(self.import_log,1)
        self.import_btn.setToolTip('Confirm patient / sample ID and assembly for each file. Variant-only exports may omit CNV and RNA quality data.')

    def build_quality(self):
        layout=self.page()
        self.qc_summary=QLabel();layout.addWidget(self.qc_summary)
        self.qc_summary.setToolTip('All rows are checked: coverage <500, CNV <1, RNAExonTiles NO CALL and RNAExonVariant ABSENT. CNV =1 requires review.')
        self.qc_model=QStandardItemModel(0,7)
        self.qc_model.setHorizontalHeaderLabels(['Patient','Gene','Category','Status','Reason','Type','Source row'])
        self.qc_table=table(self.qc_model);self.qc_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.qc_table,1)

    def build_variants(self):
        layout=self.page();row=QHBoxLayout()
        self.search=QLineEdit();self.search.setPlaceholderText('Search gene, HGVS or sample…')
        self.search.setAccessibleName('Search variants');row.addWidget(self.search,1)
        self.patient_filter=QComboBox();self.patient_filter.setAccessibleName('Filter patient');row.addWidget(self.patient_filter)
        row.addWidget(self.button('Select visible',lambda:self.select_visible(True)))
        row.addWidget(self.button('Clear visible',lambda:self.select_visible(False)))
        layout.addLayout(row)
        self.variant_model=VariantTableModel();self.variant_model.changed.connect(self.mark_dirty)
        self.proxy=VariantProxy();self.proxy.setSourceModel(self.variant_model)
        self.search.textChanged.connect(self.apply_filter);self.patient_filter.currentTextChanged.connect(self.apply_filter)
        self.variant_table=table(self.proxy)
        self.variant_table.selectionModel().currentRowChanged.connect(self.show_variant)
        split=QSplitter(Qt.Orientation.Vertical);split.addWidget(self.variant_table)
        detail=QWidget();d=QHBoxLayout(detail);d.setContentsMargins(0,0,0,0)
        self.detail=QTextEdit();self.detail.setReadOnly(True);self.detail.setPlaceholderText('Select a variant')
        self.raw_detail=QTextEdit();self.raw_detail.setReadOnly(True)
        tabs=QTabWidget();tabs.addTab(self.detail,'Details')
        source_button=self.button('Source data',self.show_raw_source)
        tabs.setCornerWidget(source_button,Qt.Corner.TopRightCorner)
        self.detail.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)
        d.addWidget(tabs,1)
        form_box=QWidget();form=QFormLayout(form_box);form.setContentsMargins(18,12,18,12)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.gene_edit=QLineEdit();self.transcript_edit=QLineEdit();self.hgvs_edit=QLineEdit()
        self.genomic_edit=QLineEdit();self.genomic_edit.setPlaceholderText('chr7-123456-A-T')
        self.hgvs_edit.setPlaceholderText('NM_…:c.… or NC_…(NM_…):c.…')
        identity=QWidget();identity_row=QHBoxLayout(identity);identity_row.setContentsMargins(0,0,0,0)
        identity_row.addWidget(QLabel('Gene'));identity_row.addWidget(self.gene_edit,1)
        identity_row.addWidget(QLabel('Transcript'));identity_row.addWidget(self.transcript_edit,2)
        form.addRow(identity)
        form.addRow('Reviewed HGVS',self.hgvs_edit)
        form.addRow('Reviewed hg19 REF/ALT',self.genomic_edit)
        self.verified_check=QCheckBox('HGVS / mapping reviewed')
        form.addRow(self.verified_check)
        form.addRow(self.button('Save review',self.save_identity))
        self.verified_check.setToolTip('Review Mutalyzer suggestions and MANE mapping before approval. Original exported fields remain in Source data.')
        tabs.addTab(form_box,'Identity review');split.addWidget(detail);split.setSizes([460,290]);split.setHandleWidth(3);layout.addWidget(split,1)
        self.selection_summary=QLabel();layout.addWidget(self.selection_summary)

    def build_evidence(self):
        layout=self.page();top=QHBoxLayout()
        self.tissue_patient=QComboBox();self.tissue_patient.currentTextChanged.connect(self.show_tissue)
        self.tissue=QComboBox();self.tissue.setEditable(True);self.tissue.addItems(['Other','Lung','Breast','Colorectal'])
        top.addWidget(QLabel('Patient'));top.addWidget(self.tissue_patient)
        top.addWidget(QLabel('MTBP tissue'));top.addWidget(self.tissue,1)
        top.addWidget(self.button('Save tissue',self.save_tissue));layout.addLayout(top)
        self.source_checks={};sources=QHBoxLayout()
        for source in SOURCES:
            check=QCheckBox(source);check.setChecked(source in self.config.get('sources',['ClinVar','MTBP','Franklin','Mutalyzer','SpliceAI']))
            sources.addWidget(check);self.source_checks[source]=check
        layout.addLayout(sources)
        row=QHBoxLayout();self.run_btn=self.button('Run searches',self.start_queue,True);row.addWidget(self.run_btn)
        self.run_btn.setText('Run pending')
        self.run_btn.setToolTip('Run new, incomplete or outdated searches. Completed matches and no-match results are preserved.')
        self.pause_btn=self.button('Pause',self.pause_queue);self.pause_btn.setEnabled(False);row.addWidget(self.pause_btn)
        self.stop_btn=self.button('Stop',self.stop_queue);self.stop_btn.setEnabled(False);row.addWidget(self.stop_btn)
        self.retry_btn=self.button('Retry failed',lambda:self.start_queue('failed'));row.addWidget(self.retry_btn)
        self.rerun_btn=self.button('Rerun selected',self.rerun_selected);row.addWidget(self.rerun_btn)
        self.rerun_all_btn=self.button('Rerun all',lambda:self.start_queue('all'));row.addWidget(self.rerun_all_btn);row.addStretch()
        self.retry_btn.setToolTip('Retry failed searches only. MTBP regenerates the complete selected patient batch.')
        self.rerun_btn.setToolTip('Rerun highlighted result rows, including completed searches. MTBP regenerates the complete selected patient batch.')
        layout.addLayout(row)
        self.progress=QProgressBar();self.progress.setRange(0,1);self.progress.setValue(0);self.progress.setTextVisible(False);layout.addWidget(self.progress)
        self.result_counts=QLabel();layout.addWidget(self.result_counts)
        self.result_filter=QComboBox();self.result_filter.addItems(['All results','Needs attention','Matches','Pending'])
        self.result_filter.currentIndexChanged.connect(self.refresh_evidence)
        filter_row=QHBoxLayout();filter_row.addWidget(self.result_filter);filter_row.addStretch()
        filter_row.addWidget(self.button('Open source',self.open_selected_source))
        filter_row.addWidget(self.button('View evidence',self.inspect_evidence));layout.addLayout(filter_row)
        self.evidence_model=QStandardItemModel(0,6);self.evidence_model.setHorizontalHeaderLabels(['Patient','Variant','Source','Result','Captured','Summary'])
        self.evidence_table=table(self.evidence_model);self.evidence_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.evidence_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.evidence_table.doubleClicked.connect(lambda index:self.inspect_evidence());layout.addWidget(self.evidence_table,2)
        for check in self.source_checks.values():check.toggled.connect(self.refresh_evidence)

    def build_report(self):
        layout=self.page();box=QGroupBox('Export reports');form=QVBoxLayout(box)
        row=QHBoxLayout();self.report_patient=QComboBox();row.addWidget(self.report_patient,1)
        self.report_btn=self.button('Export Excel',self.export,True);row.addWidget(self.report_btn)
        self.report_btn.setToolTip('One workbook per patient: selected variants, all-row QC, source evidence, screenshots and raw data. Comments are saved in the session.')
        form.addLayout(row);layout.addWidget(box)
        self.report_log=QPlainTextEdit();self.report_log.setReadOnly(True);layout.addWidget(self.report_log,1)
        self.report_log.setPlaceholderText('Exported files')

    def build_settings(self):
        outer=self.page();scroll=QScrollArea();scroll.setFrameShape(QFrame.Shape.NoFrame);scroll.setWidgetResizable(True)
        content=QWidget();layout=QVBoxLayout(content);layout.setContentsMargins(0,0,0,0);layout.setSpacing(14)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        scroll.setWidget(content);outer.addWidget(scroll)
        box=QGroupBox('Workspace');form=QFormLayout(box);form.setVerticalSpacing(10)
        folder=QWidget();row=QHBoxLayout(folder);row.setContentsMargins(0,0,0,0)
        self.output_dir=QLineEdit(self.config.get('output_dir',''));row.addWidget(self.output_dir,1)
        row.addWidget(self.button('Browse…',self.choose_directory));form.addRow('Workspace folder',folder)
        self.background=QCheckBox('Minimise automated Edge windows');self.background.setChecked(self.config.get('background',True));form.addRow(self.background)
        form.addRow(self.button('Save settings',self.save_settings))
        layout.addWidget(box)
        self.output_dir.setToolTip('Use an approved local folder for reports and evidence.')
        self.background.setToolTip('Edge remote debugging must be available. Sign in directly through Edge; Solide does not store passwords.')
        self.tissue.setToolTip('Choose an exact portal option. Default: Other.')
        account_box=QGroupBox('Database accounts');account_form=QFormLayout(account_box);account_form.setVerticalSpacing(10)
        self.login_source=QComboBox();self.login_source.addItems(ACCOUNT_PROVIDERS)
        self.account_username=QLineEdit();self.account_password=QLineEdit()
        self.account_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.account_password.setPlaceholderText('Enter a new password to save')
        account_form.addRow('Provider',self.login_source);account_form.addRow('Username / email',self.account_username)
        account_form.addRow('Password',self.account_password)
        self.account_status=QLabel();self.account_status.setWordWrap(True);account_form.addRow(self.account_status)
        actions=QWidget();actions_row=QHBoxLayout(actions);actions_row.setContentsMargins(0,0,0,0)
        self.account_save_btn=self.button('Save account',self.save_account);actions_row.addWidget(self.account_save_btn)
        self.account_clear_btn=self.button('Forget password',self.forget_password);actions_row.addWidget(self.account_clear_btn)
        self.login_btn=self.button('Sign in / check',self.login,True);actions_row.addWidget(self.login_btn)
        account_form.addRow(actions);layout.addWidget(account_box)
        self.login_source.currentTextChanged.connect(self.show_account);self.show_account()
        self.account_password.setToolTip('Saved only in Windows Credential Manager. Passwords are never stored in sessions or JSON settings.')
        self.background.setToolTip('Automated Edge uses a separate local profile. Saved passwords use Windows Credential Manager.')
        layout.addWidget(QLabel('ClinVar, Mutalyzer and SpliceAI use public access.'))
        layout.addWidget(self.button('Open log folder',self.open_log_folder),0,Qt.AlignmentFlag.AlignLeft)
        layout.addStretch()

    def navigate(self,index):
        self.pages.setCurrentIndex(index);self.title.setText(self.nav.item(index).text())

    def notify_error(self,message):
        self.record_activity('Error: '+message)
        if isinstance(self.active,EvidenceWorker):self.run_state='Failed';self.update_run_status()
        self.banner.setText(message);QMessageBox.warning(self,'Solide',message)

    def busy(self,value):
        for widget in (self.import_btn,self.open_btn,self.run_btn,self.login_btn,self.report_btn,
                       self.variant_table,self.gene_edit,self.transcript_edit,self.hgvs_edit,self.genomic_edit,
                       self.verified_check,self.output_dir,self.background,self.tissue,
                       self.retry_btn,self.rerun_btn,self.rerun_all_btn,self.account_save_btn,self.account_clear_btn,
                       self.account_username,self.account_password,self.login_source):
            widget.setEnabled(not value)
        self.save_btn.setEnabled(not value)

    def launch(self,worker):
        self.active=worker;self.workers.append(worker);self.busy(True)
        worker.error.connect(self.notify_error)
        worker.finished.connect(lambda:self.finished(worker))
        worker.start()

    def finished(self,worker):
        if isinstance(worker,EvidenceWorker):
            self.run_timer.stop();self.update_run_status()
            self.session.history.append({'event':'run_end','run_id':self.run_id,'state':self.run_state,
                'completed':len(self.run_done),'total':len(self.run_plan),'time':datetime.now().astimezone().isoformat()})
            self.dirty=True;self.auto_save()
        else:
            self.live_status.setText('Idle')
        if self.active is worker:self.active=None;self.busy(False)
        self.workers.remove(worker);worker.deleteLater()
        self.pause_btn.setEnabled(False);self.stop_btn.setEnabled(False)
        self.refresh_evidence()
        if self.dirty and self.session_path:
            self.banner.setText('Unsaved changes')

    def import_files(self):
        paths,_=QFileDialog.getOpenFileNames(self,'Import files','','Variant files (*.tsv *.xlsx)')
        if not paths:return
        def read():
            results=[]
            for path in paths:
                try:results.append((path,load_file(Path(path)),''))
                except Exception as exc:results.append((path,None,str(exc)))
            return results
        worker=Worker(read);worker.result.connect(self.accept_import);self.launch(worker)
        self.banner.setText('Reading files…')

    def accept_import(self,results):
        for path,result,error in results:
            if error:self.import_log.appendPlainText(f'Import failed: {error}');continue
            dialog=QDialog(self);dialog.setWindowTitle('Confirm sample');dialog.resize(620,330)
            form=QFormLayout(dialog);info=QLabel(f'{Path(path).name}\n{len(result.variants)} rows. Confirm the sample below.');info.setWordWrap(True);form.addRow(info)
            patient=QLineEdit(result.sample_hint);form.addRow('Patient / sample ID',patient)
            assembly=QComboBox();assembly.addItems(['GRCh37','GRCh38','Unknown'])
            assembly.setCurrentText(result.assembly if result.assembly!='Unknown' else 'GRCh37');form.addRow('Assembly',assembly)
            warnings=QLabel('\n'.join(result.warnings));warnings.setWordWrap(True);form.addRow(warnings)
            buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
            buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);form.addRow(buttons)
            if dialog.exec()!=QDialog.DialogCode.Accepted:continue
            if not patient.text().strip():self.notify_error('Enter a patient / sample ID.');continue
            existing={v.id for v in self.session.variants}
            added=0
            for v in result.variants:
                if v.id in existing:continue
                v.patient=patient.text().strip();v.assembly=assembly.currentText()
                self.session.variants.append(v);added+=1
            self.session.history.append({'event':'import','time':datetime.now().astimezone().isoformat(),
                                         'file':path,'rows':added,'patient':patient.text().strip()})
            self.import_log.appendPlainText(f'{added} rows imported; {len(result.variants)-added} duplicates skipped.\n'+'\n'.join(result.warnings))
            self.record_activity(f'Imported {added} rows; {len(result.variants)-added} duplicates skipped')
            for warning in result.warnings:self.record_activity(warning)
        self.mark_dirty();self.refresh();self.banner.setText('Imported. Review Quality and Variants.')

    def refresh(self):
        self.variant_model.set_variants(self.session.variants)
        self.qc_model.removeRows(0,self.qc_model.rowCount())
        failed=set();count=0
        for v in self.session.variants:
            for flag in qc_flags(v):
                items=[QStandardItem(str(x)) for x in [v.patient,v.gene,flag.category,flag.status,flag.message,v.kind,v.source_row]]
                self.qc_model.appendRow(items);count+=1
                if flag.category=='Coverage' and flag.status=='Failed':failed.add((v.patient,v.gene))
        self.qc_summary.setText(f'{count} quality flags · {len(failed)} patient / gene groups with coverage <500')
        for combo,first in [(self.patient_filter,'All patients'),(self.tissue_patient,None),(self.report_patient,'All patients')]:
            prior=combo.currentText();combo.blockSignals(True);combo.clear()
            if first:combo.addItem(first)
            combo.addItems(self.session.patients)
            if combo.findText(prior)>=0:combo.setCurrentText(prior)
            combo.blockSignals(False)
        self.show_tissue();self.apply_filter();self.refresh_counts();self.refresh_evidence()
        self.variant_table.setColumnWidth(0,88);self.variant_table.setColumnWidth(1,145);self.variant_table.setColumnWidth(2,95)
        self.variant_table.setColumnWidth(3,150);self.variant_table.setColumnWidth(4,200)
        self.qc_table.setColumnWidth(4,430)

    def refresh_counts(self):
        total=len(self.session.variants);selected=sum(v.selected for v in self.session.variants)
        self.summary.setText(f'{len(self.session.patients)} samples · {total:,} rows · {selected} selected')
        self.selection_summary.setText(f'{selected} selected · {self.proxy.rowCount()} visible rows')

    def apply_filter(self,*args):
        self.proxy.set_filters(self.patient_filter.currentText(),self.search.text().strip())
        self.refresh_counts()

    def searchable(self,v):
        return ' '.join(str(x) for x in (v.patient,v.gene,v.transcript,v.coding,v.protein,v.kind,v.call,v.locus)).casefold()

    def select_visible(self,value):
        if self.active:return
        for row in range(self.proxy.rowCount()):
            index=self.proxy.mapToSource(self.proxy.index(row,0))
            self.session.variants[index.row()].selected=value
        if self.session.variants:
            self.variant_model.dataChanged.emit(self.variant_model.index(0,0),self.variant_model.index(len(self.session.variants)-1,0))
        self.mark_dirty()

    def mark_dirty(self):
        self.dirty=True;self.refresh_counts();self.refresh_evidence()

    def show_variant(self,index,*args):
        if not index.isValid():
            self.current_variant=None;self.detail.clear();self.raw_detail.clear()
            for edit in (self.gene_edit,self.transcript_edit,self.hgvs_edit,self.genomic_edit):edit.clear()
            self.verified_check.setChecked(False);return
        source=self.proxy.mapToSource(index);v=self.session.variants[source.row()];self.current_variant=v
        self.gene_edit.setText(v.gene);self.transcript_edit.setText(v.transcript)
        self.hgvs_edit.setText(v.corrected_hgvs);self.verified_check.setChecked(v.nomenclature_verified)
        self.genomic_edit.setText(v.controlled_genomic)
        lines=[f'{v.gene}  {v.protein}',f'DNA: {v.coding}',f'Transcript: {v.transcript or "Missing"}',
               f'Assembly: {v.assembly}   Locus: {v.locus or "Missing"}',
               f'Allele frequency: {v.af_percent if v.af_percent is not None else "Missing"} %   Coverage: {v.coverage if v.coverage is not None else "Missing"}',
               f'Source: {Path(v.source_file).name} · row {v.source_row}',
               '\nReview needed: '+(', '.join(review_reasons(v)) or 'No additional identity checks'),
               *[f'{f.category}: {f.status} – {f.message}' for f in qc_flags(v)],
               '\nComment: '+v.comment]
        for source,e in v.evidence.items():
            state=STATUS.get(e.get('status'),e.get('status','Unknown')) if evidence_is_current(v,e,self.session.tissue(v.patient),self.session) else 'Outdated'
            lines.append(f'\n{source}: {state}\n{e.get("summary", "")}')
        self.detail.setPlainText('\n'.join(lines))
        self.raw_detail.setPlainText(json.dumps({'source':v.source_file,'row':v.source_row,'assembly':v.assembly,
            'review_needed':review_reasons(v),'raw_data':v.raw,'evidence':v.evidence},ensure_ascii=False,indent=2,default=str))

    def save_identity(self):
        if self.active:return
        v=self.current_variant
        if not v:return
        hgvs=self.hgvs_edit.text().strip()
        genomic=self.genomic_edit.text().strip()
        if genomic and not re.fullmatch(r'(?:chr)?(?:[1-9]|1\d|2[0-2]|X|Y|M)-[1-9]\d*-[ACGT]+-[ACGT]+',genomic,re.I):
            self.notify_error('Use chr-pos-REF-ALT on hg19.');return
        if self.verified_check.isChecked() and not re.fullmatch(r'(?:NM_|NC_|NG_)[\w.]+(?:\(NM_[\w.]+\))?:[cgnm]\..+',hgvs):
            self.notify_error('Enter full HGVS with a reference before approving.');return
        v.gene=self.gene_edit.text().strip();v.transcript=self.transcript_edit.text().strip()
        v.corrected_hgvs=hgvs;v.nomenclature_verified=self.verified_check.isChecked()
        v.controlled_genomic=genomic
        self.session.history.append({'event':'identity_review','id':v.id,'time':datetime.now().astimezone().isoformat(),'hgvs':hgvs})
        self.mark_dirty();self.variant_model.layoutChanged.emit();self.refresh_evidence();self.auto_save()
        self.banner.setText('Review saved. Previous evidence may be outdated.')

    def show_tissue(self,*args):
        self.tissue.setCurrentText(self.session.tissue(self.tissue_patient.currentText()))

    def save_tissue(self):
        if self.active:return
        patient=self.tissue_patient.currentText()
        if not patient:return
        self.session.tissues[patient]=self.tissue.currentText().strip() or 'Other'
        self.mark_dirty();self.refresh_evidence();self.auto_save()
        self.banner.setText('Tissue saved. Rerun searches if the tissue changed.')

    def refresh_evidence(self):
        selected_keys=set()
        if hasattr(self,'evidence_table'):
            for index in self.evidence_table.selectionModel().selectedRows():
                item=self.evidence_model.item(index.row(),0)
                if item:selected_keys.add(tuple(item.data(Qt.ItemDataRole.UserRole+1) or ()))
        self.evidence_model.removeRows(0,self.evidence_model.rowCount())
        counts={'Verified match':0,'Review match':0,'Pending':0,'attention':0}
        for v in self.session.variants:
            sources=set(v.evidence)
            if v.selected:sources.update(s for s,c in self.source_checks.items() if c.isChecked())
            for source in SOURCES:
                if source not in sources:continue
                e=v.evidence.get(source,{})
                assessment=assess_evidence(v,e,self.session)
                state=assessment.label
                if state in counts:counts[state]+=1
                attention=assessment.retryable or state in {'Review required','Review match'}
                if attention:counts['attention']+=1
                mode=self.result_filter.currentText()
                if mode=='Needs attention' and not attention:continue
                if mode=='Matches' and state not in {'Verified match','Review match'}:continue
                if mode=='Pending' and state!='Pending':continue
                variant=f'{v.gene} {v.corrected_hgvs or v.coding or v.protein}'.strip()
                row=[QStandardItem(str(x)) for x in [v.patient,variant,source,state,
                    e.get('captured_at','')[:19].replace('T',' '),e.get('summary','') or assessment.reason]]
                for item in row:item.setToolTip(assessment.reason)
                row[0].setData(e.get('url',''),Qt.ItemDataRole.UserRole)
                row[0].setData((v.id,source),Qt.ItemDataRole.UserRole+1)
                self.evidence_model.appendRow(row)
        for i,width in enumerate((125,230,100,145,155,400)):self.evidence_table.setColumnWidth(i,width)
        self.result_counts.setText(f"{counts['Verified match']} verified · {counts['Review match']} to review · {counts['attention']} need attention · {counts['Pending']} pending")
        selection=self.evidence_table.selectionModel()
        from PyQt6.QtCore import QItemSelectionModel
        for row in range(self.evidence_model.rowCount()):
            item=self.evidence_model.item(row,0)
            if tuple(item.data(Qt.ItemDataRole.UserRole+1)) in selected_keys:
                selection.select(self.evidence_model.index(row,0),QItemSelectionModel.SelectionFlag.Select|QItemSelectionModel.SelectionFlag.Rows)

    def open_evidence_url(self,index):
        url=self.evidence_model.item(index.row(),0).data(Qt.ItemDataRole.UserRole)
        if url and url.startswith(('https://','http://')):QDesktopServices.openUrl(QUrl(url))

    def selected_result_keys(self):
        return {tuple(self.evidence_model.item(i.row(),0).data(Qt.ItemDataRole.UserRole+1))
            for i in self.evidence_table.selectionModel().selectedRows()}

    def open_selected_source(self):
        rows=self.evidence_table.selectionModel().selectedRows()
        if rows:self.open_evidence_url(rows[0])

    def show_raw_source(self):
        dialog=QDialog(self);dialog.setWindowTitle('Source data');dialog.resize(850,650)
        layout=QVBoxLayout(dialog);text=QPlainTextEdit();text.setReadOnly(True)
        text.setPlainText(self.raw_detail.toPlainText());layout.addWidget(text)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close);buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons);dialog.exec()

    def inspect_evidence(self):
        keys=self.selected_result_keys()
        if not keys:return
        id,source=next(iter(keys));v=next((v for v in self.session.variants if v.id==id),None)
        if not v:return
        e=v.evidence.get(source,{})
        assessment=assess_evidence(v,e,self.session)
        dialog=QDialog(self);dialog.setWindowTitle(f'{source} · {v.gene}');dialog.resize(1000,760)
        layout=QVBoxLayout(dialog);layout.addWidget(QLabel(f'{assessment.label} · {assessment.reason}'))
        text=QPlainTextEdit();text.setReadOnly(True)
        text.setPlainText(json.dumps(e,ensure_ascii=False,indent=2,default=str));text.setMaximumHeight(170)
        layout.addWidget(text)
        from PyQt6.QtWidgets import QScrollArea
        from PyQt6.QtGui import QPixmap
        scroll=QScrollArea();scroll.setWidgetResizable(True);images=QWidget();images_layout=QVBoxLayout(images)
        raw=e.get('raw',{});captures=raw.get('screenshots',[]) or ([{'path':raw['screenshot']}] if raw.get('screenshot') else [])
        if raw.get('patient_report_screenshot'):captures=[*captures,{'path':raw['patient_report_screenshot'],'label':'Full MTBP report'}]
        for capture in captures:
            path=Path(capture.get('path',''));images_layout.addWidget(QLabel(capture.get('label','Screenshot')))
            image=QLabel();pixmap=QPixmap(str(path)) if path.is_file() else QPixmap()
            if pixmap.isNull():image.setText('Screenshot unavailable')
            else:image.setPixmap(pixmap.scaledToWidth(min(920,pixmap.width()),Qt.TransformationMode.SmoothTransformation))
            images_layout.addWidget(image)
        if not captures:images_layout.addWidget(QLabel('No screenshots captured'))
        images_layout.addStretch();scroll.setWidget(images);layout.addWidget(scroll,1)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close);buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons);dialog.exec()

    def record_activity(self,message):
        entry=self.activity.write(message) if self.activity else f'{datetime.now():%H:%M:%S}  {message}'
        if hasattr(self,'queue_log'):self.queue_log.appendPlainText(entry)

    def open_log_folder(self):
        if self.activity:QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.activity.path.parent)))

    def show_account(self,*args):
        source=self.login_source.currentText();username=self.config.get('accounts',{}).get(source,'')
        self.account_username.setText(username);self.account_password.clear()
        try:
            password=read_password(source,username)
            if password and self.activity:self.activity.secrets.add(password)
            stored='Password saved in Windows Credential Manager' if password else 'No saved password'
        except Exception:stored='Credential Manager unavailable; use Edge sign-in'
        checked=self.config.get('login_checks',{}).get(source,{})
        self.account_status.setText(stored+' · '+checked.get('state','Session not checked')+
            (' · '+checked['time'][:19].replace('T',' ') if checked.get('time') else ''))

    def save_account(self):
        if self.active:return
        source=self.login_source.currentText();username=self.account_username.text().strip();password=self.account_password.text()
        if not username:self.notify_error('Enter a username / email.');return
        if password and self.activity:self.activity.secrets.add(password)
        try:
            if password:write_password(source,username,password)
            if self.config.get('accounts',{}).get(source)!=username:
                self.config.setdefault('login_checks',{}).pop(source,None)
            self.config.setdefault('accounts',{})[source]=username
            atomic_write(self.config_path,json.dumps(self.config,ensure_ascii=False,indent=2))
            self.account_password.clear();self.show_account();self.record_activity(f'{source}: account settings saved')
        except Exception as exc:self.notify_error(str(exc))

    def forget_password(self):
        if self.active:return
        source=self.login_source.currentText();username=self.config.get('accounts',{}).get(source,'')
        try:remove_password(source,username);self.show_account();self.record_activity(f'{source}: saved password removed')
        except Exception as exc:self.notify_error(str(exc))

    def save_to(self,path):
        save_session(self.session,Path(path));self.session_path=Path(path);self.dirty=False
        if not isinstance(self.active,EvidenceWorker):self.banner.setText('Session saved')

    def save_dialog(self):
        path,_=QFileDialog.getSaveFileName(self,'Save session',str(self.session_path or 'session.solide.json'),'Solide session (*.solide.json)')
        if path:
            try:self.save_to(path)
            except Exception as exc:self.notify_error(str(exc))

    def auto_save(self):
        if self.session_path:
            try:self.save_to(self.session_path);return True
            except Exception as exc:
                self.record_activity('Save failed: '+str(exc));self.dirty=True
                self.banner.setText('Save failed. Results remain in memory; save to another file.');return False
        return False

    def open_session(self):
        if self.dirty:
            if QMessageBox.question(self,'Session','Discard unsaved changes and open another session?')!=QMessageBox.StandardButton.Yes:return
        path,_=QFileDialog.getOpenFileName(self,'Open session','','Solide session (*.solide.json *.json)')
        if not path:return
        try:self.session=load_session(Path(path));self.session_path=Path(path);self.dirty=False;self.refresh();self.record_activity('Session opened')
        except Exception as exc:self.notify_error(str(exc))

    def choose_directory(self):
        path=QFileDialog.getExistingDirectory(self,'Choose workspace folder',self.output_dir.text())
        if path:self.output_dir.setText(path)

    def save_settings(self):
        self.config.update(output_dir=self.output_dir.text().strip(),background=self.background.isChecked(),
                     sources=[s for s,c in self.source_checks.items() if c.isChecked()])
        try:atomic_write(self.config_path,json.dumps(self.config,ensure_ascii=False,indent=2));self.banner.setText('Settings saved')
        except Exception as exc:self.notify_error(str(exc))

    def work_root(self):
        if not self.output_dir.text().strip():
            self.nav.setCurrentRow(3);self.notify_error('Choose a workspace folder in Settings.');return None
        root=Path(self.output_dir.text().strip())
        try:root.mkdir(parents=True,exist_ok=True)
        except OSError as exc:self.notify_error(str(exc));return None
        return root

    def start_queue(self,mode='pending',chosen=None):
        if self.active:return
        # Qt's clicked signal may provide a boolean to a callable slot.
        if isinstance(mode,bool):mode='pending'
        sources=sorted({source for id,source in chosen}) if mode=='chosen' else [s for s,c in self.source_checks.items() if c.isChecked()]
        plan=build_search_plan(self.session,sources,mode,chosen)
        if not plan:self.banner.setText('No searches to run');self.record_activity(f'{mode}: no searches to run');return
        root=self.work_root()
        if root is None:return
        if not sources:self.notify_error('Select at least one source.');return
        if not self.session_path:
            self.save_dialog()
            if not self.session_path:return
        if not self.auto_save():
            self.notify_error('Session could not be saved. Choose a writable file before searching.');return
        try:credentials=browser_credentials({s:u for s,u in self.config.get('accounts',{}).items() if s in sources})
        except Exception:
            credentials={};self.record_activity('Saved credentials unavailable; using existing Edge sessions. Sign in through Settings if needed.')
        if self.activity:self.activity.secrets.update(value for key,value in credentials.items() if key.endswith('_password') and value)
        self.run_plan=plan;self.run_done=set();self.run_history_saved=set();self.run_id=uuid.uuid4().hex
        self.run_started=time.monotonic();self.run_state='Running';self.run_timer.start()
        self.session.history.append({'event':'run_start','run_id':self.run_id,'mode':mode,'jobs':sorted(plan),
            'time':datetime.now().astimezone().isoformat()})
        self.dirty=True
        if not self.auto_save():self.run_timer.stop();self.run_state='Failed';self.update_run_status();return
        self.control=QueueControl()
        worker=EvidenceWorker(self.session,sources,root/'evidence',self.control,self.background.isChecked(),plan,credentials)
        worker.evidence.connect(self.accept_evidence);worker.progress.connect(self.queue_progress)
        worker.outcome.connect(self.queue_outcome);self.launch(worker)
        self.pause_btn.setEnabled(True);self.stop_btn.setEnabled(True);self.pause_btn.setText('Pause')
        self.progress.setRange(0,len(plan));self.progress.setValue(0);self.progress.setTextVisible(True)
        self.progress.setFormat('%v / %m');self.update_run_status()
        self.record_activity(f'{mode}: started {len(plan)} source searches')

    def rerun_selected(self):
        keys=self.selected_result_keys()
        if not keys:self.banner.setText('Select result rows to rerun');return
        checked={v.id for v in self.session.variants if v.selected}
        if any(id not in checked for id,source in keys):
            self.banner.setText('Check these variants in Workspace before rerunning their results.');return
        self.start_queue('chosen',keys)

    def queue_progress(self,message):
        if self.activity:message=self.activity.redact(message)
        self.record_activity(message);self.banner.setText(message[:220])

    def queue_outcome(self,message):
        self.run_state='Stopped' if self.control and self.control.stopped.is_set() else 'Completed'
        self.banner.setText(message);self.record_activity(message);self.update_run_status()

    def update_run_status(self):
        elapsed=int(time.monotonic()-self.run_started) if self.run_started else 0
        errors=review=matches=0
        for v in self.session.variants:
            for source in SOURCES:
                if (v.id,source) not in self.run_done:continue
                assessment=assess_evidence(v,v.evidence.get(source,{}),self.session)
                errors+=assessment.retryable
                review+=assessment.label in {'Review required','Review match'}
                matches+=assessment.label in {'Verified match','Review match'}
        self.live_status.setText(f'{self.run_state} · {len(self.run_done)}/{len(self.run_plan)} · {matches} matches · {errors} failed · {review} to review · {elapsed//60:02}:{elapsed%60:02}' if self.run_id else self.run_state)

    def accept_evidence(self,id,source,e):
        v=next((v for v in self.session.variants if v.id==id),None)
        if not v:return
        key=(id,source)
        if key not in self.run_history_saved:
            previous=v.evidence.get(source)
            if previous:self.session.history.append({'event':'evidence_replaced','run_id':self.run_id,'id':id,'source':source,'evidence':copy.deepcopy(previous)})
            self.run_history_saved.add(key)
        e['run_id']=self.run_id;v.evidence[source]=e;self.dirty=True
        if 'provisional_status' not in e.get('raw',{}):
            self.run_done.add(key);self.progress.setValue(len(self.run_done))
            assessment=assess_evidence(v,e,self.session)
            self.record_activity(f'{source} · {v.gene}: {assessment.label}')
        self.auto_save();self.refresh_evidence();self.update_run_status()

    def pause_queue(self):
        if not self.control:return
        if self.control.paused.is_set():self.control.paused.clear();self.pause_btn.setText('Pause');self.run_state='Running'
        else:self.control.paused.set();self.pause_btn.setText('Resume');self.run_state='Pausing';self.banner.setText('Pausing at the next checkpoint')
        self.record_activity(self.run_state);self.update_run_status()

    def stop_queue(self):
        if self.control:self.control.stopped.set();self.control.paused.clear();self.run_state='Stopping';self.banner.setText('Stopping at the next checkpoint…');self.record_activity('Stopping');self.update_run_status()

    def login(self):
        if self.active:return
        source=self.login_source.currentText()
        username=self.account_username.text().strip();password=self.account_password.text()
        try:
            credentials={f'{source.lower()}_email':username,f'{source.lower()}_password':password} if password else browser_credentials({source:username})
        except Exception:
            credentials={};self.record_activity(f'{source}: saved credentials unavailable; opening manual Edge sign-in')
        if self.activity:self.activity.secrets.update(value for key,value in credentials.items() if key.endswith('_password') and value)
        service=BrowserReviewService(profile_root=Path.home()/'.solide'/'browser_profiles',browser_background=False,**credentials)
        worker=Worker(lambda:service.open_login(source,maximum_minutes=5));worker.result.connect(lambda result:self.login_result(source,str(result)))
        self.live_status.setText(f'{source}: checking sign-in');self.record_activity(f'{source}: sign-in started')
        self.launch(worker);self.banner.setText('Sign in through Edge, then close the sign-in window.')

    def login_result(self,source,message):
        confirmed='sign-in confirmed' in message.lower() or 'signed in using' in message.lower()
        self.config.setdefault('login_checks',{})[source]={'state':'Last sign-in confirmed' if confirmed else 'Sign-in not confirmed',
            'time':datetime.now().astimezone().isoformat()}
        try:atomic_write(self.config_path,json.dumps(self.config,ensure_ascii=False,indent=2))
        except Exception as exc:self.record_activity('Could not save sign-in status: '+str(exc))
        self.show_account();self.live_status.setText('Idle');self.banner.setText(message);self.record_activity(message)

    def export(self):
        root=self.work_root()
        if root is None:return
        chosen=self.report_patient.currentText()
        patients=self.session.patients if chosen=='All patients' else [chosen] if chosen else []
        if not patients:self.notify_error('Import a sample first.');return
        self.auto_save();snapshot=copy.deepcopy(self.session)
        worker=Worker(lambda:[export_patient(snapshot,p,root/'reports') for p in patients])
        worker.result.connect(self.export_finished)
        self.launch(worker);self.banner.setText('Exporting Excel…')

    def export_finished(self,paths):
        self.report_log.setPlainText('Reports exported:\n'+'\n'.join(map(str,paths)))
        self.record_activity(f'Exported {len(paths)} patient reports')

    def closeEvent(self,event):
        if self.active and self.active.isRunning():
            self.stop_queue();self.banner.setText('Wait for the current task to stop before closing.');event.ignore();return
        if self.dirty:
            reply=QMessageBox.question(self,'Session','Save changes before closing?',
                QMessageBox.StandardButton.Save|QMessageBox.StandardButton.Discard|QMessageBox.StandardButton.Cancel)
            if reply==QMessageBox.StandardButton.Cancel:event.ignore();return
            if reply==QMessageBox.StandardButton.Save:
                self.save_dialog()
                if self.dirty:event.ignore();return
        self.record_activity('Application closed')
        if self.activity:self.activity.close()
        event.accept()
