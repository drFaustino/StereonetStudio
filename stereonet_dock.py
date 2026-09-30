# -*- coding: utf-8 -*-
"""
StereonetStudio - stereonet_dock.py

Dock widget principale: pannello laterale a schede
(Stereonet, DTM, Data, Kinematic Analysis, Rosette)
+ area di disegno con proiezione stereografica.

Caratteristiche principali:
- titolo sempre interamente visibile;
- legenda in alto a sinistra, sotto al titolo;
- scala di densità posizionata in alto a destra;
- rosetta opzionale sul plot principale;
- acquisizione DTM tramite map tool QGIS;
- analisi cinematica;
- Global Mean e Global Best Fit;
- esportazione PNG/JPEG/SVG/PDF.
"""

import logging
import math

import numpy as np

import matplotlib

matplotlib.use('QtAgg')

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import Polygon, Circle
from matplotlib.lines import Line2D
from matplotlib.colors import ListedColormap

from qgis.PyQt.QtCore import Qt, QSize, QTimer
from qgis.PyQt.QtGui import QColor, QGuiApplication
from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QLabel,
    QFileDialog,
    QMessageBox,
    QSizePolicy,
    QTabWidget,
    QToolButton,
    QFrame,
)

from qgis.gui import QgsRubberBand

from qgis.core import (
    QgsWkbTypes,
    QgsCoordinateTransform,
    QgsPointXY,
    QgsProject,
    QgsGeometry,
)

from . import stereonet_math as sm
from . import icons
from . import i18n_labels as trc
from .style import STYLE_SHEET
from .settings import new_settings
from .tab_stereonet import StereonetTab
from .tab_data import DataTab
from .tab_dtm import DTMTab
from .dtm_acquisition import DTMMapTool
from .tab_kinematic_results import KinematicResultsTab
from .tab_rosette import RosetteTab


LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Palette densità in stile Dips
# ----------------------------------------------------------------------

DIPS_DENSITY_COLORS = [
    '#e9ebf1',
    '#d5eaee',
    '#b4ece0',
    '#98f0c6',
    '#8bee9d',
    '#82ee6c',
    '#c6f04f',
    '#ffe23f',
    '#ff8a1f',
    '#ff0000',
]

DIPS_DENSITY_CMAP = ListedColormap(
    DIPS_DENSITY_COLORS,
    name='dips_density',
)


# Colori dei diversi set
SET_COLORS = [
    '#1f6fb2',
    '#e67e22',
    '#27ae60',
    '#8e44ad',
    '#c0392b',
    '#16a085',
    '#d4ac0d',
    '#7f8c8d',
    '#2c3e50',
    '#e91e8c',
]


def font_elements_bm(settings):
    """
    Restituisce la dimensione del carattere usata per l'etichetta
    del Global Best Fit.
    """
    return settings.get(
        'font_size_elements',
        7.0,
    ) + 1


