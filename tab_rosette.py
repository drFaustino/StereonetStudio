# -*- coding: utf-8 -*-
"""
StereonetStudio - tab_rosette.py

Scheda "Rosette": diagramma a rosa delle direzioni dedicato, a grandezza
maggiore rispetto all'inserto sul plot principale, con statistiche
(direzione media, numero di misure) e ampiezza delle classi selezionabile.
"""

import numpy as np

import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
                                 QCheckBox, QSpinBox)

from . import settings as cfg
from . import stereonet_math as sm


class RosetteTab(QWidget):

    options_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel(self.tr('Rosette Plot'))
        title.setStyleSheet('font-weight: 600; font-size: 10.5pt; color:#1f6fb2;')
        layout.addWidget(title)

        opts_row = QHBoxLayout()
        opts_row.addWidget(QLabel(self.tr('Ampiezza classi:')))
        self.cmb_bin_width = QComboBox()
        self.cmb_bin_width.addItems(['{}°'.format(w) for w in cfg.ROSETTE_BIN_WIDTHS])
        self.cmb_bin_width.setCurrentText('10°')
        opts_row.addWidget(self.cmb_bin_width)
        opts_row.addSpacing(16)
        self.chk_show_on_plot = QCheckBox(self.tr('Mostra anche sul plot principale'))
        opts_row.addWidget(self.chk_show_on_plot)
        opts_row.addStretch()
        layout.addLayout(opts_row)

        # Dato rappresentato (Dips: "Plot Data = Apparent Strike") e filtro sul dip
        # (Dips: "Minimum / Maximum Angle To Plot").
        opts_row2 = QHBoxLayout()
        opts_row2.addWidget(QLabel(self.tr('Dato:')))
        self.cmb_data = QComboBox()
        self.cmb_data.addItem(self.tr('Strike'), 'strike')
        self.cmb_data.addItem(self.tr('Direzione di immersione'), 'dipdir')
        opts_row2.addWidget(self.cmb_data)
        opts_row2.addSpacing(16)
        opts_row2.addWidget(QLabel(self.tr('Dip min:')))
        self.spn_min_dip = QSpinBox()
        self.spn_min_dip.setRange(0, 90)
        self.spn_min_dip.setValue(0)
        self.spn_min_dip.setSuffix('°')
        opts_row2.addWidget(self.spn_min_dip)
        opts_row2.addWidget(QLabel(self.tr('Dip max:')))
        self.spn_max_dip = QSpinBox()
        self.spn_max_dip.setRange(0, 90)
        self.spn_max_dip.setValue(90)
        self.spn_max_dip.setSuffix('°')
        opts_row2.addWidget(self.spn_max_dip)
        opts_row2.addStretch()
        layout.addLayout(opts_row2)

        self.cmb_bin_width.currentTextChanged.connect(lambda _t: self.options_changed.emit())
        self.chk_show_on_plot.toggled.connect(lambda _c: self.options_changed.emit())
        self.cmb_data.currentIndexChanged.connect(lambda _i: self.options_changed.emit())
        self.spn_min_dip.valueChanged.connect(lambda _v: self.options_changed.emit())
        self.spn_max_dip.valueChanged.connect(lambda _v: self.options_changed.emit())

        self.figure = Figure(figsize=(5, 5), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas, 1)

        self.lbl_info = QLabel(self.tr('Nessun dato.'))
        self.lbl_info.setObjectName('SNRosetteInfo')
        self.lbl_info.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.lbl_info)

    def data_mode(self):
        return self.cmb_data.currentData() or 'strike'

    def angles(self, planes):
        """Angoli da rappresentare (strike o dipdir), dopo il filtro sul dip.
        Ritorna (lista_angoli, modalita')."""
        mode = self.data_mode()
        return sm.rosette_angles(planes, mode, self.spn_min_dip.value(), self.spn_max_dip.value()), mode

    def bin_width(self):
        return int(self.cmb_bin_width.currentText().replace('°', ''))

    def show_on_main_plot(self):
        return self.chk_show_on_plot.isChecked()

    def set_show_on_main_plot(self, value):
        self.chk_show_on_plot.setChecked(value)

    def set_bin_width(self, value):
        self.cmb_bin_width.setCurrentText('{}°'.format(value))

    def redraw(self, planes):
        self.figure.clear()
        if not planes:
            self.lbl_info.setText(self.tr('Nessun dato caricato.'))
            self.canvas.draw_idle()
            return

        angles, mode = self.angles(planes)
        bw = self.bin_width()
        counts, bin_width = sm.rosette_bins(angles, bin_width=bw)

        ax = self.figure.add_subplot(111, projection='polar')
        ax.set_theta_zero_location('N')
        ax.set_theta_direction(-1)
        theta = np.deg2rad(np.arange(0, 360, bin_width))
        width = np.deg2rad(bin_width)
        ax.bar(theta, counts, width=width, bottom=0.0, color='#1f6fb2', edgecolor='#0d3a5c',
               linewidth=0.4, alpha=0.85)
        ax.set_yticklabels([])
        ax.tick_params(labelsize=8)
        ax.set_title(self.tr('N = {}').format(len(angles)), fontsize=9, pad=14)
        self.figure.tight_layout()
        self.canvas.draw_idle()

        if mode == 'strike':
            mean_dir = sm.axial_mean_deg(angles)
        else:
            mean_dir = sm.circular_mean_deg(angles)
        if mean_dir is not None:
            self.lbl_info.setText(self.tr('Mean: {:.0f}°   n = {}').format(mean_dir, len(angles)))
        else:
            self.lbl_info.setText(self.tr('n = {}').format(len(angles)))
