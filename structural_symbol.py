# -*- coding: utf-8 -*-
"""StereonetStudio - simbologia strutturale classica per i layer esportati.

Simbolo di giacitura (strike/dip): linea di direzione con il tick di
immersione perpendicolare, in rosso, ruotata secondo la direzione (campo
'Strike', regola della mano destra: il tick punta verso la Dip Direction).
Accanto al simbolo viene scritto l'angolo di immersione (campo 'Dip') con
il simbolo del grado, posizionato all'estremita' del tick corto: segue la
rotazione del simbolo (offset polare calcolato dalla direzione del tick).

Lo stile viene salvato insieme al file:
  - Shapefile  -> file .qml con lo stesso nome;
  - GeoPackage -> tabella layer_styles dentro il .gpkg (stile predefinito).
"""

import base64

from qgis.PyQt.QtGui import QColor, QFont
from qgis.core import (
    Qgis, QgsMarkerSymbol, QgsSvgMarkerSymbolLayer, QgsSymbolLayer,
    QgsProperty, QgsPalLayerSettings, QgsTextFormat, QgsTextBufferSettings,
    QgsVectorLayerSimpleLabeling, QgsSingleSymbolRenderer,
)

SYMBOL_SIZE_MM = 8.0
# Il tick di immersione arriva a 0.34 * dimensione dal centro del simbolo
# (x2=84 su viewBox 100); l'etichetta parte appena oltre l'estremita'.
TICK_END_MM = 0.34 * SYMBOL_SIZE_MM
LABEL_GAP_MM = 0.7
LABEL_DISTANCE_MM = TICK_END_MM + LABEL_GAP_MM
RED = '#e00000'

# Linea di direzione verticale (N-S) + tick di immersione verso Est.
# Con angolo = Strike, il tick punta verso la Dip Direction.
_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" '
    'width="100" height="100">'
    '<line x1="50" y1="2" x2="50" y2="98" stroke="{c}" stroke-width="7" '
    'stroke-linecap="butt"/>'
    '<line x1="50" y1="50" x2="84" y2="50" stroke="{c}" stroke-width="7" '
    'stroke-linecap="butt"/>'
    '</svg>'
).format(c=RED)

# Direzione del tick = Strike + 90 (coerente con la rotazione del simbolo).
_TICK_AZ = '(("Strike" + 90) % 360)'

# Posizione dell'etichetta: punto all'estremita' del tick, ruotato con il
# simbolo. Offset in mm come nella simbologia (x positivo = destra,
# y positivo = basso), quindi y = -d * cos(azimut).
_OFFSET_EXPR = (
    "round({d} * sin(radians({az})), 3) || ',' || "
    "round(-{d} * cos(radians({az})), 3)"
).format(d=LABEL_DISTANCE_MM, az=_TICK_AZ)

# Quadrante dell'etichetta (QgsPalLayerSettings: 0 sopra-sx, 1 sopra,
# 2 sopra-dx, 3 sx, 4 sul punto, 5 dx, 6 sotto-sx, 7 sotto, 8 sotto-dx)
# scelto in base alla direzione del tick, cosi' il testo si appoggia
# all'estremita' del tick senza coprirlo.
_QUAD_EXPR = (
    'CASE '
    'WHEN {az} >= 337.5 OR {az} < 22.5 THEN 1 '
    'WHEN {az} < 67.5 THEN 2 '
    'WHEN {az} < 112.5 THEN 5 '
    'WHEN {az} < 157.5 THEN 8 '
    'WHEN {az} < 202.5 THEN 7 '
    'WHEN {az} < 247.5 THEN 6 '
    'WHEN {az} < 292.5 THEN 3 '
    'ELSE 0 END'
).format(az=_TICK_AZ)


def _enum(owner, scoped, flat):
    """Compatibilita' tra enum scoped (QGIS 4) e alias piatti (QGIS 3)."""
    try:
        sc = getattr(owner, scoped[0])
        for part in scoped[1:]:
            sc = getattr(sc, part)
        return sc
    except AttributeError:
        return getattr(owner, flat)


