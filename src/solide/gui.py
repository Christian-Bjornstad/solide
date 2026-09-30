from __future__ import annotations
import copy
from datetime import datetime
import json
from pathlib import Path
import re
from PyQt6.QtCore import Qt, QSortFilterProxyModel, QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QDesktopServices, QFontDatabase
from PyQt6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QListWidget, QStackedWidget, QFileDialog, QMessageBox, QLineEdit,
    QComboBox, QTableView, QHeaderView, QTextEdit, QCheckBox, QFormLayout, QSplitter,
    QDialog, QDialogButtonBox, QGroupBox, QAbstractItemView, QProgressBar,QTabWidget,QPlainTextEdit)
from .models import Session, Variant
from .importing import load_file
from .quality import qc_flags, review_reasons
from .session import save_session, load_session, atomic_write
from .table_model import VariantTableModel, VariantProxy
from .reporting import export_patient, STATUS
from .evidence import SOURCES, QueueControl, run_queue, evidence_is_current
from ._vendor.archer.services.browser_review import BrowserReviewService, BrowserReviewCancelled

STYLE='''
QWidget { font-family: "Segoe UI"; font-size: 14px; color: #1F2A22; }
QMainWindow, QStackedWidget { background: #F4F6F2; }
QWidget#rail { background: #425B3D; }
QLabel#brand { color: white; font-size: 29px; font-weight: 700; letter-spacing: 3px; }
QLabel#railNote { color: #E5EBDD; }
QLabel#title { font-size: 26px; font-weight: 600; }
QLabel#subtitle { color: #596454; }
QListWidget#nav { background: transparent; color: white; border: 0; outline: 0; }
QListWidget#nav::item { padding: 15px 12px; margin: 3px 0; border-radius: 6px; color: white; }
QListWidget#nav::item:selected { background: #EDF3E8; color: #283C24; font-weight: 600; }
QListWidget#nav::item:hover:!selected { background: #526C4A; }
QPushButton { background: white; border: 1px solid #C0CBB9; border-radius: 5px; padding: 9px 15px; min-height: 18px; }
QPushButton:hover { background: #EAF0E6; border-color: #425B3D; }
QPushButton:focus, QLineEdit:focus, QComboBox:focus, QTableView:focus { border: 2px solid #425B3D; }
QPushButton#primary { background: #425B3D; color: white; border-color: #425B3D; font-weight: 600; }
QPushButton#primary:hover { background: #34492F; }
QPushButton:disabled { background: #E8ECE5; color: #667260; border-color: #D6DED2; }
QLineEdit, QComboBox { background: white; border: 1px solid #C0CBB9; padding: 8px; border-radius: 4px; }
QTextEdit, QPlainTextEdit, QTableView { background: white; border: 1px solid #D6DED2; border-radius: 4px; selection-background-color: #DCE8D5; selection-color: #1F2A22; }
QHeaderView::section { background: #EAF0E6; padding: 9px; border: 0; border-bottom: 1px solid #C0CBB9; font-weight: 600; }
QGroupBox { background: white; border: 1px solid #D6DED2; border-radius: 6px; margin-top: 16px; padding: 18px; }
QGroupBox::title { subcontrol-origin: margin; left: 15px; padding: 0 5px; font-weight: 600; }
QCheckBox { spacing: 8px; padding: 5px; }
QCheckBox::indicator { width: 17px; height: 17px; }
QProgressBar { border: 1px solid #D6DED2; background: white; height: 8px; border-radius: 4px; }
QProgressBar::chunk { background: #425B3D; }
'''


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
    def __init__(self,session,sources,root,control,background):
        super().__init__();self.session=copy.deepcopy(session);self.sources=sources
        self.root=root;self.control=control;self.background=background
    def run(self):
        try:
            run_queue(self.session,self.sources,self.root,self.control,self.evidence.emit,
                      self.progress.emit,self.background)
            self.outcome.emit('Kø ferdig. Gjennomgå status for hver kilde før rapportering.')
        except BrowserReviewCancelled:self.outcome.emit('Stoppet. Fullførte resultater er beholdt.')
        except Exception as exc:self.error.emit(str(exc))


