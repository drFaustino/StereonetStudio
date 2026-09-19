# -*- coding: utf-8 -*-
"""
StereonetStudio - tab_kinematic_results.py

Scheda "Kinematic Analysis": riepilogo testuale del criterio applicato e
tabella dei dati con l'esito (critico / non critico) della verifica.
"""

from qgis.PyQt.QtGui import QColor, QBrush
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame
)

class KinematicResultsTab(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel(self.tr('Risultati Analisi Cinematica'))
        title.setStyleSheet('font-weight: 600; font-size: 10.5pt; color:#1f6fb2;')
        layout.addWidget(title)

        self.lbl_mode = QLabel(self.tr('Analisi non attiva.'))
        self.lbl_mode.setStyleSheet('font-weight: 600; color:#2c3e50;')
        layout.addWidget(self.lbl_mode)

        self.lbl_description = QLabel('')
        self.lbl_description.setWordWrap(True)
        self.lbl_description.setStyleSheet('color:#45505c;')
        layout.addWidget(self.lbl_description)

        line = QFrame(); line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet('color:#d5dbe2;')
        layout.addWidget(line)

        self.lbl_count = QLabel('')
        self.lbl_count.setStyleSheet('font-weight: 600; color:#c0392b;')
        layout.addWidget(self.lbl_count)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            [self.tr('Dip Direction'), self.tr('Dip'), self.tr('Set'), self.tr('Esito')])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table, 1)

    def clear_results(self):
        self.lbl_mode.setText(self.tr('Analisi non attiva.'))
        self.lbl_description.setText(self.tr('Attiva "Kinematic Analysis" nella scheda Stereonet e premi Generate.'))
        self.lbl_count.setText('')
        self.table.setRowCount(0)

    def show_results(self, mode, description, planes, feasible_mask, n_feasible):
        self.lbl_mode.setText(self.tr("Modalità: {}").format(mode))
        self.lbl_description.setText(description)
        n_tot = len(planes)
        self.lbl_count.setText(self.tr('Elementi critici: {} su {} misure.').format(n_feasible, n_tot))

        self.table.setRowCount(0)
        if feasible_mask is None:
            return
        for p, feasible in zip(planes, feasible_mask):
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem('{:.1f}°'.format(p['dipdir'])))
            self.table.setItem(r, 1, QTableWidgetItem('{:.1f}°'.format(p['dip'])))
            self.table.setItem(r, 2, QTableWidgetItem(str(p.get('set', ''))))
            esito = QTableWidgetItem(self.tr('CRITICO') if feasible else self.tr('OK'))
            if feasible:
                esito.setForeground(QBrush(QColor('#c0392b')))
            else:
                esito.setForeground(QBrush(QColor('#2e8b57')))
            self.table.setItem(r, 3, esito)