def _build_symbol():
    svg_path = 'base64:' + base64.b64encode(_SVG.encode('utf-8')).decode('ascii')
    layer = QgsSvgMarkerSymbolLayer(svg_path, SYMBOL_SIZE_MM, 0.0)
    layer.setFillColor(QColor(RED))
    layer.setStrokeColor(QColor(RED))
    prop_angle = _enum(QgsSymbolLayer, ('Property', 'Angle'), 'PropertyAngle')
    layer.setDataDefinedProperty(prop_angle, QgsProperty.fromExpression('"Strike"'))
    symbol = QgsMarkerSymbol()
    symbol.changeSymbolLayer(0, layer)
    symbol.setSize(SYMBOL_SIZE_MM)
    return symbol


def _build_labeling():
    fmt = QgsTextFormat()
    font = QFont()
    font.setBold(True)
    fmt.setFont(font)
    fmt.setSize(9)
    fmt.setColor(QColor(RED))
    buf = QgsTextBufferSettings()
    buf.setEnabled(True)
    buf.setSize(0.8)
    buf.setColor(QColor('#ffffff'))
    fmt.setBuffer(buf)

    s = QgsPalLayerSettings()
    s.fieldName = 'round("Dip", 0) || \'°\''
    s.isExpression = True
    s.setFormat(fmt)
    s.placement = _enum(Qgis, ('LabelPlacement', 'OverPoint'), 'OverPoint') \
        if hasattr(Qgis, 'LabelPlacement') else QgsPalLayerSettings.OverPoint
    s.xOffset = 0.0
    s.yOffset = 0.0
    try:
        s.offsetUnits = Qgis.RenderUnit.Millimeters
    except AttributeError:
        from qgis.core import QgsUnitTypes
        s.offsetUnits = QgsUnitTypes.RenderMillimeters
    s.displayAll = True
    prop_quad = _enum(QgsPalLayerSettings, ('Property', 'OffsetQuad'), 'OffsetQuad')
    props = s.dataDefinedProperties()
    props.setProperty(prop_quad, QgsProperty.fromExpression(_QUAD_EXPR))
    prop_xy = _enum(QgsPalLayerSettings, ('Property', 'OffsetXY'), 'OffsetXY')
    props.setProperty(prop_xy, QgsProperty.fromExpression(_OFFSET_EXPR))
    s.setDataDefinedProperties(props)
    return QgsVectorLayerSimpleLabeling(s)


def apply_structural_style(layer):
    """Applica al layer il simbolo di giacitura rosso con l'angolo di dip."""
    layer.setRenderer(QgsSingleSymbolRenderer(_build_symbol()))
    layer.setLabeling(_build_labeling())
    layer.setLabelsEnabled(True)
    layer.triggerRepaint()


def _result_ok(res):
    """Interpreta l'esito dei metodi di salvataggio stile (QGIS 3 e 4).

    Puo' essere: stringa di errore (vuota = ok), bool, enum
    SaveStyleResult (es. 'SaveStyleResult.Success') o tuple di questi.
    """
    items = res if isinstance(res, tuple) else (res,)
    for it in items:
        if isinstance(it, bool):
            return it
    for it in items:
        if type(it).__name__.endswith('SaveStyleResult') or 'SaveStyleResult' in str(it):
            return str(it).endswith('Success')
    return not any(isinstance(it, str) and it for it in items)


def save_style(layer, path, driver_name):
    """Salva lo stile accanto al file. Ritorna (ok, messaggio)."""
    try:
        if driver_name == 'GPKG':
            name = 'Giaciture strutturali'
            fn = getattr(layer, 'saveStyleToDatabaseV2', None)
            if fn is not None:
                res = fn(name, '', True, '')
            else:
                res = layer.saveStyleToDatabase(name, '', True, '')
        else:
            qml = path.rsplit('.', 1)[0] + '.qml'
            res = layer.saveNamedStyle(qml)
        return _result_ok(res), str(res)
    except Exception as exc:  # lo stile non deve mai far fallire l'export
        return False, str(exc)
