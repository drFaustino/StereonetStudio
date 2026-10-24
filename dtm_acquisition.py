# -*- coding: utf-8 -*-
"""StereonetStudio - acquisizione di orientazioni locali da DTM.

Il modulo contiene lo strumento QgsMapTool e le funzioni di campionamento/
fit del piano locale. L'orientazione restituita e' dip/dip-direction.
"""

import math
import numpy as np

from qgis.PyQt.QtCore import pyqtSignal, Qt
from qgis.PyQt.QtGui import QColor, QCursor
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.gui import QgsMapTool
from qgis.core import (
    QgsPointXY,
    QgsRaster,
    QgsWkbTypes,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject,
    QgsMapLayerType,
    QgsRectangle,
)


class DTMPlaneResult:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def _identify_value(provider, point):
    result = provider.identify(point, QgsRaster.IdentifyFormatValue)
    if not result.isValid():
        return None
    values = result.results()
    if not values:
        return None
    value = next(iter(values.values()))
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    return value


def _local_metric_transform(source_crs, center, project_crs):
    """Restituisce una trasformazione verso coordinate metriche locali.

    Per DTM con CRS proiettato si usa il CRS del progetto quando anch'esso e'
    proiettato; altrimenti si usa direttamente il CRS del raster. Per CRS
    geografici viene creato un piccolo sistema azimutale equidistante locale.
    """
    target = source_crs
    if project_crs.isValid() and not project_crs.isGeographic():
        target = project_crs

    if target.isGeographic():
        try:
            wgs84 = QgsCoordinateReferenceSystem('EPSG:4326')
            to_wgs = QgsCoordinateTransform(source_crs, wgs84, QgsProject.instance())
            ll = to_wgs.transform(center)
            proj4 = (
                '+proj=aeqd +lat_0={:.12f} +lon_0={:.12f} '
                '+datum=WGS84 +units=m +no_defs'
            ).format(ll.y(), ll.x())
            local = QgsCoordinateReferenceSystem.fromProj(proj4)
            return QgsCoordinateTransform(source_crs, local, QgsProject.instance()), local
        except Exception:
            return None, None

    try:
        return QgsCoordinateTransform(source_crs, target, QgsProject.instance()), target
    except Exception:
        return None, None


