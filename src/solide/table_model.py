from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt, pyqtSignal, QSortFilterProxyModel
import csv
import io
from PyQt6.QtGui import QColor
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QApplication, QTableView
from .quality import review_reasons, qc_flags, kind_key

COLUMNS=[('Selected','selected'),('Patient / sample','patient'),('Gene','gene'),('Transcript','transcript'),
         ('Coding','coding'),('Protein','protein'),('AF (%)','af_percent'),('Coverage','coverage'),
         ('Type','kind'),('Call','call'),('Locus','locus'),('Review needed','review'),('Comment','comment')]


class SpreadsheetView(QTableView):
    """Native cell selection and rectangular TSV copying for Excel."""

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Copy):
            indexes = self.selectionModel().selectedIndexes()
            if indexes:
                rows = sorted({index.row() for index in indexes})
                bounds = [index.column() for index in indexes]
                columns = [column for column in range(min(bounds), max(bounds) + 1)
                           if not self.isColumnHidden(column)]
                selected = {(index.row(), index.column()): index for index in indexes}
                output = io.StringIO(newline='')
                writer = csv.writer(output, delimiter='\t', lineterminator='\n')
                for row in range(rows[0], rows[-1] + 1):
                    writer.writerow([selected[row, column].data()
                        if (row, column) in selected else '' for column in columns])
                QApplication.clipboard().setText(output.getvalue().removesuffix('\n'))
            event.accept()
            return
        super().keyPressEvent(event)


class VariantProxy(QSortFilterProxyModel):
    def __init__(self):
        super().__init__();self.patient='';self.query='';self.candidates_only=False
        self.setSortRole(Qt.ItemDataRole.UserRole)

    def set_filters(self,patient,query):
        self.patient=patient if patient!='All patients' else ''
        self.query=query.casefold();self.invalidateFilter()

    def filterAcceptsRow(self,row,parent):
        v=self.sourceModel().variants[row]
        if self.patient and self.patient!=v.patient:return False
        if self.candidates_only and not v.selected:
            if kind_key(v.kind) in {'cnv','rnaexontiles','rnaexonvariant','fusion'}:return False
            if v.platform=='Genexus' and v.call.strip().upper()=='ABSENT':return False
        values=[v.patient,v.gene,v.transcript,v.coding,v.protein,v.kind,v.call,v.locus,v.comment]
        return self.query in ' '.join(str(x) for x in values).casefold()


class VariantTableModel(QAbstractTableModel):
    changed=pyqtSignal()
    def __init__(self,variants=None):
        super().__init__();self.variants=variants or []
    def set_variants(self,variants):
        self.beginResetModel();self.variants=variants;self.endResetModel()
    def rowCount(self,parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.variants)
    def columnCount(self,parent=QModelIndex()):
        return 0 if parent.isValid() else len(COLUMNS)
    def headerData(self,section,orientation,role=Qt.ItemDataRole.DisplayRole):
        if role==Qt.ItemDataRole.DisplayRole:
            return COLUMNS[section][0] if orientation==Qt.Orientation.Horizontal else section+1
    def data(self,index,role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid(): return None
        v=self.variants[index.row()];key=COLUMNS[index.column()][1]
        if role==Qt.ItemDataRole.CheckStateRole and key=='selected':
            return Qt.CheckState.Checked if v.selected else Qt.CheckState.Unchecked
        if role in (Qt.ItemDataRole.DisplayRole,Qt.ItemDataRole.EditRole,Qt.ItemDataRole.UserRole):
            if key=='selected': return ''
            if key=='review': return ', '.join(review_reasons(v))
            value=getattr(v,key)
            if role==Qt.ItemDataRole.DisplayRole and isinstance(value,float): return f'{value:g}'
            return value if value is not None else ''
        if role==Qt.ItemDataRole.BackgroundRole:
            if any(f.status=='Failed' for f in qc_flags(v)):return QColor('#FCE5E3')
            if review_reasons(v) and not v.nomenclature_verified:return QColor('#FFF2D5')
        if role==Qt.ItemDataRole.ToolTipRole:
            return f'{v.platform} · source row {v.source_row}\nAssembly: {v.assembly}\n{v.source_file}'
    def flags(self,index):
        flags=super().flags(index)
        if index.column()==0:flags|=Qt.ItemFlag.ItemIsUserCheckable
        if index.column()==12:flags|=Qt.ItemFlag.ItemIsEditable
        return flags
    def setData(self,index,value,role=Qt.ItemDataRole.EditRole):
        v=self.variants[index.row()]
        if index.column()==0 and role==Qt.ItemDataRole.CheckStateRole:
            v.selected=value==Qt.CheckState.Checked.value or value==Qt.CheckState.Checked
        elif index.column()==12 and role==Qt.ItemDataRole.EditRole:v.comment=str(value)
        else:return False
        self.dataChanged.emit(index,index);self.changed.emit();return True