class StereonetDock(QDockWidget):

    # ==================================================================
    # INIT
    # ==================================================================

    def __init__(self, iface, parent=None):
        super().__init__(
            'StereonetStudio',
            parent,
        )

        self.setWindowTitle(
            self.tr('StereonetStudio')
        )

        self.iface = iface

        self.setObjectName(
            'StereonetStudioDock'
        )

        self.settings = new_settings()

        # [{'v1': ..., 'v2': ..., 'set': ...}, ...]
        self.data_rows = []

        # Stato acquisizione DTM
        self.dtm_map_tool = None
        self._previous_map_tool = None
        self.dtm_preview = None
        self._dtm_was_visible = True

        # Valore usato per l'eventuale colorbar/densità
        self.last_density_max = 0.0

        self._build_ui()

        self.resize(
            900,
            700,
        )

        self.kinematic_tab.clear_results()

        self.redraw()

    # ==================================================================
    # UI
    # ==================================================================

    def _build_ui(self):
        self._build_title_bar()

        root = QWidget()
        root.setObjectName(
            'SNRoot'
        )
        root.setStyleSheet(
            STYLE_SHEET
        )

        outer = QVBoxLayout(root)

        outer.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        outer.setSpacing(0)

        splitter = QSplitter(
            Qt.Orientation.Horizontal
        )

        # --------------------------------------------------------------
        # Pannello laterale
        # --------------------------------------------------------------

        self.tabs = QTabWidget()

        self.tabs.setObjectName(
            'SNSidePanel'
        )

        self.tabs.setMinimumWidth(
            500
        )

        self.tabs.setMaximumWidth(
            560
        )

        self.tabs.setDocumentMode(
            False
        )

        self.tabs.setUsesScrollButtons(
            False
        )

        self.tabs.setElideMode(
            Qt.TextElideMode.ElideNone
        )

        self.tabs.tabBar().setIconSize(
            QSize(
                15,
                15,
            )
        )

        # Tab
        self.stereonet_tab = StereonetTab()
        self.dtm_tab = DTMTab(
            self.iface
        )
        self.data_tab = DataTab()
        self.kinematic_tab = KinematicResultsTab()
        self.rosette_tab = RosetteTab()

        # Aggiunta tab
        self.tabs.addTab(
            self.stereonet_tab,
            icons.icon_compass(),
            self.tr('Stereonet'),
        )

        self.tabs.addTab(
            self.dtm_tab,
            icons.icon_layers(),
            self.tr('DTM'),
        )

        self.tabs.addTab(
            self.data_tab,
            icons.icon_table(),
            self.tr('Data'),
        )

        self.tabs.addTab(
            self.kinematic_tab,
            icons.icon_kinematic(),
            self.tr('Kinematic Analysis'),
        )

        self.tabs.addTab(
            self.rosette_tab,
            icons.icon_rosette(),
            self.tr('Rosette'),
        )

        self.stereonet_tab.set_from_settings(
            self.settings
        )

        splitter.addWidget(
            self.tabs
        )

        # --------------------------------------------------------------
        # Area plot
        # --------------------------------------------------------------

        plot_container = QWidget()

        plot_layout = QVBoxLayout(
            plot_container
        )

        plot_layout.setContentsMargins(
            4,
            4,
            4,
            0,
        )

        self.figure = Figure(
            figsize=(7.5, 6.5),
            dpi=100,
        )

        self.canvas = FigureCanvas(
            self.figure
        )

        self.canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        plot_layout.addWidget(
            self.canvas
        )

        splitter.addWidget(
            plot_container
        )

        splitter.setStretchFactor(
            0,
            0,
        )

        splitter.setStretchFactor(
            1,
            1,
        )

        splitter.setSizes(
            [
                450,
                850,
            ]
        )

        outer.addWidget(
            splitter,
            1,
        )

        # --------------------------------------------------------------
        # Status bar
        # --------------------------------------------------------------

        self.lbl_status = QLabel(
            self.tr(
                'Nessun dato caricato.'
            )
        )

        self.lbl_status.setObjectName(
            'SNStatusBar'
        )

        outer.addWidget(
            self.lbl_status
        )

        self.setWidget(
            root
        )

        # ==============================================================
        # Segnali
        # ==============================================================

        self.stereonet_tab.generate_requested.connect(
            self.on_generate
        )

        self.stereonet_tab.clear_requested.connect(
            self.on_clear
        )

        self.stereonet_tab.export_requested.connect(
            self.export_image
        )

        self.stereonet_tab.cmb_source.currentIndexChanged.connect(
            self._sync_layer_status
        )

        self.data_tab.apply_requested.connect(
            self.on_apply_manual_data
        )

        self.dtm_tab.acquire_requested.connect(
            self.start_dtm_acquisition
        )

        self.dtm_tab.clear_requested.connect(
            self.on_dtm_clear_requested
        )

        self.dtm_tab.data_row_ready.connect(
            self.on_dtm_data_row
        )

        self.data_tab.cmb_format.currentIndexChanged.connect(
            lambda _i: self.dtm_tab.set_input_format(
                trc.combo_value(
                    self.data_tab.cmb_format
                )
            )
        )

        self.dtm_tab.set_input_format(
            self.data_tab.get_format()
        )

        self.rosette_tab.options_changed.connect(
            self._on_rosette_options_changed
        )

        # ==============================================================
        # Stereonet Options - aggiornamento live
        # ==============================================================

        for widget in (
            self.stereonet_tab.cmb_overlay,
            self.stereonet_tab.cmb_projection,
            self.stereonet_tab.cmb_hemisphere,
            self.stereonet_tab.cmb_labels,
            self.stereonet_tab.cmb_tick_spacing,
            self.stereonet_tab.cmb_outer_width,
            self.stereonet_tab.cmb_overlay_width,
        ):
            widget.currentIndexChanged.connect(
                self._on_stereonet_options_changed
            )

        self.stereonet_tab.chk_ext_ticks.toggled.connect(
            self._on_stereonet_options_changed
        )

        self.stereonet_tab.chk_center_cross.toggled.connect(
            self._on_stereonet_options_changed
        )

        self.stereonet_tab.chk_pole.toggled.connect(
            self._on_stereonet_options_changed
        )

        self.stereonet_tab.chk_planes.toggled.connect(
            self._on_stereonet_options_changed
        )

        self.stereonet_tab.chk_global_mean.toggled.connect(
            self._on_stereonet_options_changed
        )

        self.stereonet_tab.chk_best_fit.toggled.connect(
            self._on_stereonet_options_changed
        )

        self.stereonet_tab.btn_best_fit.clicked.connect(
            self._on_stereonet_options_changed
        )

        self.stereonet_tab.btn_bg.clicked.connect(
            self._on_stereonet_options_changed
        )

        self.stereonet_tab.btn_grid.clicked.connect(
            self._on_stereonet_options_changed
        )

        self.stereonet_tab.btn_mean.clicked.connect(
            self._on_stereonet_options_changed
        )

        self.stereonet_tab.btn_pole.clicked.connect(
            self._on_stereonet_options_changed
        )

        self.stereonet_tab.btn_plane.clicked.connect(
            self._on_stereonet_options_changed
        )

        # ==============================================================
        # Font live update
        # ==============================================================

        self.stereonet_tab.spn_font_title.valueChanged.connect(
            self._on_stereonet_options_changed
        )

        self.stereonet_tab.spn_font_label.valueChanged.connect(
            self._on_stereonet_options_changed
        )

        self.stereonet_tab.spn_font_elements.valueChanged.connect(
            self._on_stereonet_options_changed
        )

    # ==================================================================
    # TITLE BAR
    # ==================================================================

    def _build_title_bar(self):
        bar = QFrame()

        bar.setObjectName(
            'SNTitleBar'
        )

        layout = QHBoxLayout(bar)

        layout.setContentsMargins(
            8,
            2,
            4,
            2,
        )

        layout.setSpacing(2)

        title = QLabel(
            self.tr('StereonetStudio')
        )

        title.setObjectName(
            'SNTitleLabel'
        )

        layout.addWidget(
            title,
            1,
        )

        self.btn_maximize = QToolButton()
        self.btn_close = QToolButton()

        for btn in (
            self.btn_maximize,
            self.btn_close,
        ):
            btn.setObjectName(
                'SNWindowButton'
            )

            btn.setAutoRaise(
                True
            )

            btn.setFixedSize(
                26,
                24,
            )

        self.btn_maximize.setText(
            '□'
        )

        self.btn_close.setText(
            '×'
        )

        self.btn_maximize.setToolTip(
            self.tr(
                'Massimizza / Ripristina'
            )
        )

        self.btn_close.setToolTip(
            self.tr(
                'Chiudi'
            )
        )

        self.btn_maximize.clicked.connect(
            self._toggle_maximize
        )

        self.btn_close.clicked.connect(
            self.close
        )

        layout.addWidget(
            self.btn_maximize
        )

        layout.addWidget(
            self.btn_close
        )

        self.setTitleBarWidget(
            bar
        )

    # ==================================================================
    # FINESTRA
    # ==================================================================

    def _ensure_floating(self):
        if not self.isFloating():
            self.setFloating(
                True
            )

        # Qt deve prima creare la finestra flottante.
        QTimer.singleShot(
            0,
            self.fit_to_screen,
        )

    def _screen_for_window(self):
        """
        Restituisce il monitor appropriato per la finestra.
        """

        screen = self.screen()

        if screen is None:
            main_window = (
                self.iface.mainWindow()
                if self.iface
                else None
            )

            if main_window is not None:
                screen = main_window.screen()

        if screen is None:
            screen = QGuiApplication.primaryScreen()

        return screen

    def fit_to_screen(self):
        """
        Adatta la finestra flottante al monitor disponibile.

        Garantisce che la finestra:
        - non superi la dimensione disponibile del monitor;
        - non venga posizionata fuori dallo schermo;
        - mantenga dimensioni ragionevoli sui monitor piccoli;
        - funzioni anche con DPI scaling elevato.
        """

        if not self.isFloating():
            return

        screen = self._screen_for_window()

        if screen is None:
            return

        available = screen.availableGeometry()

        margin_x = 20
        margin_y = 20

        max_width = max(
            400,
            available.width() - 2 * margin_x,
        )

        max_height = max(
            300,
            available.height() - 2 * margin_y,
        )

        current_size = self.size()

        width = min(
            current_size.width(),
            max_width,
        )

        height = min(
            current_size.height(),
            max_height,
        )

        min_width = min(
            900,
            max_width,
        )

        min_height = min(
            650,
            max_height,
        )

        width = max(
            width,
            min_width,
        )

        height = max(
            height,
            min_height,
        )

        self.resize(
            width,
            height,
        )

        frame = self.frameGeometry()

        if frame.width() > available.width():
            width = max(
                300,
                available.width() - 2 * margin_x,
            )

        if frame.height() > available.height():
            height = max(
                250,
                available.height() - 2 * margin_y,
            )

        if (
            frame.width() != width
            or frame.height() != height
        ):
            self.resize(
                width,
                height,
            )

            frame = self.frameGeometry()

        frame.moveCenter(
            available.center()
        )

        self.move(
            frame.topLeft()
        )

    def center_on_screen(self):
        """
        Centra e adatta la finestra flottante al monitor corrente.
        """

        self.fit_to_screen()

    def _toggle_maximize(self):
        self._ensure_floating()

        if self.isMaximized():
            self.showNormal()

            QTimer.singleShot(
                0,
                self.fit_to_screen,
            )

        else:
            self.showMaximized()

    # ==================================================================
    # STEREONET OPTIONS
    # ==================================================================

    def _on_stereonet_options_changed(self, *args):
        self.settings = (
            self.stereonet_tab.get_settings(
                self.settings
            )
        )

        self.rosette_tab.set_show_on_main_plot(
            self.settings[
                'show_rosette'
            ]
        )

        self.redraw()

    # ==================================================================
    # AZIONI
    # ==================================================================

    def on_generate(self):
        rows, status = (
            self.stereonet_tab.load_data_rows()
        )

        if rows:
            self.data_rows = rows

            self.data_tab.load_rows(
                self.data_rows,
                trc.combo_value(
                    self.stereonet_tab.cmb_format
                ),
            )

        self.settings = (
            self.stereonet_tab.get_settings(
                self.settings
            )
        )

        self.rosette_tab.set_show_on_main_plot(
            self.settings[
                'show_rosette'
            ]
        )

        self.lbl_status.setText(
            status
        )

        self.redraw()

    def on_apply_manual_data(
        self,
        rows,
        fmt,
    ):
        self.data_rows = rows

        self.settings[
            'orientation_format'
        ] = fmt

        trc.set_combo_value(
            self.stereonet_tab.cmb_format,
            fmt,
        )

        self.settings = (
            self.stereonet_tab.get_settings(
                self.settings
            )
        )

        self.lbl_status.setText(
            self.tr(
                '{} misure inserite manualmente.'
            ).format(
                len(rows)
            )
        )

        self.redraw()

    def on_dtm_data_row(
        self,
        row,
        fmt,
    ):
        """
        Riceve una misura DTM e la porta
        nella tabella principale Data.
        """

        self.data_rows.append(
            dict(row)
        )

        self.data_tab.append_row(
            row
        )

        self.settings[
            'orientation_format'
        ] = fmt

        trc.set_combo_value(
            self.stereonet_tab.cmb_format,
            fmt,
        )

        self.settings = (
            self.stereonet_tab.get_settings(
                self.settings
            )
        )

        self.lbl_status.setText(
            self.tr(
                '{} misure totali; ultima acquisita dal DTM.'
            ).format(
                len(self.data_rows)
            )
        )

        self.redraw()

    # ==================================================================
    # DTM ACQUISITION
    # ==================================================================

    def start_dtm_acquisition(
        self,
        layer,
        radius,
        continuous,
    ):
        self.stop_dtm_acquisition()

        canvas = self.iface.mapCanvas()

        self._previous_map_tool = (
            canvas.mapTool()
        )

        self.dtm_map_tool = DTMMapTool(
            canvas,
            layer,
            radius,
            self,
        )

        self.dtm_map_tool.point_acquired.connect(
            lambda result, point: self._on_dtm_point(
                result,
                point,
                continuous,
                layer,
            )
        )

        self.dtm_map_tool.acquisition_cancelled.connect(
            self.stop_dtm_acquisition
        )

        self.dtm_map_tool.restore_requested.connect(
            self._restore_dtm_panel
        )

        canvas.setMapTool(
            self.dtm_map_tool
        )

        self._clear_dtm_preview()

        self.dtm_tab.acquisition_started()

        self._dtm_was_visible = (
            self.isVisible()
        )

        # Nasconde il pannello per lasciare libera
        # la mappa durante l'acquisizione.
        self.hide()

        self.lbl_status.setText(
            self.tr(
                'Acquisizione DTM attiva: clic sinistro per acquisire; '
                'clic destro per concludere e ripristinare la finestra.'
            )
        )

    def _on_dtm_point(
        self,
        result,
        point,
        continuous,
        layer,
    ):
        """
        Gestisce una misura DTM acquisita.
        """

        try:
            self._show_dtm_preview(
                result,
                layer,
            )

            fmt = self.data_tab.get_format()

            self.dtm_tab.add_record(
                result,
                fmt,
            )

        except Exception as exc:
            QMessageBox.warning(
                self,
                self.tr(
                    'Acquisizione DTM'
                ),
                self.tr(
                    'La misura è stata calcolata ma non è stato '
                    'possibile inserirla nelle tabelle:\n{}'
                ).format(
                    exc
                ),
            )

            return

        if not continuous:
            self._restore_dtm_panel()

        else:
            self.lbl_status.setText(
                self.tr(
                    'Punto DTM acquisito. Clicca un altro punto oppure '
                    'clic destro per concludere.'
                )
            )

    def _restore_dtm_panel(self):
        """
        Ripristina la finestra dopo il click destro
        e termina lo strumento.
        """

        self.stop_dtm_acquisition(
            restore_panel=True
        )

        self.show()

        self.center_on_screen()

        self.raise_()

        self.activateWindow()

    def _show_dtm_preview(
        self,
        result,
        layer,
    ):
        self._clear_dtm_preview()

        try:
            canvas = self.iface.mapCanvas()

            rb = QgsRubberBand(
                canvas,
                QgsWkbTypes.PolygonGeometry,
            )

            rb.setColor(
                QColor('#1f6fb2')
            )

            rb.setFillColor(
                QColor(
                    31,
                    111,
                    178,
                    35,
                )
            )

            rb.setWidth(
                2
            )

            transform = QgsCoordinateTransform(
                layer.crs(),
                canvas.mapSettings().destinationCrs(),
                QgsProject.instance(),
            )

            w = result.window

            points = [
                QgsPointXY(
                    w.xMinimum(),
                    w.yMinimum(),
                ),
                QgsPointXY(
                    w.xMinimum(),
                    w.yMaximum(),
                ),
                QgsPointXY(
                    w.xMaximum(),
                    w.yMaximum(),
                ),
                QgsPointXY(
                    w.xMaximum(),
                    w.yMinimum(),
                ),
            ]

            transformed = [
                transform.transform(point)
                for point in points
            ]

            rb.setToGeometry(
                QgsGeometry.fromPolygonXY(
                    [transformed]
                ),
                None,
            )

            self.dtm_preview = rb

        except Exception as exc:
            LOGGER.debug(
                'Unable to create DTM preview: %s',
                exc,
                exc_info=True,
            )

            self.dtm_preview = None

            try:
                self.iface.mapCanvas().refresh()

            except RuntimeError as refresh_exc:
                LOGGER.debug(
                    'Unable to refresh map canvas after DTM '
                    'preview failure: %s',
                    refresh_exc,
                )

        self._dtm_was_visible = True

    def _clear_dtm_preview(self):
        if self.dtm_preview is not None:
            try:
                self.dtm_preview.reset(
                    QgsWkbTypes.PolygonGeometry
                )

                self.dtm_preview.hide()

            except RuntimeError as exc:
                LOGGER.debug(
                    'DTM preview was already deleted or is no longer '
                    'valid: %s',
                    exc,
                )

            finally:
                # QgsRubberBand non è un QObject Qt.
                # Non va utilizzato deleteLater().
                self.dtm_preview = None

            try:
                self.iface.mapCanvas().refresh()

            except RuntimeError as exc:
                LOGGER.debug(
                    'Unable to refresh map canvas after clearing '
                    'DTM preview: %s',
                    exc,
                )

        self._dtm_was_visible = True

    def stop_dtm_acquisition(
        self,
        restore_panel=True,
    ):
        """
        Arresta l'acquisizione DTM e rimuove
        ogni elemento grafico temporaneo.
        """

        self._clear_dtm_preview()

        canvas = self.iface.mapCanvas()

        tool = self.dtm_map_tool

        if tool is not None:

            try:
                canvas.unsetMapTool(
                    tool
                )

            except RuntimeError as exc:
                LOGGER.debug(
                    'DTM map tool was already unset or is no longer '
                    'valid: %s',
                    exc,
                )

            try:
                tool.deleteLater()

            except RuntimeError as exc:
                LOGGER.debug(
                    'DTM map tool was already deleted or is no longer '
                    'valid: %s',
                    exc,
                )

            finally:
                self.dtm_map_tool = None

            previous_tool = (
                self._previous_map_tool
            )

            self._previous_map_tool = None

            if previous_tool is not None:
                try:
                    canvas.setMapTool(
                        previous_tool
                    )

                except RuntimeError as exc:
                    LOGGER.debug(
                        'Unable to restore previous QGIS map tool: %s',
                        exc,
                    )

        self.dtm_tab.acquisition_stopped()

        if (
            restore_panel
            and self._dtm_was_visible
        ):
            self.show()
            self.raise_()
            self.activateWindow()

    # ==================================================================
    # CLEAR
    # ==================================================================

    def on_clear(self):
        self.data_rows = []

        self.data_tab.load_rows(
            []
        )

        self.dtm_tab.clear_records()

        self.kinematic_tab.clear_results()

        self.lbl_status.setText(
            self.tr(
                'Dati azzerati.'
            )
        )

        self.redraw()

    def on_dtm_clear_requested(self):
        answer = QMessageBox.question(
            self,
            self.tr(
                'Svuota tabella DTM'
            ),
            self.tr(
                'Vuoi svuotare la tabella DTM e cancellare anche i dati '
                'attualmente visualizzati nella proiezione stereonet?\n\n'
                'Questa operazione cancellerà le misure dalla scheda Data '
                'e il relativo disegno dalla proiezione.'
            ),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        self.data_rows = []

        self.data_tab.load_rows(
            []
        )

        self.dtm_tab.clear_records()

        self.kinematic_tab.clear_results()

        self.lbl_status.setText(
            self.tr(
                'Tabella DTM e proiezione svuotate.'
            )
        )

        self.redraw()

    # ==================================================================
    # ROSETTE
    # ==================================================================

    def _on_rosette_options_changed(self):
        self.settings[
            'show_rosette'
        ] = self.rosette_tab.show_on_main_plot()

        self.stereonet_tab.chk_rosette.setChecked(
            self.settings[
                'show_rosette'
            ]
        )

        self.redraw()

    # ==================================================================
    # LAYER STATUS
    # ==================================================================

    def _sync_layer_status(self):
        """
        Riservato per eventuali aggiornamenti live futuri.
        """
        pass

    # ==================================================================
    # EXPORT
    # ==================================================================

    def export_image(self):
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            self.tr(
                'Esporta immagine'
            ),
            'stereonet.png',
            self.tr(
                'PNG (*.png);;'
                'JPEG (*.jpg *.jpeg);;'
                'SVG (*.svg);;'
                'PDF (*.pdf)'
            ),
        )

        if not path:
            return

        try:
            # Determina il formato dall'estensione.
            ext = (
                path.rsplit(
                    '.',
                    1,
                )[-1].lower()
                if '.' in path
                else ''
            )

            if ext not in (
                'png',
                'jpg',
                'jpeg',
                'svg',
                'pdf',
            ):
                path += '.png'
                ext = 'png'

            if ext in (
                'jpg',
                'jpeg',
            ):
                # JPEG non supporta trasparenza.
                self.figure.savefig(
                    path,
                    format='jpg',
                    dpi=200,
                    facecolor=self.figure.get_facecolor(),
                )

            else:
                self.figure.savefig(
                    path,
                    format=ext,
                    dpi=200,
                    facecolor=self.figure.get_facecolor(),
                )

            QMessageBox.information(
                self,
                self.tr(
                    'Esportazione completata'
                ),
                self.tr(
                    'Immagine salvata in:\n{}'
                ).format(
                    path
                ),
            )

        except Exception as exc:
            QMessageBox.warning(
                self,
                self.tr(
                    'Errore'
                ),
                self.tr(
                    'Impossibile salvare l\'immagine:\n{}'
                ).format(
                    exc
                ),
            )

    # ==================================================================
    # PREPARAZIONE DATI
    # ==================================================================

    def _planes(self):
        fmt = self.settings[
            'orientation_format'
        ]

        decl = (
            self.settings.get(
                'declination',
                0.0,
            )
            if self.settings.get(
                'use_declination'
            )
            else 0.0
        )

        planes = []

        for row in self.data_rows:
            dipdir, dip = (
                sm.to_internal_dipdir_dip(
                    row['v1'],
                    row['v2'],
                    fmt,
                )
            )

            dipdir = sm.wrap360(
                dipdir + decl
            )

            planes.append(
                {
                    'dipdir': dipdir,
                    'dip': dip,
                    'set': row.get(
                        'set',
                        'Set 1',
                    ),
                }
            )

        return planes

    # ==================================================================
    # DISEGNO PRINCIPALE
    # ==================================================================

    def redraw(self):
        s = self.settings
        fig = self.figure

        fig.clear()

        fig.patch.set_facecolor(
            s['color_background']
        )

        # --------------------------------------------------------------
        # Area stereonet
        # --------------------------------------------------------------

        ax = fig.add_axes(
            [
                0.045,
                0.045,
                0.925,
                0.815,
            ]
        )

        ax.set_facecolor(
            s['color_background']
        )

        ax.set_xlim(
            -1.30,
            1.30,
        )

        ax.set_ylim(
            -1.30,
            1.30,
        )

        ax.set_aspect(
            'equal'
        )

        ax.axis(
            'off'
        )

        projection = s[
            'projection'
        ]

        hemisphere = s[
            'hemisphere'
        ]

        legend_handles = []

        # ==============================================================
        # RETICOLO
        # ==============================================================

        grid_lines = sm.generate_grid_lines(
            s['overlay'],
            s['tick_spacing'],
            projection,
            hemisphere,
        )

        grid_color = '#9c9c9c'

        for line_vecs in grid_lines:
            xs, ys = (
                sm.project_points_masked(
                    line_vecs,
                    projection,
                    hemisphere,
                )
            )

            ax.plot(
                xs,
                ys,
                color=grid_color,
                linewidth=(
                    s['overlay_width'] * 0.4
                    + 0.2
                ),
                zorder=1,
            )

        # ==============================================================
        # CERCHIO PRIMITIVO
        # ==============================================================

        prim = sm.primitive_circle()

        px, py = (
            sm.project_points_masked(
                prim,
                projection,
                hemisphere,
            )
        )

        ax.plot(
            px,
            py,
            color=s['color_grid_outer'],
            linewidth=s['outer_grid_width'],
            zorder=3,
        )

        # ==============================================================
        # TACCHETTE ESTERNE
        # ==============================================================

        if s['exterior_ticks']:
            for az in range(
                0,
                360,
                s['tick_spacing'],
            ):
                a = sm.deg2rad(
                    az
                )

                x0 = math.sin(a)
                y0 = math.cos(a)

                x1 = (
                    math.sin(a)
                    * 1.045
                )

                y1 = (
                    math.cos(a)
                    * 1.045
                )

                ax.plot(
                    [x0, x1],
                    [y0, y1],
                    color=s['color_grid_outer'],
                    linewidth=max(
                        0.8,
                        s['outer_grid_width']
                        * 0.5,
                    ),
                    zorder=3,
                )

        # ==============================================================
        # CROCE CENTRALE
        # ==============================================================

        if s['center_cross']:
            ax.plot(
                [-0.03, 0.03],
                [0, 0],
                color=s['color_grid_outer'],
                linewidth=1.0,
                zorder=3,
            )

            ax.plot(
                [0, 0],
                [-0.03, 0.03],
                color=s['color_grid_outer'],
                linewidth=1.0,
                zorder=3,
            )

        # ==============================================================
        # ETICHETTE
        # ==============================================================

        self._draw_labels(
            ax,
            s,
        )

        # ==============================================================
        # DATI
        # ==============================================================

        planes = self._planes()

        set_names = (
            sorted(
                set(
                    p['set']
                    for p in planes
                )
            )
            if planes
            else []
        )

        pole_vectors_by_set = {}

        for p in planes:
            v = sm.pole_vector(
                p['dipdir'],
                p['dip'],
            )

            pole_vectors_by_set.setdefault(
                p['set'],
                [],
            ).append(
                v
            )

        # ==============================================================
        # DENSITÀ
        # ==============================================================

        density_cf = None
        density_title = None

        if (
            s['contour_mode'] != 'Nessuno'
            and planes
        ):
            (
                density_cf,
                density_title,
            ) = self._draw_contours(
                ax,
                s,
                planes,
                pole_vectors_by_set,
                projection,
                hemisphere,
            )

        # ==============================================================
        # PIANI
        # ==============================================================

        if (
            s.get(
                'show_planes',
                False,
            )
            and planes
        ):
            for p in planes:

                plane_gc = (
                    sm.great_circle_of_plane(
                        p['dipdir'],
                        p['dip'],
                        n_pts=361,
                    )
                )

                gx, gy = (
                    sm.project_points_masked(
                        plane_gc,
                        projection,
                        hemisphere,
                    )
                )

                ax.plot(
                    gx,
                    gy,
                    color=s.get(
                        'color_plane',
                        '#4a4a4a',
                    ),
                    linewidth=1.0,
                    zorder=4,
                )

            legend_handles.append(
                Line2D(
                    [0],
                    [0],
                    color=s.get(
                        'color_plane',
                        '#4a4a4a',
                    ),
                    linewidth=1.0,
                    label=self.tr(
                        'Piani'
                    ),
                )
            )

        # ==============================================================
        # POLI
        # ==============================================================

        if (
            s['show_pole']
            and planes
        ):
            pole_color = s.get(
                'color_pole',
                '#1f6fb2',
            )

            xs = []
            ys = []

            for p in planes:
                v = sm.pole_vector(
                    p['dipdir'],
                    p['dip'],
                )

                x, y = sm.project_vector(
                    v,
                    projection,
                    hemisphere,
                )

                if (
                    np.isfinite(x)
                    and np.isfinite(y)
                ):
                    xs.append(x)
                    ys.append(y)

            if xs:
                ax.scatter(
                    xs,
                    ys,
                    s=22,
                    facecolor=pole_color,
                    edgecolor='black',
                    linewidth=0.45,
                    zorder=6,
                )

                legend_handles.append(
                    Line2D(
                        [0],
                        [0],
                        marker='o',
                        color='none',
                        markerfacecolor=pole_color,
                        markeredgecolor='black',
                        markersize=6.5,
                        label=self.tr(
                            'Poli'
                        ),
                    )
                )

        # ==============================================================
        # GLOBAL MEAN
        # ==============================================================

        if (
            s['show_global_mean']
            and planes
        ):
            for set_name in set_names:

                vecs = (
                    pole_vectors_by_set.get(
                        set_name,
                        [],
                    )
                )

                mean_v = (
                    sm.mean_pole_vector(
                        vecs
                    )
                )

                if mean_v is None:
                    continue

                r_ratio = (
                    sm.resultant_length_ratio(
                        vecs
                    )
                )

                mx, my = sm.project_vector(
                    mean_v,
                    projection,
                    hemisphere,
                )

                mean_color = s.get(
                    'color_global_mean',
                    '#1b5e20',
                )

                ax.scatter(
                    [mx],
                    [my],
                    marker='+',
                    s=110,
                    color=mean_color,
                    linewidth=2.0,
                    zorder=6,
                )

                ax.annotate(
                    'gm',
                    (mx, my),
                    xytext=(5, -11),
                    textcoords='offset points',
                    color=mean_color,
                    fontsize=s.get(
                        'font_size_elements',
                        7.0,
                    ) + 1,
                    fontweight='bold',
                    zorder=7,
                )

                (
                    mean_dipdir,
                    mean_dip,
                ) = sm.plane_from_pole(
                    mean_v
                )

                legend_handles.append(
                    Line2D(
                        [0],
                        [0],
                        marker='+',
                        color=mean_color,
                        markersize=10,
                        linewidth=0,
                        label=self.tr(
                            'Global Mean ({set}: '
                            '{dipdir:.0f}/{dip:.0f}, R={r:.2f})'
                        ).format(
                            set=set_name,
                            dipdir=mean_dipdir,
                            dip=mean_dip,
                            r=r_ratio,
                        ),
                    )
                )

                mean_gc = (
                    sm.great_circle_of_plane(
                        mean_dipdir,
                        mean_dip,
                    )
                )

                gx, gy = (
                    sm.project_points_masked(
                        mean_gc,
                        projection,
                        hemisphere,
                    )
                )

                ax.plot(
                    gx,
                    gy,
                    color=mean_color,
                    linewidth=2.0,
                    zorder=4,
                )

        # ==============================================================
        # GLOBAL BEST FIT
        # ==============================================================

        if (
            s.get(
                'show_best_fit',
                False,
            )
            and planes
        ):
            bf_color = s.get(
                'color_best_fit',
                '#0000ff',
            )

            for set_name in set_names:

                vecs = (
                    pole_vectors_by_set.get(
                        set_name,
                        [],
                    )
                )

                bf_v = (
                    sm.best_fit_pole_vector(
                        vecs
                    )
                )

                if bf_v is None:
                    continue

                bx, by = sm.project_vector(
                    bf_v,
                    projection,
                    hemisphere,
                )

                ax.scatter(
                    [bx],
                    [by],
                    marker='+',
                    s=110,
                    color=bf_color,
                    linewidth=2.0,
                    zorder=6,
                )

                ax.annotate(
                    'bm',
                    (bx, by),
                    xytext=(5, -11),
                    textcoords='offset points',
                    color=bf_color,
                    fontsize=font_elements_bm(s),
                    fontweight='bold',
                    zorder=7,
                )

                (
                    bf_dipdir,
                    bf_dip,
                ) = sm.plane_from_pole(
                    bf_v
                )

                bgx, bgy = (
                    sm.project_points_masked(
                        sm.great_circle_of_plane(
                            bf_dipdir,
                            bf_dip,
                            n_pts=361,
                        ),
                        projection,
                        hemisphere,
                    )
                )

                ax.plot(
                    bgx,
                    bgy,
                    color=bf_color,
                    linewidth=1.6,
                    zorder=4,
                )

                legend_handles.append(
                    Line2D(
                        [0],
                        [0],
                        marker='+',
                        color=bf_color,
                        markersize=10,
                        linewidth=0,
                        label=self.tr(
                            'Global Best Fit ({set}: '
                            '{dipdir:.0f}/{dip:.0f})'
                        ).format(
                            set=set_name,
                            dipdir=bf_dipdir,
                            dip=bf_dip,
                        ),
                    )
                )

        # ==============================================================
        # ANALISI CINEMATICA
        # ==============================================================

        kin_result = None

        if (
            s['kinematic_enabled']
            and planes
        ):
            kin_result = self._draw_kinematic(
                ax,
                s,
                planes,
                projection,
                hemisphere,
                legend_handles,
            )

            self.kinematic_tab.show_results(
                self.tr(
                    s['kinematic_mode']
                ),
                self._kinematic_description(
                    s['kinematic_mode']
                ),
                planes,
                kin_result.feasible_mask,
                kin_result.n_feasible,
            )

        else:
            self.kinematic_tab.clear_results()

        # ==============================================================
        # FONT
        # ==============================================================

        font_title = s.get(
            'font_size_title',
            9.0,
        )

        font_label = s.get(
            'font_size_label',
            8.5,
        )

        font_elements = s.get(
            'font_size_elements',
            7.0,
        )

        # ==============================================================
        # LEGENDA
        # ==============================================================

        legend_artist = None

        if legend_handles:
            legend_artist = fig.legend(
                handles=legend_handles,
                loc='upper left',
                bbox_to_anchor=(
                    0.012,
                    0.895,
                ),
                bbox_transform=fig.transFigure,
                fontsize=font_elements,
                frameon=True,
                title=self.tr(
                    'Legend'
                ),
                title_fontsize=font_label,
                borderaxespad=0.0,
                handletextpad=0.5,
                labelspacing=0.5,
            )

            legend_artist.get_frame().set_edgecolor(
                '#888888'
            )

            legend_artist.get_frame().set_facecolor(
                '#ffffff'
            )

            legend_artist.get_title().set_fontweight(
                'bold'
            )

            for txt in legend_artist.get_texts():
                txt.set_fontweight(
                    'bold'
                )

        # ==============================================================
        # COLORBAR DENSITÀ
        # ==============================================================

        if density_cf is not None:
            self._place_density_colorbar(
                fig,
                density_cf,
                density_title,
                legend_artist,
                font_label,
                font_elements,
            )

        # ==============================================================
        # ROSETTA
        # ==============================================================

        if (
            s['show_rosette']
            and planes
        ):
            self._draw_rosette(
                fig,
                planes,
            )

        # ==============================================================
        # TITOLO
        # ==============================================================

        title_bits = [
            '{} - {}'.format(
                self.tr(
                    s['overlay']
                ),
                self.tr(
                    s['projection']
                ),
            )
        ]

        title_bits.append(
            '{} {}'.format(
                self.tr(
                    'Hemisphere:'
                ),
                self.tr(
                    s['hemisphere']
                ),
            )
        )

        title_bits.append(
            '{} {}°'.format(
                self.tr(
                    'Tick Spacing:'
                ),
                s['tick_spacing'],
            )
        )

        title_text = ' | '.join(
            title_bits
        )

        suptitle = fig.suptitle(
            title_text,
            fontsize=font_title,
            fontweight='bold',
            y=0.985,
            color='#45505c',
        )

        self._fit_title_to_width(
            fig,
            suptitle,
            font_title,
        )

        self.rosette_tab.redraw(
            planes
        )

        self.canvas.draw_idle()

    # ==================================================================
    # TITLE FIT
    # ==================================================================

    def _fit_title_to_width(
        self,
        fig,
        text_artist,
        base_fontsize,
    ):
        """
        Riduce automaticamente la dimensione del titolo se necessario.

        Non modifica il valore salvato nelle impostazioni dell'utente.
        """

        try:
            fig.canvas.draw()

            renderer = (
                fig.canvas.get_renderer()
            )

        except (
            AttributeError,
            RuntimeError,
        ):
            return

        max_width_px = (
            fig.bbox.width * 0.97
        )

        fontsize = base_fontsize

        for _ in range(12):

            bbox = (
                text_artist.get_window_extent(
                    renderer
                )
            )

            if (
                bbox.width <= max_width_px
                or fontsize <= 5.0
            ):
                break

            fontsize = max(
                5.0,
                fontsize * (
                    max_width_px
                    / bbox.width
                ),
            )

            text_artist.set_fontsize(
                fontsize
            )

            try:
                fig.canvas.draw()

                renderer = (
                    fig.canvas.get_renderer()
                )

            except (
                AttributeError,
                RuntimeError,
            ):
                break

    # ==================================================================
    # LABELS
    # ==================================================================

    def _draw_labels(
        self,
        ax,
        s,
    ):
        mode = s['labels']

        if mode == 'Nessuna':
            return

        r = 1.11

        if mode in (
            'NSEW',
            'NSEW+Gradi',
        ):
            points = [
                (0, 'N'),
                (90, 'E'),
                (180, 'S'),
                (270, 'W'),
            ]

            for az, txt in points:
                a = sm.deg2rad(
                    az
                )

                ax.text(
                    math.sin(a) * r,
                    math.cos(a) * r,
                    txt,
                    ha='center',
                    va='center',
                    fontsize=12,
                    fontweight='bold',
                    color=s[
                        'color_grid_outer'
                    ],
                    zorder=6,
                )

        elif mode == 'North':
            ax.text(
                0,
                r,
                'N',
                ha='center',
                va='center',
                fontsize=12,
                fontweight='bold',
                color=s[
                    'color_grid_outer'
                ],
                zorder=6,
            )

        if mode in (
            'Gradi',
            'NSEW+Gradi',
        ):
            step = s[
                'tick_spacing'
            ]

            for az in range(
                0,
                360,
                step,
            ):
                if (
                    mode == 'NSEW+Gradi'
                    and az in (
                        0,
                        90,
                        180,
                        270,
                    )
                ):
                    continue

                a = sm.deg2rad(
                    az
                )

                ax.text(
                    math.sin(a) * r,
                    math.cos(a) * r,
                    '{}°'.format(
                        az
                    ),
                    ha='center',
                    va='center',
                    fontsize=8,
                    color='#555555',
                    zorder=6,
                )

    # ==================================================================
    # CONTOURS / DENSITY
    # ==================================================================

    def _draw_contours(
        self,
        ax,
        s,
        planes,
        pole_vectors_by_set,
        projection,
        hemisphere,
    ):
        """
        Disegna il riempimento di densità.

        Ritorna:
            (contour_set, titolo)
        """

        mode = s[
            'contour_mode'
        ]

        # --------------------------------------------------------------
        # Poli
        # --------------------------------------------------------------

        if mode == 'Poli (Vettori)':

            vectors = [
                v
                for vectors_set
                in pole_vectors_by_set.values()
                for v in vectors_set
            ]

            title = self.tr(
                'Densità poli (%)'
            )

        # --------------------------------------------------------------
        # Intersezioni
        # --------------------------------------------------------------

        elif mode == 'Intersezioni':

            pairs = [
                (
                    p['dipdir'],
                    p['dip'],
                )
                for p in planes
            ]

            vectors = (
                sm.plane_intersections(
                    pairs
                )
            )

            title = self.tr(
                'Densità intersezioni (%)'
            )

        # --------------------------------------------------------------
        # Colonna / set
        # --------------------------------------------------------------

        else:
            col = s.get(
                'contour_column',
                '',
            ).strip()

            if (
                col
                and col in pole_vectors_by_set
            ):
                vectors = (
                    pole_vectors_by_set[
                        col
                    ]
                )

            else:
                vectors = [
                    v
                    for vectors_set
                    in pole_vectors_by_set.values()
                    for v in vectors_set
                ]

            title = self.tr(
                'Densità - {} (%)'
            ).format(
                col
                if col
                else self.tr(
                    'tutti i dati'
                )
            )

        # Servono almeno tre punti.
        if len(vectors) < 3:
            return None, None

        grid = sm.density_grid(
            vectors,
            projection,
            hemisphere,
            grid_n=110,
            counting_fraction=0.01,
            distribution='Fisher',
        )

        if grid is None:
            return None, None

        X, Y, Z = grid

        max_density = float(
            np.nanmax(Z)
        )

        levels = sm.nice_density_levels(
            max_density,
            n_intervals=10,
        )

        self.last_density_max = (
            max_density
        )

        # --------------------------------------------------------------
        # Contorni / Filled
        # --------------------------------------------------------------

        if (
            s.get(
                'contour_style',
                'Filled',
            )
            == 'Line'
        ):
            cf = ax.contour(
                X,
                Y,
                Z,
                levels=levels,
                cmap=DIPS_DENSITY_CMAP,
                linewidths=1.0,
                zorder=2,
            )

        else:
            cf = ax.contourf(
                X,
                Y,
                Z,
                levels=levels,
                cmap=DIPS_DENSITY_CMAP,
                alpha=0.85,
                zorder=2,
            )

        # --------------------------------------------------------------
        # Clip sul cerchio primitivo
        # --------------------------------------------------------------

        circle_clip = Circle(
            (0, 0),
            1.0,
            transform=ax.transData,
        )

        artists = (
            getattr(
                cf,
                'collections',
                None,
            )
            or [cf]
        )

        for artist in artists:
            artist.set_clip_path(
                circle_clip
            )

        return cf, title

    # ==================================================================
    # DENSITY COLORBAR
    # ==================================================================

    def _place_density_colorbar(
        self,
        fig,
        cf,
        title,
        legend_artist,
        font_label,
        font_elements,
    ):
        """
        Posiziona la scala di densità nell'angolo superiore destro.
        """

        # left, bottom, width, height
        left = 0.925
        bottom = 0.62
        width = 0.025
        height = 0.22

        cax = fig.add_axes(
            [
                left,
                bottom,
                width,
                height,
            ]
        )

        cbar = fig.colorbar(
            cf,
            cax=cax,
        )

        # Tacche ed etichette a sinistra.
        cbar.ax.yaxis.set_ticks_position(
            'left'
        )

        cbar.ax.yaxis.set_label_position(
            'left'
        )

        cbar.set_label(
            title,
            fontsize=font_label,
            fontweight='bold',
            rotation=90,
            labelpad=8,
        )

        cbar.ax.tick_params(
            labelsize=font_elements
        )

        for tick_lbl in (
            cbar.ax.get_yticklabels()
        ):
            tick_lbl.set_fontweight(
                'bold'
            )

    # ==================================================================
    # ROSETTE
    # ==================================================================

    def _draw_rosette(
        self,
        fig,
        planes,
    ):
        angles, _label = (
            self.rosette_tab.angles(
                planes
            )
        )

        bin_width = (
            self.rosette_tab.bin_width()
            if hasattr(
                self,
                'rosette_tab',
            )
            else 10
        )

        counts, bin_width = (
            sm.rosette_bins(
                angles,
                bin_width=bin_width,
            )
        )

        # Rosetta nell'angolo inferiore destro.
        rax = fig.add_axes(
            [
                0.72,
                0.06,
                0.22,
                0.16,
            ],
            projection='polar',
        )

        rax.set_theta_zero_location(
            'N'
        )

        rax.set_theta_direction(
            -1
        )

        theta = np.deg2rad(
            np.arange(
                0,
                360,
                bin_width,
            )
        )

        width = np.deg2rad(
            bin_width
        )

        rax.bar(
            theta,
            counts,
            width=width,
            bottom=0.0,
            color='#1f6fb2',
            edgecolor='black',
            linewidth=0.3,
            alpha=0.85,
        )

        # Etichette angolari.
        rax.tick_params(
            axis='x',
            labelsize=8,
            pad=5,
        )

        # Nasconde le etichette radiali.
        rax.set_yticklabels(
            []
        )

        # Titolo.
        rax.set_title(
            self.tr(
                'Rosette'
            ),
            fontsize=9,
            fontweight='bold',
            pad=8,
        )

    # ==================================================================
    # KINEMATIC DESCRIPTION
    # ==================================================================

    def _kinematic_description(
        self,
        mode,
    ):
        descriptions = {

            'Scivolamento Planare': self.tr(
                'Scivolamento planare possibile se: '
                '|DipDir_giunto - DipDir_scarpata| <= '
                'Limite laterale, e Angolo attrito <= '
                'Dip_giunto <= Dip_scarpata.'
            ),

            'Scivolamento a Cuneo': self.tr(
                'Scivolamento a cuneo possibile se il trend/plunge '
                'della retta di intersezione tra due discontinuità '
                'cade nel settore evidenziato '
                '(tra il cono di attrito e la scarpata, entro i '
                'limiti laterali).'
            ),

            'Ribaltamento Flessurale': self.tr(
                'Ribaltamento flessurale possibile se il giunto '
                'immerge (circa) in direzione opposta alla scarpata, '
                'con Dip >= 90 - Dip_scarpata + Angolo attrito.'
            ),

            'Ribaltamento Diretto': self.tr(
                'Ribaltamento diretto (di blocco) possibile per '
                'giunti molto ripidi con DipDir prossima a quella '
                'della scarpata: Dip >= 90 - Angolo attrito.'
            ),
        }

        return descriptions.get(
            mode,
            '',
        )

    # ==================================================================
    # KINEMATIC DRAW
    # ==================================================================

    def _draw_kinematic(
        self,
        ax,
        s,
        planes,
        projection,
        hemisphere,
        legend_handles,
    ):
        mode = s[
            'kinematic_mode'
        ]

        pairs = [
            (
                p['dipdir'],
                p['dip'],
            )
            for p in planes
        ]

        set_labels = [
            p['set']
            for p in planes
        ]

        result = sm.kinematic_analysis(
            mode,
            pairs,
            s['slope_dip'],
            s['slope_dipdir'],
            s['friction_angle'],
            s['lateral_limit'],
            projection,
            hemisphere,
            planes_for_intersections=pairs,
            sets_for_intersections=set_labels,
        )

        # ==============================================================
        # SLOPE GREAT CIRCLE
        # ==============================================================

        gx, gy = (
            sm.project_points_masked(
                result.slope_great_circle,
                projection,
                hemisphere,
            )
        )

        ax.plot(
            gx,
            gy,
            color='#000000',
            linewidth=2.0,
            zorder=4,
        )

        legend_handles.append(
            Line2D(
                [0],
                [0],
                color='#000000',
                linewidth=2.0,
                label=self.tr(
                    'Slope'
                ),
            )
        )

        # ==============================================================
        # CONSTRUCTION LINES
        # ==============================================================

        if s['show_construction_lines']:

            # ----------------------------------------------------------
            # Friction circle
            # ----------------------------------------------------------

            if result.friction_circle is not None:

                circ = (
                    result.friction_circle
                )

                if hemisphere == 'Superiore':
                    circ = -circ

                fx, fy = (
                    sm.project_points_masked(
                        circ,
                        projection,
                        hemisphere,
                    )
                )

                ax.plot(
                    fx,
                    fy,
                    color='#b30000',
                    linewidth=1.2,
                    linestyle=':',
                    zorder=4,
                )

                legend_handles.append(
                    Line2D(
                        [0],
                        [0],
                        color='#b30000',
                        linewidth=1.2,
                        linestyle=':',
                        label=self.tr(
                            'Friction Angle ({}°)'
                        ).format(
                            int(
                                s[
                                    'friction_angle'
                                ]
                            )
                        ),
                    )
                )

            # ----------------------------------------------------------
            # Daylight envelope
            # ----------------------------------------------------------

            if result.daylight_envelope:

                ex = [
                    p[0]
                    for p in result.daylight_envelope
                ]

                ey = [
                    p[1]
                    for p in result.daylight_envelope
                ]

                ax.plot(
                    ex,
                    ey,
                    color='#000000',
                    linewidth=1.2,
                    zorder=4,
                )

                legend_handles.append(
                    Line2D(
                        [0],
                        [0],
                        color='#000000',
                        linewidth=1.2,
                        label=self.tr(
                            'Daylight Envelope'
                        ),
                    )
                )

            # ----------------------------------------------------------
            # Lateral limits
            # ----------------------------------------------------------

            for az in (
                result.lateral_limit_lines
            ):
                a_rad = sm.deg2rad(
                    az
                )

                ax.plot(
                    [
                        -math.sin(a_rad),
                        math.sin(a_rad),
                    ],
                    [
                        -math.cos(a_rad),
                        math.cos(a_rad),
                    ],
                    color='#555555',
                    linewidth=1.0,
                    linestyle='-.',
                    zorder=4,
                )

            if result.lateral_limit_lines:
                legend_handles.append(
                    Line2D(
                        [0],
                        [0],
                        color='#555555',
                        linewidth=1.0,
                        linestyle='-.',
                        label=self.tr(
                            'Lateral Limit (±{}°)'
                        ).format(
                            int(
                                s[
                                    'lateral_limit'
                                ]
                            )
                        ),
                    )
                )

        # ==============================================================
        # HIGHLIGHT ZONE
        # ==============================================================

        if (
            s['show_highlight']
            and result.highlight_polygon
        ):
            poly = Polygon(
                result.highlight_polygon,
                closed=True,
                facecolor='#ff6600',
                alpha=0.30,
                edgecolor='#cc5200',
                linewidth=0.8,
                zorder=2.5,
            )

            ax.add_patch(
                poly
            )

            legend_handles.append(
                Polygon(
                    [(0, 0)],
                    facecolor='#ff6600',
                    alpha=0.30,
                    edgecolor='#cc5200',
                    label=self.tr(
                        'Highlighted Zone'
                    ),
                )
            )

        # ==============================================================
        # WEDGE SLIDING - INTERSECTIONS
        # ==============================================================

        if (
            mode == 'Scivolamento a Cuneo'
            and hasattr(
                result,
                'intersections',
            )
        ):
            xs = []
            ys = []
            colors = []

            for v, feasible in zip(
                result.intersections,
                result.feasible_mask,
            ):
                x, y = sm.project_vector(
                    v,
                    projection,
                    hemisphere,
                )

                xs.append(
                    x
                )

                ys.append(
                    y
                )

                colors.append(
                    '#d40000'
                    if feasible
                    else '#2c3e50'
                )

            if xs:
                ax.scatter(
                    xs,
                    ys,
                    marker='^',
                    s=30,
                    c=colors,
                    edgecolor='black',
                    linewidth=0.4,
                    zorder=6,
                )

                legend_handles.append(
                    Line2D(
                        [0],
                        [0],
                        marker='^',
                        color='none',
                        markerfacecolor='#d40000',
                        markeredgecolor='black',
                        markersize=7,
                        label=self.tr(
                            'Critical Intersections (n={})'
                        ).format(
                            result.n_feasible
                        ),
                    )
                )

        # ==============================================================
        # ALTRI MODI - CRITICAL POLES
        # ==============================================================

        else:

            if result.feasible_mask is not None:

                xs_ok = []
                ys_ok = []

                for p, feasible in zip(
                    planes,
                    result.feasible_mask,
                ):
                    if not feasible:
                        continue

                    v = sm.pole_vector(
                        p['dipdir'],
                        p['dip'],
                    )

                    x, y = sm.project_vector(
                        v,
                        projection,
                        hemisphere,
                    )

                    xs_ok.append(
                        x
                    )

                    ys_ok.append(
                        y
                    )

                if xs_ok:
                    ax.scatter(
                        xs_ok,
                        ys_ok,
                        marker='o',
                        s=34,
                        facecolor='#d40000',
                        edgecolor='black',
                        linewidth=0.6,
                        zorder=7,
                    )

                    legend_handles.append(
                        Line2D(
                            [0],
                            [0],
                            marker='o',
                            color='none',
                            markerfacecolor='#d40000',
                            markeredgecolor='black',
                            markersize=7,
                            label=self.tr(
                                'Critical Poles (n={})'
                            ).format(
                                len(xs_ok)
                            ),
                        )
                    )

        return result