def fit_local_plane(layer, click_point_map, radius_cells=3, project_crs=None):
    """Campiona una finestra quadrata del raster e stima z=a*x+b*y+c.

    Ritorna DTMPlaneResult con dip, dipdir, strike, polo, coordinate e
    indicatori di qualita'. Le coordinate X/Y sono nel CRS del raster.
    """
    if layer is None or layer.type() != QgsMapLayerType.RasterLayer:
        raise ValueError('Il layer selezionato non e\u0300 un raster.')
    if layer.bandCount() < 1:
        raise ValueError('Il DTM non contiene bande raster.')

    provider = layer.dataProvider()
    extent = layer.extent()
    xsize = provider.xSize()
    ysize = provider.ySize()
    if xsize <= 0 or ysize <= 0:
        raise ValueError('Dimensioni raster non valide.')

    to_raster = QgsCoordinateTransform(
        project_crs or QgsProject.instance().crs(),
        layer.crs(), QgsProject.instance()
    )
    center = to_raster.transform(QgsPointXY(click_point_map))

    px = extent.width() / float(xsize)
    py = extent.height() / float(ysize)
    if px <= 0 or py <= 0:
        raise ValueError('Risoluzione raster non valida.')

    radius = max(1, int(radius_cells))
    # Limita il numero massimo di campioni per mantenere reattivo lo strumento.
    radius = min(radius, 15)

    points = []
    values = []
    center_x_index = int((center.x() - extent.xMinimum()) / px)
    center_y_index = int((extent.yMaximum() - center.y()) / py)

    for row in range(center_y_index - radius, center_y_index + radius + 1):
        if row < 0 or row >= ysize:
            continue
        y = extent.yMaximum() - (row + 0.5) * py
        for col in range(center_x_index - radius, center_x_index + radius + 1):
            if col < 0 or col >= xsize:
                continue
            x = extent.xMinimum() + (col + 0.5) * px
            p = QgsPointXY(x, y)
            z = _identify_value(provider, p)
            if z is None:
                continue
            points.append(p)
            values.append(z)

    if len(points) < 3:
        raise ValueError('Campioni validi insufficienti: servono almeno 3 celle.')

    metric_transform, metric_crs = _local_metric_transform(
        layer.crs(), center, project_crs or QgsProject.instance().crs()
    )
    if metric_transform is None:
        raise ValueError('Impossibile trasformare le coordinate del DTM in un sistema metrico locale.')

    metric = [metric_transform.transform(p) for p in points]
    x0 = metric[0].x()
    y0 = metric[0].y()
    A = np.array([[p.x() - x0, p.y() - y0, 1.0] for p in metric], dtype=float)
    z = np.asarray(values, dtype=float)
    coeff, residuals, rank, _ = np.linalg.lstsq(A, z, rcond=None)
    if rank < 3:
        raise ValueError('I campioni non definiscono un piano locale valido.')

    a, b, c = coeff
    predicted = A @ coeff
    resid = z - predicted
    rmse = float(np.sqrt(np.mean(resid ** 2)))
    max_abs = float(np.max(np.abs(resid)))

    # x=Est, y=Nord, z=quota. La direzione di massima discesa e' (-a,-b).
    horizontal = math.hypot(a, b)
    dip = math.degrees(math.atan(horizontal))
    if horizontal < 1e-12:
        dipdir = 0.0
    else:
        dipdir = math.degrees(math.atan2(-a, -b)) % 360.0

    strike = (dipdir - 90.0) % 360.0
    pole_trend = (dipdir + 180.0) % 360.0
    pole_plunge = 90.0 - dip
    center_metric = metric_transform.transform(center)
    center_z_fit = float(a * (center_metric.x() - x0) +
                          b * (center_metric.y() - y0) + c)
    center_z_dtm = _identify_value(provider, center)
    if center_z_dtm is None:
        center_z_dtm = center_z_fit

    # Ingombro della finestra di campionamento nel CRS raster.
    window = QgsRectangle(
        center.x() - radius * px, center.y() - radius * py,
        center.x() + radius * px, center.y() + radius * py
    )

    return DTMPlaneResult(
        x=float(center.x()),
        y=float(center.y()),
        z=float(center_z_dtm),
        z_fit=float(center_z_fit),
        dip=float(dip),
        dipdir=float(dipdir),
        strike=float(strike),
        pole_trend=float(pole_trend),
        pole_plunge=float(pole_plunge),
        rmse=rmse,
        max_residual=max_abs,
        sample_count=len(points),
        radius_cells=radius,
        pixel_size_x=float(px),
        pixel_size_y=float(py),
        raster_crs=layer.crs().authid() or layer.crs().description(),
        metric_crs=metric_crs.authid() or metric_crs.description(),
        slope_a=float(a),
        slope_b=float(b),
        window=window,
    )


class DTMMapTool(QgsMapTool):
    point_acquired = pyqtSignal(object, object)
    acquisition_cancelled = pyqtSignal()
    restore_requested = pyqtSignal()

    def __init__(self, canvas, layer, radius_cells, parent=None):
        super().__init__(canvas)
        self.canvas = canvas
        self.layer = layer
        self.radius_cells = int(radius_cells)
        self.parent = parent
        self.setCursor(QCursor(QtCursorCross()))

    def canvasReleaseEvent(self, event):
        # Tasto destro: termina l'acquisizione e chiede al dock di
        # ricomparire. Il tasto destro non deve generare una misura.
        if event.button() == Qt.MouseButton.RightButton:
            self.restore_requested.emit()
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        try:
            # QGIS 4 / Qt6 usa position(); il fallback a pos() mantiene
            # compatibilita' con eventuali build Qt precedenti.
            pos = event.position().toPoint() if hasattr(event, 'position') else event.pos()
            point = self.toMapCoordinates(pos)
            result = fit_local_plane(
                self.layer,
                point,
                self.radius_cells,
                self.canvas.mapSettings().destinationCrs(),
            )
            self.point_acquired.emit(result, point)
        except Exception as exc:
            if self.parent is not None:
                QMessageBox.warning(
                    self.parent,
                    self.parent.tr('Acquisizione DTM'),
                    self.parent.tr('Impossibile calcolare il piano locale:\n{}').format(exc),
                )

    def keyReleaseEvent(self, event):
        if event.key() == 27:
            self.acquisition_cancelled.emit()
            self.canvas.unsetMapTool(self)


# Evita di dipendere da enum Qt5/Qt6 nella creazione del cursore.
def QtCursorCross():
    from qgis.PyQt.QtCore import Qt
    return Qt.CursorShape.CrossCursor
