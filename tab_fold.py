# -*- coding: utf-8 -*-
"""
StereonetStudio - tab_fold.py

Scheda "Folds": analisi della piega (asse beta, piano assiale da L1/L2,
suggerimento automatico dei poli dei fianchi), visibilita' dei contorni di
densita' (trasparenza / enfasi delle basse densita') e cursore piano live.
"""

from qgis.PyQt.QtCore import Qt, pyqtSignal, QTimer
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QCheckBox,
    QLabel, QPushButton, QSlider, QScrollArea, QComboBox
)

from . import icons
from .widgets_common import HintLabel


class FoldTab(QWidget):

    # emesso (con ritardo, per non ridisegnare a ogni scatto) quando cambia
    # uno slider o un'opzione di visualizzazione
    display_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(120)
        self._debounce.timeout.connect(self.display_changed.emit)
        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(10)

        lay.addWidget(self._build_density_group())
        lay.addWidget(self._build_suggest_group())
        lay.addWidget(self._build_axial_group())
        lay.addWidget(self._build_live_group())
        lay.addWidget(self._build_saved_group())
        lay.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)

    # ------------------------------------------------------------------
    def _slider(self, value):
        sl = QSlider(Qt.Orientation.Horizontal)
        sl.setRange(0, 100)
        sl.setValue(value)
        sl.setSingleStep(1)
        sl.setPageStep(10)
        sl.valueChanged.connect(lambda *_: self._debounce.start())
        return sl

    def _build_density_group(self):
        grp = QGroupBox(self.tr('Pole density contours'))
        form = QFormLayout(grp)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.chk_contours = QCheckBox(self.tr('Show pole density contours'))
        form.addRow(self.chk_contours)

        row = QHBoxLayout()
        self.sld_transparency = self._slider(15)
        self.lbl_transparency = QLabel()
        self.lbl_transparency.setMinimumWidth(38)
        row.addWidget(self.sld_transparency, 1)
        row.addWidget(self.lbl_transparency)
        form.addRow(self.tr('Transparency:'), row)

        row = QHBoxLayout()
        self.sld_emphasis = self._slider(0)
        self.lbl_emphasis = QLabel()
        self.lbl_emphasis.setMinimumWidth(38)
        row.addWidget(self.sld_emphasis, 1)
        row.addWidget(self.lbl_emphasis)
        form.addRow(self.tr('Low-density emphasis:'), row)

        row = QHBoxLayout()
        self.sld_pole_fade = self._slider(0)
        self.lbl_pole_fade = QLabel()
        self.lbl_pole_fade.setMinimumWidth(38)
        row.addWidget(self.sld_pole_fade, 1)
        row.addWidget(self.lbl_pole_fade)
        form.addRow(self.tr('Pole marker fade:'), row)

        self.sld_transparency.valueChanged.connect(self._update_slider_labels)
        self.sld_emphasis.valueChanged.connect(self._update_slider_labels)
        self.sld_pole_fade.valueChanged.connect(self._update_slider_labels)
        self._update_slider_labels()

        form.addRow(HintLabel(self.tr(
            'Transparency fades the contour fill so poles and great circles show through. '
            'Low-density emphasis packs more contour levels into the low end of the scale, '
            'so sparse pole concentrations are coloured instead of disappearing. '
            'Pole marker fade makes the data poles semi-transparent so the contours '
            'underneath can be seen (picked, suggested and mean markers stay solid).')))
        return grp

    def _update_slider_labels(self, *args):
        self.lbl_transparency.setText('{} %'.format(self.sld_transparency.value()))
        self.lbl_emphasis.setText('{} %'.format(self.sld_emphasis.value()))
        self.lbl_pole_fade.setText('{} %'.format(self.sld_pole_fade.value()))

    # ------------------------------------------------------------------
    def _build_suggest_group(self):
        grp = QGroupBox(self.tr('Suggested limb poles'))
        lay = QVBoxLayout(grp)

        row = QHBoxLayout()
        row.addWidget(QLabel(self.tr('Data:')))
        self.cmb_suggest_set = QComboBox()
        self.cmb_suggest_set.addItem(self.tr('All sets'), '')
        self.cmb_suggest_set.currentIndexChanged.connect(lambda *_: self._debounce.start())
        row.addWidget(self.cmb_suggest_set, 1)
        lay.addLayout(row)

        self.chk_show_suggest = QCheckBox(self.tr('Show suggested L1 / L2 on the stereonet'))
        self.chk_show_suggest.setChecked(True)
        self.chk_show_suggest.toggled.connect(lambda *_: self._debounce.start())
        lay.addWidget(self.chk_show_suggest)

        self.btn_use_suggest = QPushButton(self.tr('Use suggested limbs → compute axial plane'))
        lay.addWidget(self.btn_use_suggest)

        self.lbl_suggest = QLabel(self.tr('No suggestion (load at least 4 poles).'))
        self.lbl_suggest.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.lbl_suggest)

        lay.addWidget(HintLabel(self.tr(
            'The poles are split into the two limb populations (two-cluster axial '
            'k-means on the sphere); each suggestion is the mean pole of its cluster. '
            'Suggestions are also snap targets when picking L1 / L2 manually.')))
        return grp

    def set_available_sets(self, names):
        current = self.cmb_suggest_set.currentData()
        self.cmb_suggest_set.blockSignals(True)
        self.cmb_suggest_set.clear()
        self.cmb_suggest_set.addItem(self.tr('All sets'), '')
        for n in names:
            self.cmb_suggest_set.addItem(str(n), str(n))
        idx = self.cmb_suggest_set.findData(current)
        self.cmb_suggest_set.setCurrentIndex(idx if idx >= 0 else 0)
        self.cmb_suggest_set.blockSignals(False)

    def suggest_set(self):
        return self.cmb_suggest_set.currentData() or ''

    # ------------------------------------------------------------------
    def _build_axial_group(self):
        grp = QGroupBox(self.tr('Axial plane from limbs'))
        lay = QVBoxLayout(grp)
        lay.setSpacing(6)

        row1 = QHBoxLayout()
        self.btn_pick_limbs = QPushButton(self.tr('Pick L1 / L2 limb poles'))
        self.btn_pick_limbs.setCheckable(True)
        self.btn_pick_limbs.setToolTip(self.tr(
            'Click the pole to limb 1, then the pole to limb 2 on the stereonet. '
            'The fold axis (L1∩L2) and the axial plane (bisector of the limbs) are '
            'computed automatically. Right-click to cancel.'))
        self.btn_swap_axial = QPushButton(self.tr('Swap bisector'))
        self.btn_swap_axial.setToolTip(self.tr(
            'Two planes bisect the limbs (90° apart). The steeper one is used by '
            'default; swap if your fold is recumbent/reclined.'))
        row1.addWidget(self.btn_pick_limbs, 1)
        row1.addWidget(self.btn_swap_axial)
        lay.addLayout(row1)

        self.chk_snap = QCheckBox(self.tr('Snap to nearest pole / mean / β / suggestion'))
        self.chk_snap.setChecked(True)
        lay.addWidget(self.chk_snap)
        self.chk_show_alt_axial = QCheckBox(self.tr('Show alternate axial plane'))
        self.chk_show_alt_axial.setChecked(True)
        lay.addWidget(self.chk_show_alt_axial)

        self.lbl_fold_result = QLabel(self.tr('No fold defined.'))
        self.lbl_fold_result.setWordWrap(True)
        self.lbl_fold_result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.lbl_fold_result)
        return grp

    # ------------------------------------------------------------------
    def _build_live_group(self):
        grp = QGroupBox(self.tr('Live plane cursor'))
        lay = QVBoxLayout(grp)
        self.btn_live_plane = QPushButton(self.tr('Live plane cursor'))
        self.btn_live_plane.setCheckable(True)
        self.btn_live_plane.setToolTip(self.tr(
            'Move the cursor to a pole position: the pole and its great circle are '
            'updated live. Left-click saves the pole and plane; right-click exits.'))
        lay.addWidget(self.btn_live_plane)
        self.lbl_live = QLabel(self.tr('Pole: –   Plane: –'))
        self.lbl_live.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.lbl_live)
        return grp

    # ------------------------------------------------------------------
    def _build_saved_group(self):
        grp = QGroupBox(self.tr('Saved picks'))
        lay = QVBoxLayout(grp)
        row = QHBoxLayout()
        self.btn_clear_picks = QPushButton(icons.icon_clear(), self.tr(' Clear picks from plot'))
        self.btn_export_picks = QPushButton(icons.icon_export(), self.tr(' Export picks CSV'))
        row.addWidget(self.btn_clear_picks)
        row.addWidget(self.btn_export_picks)
        lay.addLayout(row)
        lay.addWidget(HintLabel(self.tr(
            'Saved picks (L1, L2, fold axis, axial plane, cursor planes) are written to '
            'the "StereonetStudio picks" table layer in the project. Clearing the plot '
            'does not delete them from the layer.')))
        return grp
