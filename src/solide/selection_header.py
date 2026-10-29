"""A visible select-all checkbox for the variant selection column."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHeaderView,QCheckBox


class SelectionCheckBox(QCheckBox):
    def nextCheckState(self):
        self.setCheckState(Qt.CheckState.Unchecked if self.checkState()==Qt.CheckState.Checked
                           else Qt.CheckState.Checked)


class SelectionHeader(QHeaderView):
    def __init__(self,parent=None):
        super().__init__(Qt.Orientation.Horizontal,parent)
        self.checkbox=SelectionCheckBox('Valgt',self.viewport());self.checkbox.setTristate(True)
        self.checkbox.setAccessibleName('Velg alle synlige varianter')
        self.checkbox.setToolTip('Velg alle synlige rader i denne analysen. Trykk igjen for å fjerne valgene.')
        self.checkbox.setStyleSheet('QCheckBox { background: #EDF2E9; padding: 0; }')
        self.sectionResized.connect(self.position_checkbox)
        self.geometriesChanged.connect(self.position_checkbox)

    def position_checkbox(self,*args):
        self.checkbox.setGeometry(self.sectionViewportPosition(0)+8,0,
            max(0,self.sectionSize(0)-12),self.height())

    def resizeEvent(self,event):
        super().resizeEvent(event);self.position_checkbox()

    def scrollContentsBy(self,dx,dy):
        super().scrollContentsBy(dx,dy);self.position_checkbox()
