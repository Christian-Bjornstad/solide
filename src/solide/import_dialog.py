"""One file, one sample: detected defaults with details available on demand."""
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog,QVBoxLayout,QFormLayout,QLabel,QLineEdit,
    QComboBox,QDialogButtonBox,QPushButton,QWidget)
from .importing import oum_numbers


class SampleImportDialog(QDialog):
    def __init__(self,result,path,parent=None):
        super().__init__(parent);self.setWindowTitle('Confirm sample');self.resize(620,350)
        layout=QVBoxLayout(self);layout.setSpacing(14)
        file=QLabel(Path(path).name);file.setWordWrap(True);file.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(file)
        self.detected=QLabel(' · '.join(filter(None,[result.profile,result.assay if result.assay!='Unknown' else '',f'{len(result.variants):,} rows'])))
        self.detected.setObjectName('settingsHeading');self.detected.setWordWrap(True);layout.addWidget(self.detected)
        form=QFormLayout();self.patient=QLineEdit(result.sample_hint if oum_numbers(result.sample_hint) else '')
        self.patient.setObjectName('sampleId');self.patient.setPlaceholderText('26OUM…')
        form.addRow('OUM / sample ID',self.patient);layout.addLayout(form)
        self.message=QLabel();self.message.setWordWrap(True);layout.addWidget(self.message)
        if len(result.sample_candidates)>1:
            warning=QLabel('Conflicting IDs: '+', '.join(result.sample_candidates));warning.setWordWrap(True);layout.addWidget(warning)
        if result.assembly=='Unknown':
            layout.addWidget(QLabel('Genome: GRCh37 / hg19 (workspace default)'))
        scope=next((v.raw.get('_export_scope') for v in result.variants if v.raw.get('_export_scope')),None)
        if scope and scope.get('filtered_export'):
            note=QLabel(f"Filtered export: {len(result.variants):,} rows. Additional source rows were not exported.")
            note.setWordWrap(True);layout.addWidget(note)
        toggle=QPushButton('Import details');toggle.setCheckable(True);layout.addWidget(toggle,0,Qt.AlignmentFlag.AlignLeft)
        self.details=QWidget();details=QFormLayout(self.details);details.setContentsMargins(0,0,0,0)
        details.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.assembly=QComboBox();self.assembly.addItems(['GRCh37','GRCh38','Unknown'])
        self.assembly.setCurrentText(result.assembly if result.assembly!='Unknown' else 'GRCh37');details.addRow('Genome',self.assembly)
        self.profile=QComboBox();self.profile.addItems(['Unassigned','OPA','Ion Torrent']);self.profile.setCurrentText(result.profile)
        details.addRow('Analysis',self.profile)
        self.assay=QLineEdit(result.assay if result.assay!='Unknown' else '');details.addRow('Assay',self.assay)
        reason=QLabel(result.detection_reason);reason.setWordWrap(True);details.addRow(reason)
        warnings=QLabel('\n'.join(result.warnings));warnings.setWordWrap(True);details.addRow(warnings)
        layout.addWidget(self.details);toggle.toggled.connect(self.details.setVisible)
        toggle.setChecked(result.profile=='Unassigned');self.details.setVisible(toggle.isChecked())
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        self.add_button=buttons.button(QDialogButtonBox.StandardButton.Ok);self.add_button.setText('Add sample')
        self.add_button.setObjectName('primary');buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject)
        layout.addWidget(buttons);self.patient.textChanged.connect(self.validate_input)
        self.profile.currentTextChanged.connect(self.validate_input);self.validate_input();self.patient.setFocus()

    def validate_input(self,*args):
        missing=not self.patient.text().strip();unknown=self.profile.currentText()=='Unassigned'
        self.add_button.setEnabled(not missing and not unknown)
        self.message.setText('Enter the OUM number for this file.' if missing else 'Choose the analysis in Import details.' if unknown else '')

    def accept(self):
        self.validate_input()
        if self.add_button.isEnabled():super().accept()
