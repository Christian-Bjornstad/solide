"""Enter a sequence interpretation without copying source event evidence."""
from PyQt6.QtWidgets import QDialog,QVBoxLayout,QFormLayout,QLabel,QLineEdit,QDialogButtonBox
from .manual_variants import validate_manual_fields


class ManualVariantDialog(QDialog):
    def __init__(self,parent=None,*,initial=None,from_selected=False):
        super().__init__(parent)
        self.setWindowTitle('Ny variant fra markert rad' if from_selected else 'Ny variant')
        self.resize(630,420)
        layout=QVBoxLayout(self)
        hint=QLabel('Legg inn én variant. Gen og genomisk posisjon kontrolleres mot transkriptet ved søk. '
                    'Originalradene beholdes. Fjern avkrysningen på dem hvis den nye varianten skal erstatte dem.')
        hint.setWordWrap(True);layout.addWidget(hint)
        form=QFormLayout();form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        initial=initial or {}
        for field,label,placeholder in [
            ('transcript','Transkript *','NM_000314.8'),
            ('coding','Nukleotidendring *','c.19G>A eller c.19_20delinsAT'),
            ('protein','Aminosyreendring','p.Glu7Lys (valgfri)'),
            ('gene','Gen','Valgfri – hentes fra transkriptet'),
            ('locus','Lokus','chr10:89624245 (valgfri)')]:
            edit=QLineEdit(str(initial.get(field,'')));edit.setMaxLength(500)
            edit.setPlaceholderText(placeholder);edit.setAccessibleName(label)
            setattr(self,field,edit);form.addRow(label,edit)
        layout.addLayout(form)
        self.error=QLabel();self.error.setWordWrap(True);self.error.setStyleSheet('color: #9E2820;')
        layout.addWidget(self.error)
        self.buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setText('Legg til variant')
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Avbryt')
        self.buttons.accepted.connect(self.validate_and_accept);self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def values(self):
        return validate_manual_fields(**{key:getattr(self,key).text() for key in ('transcript','coding','protein','gene','locus')})

    def validate_and_accept(self):
        try:self.values()
        except ValueError as exc:self.error.setText(str(exc));return
        self.accept()
