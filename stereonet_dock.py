# -*- coding: utf-8 -*-
"""
StereonetStudio - stereonet_dock.py

Dock widget principale: pannello laterale a schede (Stereonet, Data,
Kinematic Analysis, Rosette) + area di disegno con proiezione stereografica,
titolo sempre interamente visibile, legenda in alto a sinistra (sotto al
titolo) e scala di densita' subito sotto la legenda, allineata.
"""

import csv
import math
import numpy as np

import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import Polygon, Circle
from matplotlib.lines import Line2D
from matplotlib.colors import ListedColormap
from matplotlib.ticker import FuncFormatter

from qgis.PyQt.QtCore import Qt, QSize
from qgis.PyQt.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel,
    QFileDialog, QMessageBox, QSizePolicy, QTabWidget, QToolButton, QFrame
)
from qgis.core import QgsProject, QgsVectorLayer, QgsFeature

from . import stereonet_math as sm
from . import icons
from . import i18n_labels as trc
from .style import STYLE_SHEET
from .settings import new_settings
from .tab_stereonet import StereonetTab
from .tab_data import DataTab
from .tab_kinematic_results import KinematicResultsTab
from .tab_rosette import RosetteTab
from .tab_fold import FoldTab

# Scala di densita' in stile Dips (grigio-azzurro -> verde -> giallo -> rosso)
DIPS_DENSITY_COLORS = ['#e9ebf1', '#d5eaee', '#b4ece0', '#98f0c6', '#8bee9d',
                       '#82ee6c', '#c6f04f', '#ffe23f', '#ff8a1f', '#ff0000']
DIPS_DENSITY_CMAP = ListedColormap(DIPS_DENSITY_COLORS, name='dips_density')
# Variante per "Low-density emphasis": la fascia 0 resta trasparente e le
# fasce basse hanno colori piu' saturi, quindi visibili.
EMPHASIS_DENSITY_COLORS = ['#a6d8f5', '#7fd3e0', '#79e6b4', '#8bee9d', '#82ee6c',
                           '#c6f04f', '#ffe23f', '#ffb52f', '#ff8a1f', '#ff0000']

SET_COLORS = ['#1f6fb2', '#e67e22', '#27ae60', '#8e44ad', '#c0392b',
              '#16a085', '#d4ac0d', '#7f8c8d', '#2c3e50', '#e91e8c']


def font_elements_bm(s):
    return s.get('font_size_elements', 7.0) + 1


