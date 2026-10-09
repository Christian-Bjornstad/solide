"""Manual assessments live in the session; Excel is an exported snapshot."""
from datetime import datetime,timezone
from PyQt6.QtWidgets import QDialog,QFormLayout,QComboBox,QLineEdit,QPlainTextEdit,QDialogButtonBox,QLabel
from .appearance import light_palette

FIELDS=('classification','report_decision','reviewer','comment','reviewed_at')
CLASSIFICATIONS=('','Oncogenic','Likely oncogenic','VUS','Likely benign','Benign')


def save_assessment(session,variant,*,classification,decision,reviewer,comment):
    if decision not in {'Pending','Include','Exclude'}:
        raise ValueError('Choose Pending, Include or Exclude.')
    before={field:getattr(variant,field) for field in FIELDS}
    variant.classification=classification.strip()
    variant.report_decision=decision
    variant.reviewer=reviewer.strip()
    variant.comment=comment.strip()
    variant.reviewed_at=datetime.now(timezone.utc).isoformat()
    session.history.append({'event':'assessment','id':variant.id,'time':variant.reviewed_at,
        'before':before,'after':{field:getattr(variant,field) for field in FIELDS}})


class AssessmentDialog(QDialog):
    def __init__(self,variant,parent=None):
        super().__init__(parent)
        self.setPalette(light_palette())
        self.setWindowTitle('Variant assessment');self.resize(640,440)
        form=QFormLayout(self);form.setContentsMargins(24,24,24,24);form.setSpacing(14)
        form.addRow(QLabel(f'{variant.gene}  {variant.corrected_hgvs or variant.coding or variant.protein}'))
        self.classification=QComboBox();self.classification.setEditable(True)
        self.classification.addItems(CLASSIFICATIONS);self.classification.setCurrentText(variant.classification)
        self.decision=QComboBox();self.decision.addItems(['Pending','Include','Exclude'])
        self.decision.setCurrentText(variant.report_decision)
        for combo in (self.classification,self.decision):combo.view().setPalette(light_palette())
        self.reviewer=QLineEdit(variant.reviewer)
        self.comment=QPlainTextEdit(variant.comment);self.comment.setMinimumHeight(150)
        form.addRow('Classification',self.classification);form.addRow('Report decision',self.decision)
        form.addRow('Reviewer',self.reviewer);form.addRow('Assessment / notes',self.comment)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);form.addRow(buttons)

    def values(self):
        return dict(classification=self.classification.currentText(),decision=self.decision.currentText(),
            reviewer=self.reviewer.text(),comment=self.comment.toPlainText())
