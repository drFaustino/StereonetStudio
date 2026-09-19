
# -*- coding: utf-8 -*-
"""
StereonetStudio - tab_stereonet.py

Scheda principale "Stereonet": Input Data (file CSV/TXT o layer vettoriale
con selezione campi), Stereonet Options, Plot Options, Kinematic Analysis
e pulsanti Generate / Clear / Export PNG - come da interfaccia di riferimento.
"""

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QComboBox,
    QCheckBox, QLabel, QLineEdit, QPushButton, QDoubleSpinBox, QScrollArea,
    QStackedWidget, QFileDialog, QMessageBox, QFrame
)

from qgis.core import QgsMapLayerProxyModel, QgsFieldProxyModel
from qgis.gui import QgsMapLayerComboBox, QgsFieldComboBox

from . import settings as cfg
from . import data_io
from . import icons
from . import i18n_labels as trc
from .widgets_common import ColorButton, HintLabel


class StereonetTab(QWidget):

    generate_requested = pyqtSignal()
    clear_requested = pyqtSignal()
    export_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(8, 8, 8, 4)
        lay.setSpacing(10)

        lay.addWidget(self._build_input_data_group())
        lay.addWidget(self._build_stereonet_options_group())
        lay.addWidget(self._build_plot_options_group())
        lay.addWidget(self._build_kinematic_group())
        lay.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        outer.addWidget(self._build_action_bar())

    # ------------------------------------------------------------------
    # Input Data
    # ------------------------------------------------------------------
    def _build_input_data_group(self):
        grp = QGroupBox(self.tr('Input Data'))
        form = QFormLayout(grp)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.cmb_source = QComboBox()
        trc.populate_combo(self.cmb_source, self.tr, cfg.DATA_SOURCE_TYPES)
        form.addRow(self.tr('Source:'), self.cmb_source)

        self.stack_source = QStackedWidget()
        self.stack_source.addWidget(self._build_file_source_page())
        self.stack_source.addWidget(self._build_layer_source_page())
        form.addRow(self.stack_source)
        self.cmb_source.currentIndexChanged.connect(self.stack_source.setCurrentIndex)

        decl_row = QHBoxLayout()
        self.chk_use_declination = QCheckBox(self.tr('Use Declination'))
        self.spn_declination = QDoubleSpinBox()
        self.spn_declination.setRange(-180.0, 180.0)
        self.spn_declination.setDecimals(1)
        self.spn_declination.setSuffix(' °')
        decl_row.addWidget(self.chk_use_declination)
        decl_row.addWidget(self.spn_declination)
        decl_row.addStretch()
        form.addRow(self.tr('Declination:'), decl_row)
        self.chk_use_declination.toggled.connect(self.spn_declination.setEnabled)
        self.spn_declination.setEnabled(False)

        self.lbl_source_hint = HintLabel(
            self.tr('Formato dei campi: vedi "Global Orientation Format" nella sezione Plot Options.'))
        form.addRow(self.lbl_source_hint)

        return grp

    def _build_file_source_page(self):
        page = QWidget()
        form = QFormLayout(page)
        form.setContentsMargins(0, 4, 0, 0)

        row = QHBoxLayout()
        self.txt_csv_path = QLineEdit()
        self.txt_csv_path.setReadOnly(True)
        self.txt_csv_path.setPlaceholderText(self.tr('Nessun file selezionato...'))
        self.btn_browse_csv = QPushButton(icons.icon_folder(), self.tr(' Sfoglia...'))
        self.btn_browse_csv.clicked.connect(self._browse_csv)
        row.addWidget(self.txt_csv_path, 1)
        row.addWidget(self.btn_browse_csv)
        form.addRow(self.tr('File:'), row)

        self.cmb_csv_dip = QComboBox()
        self.cmb_csv_dip.setEditable(True)
        form.addRow(self.tr('Field for Dip:'), self.cmb_csv_dip)

        self.cmb_csv_dipdir = QComboBox()
        self.cmb_csv_dipdir.setEditable(True)
        form.addRow(self.tr('Field for Dip Direction:'), self.cmb_csv_dipdir)

        self.cmb_csv_set = QComboBox()
        self.cmb_csv_set.setEditable(True)
        form.addRow(self.tr('Field for Set/Group:'), self.cmb_csv_set)

        return page

    def _build_layer_source_page(self):
        page = QWidget()
        form = QFormLayout(page)
        form.setContentsMargins(0, 4, 0, 0)

        self.cmb_layer = QgsMapLayerComboBox()
        self.cmb_layer.setFilters(QgsMapLayerProxyModel.Filter.VectorLayer)
        form.addRow(self.tr('Layer:'), self.cmb_layer)

        self.cmb_layer_dip = QgsFieldComboBox()
        self.cmb_layer_dip.setFilters(QgsFieldProxyModel.Filter.Numeric)
        form.addRow(self.tr('Field for Dip:'), self.cmb_layer_dip)

        self.cmb_layer_dipdir = QgsFieldComboBox()
        self.cmb_layer_dipdir.setFilters(QgsFieldProxyModel.Filter.Numeric)
        form.addRow(self.tr('Field for Dip Direction:'), self.cmb_layer_dipdir)

        self.cmb_layer_set = QgsFieldComboBox()
        self.cmb_layer_set.setAllowEmptyFieldName(True)
        form.addRow(self.tr('Field for Set/Group:'), self.cmb_layer_set)

        self.cmb_layer.layerChanged.connect(self.cmb_layer_dip.setLayer)
        self.cmb_layer.layerChanged.connect(self.cmb_layer_dipdir.setLayer)
        self.cmb_layer.layerChanged.connect(self.cmb_layer_set.setLayer)
        if self.cmb_layer.currentLayer() is not None:
            self.cmb_layer_dip.setLayer(self.cmb_layer.currentLayer())
            self.cmb_layer_dipdir.setLayer(self.cmb_layer.currentLayer())
            self.cmb_layer_set.setLayer(self.cmb_layer.currentLayer())

        return page

    def _browse_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, self.tr('Seleziona file dati'), '',
            self.tr('CSV/TXT (*.csv *.txt);;Tutti i file (*.*)'))
        if not path:
            return
        try:
            header, _delim, _has_header = data_io.read_header(path)
        except Exception as exc:
            QMessageBox.warning(
                self,
                self.tr('Errore'),
                self.tr('Impossibile leggere il file:') + '\n{}'.format(exc)
            )
            return

        self.txt_csv_path.setText(path)
        for combo in (self.cmb_csv_dip, self.cmb_csv_dipdir, self.cmb_csv_set):
            combo.clear()

        self.cmb_csv_set.addItem(self.tr('-- Nessuno --'), '')
        for name in header:
            self.cmb_csv_dip.addItem(name, name)
            self.cmb_csv_dipdir.addItem(name, name)
            self.cmb_csv_set.addItem(name, name)

        if len(header) > 0:
            self.cmb_csv_dip.setCurrentIndex(0)
        if len(header) > 1:
            self.cmb_csv_dipdir.setCurrentIndex(1)

    # ------------------------------------------------------------------
    # Stereonet Options
    # ------------------------------------------------------------------
    def _build_stereonet_options_group(self):
        grp = QGroupBox(self.tr('Stereonet Options'))
        form = QFormLayout(grp)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.cmb_overlay = QComboBox()
        trc.populate_combo(self.cmb_overlay, self.tr, cfg.OVERLAY_TYPES)
        form.addRow(self.tr('Stereonet Overlay:'), self.cmb_overlay)

        self.cmb_projection = QComboBox()
        trc.populate_combo(self.cmb_projection, self.tr, cfg.PROJECTION_TYPES)
        form.addRow(self.tr('Projection:'), self.cmb_projection)

        self.cmb_hemisphere = QComboBox()
        trc.populate_combo(self.cmb_hemisphere, self.tr, cfg.HEMISPHERE_TYPES)
        form.addRow(self.tr('Hemisphere:'), self.cmb_hemisphere)

        self.cmb_labels = QComboBox()
        trc.populate_combo(self.cmb_labels, self.tr, cfg.LABEL_MODES)
        form.addRow(self.tr('Labels:'), self.cmb_labels)

        chk_row = QHBoxLayout()
        self.chk_ext_ticks = QCheckBox(self.tr('Exterior Ticks'))
        self.chk_center_cross = QCheckBox(self.tr('Center Cross'))
        chk_row.addWidget(self.chk_ext_ticks)
        chk_row.addWidget(self.chk_center_cross)
        chk_row.addStretch()
        form.addRow(chk_row)

        self.cmb_tick_spacing = QComboBox()
        self.cmb_tick_spacing.addItems(
            ['{}°'.format(t) for t in cfg.TICK_SPACINGS]
        )
        form.addRow(self.tr('Tick Spacing:'), self.cmb_tick_spacing)

        self.cmb_outer_width = QComboBox()
        self.cmb_outer_width.addItems([str(w) for w in cfg.OUTER_GRID_WIDTHS])
        form.addRow(self.tr('Outer Grid Width:'), self.cmb_outer_width)

        self.cmb_overlay_width = QComboBox()
        self.cmb_overlay_width.addItems([str(w) for w in cfg.OVERLAY_WIDTHS])
        form.addRow(self.tr('Overlay Width:'), self.cmb_overlay_width)

        color_row = QHBoxLayout()
        self.btn_bg = ColorButton('#ffffff')
        self.btn_grid = ColorButton('#1a1a1a')

        for lbl, btn in (
            (self.tr('Background'), self.btn_bg),
            (self.tr('Grid Outer'), self.btn_grid)
        ):
            box = QVBoxLayout()
            cap = QLabel(lbl)
            cap.setStyleSheet(
                'font-weight: normal; font-size: 8pt; color:#7f8c8d;'
            )
            box.addWidget(cap, 0, Qt.AlignmentFlag.AlignHCenter)
            box.addWidget(btn, 0, Qt.AlignmentFlag.AlignHCenter)
            color_row.addLayout(box)

        color_row.addStretch()
        form.addRow(self.tr('Colors:'), color_row)

        return grp

    # ------------------------------------------------------------------
    # Plot Options
    # ------------------------------------------------------------------
    def _build_plot_options_group(self):
        grp = QGroupBox(self.tr('Plot Options'))
        form = QFormLayout(grp)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        chk_row = QHBoxLayout()
        self.chk_pole = QCheckBox(self.tr('Poli'))
        self.chk_planes = QCheckBox(self.tr('Piani'))
        self.chk_global_mean = QCheckBox(self.tr('Global Mean'))
        self.chk_best_fit = QCheckBox(self.tr('Global Best Fit'))
        chk_row.addWidget(self.chk_pole)
        chk_row.addWidget(self.chk_planes)
        chk_row.addWidget(self.chk_global_mean)
        chk_row.addWidget(self.chk_best_fit)
        chk_row.addStretch()
        form.addRow(chk_row)

        plot_color_row = QHBoxLayout()
        self.btn_pole = ColorButton('#1f6fb2')
        self.btn_plane = ColorButton('#4a4a4a')
        self.btn_mean = ColorButton('#1b5e20')
        self.btn_best_fit = ColorButton('#0000ff')

        for lbl, btn in (
            (self.tr('Poli'), self.btn_pole),
            (self.tr('Piani'), self.btn_plane),
            (self.tr('Global Mean'), self.btn_mean),
            (self.tr('Global Best Fit'), self.btn_best_fit)
        ):
            box = QVBoxLayout()
            cap = QLabel(lbl)
            cap.setStyleSheet(
                'font-weight: normal; font-size: 8pt; color:#7f8c8d;'
            )
            box.addWidget(cap, 0, Qt.AlignmentFlag.AlignHCenter)
            box.addWidget(btn, 0, Qt.AlignmentFlag.AlignHCenter)
            plot_color_row.addLayout(box)

        plot_color_row.addStretch()
        form.addRow(self.tr('Colors:'), plot_color_row)

        contour_row = QHBoxLayout()
        self.cmb_contours = QComboBox()
        trc.populate_combo(
            self.cmb_contours, self.tr, cfg.CONTOUR_MODES
        )
        self.cmb_contour_style = QComboBox()
        trc.populate_combo(
            self.cmb_contour_style, self.tr, cfg.CONTOUR_STYLES
        )
        contour_row.addWidget(self.cmb_contours, 1)
        contour_row.addWidget(QLabel(self.tr('Contour Style:')))
        contour_row.addWidget(self.cmb_contour_style)
        form.addRow(self.tr('Contours:'), contour_row)

        self.txt_contour_col = QLineEdit()
        self.txt_contour_col.setPlaceholderText(
            self.tr('Nome Set/Colonna da contornare (solo se "Colonna dati")')
        )
        form.addRow(self.tr('Contour Column:'), self.txt_contour_col)

        self.cmb_format = QComboBox()
        trc.populate_combo(
            self.cmb_format, self.tr, cfg.ORIENTATION_FORMATS
        )
        form.addRow(
            self.tr('Global Orientation Format:'), self.cmb_format
        )

        rosette_row = QHBoxLayout()
        self.chk_rosette = QCheckBox(self.tr('Rosette Plot'))
        rosette_row.addWidget(self.chk_rosette)
        rosette_row.addStretch()
        form.addRow(rosette_row)

        # --------------------------------------------------------------
        # Dimensione testo
        #
        # Ogni controllo viene disposto su una riga separata.
        # L'etichetta "Dimensione Testo:" rimane nella colonna sinistra
        # del QFormLayout, mentre i tre controlli sono nella colonna destra.
        # --------------------------------------------------------------
        font_container = QWidget()

        font_form = QFormLayout(font_container)
        font_form.setContentsMargins(0, 0, 0, 0)
        font_form.setHorizontalSpacing(8)
        font_form.setVerticalSpacing(4)
        font_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.spn_font_title = QDoubleSpinBox()
        self.spn_font_title.setRange(6.0, 24.0)
        self.spn_font_title.setDecimals(1)
        self.spn_font_title.setSuffix(' pt')

        self.spn_font_label = QDoubleSpinBox()
        self.spn_font_label.setRange(6.0, 24.0)
        self.spn_font_label.setDecimals(1)
        self.spn_font_label.setSuffix(' pt')

        self.spn_font_elements = QDoubleSpinBox()
        self.spn_font_elements.setRange(5.0, 20.0)
        self.spn_font_elements.setDecimals(1)
        self.spn_font_elements.setSuffix(' pt')

        font_form.addRow(
            self.tr('Titolo:'),
            self.spn_font_title
        )

        font_form.addRow(
            self.tr('Legenda / Densità:'),
            self.spn_font_label
        )

        font_form.addRow(
            self.tr('Elementi / Valori:'),
            self.spn_font_elements
        )

        form.addRow(
            self.tr('Dimensione Testo:'),
            font_container
        )

        return grp

    # ------------------------------------------------------------------
    # Kinematic Analysis
    # ------------------------------------------------------------------
    def _build_kinematic_group(self):
        grp = QGroupBox(self.tr('Kinematic Analysis'))
        grp.setCheckable(True)
        self.grp_kinematic = grp

        form = QFormLayout(grp)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.cmb_kin_mode = QComboBox()
        trc.populate_combo(
            self.cmb_kin_mode, self.tr, cfg.KINEMATIC_MODES
        )
        form.addRow(self.tr('Type:'), self.cmb_kin_mode)

        # Ogni parametro geometrico è ora disposto su una riga separata.
        self.spn_slope_dip = QDoubleSpinBox()
        self.spn_slope_dip.setRange(0.0, 90.0)
        self.spn_slope_dip.setSuffix(' °')
        form.addRow(self.tr('Slope Dip:'), self.spn_slope_dip)

        self.spn_slope_dipdir = QDoubleSpinBox()
        self.spn_slope_dipdir.setRange(0.0, 360.0)
        self.spn_slope_dipdir.setSuffix(' °')
        form.addRow(
            self.tr('Slope Dip Direction:'), self.spn_slope_dipdir
        )

        self.spn_friction = QDoubleSpinBox()
        self.spn_friction.setRange(0.0, 90.0)
        self.spn_friction.setSuffix(' °')
        form.addRow(self.tr('Friction Angle:'), self.spn_friction)

        self.spn_lateral = QDoubleSpinBox()
        self.spn_lateral.setRange(0.0, 90.0)
        self.spn_lateral.setSuffix(' °')
        form.addRow(self.tr('Lateral Limit:'), self.spn_lateral)

        self.chk_construction = QCheckBox(
            self.tr('Show Construction Lines')
        )
        form.addRow(self.chk_construction)

        self.chk_highlight = QCheckBox(self.tr('Show Highlight'))
        form.addRow(self.chk_highlight)

        return grp

    # ------------------------------------------------------------------
    # Barra azioni
    # ------------------------------------------------------------------
    def _build_action_bar(self):
        bar = QFrame()
        bar.setFrameShape(QFrame.Shape.NoFrame)
        row = QHBoxLayout(bar)
        row.setContentsMargins(8, 6, 8, 8)

        self.btn_generate = QPushButton(
            icons.icon_play(color='#ffffff'), self.tr(' Generate')
        )
        self.btn_generate.setObjectName('SNPrimaryButton')

        self.btn_clear = QPushButton(
            icons.icon_clear(), self.tr(' Clear')
        )
        self.btn_clear.setObjectName('SNDangerButton')

        self.btn_export = QPushButton(
            icons.icon_export(), self.tr(' Export PNG')
        )

        self.btn_generate.clicked.connect(self.generate_requested.emit)
        self.btn_clear.clicked.connect(self.clear_requested.emit)
        self.btn_export.clicked.connect(self.export_requested.emit)

        row.addWidget(self.btn_generate, 1)
        row.addWidget(self.btn_clear)
        row.addWidget(self.btn_export)

        return bar

    # ------------------------------------------------------------------
    # Sincronizzazione con il dizionario 'settings'
    # ------------------------------------------------------------------
    def set_from_settings(self, s):
        trc.set_combo_value(self.cmb_source, s['data_source'])
        self.stack_source.setCurrentIndex(self.cmb_source.currentIndex())
        self.txt_csv_path.setText(s.get('csv_path', ''))
        self.chk_use_declination.setChecked(
            s.get('use_declination', False)
        )
        self.spn_declination.setValue(s.get('declination', 0.0))

        trc.set_combo_value(self.cmb_overlay, s['overlay'])
        trc.set_combo_value(self.cmb_projection, s['projection'])
        trc.set_combo_value(self.cmb_hemisphere, s['hemisphere'])
        trc.set_combo_value(self.cmb_labels, s['labels'])
        self.chk_ext_ticks.setChecked(s['exterior_ticks'])
        self.chk_center_cross.setChecked(s['center_cross'])
        self.cmb_tick_spacing.setCurrentText(
            '{}°'.format(s['tick_spacing'])
        )
        self.cmb_outer_width.setCurrentText(
            str(s['outer_grid_width'])
        )
        self.cmb_overlay_width.setCurrentText(
            str(s['overlay_width'])
        )
        self.btn_bg.set_color(s['color_background'])
        self.btn_grid.set_color(s['color_grid_outer'])
        self.btn_mean.set_color(
            s.get('color_global_mean', '#1b5e20')
        )

        self.chk_pole.setChecked(s['show_pole'])
        self.chk_planes.setChecked(s.get('show_planes', False))
        self.btn_pole.set_color(s.get('color_pole', '#1f6fb2'))
        self.btn_plane.set_color(s.get('color_plane', '#4a4a4a'))
        self.chk_global_mean.setChecked(s['show_global_mean'])
        self.chk_best_fit.setChecked(s.get('show_best_fit', False))
        self.btn_best_fit.set_color(s.get('color_best_fit', '#0000ff'))
        trc.set_combo_value(self.cmb_contours, s['contour_mode'])
        trc.set_combo_value(
            self.cmb_contour_style, s['contour_style']
        )
        self.txt_contour_col.setText(s.get('contour_column', ''))
        trc.set_combo_value(
            self.cmb_format, s['orientation_format']
        )
        self.chk_rosette.setChecked(s['show_rosette'])

        self.spn_font_title.setValue(
            s.get('font_size_title', 9.0)
        )
        self.spn_font_label.setValue(
            s.get('font_size_label', 8.5)
        )
        self.spn_font_elements.setValue(
            s.get('font_size_elements', 7.0)
        )

        self.grp_kinematic.setChecked(s['kinematic_enabled'])
        trc.set_combo_value(
            self.cmb_kin_mode, s['kinematic_mode']
        )
        self.spn_slope_dip.setValue(s['slope_dip'])
        self.spn_slope_dipdir.setValue(s['slope_dipdir'])
        self.spn_friction.setValue(s['friction_angle'])
        self.spn_lateral.setValue(s['lateral_limit'])
        self.chk_construction.setChecked(
            s['show_construction_lines']
        )
        self.chk_highlight.setChecked(s['show_highlight'])

    def get_settings(self, base_settings):
        s = dict(base_settings)
        s['data_source'] = trc.combo_value(self.cmb_source)
        s['csv_path'] = self.txt_csv_path.text()
        s['csv_col_dip'] = self.cmb_csv_dip.currentText()
        s['csv_col_dipdir'] = self.cmb_csv_dipdir.currentText()
        s['csv_col_set'] = trc.combo_value(self.cmb_csv_set) or ''

        layer = self.cmb_layer.currentLayer()
        s['vector_layer_id'] = layer.id() if layer is not None else ''
        s['vector_field_dip'] = self.cmb_layer_dip.currentField()
        s['vector_field_dipdir'] = self.cmb_layer_dipdir.currentField()
        s['vector_field_set'] = self.cmb_layer_set.currentField()

        s['use_declination'] = self.chk_use_declination.isChecked()
        s['declination'] = self.spn_declination.value()

        s['overlay'] = trc.combo_value(self.cmb_overlay)
        s['projection'] = trc.combo_value(self.cmb_projection)
        s['hemisphere'] = trc.combo_value(self.cmb_hemisphere)
        s['labels'] = trc.combo_value(self.cmb_labels)
        s['exterior_ticks'] = self.chk_ext_ticks.isChecked()
        s['center_cross'] = self.chk_center_cross.isChecked()
        s['tick_spacing'] = int(
            self.cmb_tick_spacing.currentText().replace('°', '')
        )
        s['outer_grid_width'] = int(
            self.cmb_outer_width.currentText()
        )
        s['overlay_width'] = int(
            self.cmb_overlay_width.currentText()
        )
        s['color_background'] = self.btn_bg.color_hex()
        s['color_grid_outer'] = self.btn_grid.color_hex()
        s['color_global_mean'] = self.btn_mean.color_hex()

        s['show_pole'] = self.chk_pole.isChecked()
        s['show_planes'] = self.chk_planes.isChecked()
        s['color_pole'] = self.btn_pole.color_hex()
        s['color_plane'] = self.btn_plane.color_hex()
        s['show_global_mean'] = self.chk_global_mean.isChecked()
        s['show_best_fit'] = self.chk_best_fit.isChecked()
        s['color_best_fit'] = self.btn_best_fit.color_hex()
        s['contour_mode'] = trc.combo_value(self.cmb_contours)
        s['contour_style'] = trc.combo_value(
            self.cmb_contour_style
        )
        s['contour_column'] = self.txt_contour_col.text().strip()
        s['orientation_format'] = trc.combo_value(self.cmb_format)
        s['show_rosette'] = self.chk_rosette.isChecked()

        s['font_size_title'] = self.spn_font_title.value()
        s['font_size_label'] = self.spn_font_label.value()
        s['font_size_elements'] = self.spn_font_elements.value()

        s['kinematic_enabled'] = self.grp_kinematic.isChecked()
        s['kinematic_mode'] = trc.combo_value(self.cmb_kin_mode)
        s['slope_dip'] = self.spn_slope_dip.value()
        s['slope_dipdir'] = self.spn_slope_dipdir.value()
        s['friction_angle'] = self.spn_friction.value()
        s['lateral_limit'] = self.spn_lateral.value()
        s['show_construction_lines'] = (
            self.chk_construction.isChecked()
        )
        s['show_highlight'] = self.chk_highlight.isChecked()

        return s

    # ------------------------------------------------------------------
    # Lettura dei dati in base alla sorgente selezionata
    # ------------------------------------------------------------------
    def load_data_rows(self):
        """Legge i dati dalla sorgente configurata (file o layer vettoriale).
        Ritorna (rows, status_message)."""
        if self.cmb_source.currentIndex() == 0:
            path = self.txt_csv_path.text().strip()
            if not path:
                return [], self.tr('Nessun file selezionato.')

            col_dip = self.cmb_csv_dip.currentText()
            col_dipdir = self.cmb_csv_dipdir.currentText()
            col_set = trc.combo_value(self.cmb_csv_set) or None

            try:
                rows = data_io.read_csv_rows(
                    path, col_dip, col_dipdir, col_set
                )
            except Exception as exc:
                return [], self.tr(
                    'Errore lettura file: {}'
                ).format(exc)

            return rows, self.tr(
                '{} misure lette da {}.'
            ).format(len(rows), path.split('/')[-1])

        else:
            layer = self.cmb_layer.currentLayer()
            if layer is None:
                return [], self.tr(
                    'Nessun layer vettoriale selezionato.'
                )

            field_dip = self.cmb_layer_dip.currentField()
            field_dipdir = self.cmb_layer_dipdir.currentField()
            field_set = self.cmb_layer_set.currentField() or None

            if not field_dip or not field_dipdir:
                return [], self.tr(
                    'Seleziona i campi Dip e Dip Direction del layer.'
                )

            rows, used_sel, n_source = data_io.read_vector_layer_rows(
                layer,
                field_dip,
                field_dipdir,
                field_set,
                prefer_selected=True
            )

            if used_sel:
                msg = self.tr(
                    '{} feature(s) selected on layer {}.'
                ).format(n_source, layer.name())
            else:
                msg = self.tr(
                    '{} feature(s) on layer {} (nessuna selezione attiva).'
                ).format(n_source, layer.name())

            return rows, msg