class StereonetDock(QDockWidget):

    def __init__(self, iface, parent=None):
        super().__init__('StereonetStudio', parent)
        self.setWindowTitle(self.tr('StereonetStudio'))
        self.iface = iface
        self.setObjectName('StereonetStudioDock')

        self.settings = new_settings()
        self.data_rows = []  # [{'v1':.., 'v2':.., 'set':..}, ...]

        # ---- strumenti interattivi (piega / cursore piano) ----
        self.ax = None
        self._pick_mode = None          # None | 'limbs' | 'live'
        self._pending_limbs = []        # poli L1/L2 in fase di selezione
        self.fold = None                # piega corrente {'L1','L2','group','swap','result'}
        self.cursor_planes = []         # [{'pole': vec, 'group': str}]
        self.pick_records = []          # archivio salvato (anche nel layer)
        self._fold_count = 0
        self._plane_count = 0
        self._picks_layer_id = None
        self._snap_targets = []         # [(x, y, vec)]
        self._live_bg = None
        self._live_artists = []
        self._suggestion = None         # [(polo, n), (polo, n)] o None

        self._build_ui()
        self.kinematic_tab.clear_results()
        self.redraw()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        self._build_title_bar()
        root = QWidget()
        root.setObjectName('SNRoot')
        root.setStyleSheet(STYLE_SHEET)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ---- pannello laterale a schede ----
        self.tabs = QTabWidget()
        self.tabs.setObjectName('SNSidePanel')
        self.tabs.setMinimumWidth(480)
        self.tabs.setMaximumWidth(560)
        self.tabs.setDocumentMode(False)
        self.tabs.setUsesScrollButtons(False)
        self.tabs.setElideMode(Qt.TextElideMode.ElideNone)
        self.tabs.tabBar().setIconSize(QSize(15, 15))

        self.stereonet_tab = StereonetTab()
        self.data_tab = DataTab()
        self.kinematic_tab = KinematicResultsTab()
        self.rosette_tab = RosetteTab()
        self.fold_tab = FoldTab()

        self.tabs.addTab(self.stereonet_tab, icons.icon_compass(), self.tr('Stereonet'))
        self.tabs.addTab(self.data_tab, icons.icon_table(), self.tr('Data'))
        self.tabs.addTab(self.kinematic_tab, icons.icon_kinematic(), self.tr('Kinematics'))
        self.tabs.addTab(self.fold_tab, icons.icon_fold(), self.tr('Folds'))
        self.tabs.addTab(self.rosette_tab, icons.icon_rosette(), self.tr(self.tr('Rosette')))

        self.stereonet_tab.set_from_settings(self.settings)
        splitter.addWidget(self.tabs)

        # ---- area di disegno ----
        plot_container = QWidget()
        plot_layout = QVBoxLayout(plot_container)
        plot_layout.setContentsMargins(4, 4, 4, 0)

        self.figure = Figure(figsize=(7.5, 6.5), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        plot_layout.addWidget(self.canvas)

        splitter.addWidget(plot_container)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([430, 850])

        outer.addWidget(splitter, 1)

        self.lbl_status = QLabel(self.tr('Nessun dato caricato.'))
        self.lbl_status.setObjectName('SNStatusBar')
        outer.addWidget(self.lbl_status)

        self.setWidget(root)

        # ---- segnali ----
        self.stereonet_tab.generate_requested.connect(self.on_generate)
        self.stereonet_tab.clear_requested.connect(self.on_clear)
        self.stereonet_tab.export_requested.connect(self.export_image)
        self.stereonet_tab.cmb_source.currentIndexChanged.connect(self._sync_layer_status)
        self.data_tab.apply_requested.connect(self.on_apply_manual_data)
        self.rosette_tab.options_changed.connect(self._on_rosette_options_changed)

        # Aggiornamento immediato del reticolo e del layout quando cambia
        # una qualsiasi impostazione del gruppo 'Stereonet Options'.
        for widget in (
            self.stereonet_tab.cmb_overlay,
            self.stereonet_tab.cmb_projection,
            self.stereonet_tab.cmb_hemisphere,
            self.stereonet_tab.cmb_labels,
            self.stereonet_tab.cmb_tick_spacing,
            self.stereonet_tab.cmb_outer_width,
            self.stereonet_tab.cmb_overlay_width,
        ):
            widget.currentIndexChanged.connect(self._on_stereonet_options_changed)
        self.stereonet_tab.chk_ext_ticks.toggled.connect(self._on_stereonet_options_changed)
        self.stereonet_tab.chk_center_cross.toggled.connect(self._on_stereonet_options_changed)
        self.stereonet_tab.chk_pole.toggled.connect(self._on_stereonet_options_changed)
        self.stereonet_tab.chk_planes.toggled.connect(self._on_stereonet_options_changed)
        self.stereonet_tab.chk_global_mean.toggled.connect(self._on_stereonet_options_changed)
        self.stereonet_tab.chk_best_fit.toggled.connect(self._on_stereonet_options_changed)
        self.stereonet_tab.btn_best_fit.clicked.connect(self._on_stereonet_options_changed)
        self.stereonet_tab.btn_bg.clicked.connect(self._on_stereonet_options_changed)
        self.stereonet_tab.btn_grid.clicked.connect(self._on_stereonet_options_changed)
        self.stereonet_tab.btn_mean.clicked.connect(self._on_stereonet_options_changed)
        self.stereonet_tab.btn_pole.clicked.connect(self._on_stereonet_options_changed)
        self.stereonet_tab.btn_plane.clicked.connect(self._on_stereonet_options_changed)
        # Dimensione testo (Titolo / Legenda-Densita' / Elementi-Valori): aggiornamento live
        self.stereonet_tab.spn_font_title.valueChanged.connect(self._on_stereonet_options_changed)
        self.stereonet_tab.spn_font_label.valueChanged.connect(self._on_stereonet_options_changed)
        self.stereonet_tab.spn_font_elements.valueChanged.connect(self._on_stereonet_options_changed)

        # ---- strumenti piega / cursore piano (scheda Folds) ----
        t = self.fold_tab
        t.btn_pick_limbs.toggled.connect(self._on_pick_limbs_toggled)
        t.btn_live_plane.toggled.connect(self._on_live_plane_toggled)
        t.btn_swap_axial.clicked.connect(self._on_swap_axial)
        t.chk_show_alt_axial.toggled.connect(lambda *_: self.redraw())
        t.btn_clear_picks.clicked.connect(self._on_clear_picks)
        t.btn_export_picks.clicked.connect(self._export_picks_csv)
        t.display_changed.connect(self.redraw)
        t.btn_use_suggest.clicked.connect(self._on_use_suggestion)
        t.chk_contours.toggled.connect(self._on_fold_contours_toggled)
        self.stereonet_tab.cmb_contours.currentIndexChanged.connect(self._sync_fold_contour_checkbox)
        self._sync_fold_contour_checkbox()
        self.canvas.mpl_connect('draw_event', self._on_canvas_draw)
        self.canvas.mpl_connect('motion_notify_event', self._on_canvas_motion)
        self.canvas.mpl_connect('button_press_event', self._on_canvas_click)
        self.canvas.mpl_connect('figure_leave_event', self._on_canvas_leave)

    # ------------------------------------------------------------------
    # Barra del titolo personalizzata
    # ------------------------------------------------------------------
    def _build_title_bar(self):
        bar = QFrame()
        bar.setObjectName('SNTitleBar')
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 2, 4, 2)
        layout.setSpacing(2)

        title = QLabel(self.tr('StereonetStudio'))
        title.setObjectName('SNTitleLabel')
        layout.addWidget(title, 1)

        self.btn_maximize = QToolButton()
        self.btn_close = QToolButton()
        for btn in (self.btn_maximize, self.btn_close):
            btn.setObjectName('SNWindowButton')
            btn.setAutoRaise(True)
            btn.setFixedSize(26, 24)

        self.btn_maximize.setText('□')
        self.btn_close.setText('×')
        self.btn_maximize.setToolTip(self.tr('Massimizza / Ripristina'))
        self.btn_close.setToolTip(self.tr('Chiudi'))

        self.btn_maximize.clicked.connect(self._toggle_maximize)
        self.btn_close.clicked.connect(self.close)

        layout.addWidget(self.btn_maximize)
        layout.addWidget(self.btn_close)
        self.setTitleBarWidget(bar)

    def _ensure_floating(self):
        if not self.isFloating():
            self.setFloating(True)

    def _toggle_maximize(self):
        self._ensure_floating()
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    # ------------------------------------------------------------------
    # Aggiornamento live delle Stereonet Options
    # ------------------------------------------------------------------
    def _on_stereonet_options_changed(self, *args):
        self.settings = self.stereonet_tab.get_settings(self.settings)
        self.rosette_tab.set_show_on_main_plot(self.settings['show_rosette'])
        self.redraw()

    # ------------------------------------------------------------------
    # Azioni
    # ------------------------------------------------------------------
    def on_generate(self):
        rows, status = self.stereonet_tab.load_data_rows()
        if rows:
            self.data_rows = rows
            self.data_tab.load_rows(self.data_rows, trc.combo_value(self.stereonet_tab.cmb_format))
        self.settings = self.stereonet_tab.get_settings(self.settings)
        self.rosette_tab.set_show_on_main_plot(self.settings['show_rosette'])
        self.lbl_status.setText(status)
        self.redraw()

    def on_apply_manual_data(self, rows, fmt):
        self.data_rows = rows
        self.settings['orientation_format'] = fmt
        trc.set_combo_value(self.stereonet_tab.cmb_format, fmt)
        self.settings = self.stereonet_tab.get_settings(self.settings)
        self.lbl_status.setText(self.tr('{} misure inserite manualmente.').format(len(rows)))
        self.redraw()

    def on_clear(self):
        self.data_rows = []
        self.data_tab.load_rows([])
        self.kinematic_tab.clear_results()
        self.lbl_status.setText(self.tr('Dati azzerati.'))
        self.redraw()

    def _on_rosette_options_changed(self):
        self.settings['show_rosette'] = self.rosette_tab.show_on_main_plot()
        self.stereonet_tab.chk_rosette.setChecked(self.settings['show_rosette'])
        self.redraw()

    def _sync_layer_status(self):
        pass  # riservato per eventuali aggiornamenti live in futuro

    def export_image(self):
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            self.tr('Esporta immagine'),
            'stereonet.png',
            self.tr(
                'PNG (*.png);;JPEG (*.jpg *.jpeg);;SVG (*.svg);;PDF (*.pdf)'
            )
        )

        if not path:
            return

        try:
            # Determina il formato in base all'estensione.
            ext = path.rsplit('.', 1)[-1].lower() if '.' in path else ''

            if ext not in ('png', 'jpg', 'jpeg', 'svg', 'pdf'):
                # Se l'utente non ha indicato un'estensione, usa PNG.
                path += '.png'
                ext = 'png'

            if ext in ('jpg', 'jpeg'):
                # JPEG non gestisce la trasparenza: usa lo sfondo della figura.
                self.figure.savefig(
                    path,
                    format='jpg',
                    dpi=200,
                    facecolor=self.figure.get_facecolor()
                )
            else:
                self.figure.savefig(
                    path,
                    format=ext,
                    dpi=200,
                    facecolor=self.figure.get_facecolor()
                )

            QMessageBox.information(
                self,
                self.tr('Esportazione completata'),
                self.tr('Immagine salvata in:\n{}').format(path)
            )

        except Exception as exc:
            QMessageBox.warning(
                self,
                self.tr('Errore'),
                self.tr(
                    'Impossibile salvare l\'immagine:\n{}'
                ).format(exc)
            )

    # ------------------------------------------------------------------
    # Preparazione dati
    # ------------------------------------------------------------------
    def _planes(self):
        fmt = self.settings['orientation_format']
        decl = self.settings.get('declination', 0.0) if self.settings.get('use_declination') else 0.0
        planes = []
        for row in self.data_rows:
            dipdir, dip = sm.to_internal_dipdir_dip(row['v1'], row['v2'], fmt)
            dipdir = sm.wrap360(dipdir + decl)
            planes.append({'dipdir': dipdir, 'dip': dip, 'set': row.get('set', 'Set 1')})
        return planes

    # ------------------------------------------------------------------
    # Disegno principale
    # ------------------------------------------------------------------
    def redraw(self):
        s = self.settings
        fig = self.figure
        fig.clear()
        fig.patch.set_facecolor(s['color_background'])

        # Area del reticolo: occupa quasi tutta la figura. La legenda e la
        # scala di densita' sono ancorate nell'angolo in alto a sinistra,
        # subito sotto al titolo, sovrapposte allo spazio vuoto agli angoli
        # del cerchio primitivo (che non tocca gli angoli del riquadro).
        ax = fig.add_axes([0.045, 0.045, 0.925, 0.815])
        ax.set_facecolor(s['color_background'])
        ax.set_xlim(-1.30, 1.30)
        ax.set_ylim(-1.30, 1.30)
        ax.set_aspect('equal')
        ax.axis('off')
        self.ax = ax
        self._snap_targets = []
        self._live_artists = []
        self._live_bg = None

        projection = s['projection']
        hemisphere = s['hemisphere']

        legend_handles = []

        # ---- reticolo (grid) ----
        grid_lines = sm.generate_grid_lines(s['overlay'], s['tick_spacing'], projection, hemisphere)
        grid_color = '#9c9c9c'
        for line_vecs in grid_lines:
            xs, ys = sm.project_points_masked(line_vecs, projection, hemisphere)
            ax.plot(xs, ys, color=grid_color, linewidth=s['overlay_width'] * 0.4 + 0.2, zorder=1)

        # ---- cerchio primitivo (grande cerchio esterno) ----
        prim = sm.primitive_circle()
        px, py = sm.project_points_masked(prim, projection, hemisphere)
        ax.plot(px, py, color=s['color_grid_outer'], linewidth=s['outer_grid_width'], zorder=3)

        # ---- tacche esterne ----
        if s['exterior_ticks']:
            for az in range(0, 360, s['tick_spacing']):
                a = sm.deg2rad(az)
                x0, y0 = math.sin(a), math.cos(a)
                x1, y1 = math.sin(a) * 1.045, math.cos(a) * 1.045
                ax.plot([x0, x1], [y0, y1], color=s['color_grid_outer'],
                        linewidth=max(0.8, s['outer_grid_width'] * 0.5), zorder=3)

        # ---- croce centrale ----
        if s['center_cross']:
            ax.plot([-0.03, 0.03], [0, 0], color=s['color_grid_outer'], linewidth=1.0, zorder=3)
            ax.plot([0, 0], [-0.03, 0.03], color=s['color_grid_outer'], linewidth=1.0, zorder=3)

        # ---- etichette N/S/E/W e gradi ----
        self._draw_labels(ax, s)

        # ---- preparazione dati (piani, poli, set) ----
        planes = self._planes()
        set_names = sorted(set(p['set'] for p in planes)) if planes else []
        pole_vectors_by_set = {}
        for p in planes:
            v = sm.pole_vector(p['dipdir'], p['dip'])
            pole_vectors_by_set.setdefault(p['set'], []).append(v)

        # ---- contorni di densita' ----
        # Il colorbar (scala densita') viene posizionato piu' avanti, sotto
        # la legenda, quindi qui teniamo solo il contour-set e l'etichetta.
        density_cf = None
        density_title = None
        if s['contour_mode'] != 'Nessuno' and planes:
            density_cf, density_title = self._draw_contours(ax, s, planes, pole_vectors_by_set, projection, hemisphere)

        # ---- piani / tracce dei piani ----
        # Ogni polo definisce un piano. La sua traccia e' il cerchio massimo
        # contenuto nel piano; proiettandolo e mascherando l'emisfero si ottiene
        # automaticamente il semicerchio corretto del piano sullo stereonet.
        if s.get('show_planes', False) and planes:
            for p in planes:
                plane_gc = sm.great_circle_of_plane(p['dipdir'], p['dip'], n_pts=361)
                gx, gy = sm.project_points_masked(plane_gc, projection, hemisphere)
                ax.plot(gx, gy, color=s.get('color_plane', '#4a4a4a'),
                        linewidth=1.0, zorder=4)
            legend_handles.append(Line2D([0], [0], color=s.get('color_plane', '#4a4a4a'),
                                          linewidth=1.0, label=self.tr('Piani')))

        # ---- poli ----
        if s['show_pole'] and planes:
            pole_color = s.get('color_pole', '#1f6fb2')
            xs, ys = [], []
            for p in planes:
                v = sm.pole_vector(p['dipdir'], p['dip'])
                x, y = sm.project_vector(v, projection, hemisphere)
                if np.isfinite(x) and np.isfinite(y):
                    xs.append(x); ys.append(y)
                    self._snap_targets.append((x, y, v))
            if xs:
                pole_alpha = max(0.05, 1.0 - self.fold_tab.sld_pole_fade.value() / 100.0)
                ax.scatter(xs, ys, s=22, facecolor=pole_color, edgecolor='black', linewidth=0.45,
                           alpha=pole_alpha, zorder=6)
                legend_handles.append(Line2D([0], [0], marker='o', color='none',
                                              markerfacecolor=pole_color, markeredgecolor='black',
                                              markersize=6.5, alpha=max(pole_alpha, 0.3),
                                              label=self.tr('Poli')))

        # ---- media globale (Global Mean) ----
        if s['show_global_mean'] and planes:
            for set_name in set_names:
                vecs = pole_vectors_by_set.get(set_name, [])
                mean_v = sm.mean_pole_vector(vecs)
                if mean_v is None:
                    continue
                r_ratio = sm.resultant_length_ratio(vecs)
                mx, my = sm.project_vector(mean_v, projection, hemisphere)
                self._snap_targets.append((mx, my, mean_v))
                ax.scatter([mx], [my], marker='+', s=110, color=s.get('color_global_mean', '#1b5e20'),
                           linewidth=2.0, zorder=6)
                ax.annotate('gm', (mx, my), xytext=(5, -11), textcoords='offset points',
                            color=s.get('color_global_mean', '#1b5e20'), fontsize=s.get('font_size_elements', 7.0) + 1,
                            fontweight='bold', zorder=7)
                mean_dipdir, mean_dip = sm.plane_from_pole(mean_v)
                legend_handles.append(Line2D([0], [0], marker='+', color=s.get('color_global_mean', '#1b5e20'),
                                              markersize=10, linewidth=0,
                                              label=self.tr('Global Mean ({set}: {dipdir:.0f}/{dip:.0f}, R={r:.2f})').format(
                                                  set=set_name, dipdir=mean_dipdir, dip=mean_dip, r=r_ratio)))
                mean_gc = sm.great_circle_of_plane(mean_dipdir, mean_dip)
                gx, gy = sm.project_points_masked(mean_gc, projection, hemisphere)
                ax.plot(gx, gy, color=s.get('color_global_mean', '#1b5e20'), linewidth=2.0, linestyle='--', zorder=4)

        # ---- Global Best Fit (piano di miglior adattamento ai poli) ----
        if s.get('show_best_fit', False) and planes:
            bf_color = s.get('color_best_fit', '#0000ff')
            for set_name in set_names:
                vecs = pole_vectors_by_set.get(set_name, [])
                bf_v = sm.best_fit_pole_vector(vecs)
                if bf_v is None:
                    continue
                bx, by = sm.project_vector(bf_v, projection, hemisphere)
                self._snap_targets.append((bx, by, bf_v))
                ax.scatter([bx], [by], marker='+', s=110, color=bf_color, linewidth=2.0, zorder=6)
                ax.annotate('β', (bx, by), xytext=(5, -11), textcoords='offset points',
                            color=bf_color, fontsize=font_elements_bm(s), fontweight='bold', zorder=7)
                bf_dipdir, bf_dip = sm.plane_from_pole(bf_v)
                bgx, bgy = sm.project_points_masked(sm.great_circle_of_plane(bf_dipdir, bf_dip, n_pts=361),
                                                    projection, hemisphere)
                ax.plot(bgx, bgy, color=bf_color, linewidth=1.6, zorder=4)
                legend_handles.append(Line2D([0], [0], color=bf_color, linewidth=1.6,
                                              label=self.tr('Best Fit girdle ({set}): dip/dd {pl}').format(
                                                  set=set_name, pl=sm.fmt_plane(bf_dipdir, bf_dip))))
                legend_handles.append(Line2D([0], [0], marker='+', color=bf_color, markersize=10, linewidth=0,
                                              markeredgewidth=2.0,
                                              label=self.tr('β fold hinge ({set}): {ln}').format(
                                                  set=set_name, ln=sm.fmt_line(bf_v))))

        # ---- poli dei fianchi suggeriti automaticamente ----
        self.fold_tab.set_available_sets(set_names)
        self._update_suggestion(planes, pole_vectors_by_set)
        self._draw_suggestion(ax, s, projection, hemisphere, legend_handles)

        # ---- piega (L1/L2, asse, piano assiale) e piani salvati col cursore ----
        self._draw_fold_and_picks(ax, s, projection, hemisphere, legend_handles)

        # ---- analisi cinematica ----
        kin_result = None
        if s['kinematic_enabled'] and planes:
            kin_result = self._draw_kinematic(ax, s, planes, projection, hemisphere, legend_handles)
            self.kinematic_tab.show_results(self.tr(s['kinematic_mode']), self._kinematic_description(s['kinematic_mode']),
                                             planes, kin_result.feasible_mask, kin_result.n_feasible)
        else:
            self.kinematic_tab.clear_results()

        font_title = s.get('font_size_title', 9.0)
        font_label = s.get('font_size_label', 8.5)
        font_elements = s.get('font_size_elements', 7.0)

        # ---- legenda: sotto al titolo, in alto a sinistra ----
        legend_artist = None
        if legend_handles:
            legend_artist = fig.legend(handles=legend_handles, loc='upper left',
                             bbox_to_anchor=(0.012, 0.895), bbox_transform=fig.transFigure,
                             fontsize=font_elements, frameon=True, title=self.tr('Legend'),
                             title_fontsize=font_label,
                             borderaxespad=0.0, handletextpad=0.5, labelspacing=0.5)
            legend_artist.get_frame().set_edgecolor('#888888')
            legend_artist.get_frame().set_facecolor('#ffffff')
            legend_artist.get_title().set_fontweight('bold')
            for txt in legend_artist.get_texts():
                txt.set_fontweight('bold')

        # ---- scala di densita': sotto la legenda, allineata a sinistra ----
        if density_cf is not None:
            self._place_density_colorbar(fig, density_cf, density_title, legend_artist,
                                          font_label, font_elements)

        # ---- rosetta (inserto sul plot principale, opzionale) ----
        if s['show_rosette'] and planes:
            self._draw_rosette(fig, planes)

        # ---- titolo (sopra la proiezione, sempre interamente visibile) ----
        title_bits = ['{} - {}'.format(self.tr(s['overlay']), self.tr(s['projection']))]
        title_bits.append('{} {}'.format(self.tr('Hemisphere:'), self.tr(s['hemisphere'])))
        title_bits.append('{} {}°'.format(self.tr('Tick Spacing:'), s['tick_spacing']))
        title_text = ' | '.join(title_bits)
        suptitle = fig.suptitle(title_text, fontsize=font_title, fontweight='bold',
                                 y=0.985, color='#45505c')
        self._fit_title_to_width(fig, suptitle, font_title)

        self._create_live_artists(ax, s)

        self.rosette_tab.redraw(planes)
        self.canvas.draw_idle()

    # ------------------------------------------------------------------
    def _fit_title_to_width(self, fig, text_artist, base_fontsize):
        """Riduce automaticamente la dimensione del titolo.

        Se, con la larghezza attuale della finestra, il testo supererebbe
        i bordi della figura, riduce progressivamente la dimensione del
        carattere senza modificare l'impostazione salvata dall'utente.

        Se il renderer Matplotlib non è disponibile, il ridimensionamento
        viene semplicemente saltato.
        """
        try:
            fig.canvas.draw()
            renderer = fig.canvas.get_renderer()
        except (AttributeError, RuntimeError):
            return

        max_width_px = fig.bbox.width * 0.97
        fontsize = base_fontsize

        for _ in range(12):
            bbox = text_artist.get_window_extent(renderer)

            if bbox.width <= max_width_px or fontsize <= 5.0:
                break

            fontsize = max(5.0, fontsize * (max_width_px / bbox.width))
            text_artist.set_fontsize(fontsize)

            try:
                fig.canvas.draw()
                renderer = fig.canvas.get_renderer()
            except (AttributeError, RuntimeError):
                break

    # ------------------------------------------------------------------
    def _draw_labels(self, ax, s):
        mode = s['labels']
        if mode == 'Nessuna':
            return
        r = 1.11
        if mode in ('NSEW', 'NSEW+Gradi'):
            pts = [(0, 'N'), (90, 'E'), (180, 'S'), (270, 'W')]
            for az, txt in pts:
                a = sm.deg2rad(az)
                ax.text(math.sin(a) * r, math.cos(a) * r, txt, ha='center', va='center',
                        fontsize=10, fontweight='bold', color=s['color_grid_outer'], zorder=6)
        elif mode == 'North':
            ax.text(0, r, 'N', ha='center', va='center', fontsize=11, fontweight='bold',
                    color=s['color_grid_outer'], zorder=6)

        if mode in ('Gradi', 'NSEW+Gradi'):
            step = s['tick_spacing']
            for az in range(0, 360, step):
                if mode == 'NSEW+Gradi' and az in (0, 90, 180, 270):
                    continue
                a = sm.deg2rad(az)
                ax.text(math.sin(a) * r, math.cos(a) * r, '{}°'.format(az), ha='center', va='center',
                        fontsize=6.5, color='#555555', zorder=6)

    # ------------------------------------------------------------------
    def _draw_contours(self, ax, s, planes, pole_vectors_by_set, projection, hemisphere):
        """Disegna il riempimento di densita' e ritorna (contour_set, titolo)
        cosi' che il colorbar possa essere posizionato in seguito, sotto la
        legenda (vedi _place_density_colorbar)."""
        mode = s['contour_mode']
        if mode == 'Poli (Vettori)':
            vectors = [v for vs in pole_vectors_by_set.values() for v in vs]
            title = self.tr("Densità poli (%)")
        elif mode == 'Intersezioni':
            pairs = [(p['dipdir'], p['dip']) for p in planes]
            vectors = sm.plane_intersections(pairs)
            title = self.tr("Densità intersezioni (%)")
        else:  # Colonna dati
            col = s.get('contour_column', '').strip()
            if col and col in pole_vectors_by_set:
                vectors = pole_vectors_by_set[col]
            else:
                vectors = [v for vs in pole_vectors_by_set.values() for v in vs]
            title = self.tr("Densità - {} (%)").format(col if col else self.tr('tutti i dati'))

        if len(vectors) < 3:
            return None, None
        grid = sm.density_grid(vectors, projection, hemisphere, grid_n=110,
                               counting_fraction=0.01, distribution='Fisher')
        if grid is None:
            return None, None
        X, Y, Z = grid
        # Densita' assoluta (% dei poli per 1% di area), come "Density
        # Concentrations" di Dips, con livelli 'tondi' (es. 0-2.5-...-25).
        emphasis = self.fold_tab.sld_emphasis.value() / 100.0
        alpha = max(0.0, min(1.0, 1.0 - self.fold_tab.sld_transparency.value() / 100.0))
        if emphasis > 0:
            # 11 livelli -> si scarta la fascia [0, l1] (resta non colorata)
            levels = sm.emphasized_density_levels(float(np.nanmax(Z)), emphasis, n_intervals=10)[1:]
            cmap = ListedColormap(EMPHASIS_DENSITY_COLORS[-(len(levels) - 1):], name='dips_emph')
        else:
            levels = sm.nice_density_levels(float(np.nanmax(Z)), n_intervals=10)
            cmap = DIPS_DENSITY_CMAP
        self.last_density_max = float(np.nanmax(Z))
        if s.get('contour_style', 'Filled') == 'Line':
            cf = ax.contour(X, Y, Z, levels=levels, cmap=cmap, linewidths=1.0,
                            alpha=max(alpha, 0.05), zorder=2)
        else:
            cf = ax.contourf(X, Y, Z, levels=levels, cmap=cmap, alpha=alpha, zorder=2)

        # Ritaglia il riempimento esattamente sul contorno del grande cerchio,
        # cosi' lo sfondo colorato arriva fino al bordo senza lasciare una
        # sottile fascia non colorata tra la mappa di densita' e il cerchio.
        circle_clip = Circle((0, 0), 1.0, transform=ax.transData)
        artists = getattr(cf, 'collections', None) or [cf]
        for artist in artists:
            artist.set_clip_path(circle_clip)

        return cf, title

    # ------------------------------------------------------------------
    def _place_density_colorbar(
        self,
        fig,
        cf,
        title,
        legend_artist,
        font_label,
        font_elements
    ):
        """Posiziona la scala di densita' in posizione fissa,
        nell'angolo superiore destro della figura, senza dipendere
        dalla posizione della legenda."""

        # Posizione fissa in alto a destra.
        # left, bottom, width, height
        left = 0.925
        bottom = 0.62
        width = 0.025
        height = 0.22

        cax = fig.add_axes(
            [left, bottom, width, height]
        )

        cbar = fig.colorbar(
            cf,
            cax=cax
        )

        # Etichette e tacche sulla sinistra della barra,
        # così rimangono completamente dentro la figura.
        cbar.ax.yaxis.set_ticks_position('left')
        cbar.ax.yaxis.set_label_position('left')

        cbar.set_label(
            title,
            fontsize=font_label,
            fontweight='bold',
            rotation=90,
            labelpad=8
        )

        cbar.ax.tick_params(
            labelsize=font_elements
        )
        cbar.ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _pos: '{:g}'.format(v)))

        for tick_lbl in cbar.ax.get_yticklabels():
            tick_lbl.set_fontweight('bold')

    # ------------------------------------------------------------------
    def _draw_rosette(self, fig, planes):
        angles, _label = self.rosette_tab.angles(planes)
        bin_width = (
            self.rosette_tab.bin_width()
            if hasattr(self, 'rosette_tab')
            else 10
        )

        counts, bin_width = sm.rosette_bins(
            angles,
            bin_width=bin_width
        )

        # Rosetta nell'angolo inferiore destro.
        # La posizione mantiene la rosetta esterna allo stereonet
        # e sufficientemente distante dalle sue etichette.
        rax = fig.add_axes(
            [0.72, 0.06, 0.22, 0.16],
            projection='polar'
        )

        rax.set_theta_zero_location('N')
        rax.set_theta_direction(-1)

        theta = np.deg2rad(
            np.arange(0, 360, bin_width)
        )
        width = np.deg2rad(bin_width)

        rax.bar(
            theta,
            counts,
            width=width,
            bottom=0.0,
            color='#1f6fb2',
            edgecolor='black',
            linewidth=0.3,
            alpha=0.85
        )

        # Etichette angolari più grandi
        rax.tick_params(
            axis='x',
            labelsize=8,
            pad=5
        )

        # Nasconde le etichette radiali
        rax.set_yticklabels([])

        # Titolo più grande, in grassetto e più distante dal grafico
        rax.set_title(
            self.tr('Rosette'),
            fontsize=9,
            fontweight='bold',
            pad=8
        )

    # ------------------------------------------------------------------
    def _kinematic_description(self, mode):
        descriptions = {
            'Scivolamento Planare': self.tr(
                'Scivolamento planare possibile se: |DipDir_giunto - DipDir_scarpata| <= '
                'Limite laterale, e Angolo attrito <= Dip_giunto <= Dip_scarpata.'),
            'Scivolamento a Cuneo': self.tr(
                'Scivolamento a cuneo possibile se il trend/plunge della retta di '
                'intersezione tra due discontinuità cade nel settore evidenziato '
                '(tra il cono di attrito e la scarpata, entro i limiti laterali).'),
            'Ribaltamento Flessurale': self.tr(
                'Ribaltamento flessurale possibile se il giunto immerge (circa) in '
                'direzione opposta alla scarpata, con Dip >= 90 - Dip_scarpata + Angolo attrito.'),
            'Ribaltamento Diretto': self.tr(
                'Ribaltamento diretto (di blocco) possibile per giunti molto ripidi con '
                'DipDir prossima a quella della scarpata: Dip >= 90 - Angolo attrito.'),
        }
        return descriptions.get(mode, '')

    # ------------------------------------------------------------------
    def _draw_kinematic(self, ax, s, planes, projection, hemisphere, legend_handles):
        mode = s['kinematic_mode']
        pairs = [(p['dipdir'], p['dip']) for p in planes]
        set_labels = [p['set'] for p in planes]
        result = sm.kinematic_analysis(
            mode, pairs, s['slope_dip'], s['slope_dipdir'], s['friction_angle'],
            s['lateral_limit'], projection, hemisphere, planes_for_intersections=pairs,
            sets_for_intersections=set_labels)

        gx, gy = sm.project_points_masked(result.slope_great_circle, projection, hemisphere)
        ax.plot(gx, gy, color='#000000', linewidth=2.0, zorder=4)
        legend_handles.append(Line2D([0], [0], color='#000000', linewidth=2.0, label=self.tr('Slope')))

        if s['show_construction_lines']:
            if result.friction_circle is not None:
                circ = result.friction_circle
                if hemisphere == 'Superiore':
                    circ = -circ   # il cerchio e' simmetrico rispetto alla verticale
                fx, fy = sm.project_points_masked(circ, projection, hemisphere)
                ax.plot(fx, fy, color='#b30000', linewidth=1.2, linestyle=':', zorder=4)
                legend_handles.append(Line2D([0], [0], color='#b30000', linewidth=1.2, linestyle=':',
                                              label=self.tr('Friction Angle ({}°)').format(int(s['friction_angle']))))

            if result.daylight_envelope:
                ex = [p[0] for p in result.daylight_envelope]
                ey = [p[1] for p in result.daylight_envelope]
                ax.plot(ex, ey, color='#000000', linewidth=1.2, zorder=4)
                legend_handles.append(Line2D([0], [0], color='#000000', linewidth=1.2,
                                              label=self.tr('Daylight Envelope')))

            # limiti laterali: diametri completi, come in Dips
            for az in result.lateral_limit_lines:
                a_rad = sm.deg2rad(az)
                ax.plot([-math.sin(a_rad), math.sin(a_rad)], [-math.cos(a_rad), math.cos(a_rad)],
                        color='#555555', linewidth=1.0, linestyle='-.', zorder=4)
            if result.lateral_limit_lines:
                legend_handles.append(Line2D([0], [0], color='#555555', linewidth=1.0, linestyle='-.',
                                              label=self.tr('Lateral Limit (±{}°)').format(int(s['lateral_limit']))))

        if s['show_highlight'] and result.highlight_polygon:
            poly = Polygon(result.highlight_polygon, closed=True, facecolor='#ff6600', alpha=0.30,
                            edgecolor='#cc5200', linewidth=0.8, zorder=2.5)
            ax.add_patch(poly)
            legend_handles.append(Polygon([(0, 0)], facecolor='#ff6600', alpha=0.30, edgecolor='#cc5200',
                                           label=self.tr('Highlighted Zone')))

        if mode == 'Scivolamento a Cuneo' and hasattr(result, 'intersections'):
            xs, ys, colors = [], [], []
            for v, feasible in zip(result.intersections, result.feasible_mask):
                x, y = sm.project_vector(v, projection, hemisphere)
                xs.append(x); ys.append(y)
                colors.append('#d40000' if feasible else '#2c3e50')
            if xs:
                ax.scatter(xs, ys, marker='^', s=30, c=colors, edgecolor='black', linewidth=0.4, zorder=6)
                legend_handles.append(Line2D([0], [0], marker='^', color='none', markerfacecolor='#d40000',
                                              markeredgecolor='black', markersize=7,
                                              label=self.tr('Critical Intersections (n={})').format(result.n_feasible)))
        else:
            if result.feasible_mask is not None:
                xs_ok, ys_ok = [], []
                for p, feasible in zip(planes, result.feasible_mask):
                    if not feasible:
                        continue
                    v = sm.pole_vector(p['dipdir'], p['dip'])
                    x, y = sm.project_vector(v, projection, hemisphere)
                    xs_ok.append(x); ys_ok.append(y)
                if xs_ok:
                    ax.scatter(xs_ok, ys_ok, marker='o', s=34, facecolor='#d40000',
                               edgecolor='black', linewidth=0.6, zorder=7)
                    legend_handles.append(Line2D([0], [0], marker='o', color='none', markerfacecolor='#d40000',
                                                  markeredgecolor='black', markersize=7,
                                                  label=self.tr('Critical Poles (n={})').format(len(xs_ok))))

        return result

    # ==================================================================
    # Analisi della piega e strumenti interattivi
    # ==================================================================
    FOLD_L_COLOR = '#c0392b'
    FOLD_AXIS_COLOR = '#6a1b9a'
    FOLD_AP_COLOR = '#d35400'
    CURSOR_COLOR = '#e0007a'
    SNAP_TOL = 0.06          # tolleranza di aggancio (unita' del disco)
    MAX_PLANE_LEGEND = 6

    def _draw_fold_and_picks(self, ax, s, projection, hemisphere, legend_handles):
        fs = font_elements_bm(s)

        def gc(pole_v, **kw):
            dd, dp = sm.plane_from_pole(pole_v)
            gx, gy = sm.project_points_masked(sm.great_circle_of_plane(dd, dp, n_pts=361),
                                              projection, hemisphere)
            ax.plot(gx, gy, **kw)
            return dd, dp

        def marker(v, label, **kw):
            x, y = sm.project_vector(v, projection, hemisphere)
            ax.plot([x], [y], linestyle='none', zorder=8, **kw)
            if label:
                ax.annotate(label, (x, y), xytext=(6, 5), textcoords='offset points',
                            color=kw.get('markeredgecolor', '#000000'), fontsize=fs,
                            fontweight='bold', zorder=8)

        # ---- poli dei fianchi (anche durante la selezione) ----
        limbs = self.fold['limbs'] if self.fold else self._pending_limbs
        for i, v in enumerate(limbs):
            name = 'L{}'.format(i + 1)
            marker(v, name, marker='s', markersize=7, markerfacecolor='#ffffff',
                   markeredgecolor=self.FOLD_L_COLOR, markeredgewidth=2.0)
            dd, dp = gc(v, color=self.FOLD_L_COLOR, linewidth=1.1, linestyle='--', zorder=5)
            legend_handles.append(Line2D(
                [0], [0], marker='s', color=self.FOLD_L_COLOR, linestyle='--', linewidth=1.1,
                markerfacecolor='#ffffff', markeredgewidth=2.0, markersize=6,
                label=self.tr('{n} limb: dip/dd {pl}, pole {ln}').format(
                    n=name, pl=sm.fmt_plane(dd, dp), ln=sm.fmt_line(v))))

        # ---- asse di piega e piano assiale ----
        if self.fold and self.fold.get('result'):
            r = self.fold['result']
            if self.fold_tab.chk_show_alt_axial.isChecked():
                gc(r['alt_pole'], color=self.FOLD_AP_COLOR, linewidth=1.0, linestyle=':', zorder=5)
                legend_handles.append(Line2D(
                    [0], [0], color=self.FOLD_AP_COLOR, linewidth=1.0, linestyle=':',
                    label=self.tr('Alt. axial plane: dip/dd {pl} (interlimb {il:.0f}°)').format(
                        pl=sm.fmt_plane(r['alt_dipdir'], r['alt_dip']), il=r['alt_interlimb'])))
            gc(r['axial_pole'], color=self.FOLD_AP_COLOR, linewidth=2.2, linestyle='-.', zorder=5)
            legend_handles.append(Line2D(
                [0], [0], color=self.FOLD_AP_COLOR, linewidth=2.2, linestyle='-.',
                label=self.tr('Axial plane: dip/dd {pl} (interlimb {il:.0f}°)').format(
                    pl=sm.fmt_plane(r['axial_dipdir'], r['axial_dip']), il=r['interlimb'])))
            marker(r['axis'], self.tr('FA'), marker='*', markersize=13,
                   markerfacecolor=self.FOLD_AXIS_COLOR, markeredgecolor=self.FOLD_AXIS_COLOR)
            legend_handles.append(Line2D(
                [0], [0], marker='*', color='none', markerfacecolor=self.FOLD_AXIS_COLOR,
                markeredgecolor=self.FOLD_AXIS_COLOR, markersize=10,
                label=self.tr('Fold axis (L1∩L2): {ln}').format(ln=sm.fmt_line(r['axis']))))

        # ---- piani salvati con il cursore ----
        for i, cp in enumerate(self.cursor_planes):
            dd, dp = gc(cp['pole'], color=self.CURSOR_COLOR, linewidth=1.3, zorder=5)
            marker(cp['pole'], cp['group'], marker='o', markersize=6,
                   markerfacecolor=self.CURSOR_COLOR, markeredgecolor='#000000', markeredgewidth=0.5)
            if i < self.MAX_PLANE_LEGEND:
                legend_handles.append(Line2D(
                    [0], [0], marker='o', color=self.CURSOR_COLOR, linewidth=1.3,
                    markerfacecolor=self.CURSOR_COLOR, markeredgecolor='#000000', markersize=5,
                    label=self.tr('{g}: dip/dd {pl}, pole {ln}').format(
                        g=cp['group'], pl=sm.fmt_plane(dd, dp), ln=sm.fmt_line(cp['pole']))))
        extra = len(self.cursor_planes) - self.MAX_PLANE_LEGEND
        if extra > 0:
            legend_handles.append(Line2D([0], [0], color='none',
                                         label=self.tr('… +{} more saved planes').format(extra)))

    # ------------------------------------------------------------------
    # Artisti "animati" per l'aggiornamento live (blitting)
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Suggerimento automatico dei poli dei fianchi
    # ------------------------------------------------------------------
    SUGGEST_COLOR = '#00897b'

    def _update_suggestion(self, planes, pole_vectors_by_set):
        sel = self.fold_tab.suggest_set()
        if sel and sel in pole_vectors_by_set:
            vecs = pole_vectors_by_set[sel]
        else:
            vecs = [v for vs in pole_vectors_by_set.values() for v in vs]
        self._suggestion = sm.suggest_limb_poles(vecs) if planes else None
        lbl = self.fold_tab.lbl_suggest
        self.fold_tab.btn_use_suggest.setEnabled(self._suggestion is not None)
        if self._suggestion is None:
            lbl.setText(self.tr('No suggestion (need ≥ 4 poles forming two distinct groups).'))
            return
        parts = []
        for i, (v, n) in enumerate(self._suggestion):
            dd, dp = sm.plane_from_pole(v)
            parts.append(self.tr('S{i}: pole {ln} → limb dip/dd {pl}  (n={n})').format(
                i=i + 1, ln=sm.fmt_line(v), pl=sm.fmt_plane(dd, dp), n=n))
        r = sm.fold_from_limbs(self._suggestion[0][0], self._suggestion[1][0])
        if r is not None:
            parts.append(self.tr('→ fold axis {ax}, axial plane dip/dd {ap}').format(
                ax=sm.fmt_line(r['axis']), ap=sm.fmt_plane(r['axial_dipdir'], r['axial_dip'])))
        lbl.setText('\n'.join(parts))

    def _draw_suggestion(self, ax, s, projection, hemisphere, legend_handles):
        if self._suggestion is None:
            return
        show = self.fold_tab.chk_show_suggest.isChecked()
        for i, (v, n) in enumerate(self._suggestion):
            x, y = sm.project_vector(v, projection, hemisphere)
            self._snap_targets.append((x, y, v))
            if not show:
                continue
            ax.plot([x], [y], marker='D', markersize=10, markerfacecolor='none',
                    markeredgecolor=self.SUGGEST_COLOR, markeredgewidth=2.0,
                    linestyle='none', zorder=7.5)
            ax.annotate('S{}'.format(i + 1), (x, y), xytext=(7, -12), textcoords='offset points',
                        color=self.SUGGEST_COLOR, fontsize=font_elements_bm(s), fontweight='bold',
                        zorder=7.5)
        if show:
            legend_handles.append(Line2D(
                [0], [0], marker='D', color='none', markerfacecolor='none',
                markeredgecolor=self.SUGGEST_COLOR, markeredgewidth=2.0, markersize=7,
                label=self.tr('Suggested limb poles: S1 {a}, S2 {b}').format(
                    a=sm.fmt_line(self._suggestion[0][0]), b=sm.fmt_line(self._suggestion[1][0]))))

    def _on_use_suggestion(self):
        if self._suggestion is None:
            return
        self._exit_modes()
        self._pending_limbs = [self._suggestion[0][0], self._suggestion[1][0]]
        self._complete_fold()

    # ------------------------------------------------------------------
    # Contorni: casella "Show pole density contours" nella scheda Folds
    # ------------------------------------------------------------------
    def _on_fold_contours_toggled(self, on):
        cmb = self.stereonet_tab.cmb_contours
        current = trc.combo_value(cmb)
        if on and current == 'Nessuno':
            trc.set_combo_value(cmb, 'Poli (Vettori)')
        elif not on and current != 'Nessuno':
            trc.set_combo_value(cmb, 'Nessuno')
        self._on_stereonet_options_changed()

    def _sync_fold_contour_checkbox(self, *args):
        chk = self.fold_tab.chk_contours
        chk.blockSignals(True)
        chk.setChecked(trc.combo_value(self.stereonet_tab.cmb_contours) != 'Nessuno')
        chk.blockSignals(False)

    def _create_live_artists(self, ax, s):
        line, = ax.plot([], [], color=self.CURSOR_COLOR, linewidth=1.8, zorder=9, animated=True)
        pt, = ax.plot([], [], marker='o', markersize=8, markerfacecolor='none',
                      markeredgecolor=self.CURSOR_COLOR, markeredgewidth=2.0,
                      linestyle='none', zorder=9, animated=True)
        snap, = ax.plot([], [], marker='o', markersize=13, markerfacecolor='none',
                        markeredgecolor='#ff9800', markeredgewidth=2.0,
                        linestyle='none', zorder=9, animated=True)
        txt = ax.text(-1.28, -1.28, '', ha='left', va='bottom', zorder=10, animated=True,
                      fontsize=font_elements_bm(s), fontweight='bold', color='#222222',
                      bbox=dict(boxstyle='round,pad=0.35', facecolor='#ffffff',
                                edgecolor=self.CURSOR_COLOR, alpha=0.95))
        txt.set_visible(False)
        self._live_line, self._live_pt, self._live_snap, self._live_txt = line, pt, snap, txt
        self._live_artists = [line, pt, snap, txt]

    def _on_canvas_draw(self, event):
        try:
            self._live_bg = self.canvas.copy_from_bbox(self.figure.bbox)
        except Exception:
            self._live_bg = None
        for a in self._live_artists:
            try:
                a.axes.draw_artist(a)
            except Exception:
                pass

    def _blit_live(self):
        if not self._live_artists:
            return
        if self._live_bg is None:
            self.canvas.draw_idle()
            return
        self.canvas.restore_region(self._live_bg)
        for a in self._live_artists:
            a.axes.draw_artist(a)
        self.canvas.blit(self.figure.bbox)

    def _hide_live(self):
        if not self._live_artists:
            return
        self._live_line.set_data([], [])
        self._live_pt.set_data([], [])
        self._live_snap.set_data([], [])
        self._live_txt.set_visible(False)
        self._blit_live()

    # ------------------------------------------------------------------
    # Modalita'
    # ------------------------------------------------------------------
    def _on_pick_limbs_toggled(self, on):
        t = self.fold_tab
        if on:
            if t.btn_live_plane.isChecked():
                t.btn_live_plane.setChecked(False)
            self._pick_mode = 'limbs'
            self._pending_limbs = []
            self.canvas.setCursor(Qt.CursorShape.CrossCursor)
            self.lbl_status.setText(self.tr('Click the pole to limb L1 (right-click to cancel).'))
        else:
            if self._pick_mode == 'limbs':
                self._pick_mode = None
                self.canvas.unsetCursor()
                if self._pending_limbs:      # uscita prima di aver scelto L2
                    self._pending_limbs = []
                    self.lbl_status.setText(self.tr('Limb picking cancelled.'))
                self._hide_live()
                self.redraw()

    def _on_live_plane_toggled(self, on):
        t = self.fold_tab
        if on:
            if t.btn_pick_limbs.isChecked():
                t.btn_pick_limbs.setChecked(False)
            self._pick_mode = 'live'
            self.canvas.setCursor(Qt.CursorShape.CrossCursor)
            self.lbl_status.setText(self.tr(
                'Live plane cursor: move to a pole position, left-click to save, right-click to exit.'))
        else:
            if self._pick_mode == 'live':
                self._pick_mode = None
                self.canvas.unsetCursor()
                self._hide_live()
                self.lbl_status.setText(self.tr('Live plane cursor off.'))

    def _exit_modes(self):
        t = self.fold_tab
        t.btn_pick_limbs.setChecked(False)
        t.btn_live_plane.setChecked(False)

    # ------------------------------------------------------------------
    # Eventi del mouse
    # ------------------------------------------------------------------
    def _event_vector(self, event, allow_snap):
        """Vettore 3D (polo) sotto il cursore, con eventuale aggancio.
        Ritorna (vec, snapped_xy) o (None, None)."""
        if self.ax is None or event.inaxes is not self.ax or event.xdata is None:
            return None, None
        x, y = event.xdata, event.ydata
        if allow_snap and self.fold_tab.chk_snap.isChecked() and self._snap_targets:
            best = min(self._snap_targets, key=lambda t: (t[0] - x) ** 2 + (t[1] - y) ** 2)
            if math.hypot(best[0] - x, best[1] - y) <= self.SNAP_TOL:
                return sm.lower_vector(best[2]), (best[0], best[1])
        v = sm.inverse_project(x, y, self.settings['projection'], self.settings['hemisphere'])
        if v is None:
            return None, None
        return sm.lower_vector(v), None

    def _on_canvas_leave(self, event):
        if self._pick_mode:
            self._hide_live()

    def _on_canvas_motion(self, event):
        if self._pick_mode is None or not self._live_artists:
            return
        v, snapped = self._event_vector(event, allow_snap=(self._pick_mode == 'limbs'))
        if v is None:
            self._hide_live()
            return
        s = self.settings
        dd, dp = sm.plane_from_pole(v)
        pole_txt = sm.fmt_line(v)
        plane_txt = sm.fmt_plane(dd, dp)
        x, y = sm.project_vector(v, s['projection'], s['hemisphere'])

        if self._pick_mode == 'live':
            gx, gy = sm.project_points_masked(sm.great_circle_of_plane(dd, dp, n_pts=361),
                                              s['projection'], s['hemisphere'])
            self._live_line.set_data(gx, gy)
            self._live_pt.set_data([x], [y])
            self._live_snap.set_data([], [])
            self._live_txt.set_text(self.tr('Pole  {p}\nPlane dip/dd  {pl}').format(p=pole_txt, pl=plane_txt))
            self.fold_tab.lbl_live.setText(
                self.tr('Pole: {p}   Plane (dip/dd): {pl}').format(p=pole_txt, pl=plane_txt))
        else:  # limbs
            self._live_line.set_data([], [])
            self._live_pt.set_data([x], [y])
            self._live_snap.set_data(([snapped[0]], [snapped[1]]) if snapped else ([], []))
            n = len(self._pending_limbs) + 1
            self._live_txt.set_text(self.tr('L{n} pole  {p}\nlimb dip/dd  {pl}{snap}').format(
                n=n, p=pole_txt, pl=plane_txt, snap=self.tr('  [snap]') if snapped else ''))
        self._live_txt.set_visible(True)
        self._blit_live()

    def _on_canvas_click(self, event):
        if self._pick_mode is None:
            return
        if event.button == 3:     # tasto destro: esci
            self._exit_modes()
            return
        if event.button != 1:
            return
        v, _snapped = self._event_vector(event, allow_snap=(self._pick_mode == 'limbs'))
        if v is None:
            return

        if self._pick_mode == 'limbs':
            if not self._pending_limbs:
                self.fold = None      # una nuova selezione sostituisce la piega a video
            self._pending_limbs.append(v)
            if len(self._pending_limbs) == 1:
                self.lbl_status.setText(self.tr('L1 picked. Click the pole to limb L2.'))
                self.redraw()
                return
            self._complete_fold()
        else:  # live
            self._plane_count += 1
            group = self.tr('P{}').format(self._plane_count)
            self.cursor_planes.append({'pole': v, 'group': group})
            dd, dp = sm.plane_from_pole(v)
            t, pl = sm.line_trend_plunge(v)
            self.pick_records.append(self._record(group, 'Plane (cursor)', dd, dp, t, pl, None, None))
            self._sync_picks_layer()
            self.lbl_status.setText(self.tr('{g} saved: plane dip/dd {pl}, pole {ln}.').format(
                g=group, pl=sm.fmt_plane(dd, dp), ln=sm.fmt_line(v)))
            self.redraw()

    # ------------------------------------------------------------------
    def _complete_fold(self):
        l1, l2 = self._pending_limbs[:2]
        self._pending_limbs = []
        result = sm.fold_from_limbs(l1, l2, swap=False)
        if result is None:
            QMessageBox.warning(self, self.tr('Fold analysis'),
                                self.tr('L1 and L2 are (almost) parallel: no fold axis can be defined.'))
            self.fold = None
            self.fold_tab.btn_pick_limbs.setChecked(False)
            self.redraw()
            return
        self._fold_count += 1
        self.fold = {'limbs': [l1, l2], 'group': self.tr('Fold {}').format(self._fold_count),
                     'swap': False, 'result': result}
        self._store_fold_records()
        self._update_fold_label()
        self.lbl_status.setText(self.tr('{g}: axial plane computed and saved.').format(g=self.fold['group']))
        if self.fold_tab.btn_pick_limbs.isChecked():
            self.fold_tab.btn_pick_limbs.setChecked(False)   # esce dalla modalita' e ridisegna
        else:
            self.redraw()

    def _on_swap_axial(self):
        if not self.fold:
            return
        self.fold['swap'] = not self.fold['swap']
        self.fold['result'] = sm.fold_from_limbs(*self.fold['limbs'], swap=self.fold['swap'])
        self._store_fold_records()
        self._update_fold_label()
        self.redraw()

    def _update_fold_label(self):
        lbl = self.fold_tab.lbl_fold_result
        if not self.fold or not self.fold.get('result'):
            lbl.setText(self.tr('No fold defined.'))
            return
        r = self.fold['result']
        l1, l2 = self.fold['limbs']
        d1, p1 = sm.plane_from_pole(l1)
        d2, p2 = sm.plane_from_pole(l2)
        lbl.setText(self.tr(
            '<b>{g}</b><br>'
            'L1 limb: dip/dd {l1} (pole {pl1})<br>'
            'L2 limb: dip/dd {l2} (pole {pl2})<br>'
            'Fold axis (L1∩L2): <b>{ax}</b><br>'
            'Axial plane: <b>dip/dd {ap}</b> — interlimb {il:.0f}°<br>'
            'Alternate: dip/dd {alt} — interlimb {ail:.0f}°').format(
                g=self.fold['group'],
                l1=sm.fmt_plane(d1, p1), pl1=sm.fmt_line(l1),
                l2=sm.fmt_plane(d2, p2), pl2=sm.fmt_line(l2),
                ax=sm.fmt_line(r['axis']),
                ap=sm.fmt_plane(r['axial_dipdir'], r['axial_dip']), il=r['interlimb'],
                alt=sm.fmt_plane(r['alt_dipdir'], r['alt_dip']), ail=r['alt_interlimb']))

    def _on_clear_picks(self):
        self._exit_modes()
        self._pending_limbs = []
        self.fold = None
        self.cursor_planes = []
        self._update_fold_label()
        self.fold_tab.lbl_live.setText(self.tr('Pole: –   Plane: –'))
        self.lbl_status.setText(self.tr('Picks cleared from the plot (still stored in the picks layer).'))
        self.redraw()

    # ------------------------------------------------------------------
    # Archivio delle selezioni: layer tabellare di progetto + CSV
    # ------------------------------------------------------------------
    PICK_FIELDS = ['group', 'type', 'dip', 'dipdir', 'pole_trend', 'pole_plunge',
                   'line_trend', 'line_plunge', 'note']

    @staticmethod
    def _record(group, typ, dipdir, dip, pole_trend, pole_plunge, line_trend, line_plunge, note=''):
        r2 = lambda v: None if v is None else round(float(v), 1)
        return {'group': group, 'type': typ, 'dip': r2(dip), 'dipdir': r2(dipdir),
                'pole_trend': r2(pole_trend), 'pole_plunge': r2(pole_plunge),
                'line_trend': r2(line_trend), 'line_plunge': r2(line_plunge), 'note': note or ''}

    def _store_fold_records(self):
        g = self.fold['group']
        r = self.fold['result']
        self.pick_records = [rec for rec in self.pick_records if rec['group'] != g]
        for name, v in zip(('L1 limb', 'L2 limb'), self.fold['limbs']):
            dd, dp = sm.plane_from_pole(v)
            t, pl = sm.line_trend_plunge(v)
            self.pick_records.append(self._record(g, name, dd, dp, t, pl, None, None))
        at, apl = sm.line_trend_plunge(r['axis'])
        self.pick_records.append(self._record(g, 'Fold axis (L1∩L2)', None, None, None, None, at, apl))
        pt, ppl = sm.line_trend_plunge(r['axial_pole'])
        self.pick_records.append(self._record(
            g, 'Axial plane', r['axial_dipdir'], r['axial_dip'], pt, ppl, None, None,
            'interlimb {:.0f}; alt. axial plane {} (interlimb {:.0f})'.format(
                r['interlimb'], sm.fmt_plane(r['alt_dipdir'], r['alt_dip']), r['alt_interlimb'])))
        self._sync_picks_layer()

    def _picks_layer(self):
        project = QgsProject.instance()
        layer = project.mapLayer(self._picks_layer_id) if self._picks_layer_id else None
        if layer is None:
            uri = ('None?field=group:string(30)&field=type:string(40)'
                   '&field=dip:double&field=dipdir:double'
                   '&field=pole_trend:double&field=pole_plunge:double'
                   '&field=line_trend:double&field=line_plunge:double'
                   '&field=note:string(160)')
            layer = QgsVectorLayer(uri, 'StereonetStudio picks', 'memory')
            if not layer.isValid():
                return None
            project.addMapLayer(layer)
            self._picks_layer_id = layer.id()
        return layer

    def _sync_picks_layer(self):
        """Riscrive il layer tabellare con l'archivio corrente."""
        try:
            layer = self._picks_layer()
            if layer is None:
                return
            pr = layer.dataProvider()
            ids = [f.id() for f in layer.getFeatures()]
            if ids:
                pr.deleteFeatures(ids)
            feats = []
            for rec in self.pick_records:
                f = QgsFeature(layer.fields())
                f.setAttributes([rec[k] for k in self.PICK_FIELDS])
                feats.append(f)
            pr.addFeatures(feats)
            layer.triggerRepaint()
            layer.reload()
        except Exception as exc:  # il salvataggio non deve bloccare il disegno
            self.lbl_status.setText(self.tr('Could not update picks layer: {}').format(exc))

    def _export_picks_csv(self):
        if not self.pick_records:
            QMessageBox.information(self, self.tr('Export picks'), self.tr('No picks saved yet.'))
            return
        path, _ = QFileDialog.getSaveFileName(self, self.tr('Export picks'), 'stereonet_picks.csv',
                                              self.tr('CSV (*.csv)'))
        if not path:
            return
        if not path.lower().endswith('.csv'):
            path += '.csv'
        try:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=self.PICK_FIELDS)
                w.writeheader()
                for rec in self.pick_records:
                    w.writerow({k: ('' if rec[k] is None else rec[k]) for k in self.PICK_FIELDS})
            self.lbl_status.setText(self.tr('{} picks exported to {}').format(len(self.pick_records), path))
        except Exception as exc:
            QMessageBox.warning(self, self.tr('Error'), self.tr('Could not write file:\n{}').format(exc))
