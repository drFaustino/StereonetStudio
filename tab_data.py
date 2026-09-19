# -*- coding: utf-8 -*-
"""
StereonetStudio - tab_data.py

Scheda "Data": editor tabellare manuale dei dati di giacitura, con
importazione/esportazione CSV e formato di orientazione selezionabile.
Utile per inserimento diretto o per rivedere/correggere i dati caricati
da file o da layer vettoriale.
"""

import csv

from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QComboBox, QFileDialog, QMessageBox, QHeaderView
)

from . import settings as cfg
from . import icons
from . import i18n_labels as trc
from .widgets_common import HintLabel


class DataTab(QWidget):

    apply_requested = pyqtSignal(list, str)  # rows, formato

    COLS = ['Valore 1', 'Valore 2', 'Set / Gruppo']

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel(self.tr('Editor Dati di Giacitura'))
        title.setStyleSheet('font-weight: 600; font-size: 10.5pt; color:#1f6fb2;')
        layout.addWidget(title)

        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel(self.tr('Formato inserimento:')))
        self.cmb_format = QComboBox()
        trc.populate_combo(self.cmb_format, self.tr, cfg.ORIENTATION_FORMATS)
        fmt_row.addWidget(self.cmb_format, 1)
        layout.addLayout(fmt_row)

        self.lbl_hint = HintLabel('')
        layout.addWidget(self.lbl_hint)
        self.cmb_format.currentIndexChanged.connect(lambda _i: self._update_hint(trc.combo_value(self.cmb_format)))
        self._update_hint(trc.combo_value(self.cmb_format))

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(
            [self.tr('Valore 1'), self.tr('Valore 2'), self.tr('Set / Gruppo')])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton(icons.icon_add(), self.tr(' Aggiungi riga'))
        self.btn_del = QPushButton(icons.icon_remove(), self.tr(' Elimina riga'))
        self.btn_import = QPushButton(icons.icon_import(), self.tr(' Importa CSV...'))
        self.btn_export = QPushButton(icons.icon_export(), self.tr(' Esporta CSV...'))
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_del)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_import)
        btn_row.addWidget(self.btn_export)
        layout.addLayout(btn_row)

        self.btn_add.clicked.connect(self._add_row)
        self.btn_del.clicked.connect(self._del_row)
        self.btn_import.clicked.connect(self._import_csv)
        self.btn_export.clicked.connect(self._export_csv)

        apply_row = QHBoxLayout()
        apply_row.addStretch()
        self.btn_apply = QPushButton(icons.icon_play(color='#ffffff'), self.tr(' Applica e Ridisegna'))
        self.btn_apply.setObjectName('SNPrimaryButton')
        self.btn_apply.clicked.connect(self._emit_apply)
        apply_row.addWidget(self.btn_apply)
        layout.addLayout(apply_row)

    def _update_hint(self, fmt):
        hints = {
            'Dip / Direzione Immersione': self.tr('Valore 1 = Dip (0-90), Valore 2 = Direzione di immersione (0-360)'),
            'Direzione (destra) / Dip': self.tr('Valore 1 = Direzione/Strike (regola mano destra), Valore 2 = Dip'),
            'Direzione (sinistra) / Dip': self.tr('Valore 1 = Direzione/Strike (regola mano sinistra), Valore 2 = Dip'),
            'Trend / Plunge': self.tr('Valore 1 = Trend (0-360), Valore 2 = Plunge (0-90) del polo/linea'),
        }
        self.lbl_hint.setText(hints.get(fmt, ''))

    def _add_row(self, v1=0.0, v2=0.0, s='Set 1'):
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r, 0, QTableWidgetItem(str(v1)))
        self.table.setItem(r, 1, QTableWidgetItem(str(v2)))
        self.table.setItem(r, 2, QTableWidgetItem(str(s)))

    def _del_row(self):
        rows = sorted(set(i.row() for i in self.table.selectedIndexes()), reverse=True)
        for r in rows:
            self.table.removeRow(r)

    def load_rows(self, data_rows, fmt=None):
        self.table.setRowCount(0)
        for row in data_rows:
            self._add_row(row.get('v1', 0.0), row.get('v2', 0.0), row.get('set', 'Set 1'))
        if fmt:
            trc.set_combo_value(self.cmb_format, fmt)

    def _import_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, self.tr('Importa CSV'), '', self.tr('CSV/TXT (*.csv *.txt);;Tutti i file (*.*)'))
        if not path:
            return
        try:
            with open(path, newline='', encoding='utf-8-sig') as f:
                sample = f.readline()
                delim = ';' if ';' in sample else ('\t' if '\t' in sample else ',')
                f.seek(0)
                reader = csv.reader(f, delimiter=delim)
                rows = list(reader)
        except Exception as exc:
            QMessageBox.warning(self, self.tr('Errore'), self.tr('Impossibile leggere il file:') + '\n{}'.format(exc))
            return
        start = 0
        if rows and not _is_number(rows[0][0] if rows[0] else ''):
            start = 1
        count = 0
        for row in rows[start:]:
            if len(row) < 2:
                continue
            try:
                v1 = float(row[0].replace(',', '.'))
                v2 = float(row[1].replace(',', '.'))
            except ValueError:
                continue
            s = row[2].strip() if len(row) > 2 and row[2].strip() else 'Set 1'
            self._add_row(v1, v2, s)
            count += 1
        QMessageBox.information(self, self.tr('Importazione completata'), self.tr('{} righe importate.').format(count))

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, self.tr('Esporta CSV'), 'dati_stereonet.csv', self.tr('CSV (*.csv)'))
        if not path:
            return
        try:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Valore1', 'Valore2', 'Set'])
                for row in self.get_rows():
                    writer.writerow([row['v1'], row['v2'], row['set']])
        except Exception as exc:
            QMessageBox.warning(self, self.tr('Errore'), self.tr('Impossibile scrivere il file:') + '\n{}'.format(exc))

    def get_rows(self):
        out = []
        for r in range(self.table.rowCount()):
            try:
                v1 = float(self.table.item(r, 0).text().replace(',', '.'))
                v2 = float(self.table.item(r, 1).text().replace(',', '.'))
            except (ValueError, AttributeError):
                continue
            set_item = self.table.item(r, 2)
            s = set_item.text().strip() if set_item and set_item.text().strip() else 'Set 1'
            out.append({'v1': v1, 'v2': v2, 'set': s})
        return out

    def get_format(self):
        return trc.combo_value(self.cmb_format)

    def _emit_apply(self):
        self.apply_requested.emit(self.get_rows(), self.get_format())


def _is_number(s):
    try:
        float(str(s).replace(',', '.'))
        return True
    except ValueError:
        return False
