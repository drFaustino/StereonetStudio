# -*- coding: utf-8 -*-
"""StereonetStudio - scheda Acquisizione da DTM."""

import csv

from qgis.PyQt.QtCore import pyqtSignal, Qt
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel,
    QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QFileDialog,
    QCheckBox
)
from qgis.core import (
    QgsProject, QgsMapLayerType, QgsVectorLayer, QgsField, QgsFields,
    QgsFeature, QgsGeometry, QgsPointXY, QgsVectorFileWriter,
    QgsCoordinateTransformContext, Qgis
)
from qgis.PyQt.QtCore import QVariant

from . import icons
from . import settings as cfg
from .widgets_common import HintLabel


class DTMTab(QWidget):
    """Interfaccia a tre livelli per acquisire orientazioni locali dal DTM."""

    acquire_requested = pyqtSignal(object, int, bool)  # layer, radius, continuous
    clear_requested = pyqtSignal()
    data_row_ready = pyqtSignal(object, str)  # {'v1','v2','set'}, format

    HEADERS = [
        'ID', 'X', 'Y', 'Z DTM', 'Dip', 'Dip Direction', 'Strike',
        'Pole Trend', 'Pole Plunge', 'RMSE', 'Max Resid.', 'N campioni',
        'Raggio', 'Set / Gruppo', 'CRS'
    ]

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self._records = []
        self._building = False
        self._build_ui()
        self.refresh_layers()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(7)

        title = QLabel(self.tr('Acquisizione orientazione da DTM'))
        title.setStyleSheet('font-weight: 600; font-size: 10.5pt; color:#1f6fb2;')
        layout.addWidget(title)
        hint = HintLabel(self.tr(
            'Clicca sulla superficie del DTM per stimare il piano locale e ottenere dip, direzione di immersione e dati topografici.'
        ))
        layout.addWidget(hint)

        # ---------------- Livello 1 ----------------
        g1 = QGroupBox(self.tr('Livello 1 — Acquisizione base'))
        grid = QGridLayout(g1)
        grid.setColumnStretch(1, 1)
        grid.addWidget(QLabel(self.tr('DTM:')), 0, 0)
        self.cmb_dtm = QComboBox()
        grid.addWidget(self.cmb_dtm, 0, 1)
        self.btn_refresh = QPushButton(icons.icon_layers(), self.tr(' Aggiorna'))
        grid.addWidget(self.btn_refresh, 0, 2)

        grid.addWidget(QLabel(self.tr('Metodo:')), 1, 0)
        self.cmb_method = QComboBox()
        self.cmb_method.addItem(self.tr('Piano locale — fit ai minimi quadrati'), 'least_squares')
        grid.addWidget(self.cmb_method, 1, 1, 1, 2)

        grid.addWidget(QLabel(self.tr('Raggio:')), 2, 0)
        self.spn_radius = QSpinBox()
        self.spn_radius.setRange(1, 15)
        self.spn_radius.setValue(3)
        self.spn_radius.setSuffix(self.tr(' celle'))
        grid.addWidget(self.spn_radius, 2, 1)

        grid.addWidget(QLabel(self.tr('Formato destinazione:')), 3, 0)
        self.lbl_format = QLabel(self.tr('Dip / Direzione Immersione'))
        self.lbl_format.setStyleSheet('font-weight: 600; color:#2c3e50;')
        grid.addWidget(self.lbl_format, 3, 1, 1, 2)

        grid.addWidget(QLabel(self.tr('Set / Gruppo:')), 4, 0)
        self.txt_set = QLineEdit('DTM')
        grid.addWidget(self.txt_set, 4, 1, 1, 2)

        self.btn_acquire = QPushButton(icons.icon_dot(), self.tr(' Acquisisci da DTM'))
        self.btn_acquire.setObjectName('SNPrimaryButton')
        row = QHBoxLayout()
        row.addWidget(self.btn_acquire)
        row.addStretch()
        grid.addLayout(row, 5, 0, 1, 3)

        self.lbl_finish = QLabel(self.tr('Per concludere l’acquisizione, clicca con il tasto destro sulla mappa.'))
        self.lbl_finish.setWordWrap(True)
        self.lbl_finish.setStyleSheet('color:#666; font-style: italic; padding: 2px 0;')
        grid.addWidget(self.lbl_finish, 6, 0, 1, 3)
        layout.addWidget(g1)

        # ---------------- Livello 2 ----------------
        g2 = QGroupBox(self.tr('Livello 2 — Controllo qualità'))
        grid2 = QGridLayout(g2)
        self.spn_rmse = QDoubleSpinBox()
        self.spn_rmse.setRange(0.0, 1e9)
        self.spn_rmse.setDecimals(4)
        self.spn_rmse.setValue(1.0)
        self.spn_rmse.setSuffix(self.tr(' unità Z'))
        self.chk_quality = QCheckBox(self.tr('Segnala quando RMSE supera la soglia'))
        self.chk_quality.setChecked(True)
        self.chk_reject = QCheckBox(self.tr('Non trasferire alla tabella Data se sopra soglia'))
        self.chk_reject.setChecked(False)
        grid2.addWidget(QLabel(self.tr('Soglia RMSE:')), 0, 0)
        grid2.addWidget(self.spn_rmse, 0, 1)
        grid2.addWidget(self.chk_quality, 1, 0, 1, 2)
        grid2.addWidget(self.chk_reject, 2, 0, 1, 2)
        self.lbl_quality = QLabel(self.tr('Qualità: nessuna acquisizione'))
        self.lbl_quality.setWordWrap(True)
        grid2.addWidget(self.lbl_quality, 3, 0, 1, 2)
        layout.addWidget(g2)

        # ---------------- Livello 3 ----------------
        g3 = QGroupBox(self.tr('Livello 3 — Acquisizione multipla'))
        grid3 = QGridLayout(g3)
        self.chk_continuous = QCheckBox(self.tr('Mantieni lo strumento attivo dopo ogni click'))
        self.chk_continuous.setChecked(True)
        grid3.addWidget(self.chk_continuous, 0, 0, 1, 2)
        self.lbl_count = QLabel(self.tr('Misure acquisite: 0'))
        grid3.addWidget(self.lbl_count, 1, 0)
        self.btn_export = QPushButton(icons.icon_export(), self.tr(' Esporta tabella DTM...'))
        self.btn_clear = QPushButton(icons.icon_clear(), self.tr(' Svuota tabella'))
        grid3.addWidget(self.btn_clear, 1, 1)
        grid3.addWidget(self.btn_export, 2, 0, 1, 2)
        layout.addWidget(g3)

        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels([self.tr(h) for h in self.HEADERS])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)

        self.btn_refresh.clicked.connect(self.refresh_layers)
        self.btn_acquire.clicked.connect(self._request_acquire)
        self.btn_clear.clicked.connect(self.clear_requested.emit)
        self.btn_export.clicked.connect(self._export_csv)

    def set_input_format(self, fmt):
        self.lbl_format.setText(fmt or '')

    def refresh_layers(self):
        current = self.cmb_dtm.currentData()
        self.cmb_dtm.blockSignals(True)
        self.cmb_dtm.clear()
        for layer in QgsProject.instance().mapLayers().values():
            if layer.type() == QgsMapLayerType.RasterLayer:
                self.cmb_dtm.addItem(layer.name(), layer.id())
        if current:
            idx = self.cmb_dtm.findData(current)
            if idx >= 0:
                self.cmb_dtm.setCurrentIndex(idx)
        self.cmb_dtm.blockSignals(False)
        if self.cmb_dtm.count() == 0:
            self.cmb_dtm.addItem(self.tr('Nessun raster disponibile'), '')

    def selected_layer(self):
        layer_id = self.cmb_dtm.currentData()
        return QgsProject.instance().mapLayer(layer_id) if layer_id else None

    def _request_acquire(self):
        layer = self.selected_layer()
        if layer is None:
            QMessageBox.warning(self, self.tr('DTM'), self.tr('Seleziona un raster DTM valido.'))
            return
        self.btn_acquire.setEnabled(False)
        self.acquire_requested.emit(layer, self.spn_radius.value(), self.chk_continuous.isChecked())

    def acquisition_started(self):
        self.btn_acquire.setEnabled(False)

    def acquisition_stopped(self):
        self.btn_acquire.setEnabled(True)

    def add_record(self, result, fmt):
        rec_id = len(self._records) + 1
        set_name = self.txt_set.text().strip() or 'DTM'
        record = {
            'id': rec_id,
            'x': result.x,
            'y': result.y,
            'z': result.z,
            'dip': result.dip,
            'dipdir': result.dipdir,
            'strike': result.strike,
            'pole_trend': result.pole_trend,
            'pole_plunge': result.pole_plunge,
            'rmse': result.rmse,
            'max_residual': result.max_residual,
            'sample_count': result.sample_count,
            'radius': result.radius_cells,
            'set': set_name,
            'crs': result.raster_crs,
        }
        self._records.append(record)
        self._append_table_row(record)
        self.lbl_count.setText(self.tr('Misure acquisite: {}').format(len(self._records)))
        quality = self.tr('OK') if result.rmse <= self.spn_rmse.value() else self.tr('sopra soglia')
        self.lbl_quality.setText(self.tr(
            'Ultima misura: Dip {:.2f}°, Dip Direction {:.2f}°, RMSE {:.4f} — {}.'
        ).format(result.dip, result.dipdir, result.rmse, quality))

        if result.rmse > self.spn_rmse.value() and self.chk_reject.isChecked():
            self.lbl_quality.setText(self.lbl_quality.text() + self.tr(' La misura resta nella tabella DTM ma non viene trasferita in Data.'))
            return

        v1, v2 = self._format_values(result.dip, result.dipdir, fmt)
        self.data_row_ready.emit({'v1': v1, 'v2': v2, 'set': set_name}, fmt)

    @staticmethod
    def _format_values(dip, dipdir, fmt):
        if fmt == 'Dip / Direzione Immersione':
            return dip, dipdir
        if fmt == 'Direzione (destra) / Dip':
            return (dipdir - 90.0) % 360.0, dip
        if fmt == 'Direzione (sinistra) / Dip':
            return (dipdir + 90.0) % 360.0, dip
        # Trend / Plunge del polo inferiore.
        return (dipdir + 180.0) % 360.0, 90.0 - dip

    def _append_table_row(self, r):
        row = self.table.rowCount()
        self.table.insertRow(row)
        values = [
            r['id'], f"{r['x']:.3f}", f"{r['y']:.3f}", f"{r['z']:.3f}",
            f"{r['dip']:.2f}", f"{r['dipdir']:.2f}", f"{r['strike']:.2f}",
            f"{r['pole_trend']:.2f}", f"{r['pole_plunge']:.2f}",
            f"{r['rmse']:.4f}", f"{r['max_residual']:.4f}", r['sample_count'],
            r['radius'], r['set'], r['crs']
        ]
        for col, value in enumerate(values):
            self.table.setItem(row, col, QTableWidgetItem(str(value)))

    def records(self):
        return list(self._records)

    def clear_records(self):
        self._records = []
        self.table.setRowCount(0)
        self.lbl_count.setText(self.tr('Misure acquisite: 0'))
        self.lbl_quality.setText(self.tr('Qualità: nessuna acquisizione'))

    def _export_csv(self):
        if not self._records:
            QMessageBox.information(self, self.tr('Esporta'), self.tr('Non ci sono misure da esportare.'))
            return

        path, selected_filter = QFileDialog.getSaveFileName(
            self, self.tr('Esporta tabella DTM'), 'dtm_orientations.csv',
            self.tr('CSV (*.csv);;ESRI Shapefile (*.shp);;GeoPackage (*.gpkg)')
        )
        if not path:
            return

        try:
            low = path.lower()
            if selected_filter.startswith('ESRI Shapefile') or low.endswith('.shp'):
                if not low.endswith('.shp'):
                    path += '.shp'
                self._export_vector(path, 'ESRI Shapefile')
            elif selected_filter.startswith('GeoPackage') or low.endswith('.gpkg'):
                if not low.endswith('.gpkg'):
                    path += '.gpkg'
                self._export_vector(path, 'GPKG')
            else:
                if not low.endswith('.csv'):
                    path += '.csv'
                with open(path, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f, delimiter=';')
                    writer.writerow(self.HEADERS)
                    for r in self._records:
                        writer.writerow([
                            r['id'], r['x'], r['y'], r['z'], r['dip'], r['dipdir'],
                            r['strike'], r['pole_trend'], r['pole_plunge'], r['rmse'],
                            r['max_residual'], r['sample_count'], r['radius'], r['set'], r['crs']
                        ])
                self._ask_load_export(path)
        except Exception as exc:
            QMessageBox.warning(self, self.tr('Errore'), self.tr('Impossibile esportare la tabella DTM:\n{}').format(exc))

    def _export_vector(self, path, driver_name):
        # Le misure DTM sono punti: X/Y sono mantenute nel CRS del raster
        # indicato nella registrazione. Per dataset misti il CRS viene assunto
        # quello della prima misura (normalmente tutte provengono dallo stesso DTM).
        crs_authid = self._records[0].get('crs', '')
        layer_crs = None
        if crs_authid:
            try:
                from qgis.core import QgsCoordinateReferenceSystem
                layer_crs = QgsCoordinateReferenceSystem(crs_authid)
            except Exception:
                layer_crs = None

        crs_part = crs_authid if layer_crs and layer_crs.isValid() else 'EPSG:4326'
        mem = QgsVectorLayer(f'Point?crs={crs_part}', 'DTM_Orientations', 'memory')
        if not mem.isValid():
            raise RuntimeError(self.tr('Impossibile creare il layer vettoriale temporaneo.'))
        pr = mem.dataProvider()
        fields = QgsFields()
        definitions = [
            ('ID', QVariant.Int), ('X', QVariant.Double), ('Y', QVariant.Double),
            ('Z_DTM', QVariant.Double), ('Dip', QVariant.Double),
            ('Dip_Dir', QVariant.Double), ('Strike', QVariant.Double),
            ('Pole_Tr', QVariant.Double), ('Pole_Pl', QVariant.Double),
            ('RMSE', QVariant.Double), ('Max_Res', QVariant.Double),
            ('N_Samp', QVariant.Int), ('Radius', QVariant.Int),
            ('Set', QVariant.String), ('CRS', QVariant.String)
        ]
        for name, typ in definitions:
            fields.append(QgsField(name, typ))
        pr.addAttributes(list(fields))
        mem.updateFields()

        feats = []
        for r in self._records:
            f = QgsFeature(mem.fields())
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(float(r['x']), float(r['y']))))
            f.setAttributes([
                int(r['id']), float(r['x']), float(r['y']), float(r['z']),
                float(r['dip']), float(r['dipdir']), float(r['strike']),
                float(r['pole_trend']), float(r['pole_plunge']), float(r['rmse']),
                float(r['max_residual']), int(r['sample_count']), int(r['radius']),
                str(r['set']), str(r['crs'])
            ])
            feats.append(f)
        pr.addFeatures(feats)
        mem.updateExtents()

        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = driver_name
        options.fileEncoding = 'UTF-8'
        options.layerName = 'DTM_Orientations'
        if driver_name == 'GPKG':
            options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
        else:
            options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile

        result = QgsVectorFileWriter.writeAsVectorFormatV3(
            mem, path, QgsProject.instance().transformContext(), options
        )
        err = result[0] if isinstance(result, tuple) else result
        if err != QgsVectorFileWriter.NoError:
            message = result[1] if isinstance(result, tuple) and len(result) > 1 else str(err)
            raise RuntimeError(str(message))
        self._ask_load_export(path)

    def _ask_load_export(self, path):
        answer = QMessageBox.question(
            self, self.tr('Esportazione completata'),
            self.tr('File esportato in:\n{}\n\nVuoi caricarlo automaticamente nel progetto QGIS?').format(path),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if answer == QMessageBox.StandardButton.Yes:
            try:
                layer_name = path.replace('\\', '/').rsplit('/', 1)[-1].rsplit('.', 1)[0]
                layer = QgsVectorLayer(path, layer_name, 'ogr')
                if layer.isValid():
                    QgsProject.instance().addMapLayer(layer)
                else:
                    QMessageBox.warning(self, self.tr('Caricamento'), self.tr('Il file è stato esportato, ma non è stato possibile caricarlo nel progetto QGIS.'))
            except Exception as exc:
                QMessageBox.warning(self, self.tr('Caricamento'), self.tr('Il file è stato esportato, ma il caricamento nel progetto QGIS non è riuscito:\n{}').format(exc))