def table(model):
    widget=QTableView();widget.setModel(model);widget.setSortingEnabled(True)
    widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    widget.setAlternatingRowColors(True);widget.verticalHeader().setDefaultSectionSize(34)
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
        self.config_path=Path.home()/'.solide'/'ui_config.json'
        try:self.config=json.loads(self.config_path.read_text(encoding='utf8'))
        except (OSError,ValueError):self.config={}
        self.setWindowTitle('Solide | Variantgjennomgang');self.resize(1440,940)
        self.setMinimumSize(1050,700);self.setStyleSheet(STYLE)
        central=QWidget();self.setCentralWidget(central)
        horizontal=QHBoxLayout(central);horizontal.setContentsMargins(0,0,0,0);horizontal.setSpacing(0)
        rail=QWidget();rail.setObjectName('rail');rail.setFixedWidth(218)
        rail_layout=QVBoxLayout(rail);rail_layout.setContentsMargins(20,28,20,25)
        brand=QLabel('SOLIDE');brand.setObjectName('brand');rail_layout.addWidget(brand)
        note=QLabel('Molekylær patologi\nSolide svulster');note.setObjectName('railNote');rail_layout.addWidget(note)
        self.nav=QListWidget();self.nav.setObjectName('nav')
        self.nav.addItems(['Import','Kvalitet','Variantutvalg','Databaseoppslag','Rapport','Innstillinger'])
        rail_layout.addWidget(self.nav,1)
        footer=QLabel('Lokal arbeidsflate\nGRCh37 / hg19 · v0.1.0');footer.setObjectName('railNote');rail_layout.addWidget(footer)
        horizontal.addWidget(rail)
        body=QWidget();vertical=QVBoxLayout(body);vertical.setContentsMargins(28,25,28,18)
        self.title=QLabel('Import');self.title.setObjectName('title');vertical.addWidget(self.title)
        self.summary=QLabel('Ingen filer lastet inn');self.summary.setObjectName('subtitle');vertical.addWidget(self.summary)
        self.pages=QStackedWidget();vertical.addWidget(self.pages,1)
        self.banner=QLabel('Klar. Last inn en TSV-fil eller Genexus-arbeidsskjema.');self.banner.setWordWrap(True)
        vertical.addWidget(self.banner);horizontal.addWidget(body,1)
        self.build_import();self.build_quality();self.build_variants();self.build_evidence();self.build_report();self.build_settings()
        self.nav.currentRowChanged.connect(self.navigate);self.nav.setCurrentRow(0)
        self.refresh()

    def page(self):
        w=QWidget();layout=QVBoxLayout(w);layout.setContentsMargins(0,18,0,0)
        layout.setSpacing(14);self.pages.addWidget(w);return layout

    def button(self,label,fn,primary=False):
        b=QPushButton(label);b.clicked.connect(fn)
        if primary:b.setObjectName('primary')
        return b

    def build_import(self):
        layout=self.page()
        box=QGroupBox('Fra eksportfil til arbeidsøkt');content=QVBoxLayout(box)
        info=QLabel('Les Ion Reporter TSV, Genexus TSV eller komplett Genexus XLSX.\n'
                    'Originaldata beholdes. Pasient/prøve og genomversjon bekreftes ved import.');info.setWordWrap(True)
        content.addWidget(info)
        row=QHBoxLayout()
        self.import_btn=self.button('Last inn TSV / Excel …',self.import_files,True);row.addWidget(self.import_btn)
        self.open_btn=self.button('Åpne arbeidsøkt …',self.open_session);row.addWidget(self.open_btn)
        self.save_btn=self.button('Lagre arbeidsøkt …',self.save_dialog);row.addWidget(self.save_btn);row.addStretch()
        content.addLayout(row);layout.addWidget(box)
        self.import_log=QPlainTextEdit();self.import_log.setReadOnly(True)
        self.import_log.setPlaceholderText('Importoppsummering og eventuelle mangler vises her.');layout.addWidget(self.import_log,1)
        layout.addWidget(QLabel('TSV med bare funn inneholder ikke nødvendigvis CNV- og RNA-kvalitetsdata.'))

    def build_quality(self):
        layout=self.page()
        note=QLabel('Alle importerte rader kontrolleres, også de som ikke er valgt til oppslag.\n'
                    'Coverage <500 per rad · CNV <1 · RNAExonTiles NO CALL · RNAExonVariant ABSENT.');note.setWordWrap(True)
        layout.addWidget(note)
        self.qc_summary=QLabel();layout.addWidget(self.qc_summary)
        self.qc_model=QStandardItemModel(0,7)
        self.qc_model.setHorizontalHeaderLabels(['Pasient','Gen','Kategori','Status','Begrunnelse','Type','Kilderad'])
        self.qc_table=table(self.qc_model);self.qc_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.qc_table,1)

    def build_variants(self):
        layout=self.page();row=QHBoxLayout()
        self.search=QLineEdit();self.search.setPlaceholderText('Søk i gen, HGVS, type eller prøve …')
        self.search.setAccessibleName('Søk i varianter');row.addWidget(self.search,1)
        self.patient_filter=QComboBox();self.patient_filter.setAccessibleName('Filtrer pasient');row.addWidget(self.patient_filter)
        row.addWidget(self.button('Velg synlige',lambda:self.select_visible(True)))
        row.addWidget(self.button('Fjern valg for synlige',lambda:self.select_visible(False)))
        layout.addLayout(row)
        self.variant_model=VariantTableModel();self.variant_model.changed.connect(self.mark_dirty)
        self.proxy=VariantProxy();self.proxy.setSourceModel(self.variant_model)
        self.search.textChanged.connect(self.apply_filter);self.patient_filter.currentTextChanged.connect(self.apply_filter)
        self.variant_table=table(self.proxy)
        self.variant_table.selectionModel().currentRowChanged.connect(self.show_variant)
        split=QSplitter(Qt.Orientation.Vertical);split.addWidget(self.variant_table)
        detail=QWidget();d=QHBoxLayout(detail);d.setContentsMargins(0,0,0,0)
        self.detail=QTextEdit();self.detail.setReadOnly(True);self.detail.setPlaceholderText('Velg en rad for kildeinformasjon og oppslagsresultater.')
        self.raw_detail=QTextEdit();self.raw_detail.setReadOnly(True)
        tabs=QTabWidget();tabs.addTab(self.detail,'Variant og funn');tabs.addTab(self.raw_detail,'Originaldata / kilderespons')
        d.addWidget(tabs,3)
        form_box=QGroupBox('Kontrollert variantidentitet');form=QFormLayout(form_box)
        self.gene_edit=QLineEdit();self.transcript_edit=QLineEdit();self.hgvs_edit=QLineEdit()
        self.genomic_edit=QLineEdit();self.genomic_edit.setPlaceholderText('chr7-123456-A-T')
        self.hgvs_edit.setPlaceholderText('NM_…:c.… eller NC_…(NM_…):c.…')
        form.addRow('Gen',self.gene_edit);form.addRow('Transkript',self.transcript_edit)
        form.addRow('Full kontrollert HGVS',self.hgvs_edit)
        form.addRow('Kontrollert hg19 REF/ALT',self.genomic_edit)
        self.verified_check=QCheckBox('Nomenklatur / omregning er kontrollert')
        form.addRow(self.verified_check)
        form.addRow(self.button('Lagre kontroll',self.save_identity))
        explanation=QLabel('Original eksport beholdes i rådata.\nMutalyzer-forslag krever egen kontroll.');explanation.setWordWrap(True);form.addRow(explanation)
        d.addWidget(form_box,2);split.addWidget(detail);split.setSizes([430,250]);layout.addWidget(split,1)
        self.selection_summary=QLabel();layout.addWidget(self.selection_summary)

    def build_evidence(self):
        layout=self.page();top=QHBoxLayout()
        self.tissue_patient=QComboBox();self.tissue_patient.currentTextChanged.connect(self.show_tissue)
        self.tissue=QComboBox();self.tissue.setEditable(True);self.tissue.addItems(['Other','Lung','Breast','Colorectal'])
        top.addWidget(QLabel('Pasient'));top.addWidget(self.tissue_patient)
        top.addWidget(QLabel('MTBP-vev'));top.addWidget(self.tissue,1)
        top.addWidget(self.button('Lagre vev',self.save_tissue));layout.addLayout(top)
        self.source_checks={};sources=QHBoxLayout()
        for source in SOURCES:
            check=QCheckBox(source);check.setChecked(source in self.config.get('sources',['ClinVar','MTBP','Franklin','Mutalyzer','SpliceAI']))
            sources.addWidget(check);self.source_checks[source]=check
        layout.addLayout(sources)
        note=QLabel('Bare valgte varianter søkes. Delins og MANE-avvik må ha kontrollert HGVS først.\n'
                    'SpliceAI: intronregel ±100 bp; modellvindu 500 bp, mask=1. Genomiske søk krever REF/ALT.');note.setWordWrap(True);layout.addWidget(note)
        row=QHBoxLayout();self.run_btn=self.button('Start / gjenoppta oppslag',self.start_queue,True);row.addWidget(self.run_btn)
        self.pause_btn=self.button('Pause',self.pause_queue);self.pause_btn.setEnabled(False);row.addWidget(self.pause_btn)
        self.stop_btn=self.button('Stopp',self.stop_queue);self.stop_btn.setEnabled(False);row.addWidget(self.stop_btn)
        self.login_source=QComboBox();self.login_source.addItems(SOURCES[:5]);row.addWidget(self.login_source)
        self.login_btn=self.button('Åpne Edge for innlogging',self.login);row.addWidget(self.login_btn);row.addStretch()
        layout.addLayout(row)
        self.progress=QProgressBar();self.progress.setRange(0,1);self.progress.setValue(0);self.progress.setTextVisible(False);layout.addWidget(self.progress)
        self.evidence_model=QStandardItemModel(0,5);self.evidence_model.setHorizontalHeaderLabels(['Pasient','Gen','Kilde','Status','Oppsummering'])
        self.evidence_table=table(self.evidence_model);self.evidence_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.evidence_table.doubleClicked.connect(self.open_evidence_url);layout.addWidget(self.evidence_table,2)
        self.queue_log=QPlainTextEdit();self.queue_log.setReadOnly(True);layout.addWidget(self.queue_log,1)

    def build_report(self):
        layout=self.page();box=QGroupBox('Én Excel-rapport per pasient');form=QVBoxLayout(box)
        info=QLabel('Rapporten inneholder valgte funn, QC fra alle rader, kildehenvisninger,\n'
                    'variantark med tilgjengelige skjermbilder og rådata. Feil og utdatert evidens vises.');info.setWordWrap(True);form.addWidget(info)
        row=QHBoxLayout();self.report_patient=QComboBox();row.addWidget(self.report_patient,1)
        self.report_btn=self.button('Generer Excel-rapport',self.export,True);row.addWidget(self.report_btn)
        form.addLayout(row);layout.addWidget(box)
        self.report_log=QPlainTextEdit();self.report_log.setReadOnly(True);layout.addWidget(self.report_log,1)
        layout.addWidget(QLabel('Kommentarer lagres i arbeidsøkten. Regenerering erstatter appens rapportfil.'))

    def build_settings(self):
        layout=self.page();box=QGroupBox('Arbeidsmappe og Edge');form=QFormLayout(box)
        folder=QWidget();row=QHBoxLayout(folder);row.setContentsMargins(0,0,0,0)
        self.output_dir=QLineEdit(self.config.get('output_dir',''));row.addWidget(self.output_dir,1)
        row.addWidget(self.button('Bla gjennom …',self.choose_directory));form.addRow('Arbeidsmappe',folder)
        self.background=QCheckBox('Kjør automatiske Edge-vinduer minimert');self.background.setChecked(self.config.get('background',True));form.addRow(self.background)
        form.addRow(self.button('Lagre innstillinger',self.save_settings))
        layout.addWidget(box)
        text=QLabel('Velg laboratoriets godkjente lagringsmappe før oppslag og rapportering.\n'
                    'Innlogging skjer direkte i Edge. Appen lagrer ingen passord.\n'
                    'Edge må tillate lokal remote debugging. Databaseprofiler lagres separat for Solide.\n\n'
                    'MTBP-vev må være et eksakt valg i portalen; «Other» er standard.\n'
                    'SpliceAI-oppslag kjøres med minst 30 sekunders mellomrom.\n'
                    'HSMD føres foreløpig manuelt i variantkommentaren.');text.setWordWrap(True)
        layout.addWidget(text);layout.addStretch()

    def navigate(self,index):
        self.pages.setCurrentIndex(index);self.title.setText(self.nav.item(index).text())

    def notify_error(self,message):
        self.banner.setText(message);QMessageBox.warning(self,'Solide',message)

    def busy(self,value):
        for widget in (self.import_btn,self.open_btn,self.run_btn,self.login_btn,self.report_btn,
                       self.variant_table,self.gene_edit,self.transcript_edit,self.hgvs_edit,self.genomic_edit,
                       self.verified_check,self.output_dir,self.background,self.tissue):
            widget.setEnabled(not value)
        self.save_btn.setEnabled(not value)

    def launch(self,worker):
        self.active=worker;self.workers.append(worker);self.busy(True)
        worker.error.connect(self.notify_error)
        worker.finished.connect(lambda:self.finished(worker))
        worker.start()

    def finished(self,worker):
        if self.active is worker:self.active=None;self.busy(False)
        self.workers.remove(worker);worker.deleteLater()
        self.pause_btn.setEnabled(False);self.stop_btn.setEnabled(False)
        self.progress.setRange(0,1);self.progress.setValue(1)
        self.refresh_evidence()
        if self.dirty and self.session_path:
            self.banner.setText('Det finnes ulagrede endringer. Lagre arbeidsøkten før appen lukkes.')

    def import_files(self):
        paths,_=QFileDialog.getOpenFileNames(self,'Importer eksportfiler','','Variantfiler (*.tsv *.xlsx)')
        if not paths:return
        def read():
            results=[]
            for path in paths:
                try:results.append((path,load_file(Path(path)),''))
                except Exception as exc:results.append((path,None,str(exc)))
            return results
        worker=Worker(read);worker.result.connect(self.accept_import);self.launch(worker)
        self.banner.setText('Leser eksportfiler …')

    def accept_import(self,results):
        for path,result,error in results:
            if error:self.import_log.appendPlainText(f'Importfeil: {error}');continue
            dialog=QDialog(self);dialog.setWindowTitle('Bekreft pasienttilknytning');dialog.resize(620,330)
            form=QFormLayout(dialog);info=QLabel(f'{Path(path).name}\n{len(result.variants)} rader. Ingen pasienttilknytning fra filnavn antas.');info.setWordWrap(True);form.addRow(info)
            patient=QLineEdit(result.sample_hint);form.addRow('Pasient/prøve-ID',patient)
            assembly=QComboBox();assembly.addItems(['GRCh37','GRCh38','Ukjent'])
            assembly.setCurrentText(result.assembly if result.assembly!='Ukjent' else 'GRCh37');form.addRow('Genomversjon',assembly)
            warnings=QLabel('\n'.join(result.warnings));warnings.setWordWrap(True);form.addRow(warnings)
            buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
            buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);form.addRow(buttons)
            if dialog.exec()!=QDialog.DialogCode.Accepted:continue
            if not patient.text().strip():self.notify_error('Pasient/prøve-ID må fylles ut.');continue
            existing={v.id for v in self.session.variants}
            added=0
            for v in result.variants:
                if v.id in existing:continue
                v.patient=patient.text().strip();v.assembly=assembly.currentText()
                self.session.variants.append(v);added+=1
            self.session.history.append({'event':'import','time':datetime.now().astimezone().isoformat(),
                                         'file':path,'rows':added,'patient':patient.text().strip()})
            self.import_log.appendPlainText(f'{added} rader importert; {len(result.variants)-added} duplikater hoppet over.\n'+'\n'.join(result.warnings))
        self.mark_dirty();self.refresh();self.banner.setText('Import ferdig. Gjennomgå Kvalitet og Variantutvalg.')

    def refresh(self):
        self.variant_model.set_variants(self.session.variants)
        self.qc_model.removeRows(0,self.qc_model.rowCount())
        failed=set();count=0
        for v in self.session.variants:
            for flag in qc_flags(v):
                items=[QStandardItem(str(x)) for x in [v.patient,v.gene,flag.category,flag.status,flag.message,v.kind,v.source_row]]
                self.qc_model.appendRow(items);count+=1
                if flag.category=='Coverage' and flag.status=='Feilet':failed.add((v.patient,v.gene))
        self.qc_summary.setText(f'{count} kontrollpunkter · {len(failed)} pasient/gen-kombinasjoner med coverage <500')
        for combo,first in [(self.patient_filter,'Alle pasienter'),(self.tissue_patient,None),(self.report_patient,'Alle pasienter')]:
            prior=combo.currentText();combo.blockSignals(True);combo.clear()
            if first:combo.addItem(first)
            combo.addItems(self.session.patients)
            if combo.findText(prior)>=0:combo.setCurrentText(prior)
            combo.blockSignals(False)
        self.show_tissue();self.apply_filter();self.refresh_counts();self.refresh_evidence()
        self.variant_table.setColumnWidth(0,60);self.variant_table.setColumnWidth(1,145);self.variant_table.setColumnWidth(2,95)
        self.variant_table.setColumnWidth(3,150);self.variant_table.setColumnWidth(4,200)
        self.qc_table.setColumnWidth(4,430)

    def refresh_counts(self):
        total=len(self.session.variants);selected=sum(v.selected for v in self.session.variants)
        self.summary.setText(f'{len(self.session.patients)} pasienter/prøver · {total:,} rader · {selected} valgt til oppslag')
        self.selection_summary.setText(f'{selected} valgt totalt · {self.proxy.rowCount()} synlige rader. QC gjelder også rader som ikke er valgt.')

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
        lines=[f'{v.gene}  {v.protein}',f'DNA: {v.coding}',f'Transkript: {v.transcript or "Mangler"}',
               f'Genom: {v.assembly}   Locus: {v.locus or "Mangler"}',
               f'Allelfrekvens: {v.af_percent if v.af_percent is not None else "Mangler"} %   Coverage: {v.coverage if v.coverage is not None else "Mangler"}',
               f'Kilde: {Path(v.source_file).name} · rad {v.source_row}',
               '\nKontrollbehov: '+(', '.join(review_reasons(v)) or 'Ingen særskilte nomenklaturflagg'),
               *[f'{f.category}: {f.status} – {f.message}' for f in qc_flags(v)],
               '\nKommentar: '+v.comment]
        for source,e in v.evidence.items():
            state=STATUS.get(e.get('status'),e.get('status','Ukjent')) if evidence_is_current(v,e,self.session.tissue(v.patient),self.session) else 'Utdatert'
            lines.append(f'\n{source}: {state}\n{e.get("summary", "")}')
        self.detail.setPlainText('\n'.join(lines))
        self.raw_detail.setPlainText(json.dumps({'kilde':v.source_file,'rad':v.source_row,'genom':v.assembly,
            'kontrollbehov':review_reasons(v),'rådata':v.raw,'oppslag':v.evidence},ensure_ascii=False,indent=2,default=str))

    def save_identity(self):
        if self.active:return
        v=self.current_variant
        if not v:return
        hgvs=self.hgvs_edit.text().strip()
        genomic=self.genomic_edit.text().strip()
        if genomic and not re.fullmatch(r'(?:chr)?(?:[1-9]|1\d|2[0-2]|X|Y|M)-[1-9]\d*-[ACGT]+-[ACGT]+',genomic,re.I):
            self.notify_error('Kontrollert genomisk variant må være chr-pos-REF-ALT på hg19.');return
        if self.verified_check.isChecked() and not re.fullmatch(r'(?:NM_|NC_|NG_)[\w.]+(?:\(NM_[\w.]+\))?:[cgnm]\..+',hgvs):
            self.notify_error('Angi full HGVS med referanse før nomenklaturen godkjennes.');return
        v.gene=self.gene_edit.text().strip();v.transcript=self.transcript_edit.text().strip()
        v.corrected_hgvs=hgvs;v.nomenclature_verified=self.verified_check.isChecked()
        v.controlled_genomic=genomic
        self.session.history.append({'event':'identity_review','id':v.id,'time':datetime.now().astimezone().isoformat(),'hgvs':hgvs})
        self.mark_dirty();self.variant_model.layoutChanged.emit();self.refresh_evidence();self.auto_save()
        self.banner.setText('Kontroll lagret. Tidligere oppslag med annen variantidentitet vises som utdaterte.')

    def show_tissue(self,*args):
        self.tissue.setCurrentText(self.session.tissue(self.tissue_patient.currentText()))

    def save_tissue(self):
        if self.active:return
        patient=self.tissue_patient.currentText()
        if not patient:return
        self.session.tissues[patient]=self.tissue.currentText().strip() or 'Other'
        self.mark_dirty();self.refresh_evidence();self.auto_save()
        self.banner.setText('Vev lagret. Tidligere resultater med annet vev må søkes på nytt.')

    def refresh_evidence(self):
        self.evidence_model.removeRows(0,self.evidence_model.rowCount())
        for v in self.session.variants:
            for source,e in v.evidence.items():
                state=STATUS.get(e.get('status'),e.get('status','Ukjent')) if evidence_is_current(v,e,self.session.tissue(v.patient),self.session) else 'Utdatert'
                row=[QStandardItem(str(x)) for x in [v.patient,v.gene,source,state,e.get('summary','')]]
                row[0].setData(e.get('url',''),Qt.ItemDataRole.UserRole);self.evidence_model.appendRow(row)
        self.evidence_table.setColumnWidth(4,550)

    def open_evidence_url(self,index):
        url=self.evidence_model.item(index.row(),0).data(Qt.ItemDataRole.UserRole)
        if url and url.startswith(('https://','http://')):QDesktopServices.openUrl(QUrl(url))

    def save_to(self,path):
        save_session(self.session,Path(path));self.session_path=Path(path);self.dirty=False
        self.banner.setText('Arbeidsøkt lagret lokalt.')

    def save_dialog(self):
        path,_=QFileDialog.getSaveFileName(self,'Lagre arbeidsøkt',str(self.session_path or 'arbeidsokt.solide.json'),'Solide-økt (*.solide.json)')
        if path:
            try:self.save_to(path)
            except Exception as exc:self.notify_error(str(exc))

    def auto_save(self):
        if self.session_path:
            try:self.save_to(self.session_path);return True
            except Exception as exc:
                self.queue_log.appendPlainText('Lagring feilet: '+str(exc));self.dirty=True
                self.banner.setText('Lagring feilet. Resultatene er i minnet; lagre økten til en annen fil.');return False
        return False

    def open_session(self):
        if self.dirty:
            if QMessageBox.question(self,'Arbeidsøkt','Forkaste ulagrede endringer og åpne en annen økt?')!=QMessageBox.StandardButton.Yes:return
        path,_=QFileDialog.getOpenFileName(self,'Åpne arbeidsøkt','','Solide-økt (*.solide.json *.json)')
        if not path:return
        try:self.session=load_session(Path(path));self.session_path=Path(path);self.dirty=False;self.refresh()
        except Exception as exc:self.notify_error(str(exc))

    def choose_directory(self):
        path=QFileDialog.getExistingDirectory(self,'Velg lokal arbeidsmappe',self.output_dir.text())
        if path:self.output_dir.setText(path)

    def save_settings(self):
        self.config={'output_dir':self.output_dir.text().strip(),'background':self.background.isChecked(),
                     'sources':[s for s,c in self.source_checks.items() if c.isChecked()]}
        try:atomic_write(self.config_path,json.dumps(self.config,ensure_ascii=False,indent=2));self.banner.setText('Innstillinger lagret.')
        except Exception as exc:self.notify_error(str(exc))

    def work_root(self):
        if not self.output_dir.text().strip():
            self.nav.setCurrentRow(5);self.notify_error('Velg arbeidsmappe i Innstillinger først.');return None
        root=Path(self.output_dir.text().strip())
        try:root.mkdir(parents=True,exist_ok=True)
        except OSError as exc:self.notify_error(str(exc));return None
        return root

    def start_queue(self):
        root=self.work_root()
        if root is None:return
        sources=[s for s,c in self.source_checks.items() if c.isChecked()]
        if not sources:self.notify_error('Velg minst én database.');return
        if not self.session_path:
            self.save_dialog()
            if not self.session_path:return
        if not self.auto_save():
            self.notify_error('Arbeidsøkten kunne ikke lagres. Velg en skrivbar øktfil før oppslag.');return
        self.control=QueueControl()
        worker=EvidenceWorker(self.session,sources,root/'evidence',self.control,self.background.isChecked())
        worker.evidence.connect(self.accept_evidence);worker.progress.connect(self.queue_log.appendPlainText)
        worker.outcome.connect(self.banner.setText);self.launch(worker)
        self.pause_btn.setEnabled(True);self.stop_btn.setEnabled(True);self.pause_btn.setText('Pause')
        self.progress.setRange(0,0);self.banner.setText('Databaseoppslag kjører. Resultater lagres underveis.')

    def accept_evidence(self,id,source,e):
        v=next((v for v in self.session.variants if v.id==id),None)
        if v:v.evidence[source]=e;self.dirty=True;self.auto_save();self.refresh_evidence()

    def pause_queue(self):
        if not self.control:return
        if self.control.paused.is_set():self.control.paused.clear();self.pause_btn.setText('Pause')
        else:self.control.paused.set();self.pause_btn.setText('Fortsett');self.banner.setText('Pause ved neste sikre stoppunkt.')

    def stop_queue(self):
        if self.control:self.control.stopped.set();self.control.paused.clear();self.banner.setText('Stopper ved neste sikre stoppunkt …')

    def login(self):
        source=self.login_source.currentText()
        service=BrowserReviewService(profile_root=Path.home()/'.solide'/'browser_profiles',browser_background=False)
        worker=Worker(lambda:service.open_login(source,maximum_minutes=5));worker.result.connect(lambda result:self.banner.setText(str(result)))
        self.launch(worker);self.banner.setText('Logg inn i Edge. Lukk innloggingsvinduet når du er ferdig.')

    def export(self):
        root=self.work_root()
        if root is None:return
        chosen=self.report_patient.currentText()
        patients=self.session.patients if chosen=='Alle pasienter' else [chosen] if chosen else []
        if not patients:self.notify_error('Importer en prøve først.');return
        self.auto_save();snapshot=copy.deepcopy(self.session)
        worker=Worker(lambda:[export_patient(snapshot,p,root/'reports') for p in patients])
        worker.result.connect(lambda paths:self.report_log.setPlainText('Rapporter skrevet:\n'+'\n'.join(map(str,paths))))
        self.launch(worker);self.banner.setText('Genererer Excel-rapport …')

    def closeEvent(self,event):
        if self.active and self.active.isRunning():
            self.stop_queue();self.banner.setText('Vent til pågående arbeid har stoppet før appen lukkes.');event.ignore();return
        if self.dirty:
            reply=QMessageBox.question(self,'Arbeidsøkt','Lagre endringer før appen lukkes?',
                QMessageBox.StandardButton.Save|QMessageBox.StandardButton.Discard|QMessageBox.StandardButton.Cancel)
            if reply==QMessageBox.StandardButton.Cancel:event.ignore();return
            if reply==QMessageBox.StandardButton.Save:
                self.save_dialog()
                if self.dirty:event.ignore();return
        event.accept()
