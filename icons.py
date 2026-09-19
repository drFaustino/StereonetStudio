# -*- coding: utf-8 -*-
"""
StereonetStudio - icons.py

Icone vettoriali generate a runtime con QPainter (nessun file immagine
esterno richiesto, sempre nitide a qualunque risoluzione/scaling).
"""

import math

from qgis.PyQt.QtCore import Qt, QRectF, QPointF
from qgis.PyQt.QtGui import QIcon, QPixmap, QPainter, QPen, QBrush, QColor, QPolygonF


def _new_painter(size):
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    return pm, p


def _finish(pm, p):
    p.end()
    return QIcon(pm)


def icon_compass(color='#1f6fb2', size=28):
    pm, p = _new_painter(size)
    pen = QPen(QColor(color)); pen.setWidthF(1.6)
    p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
    m = size * 0.12
    p.drawEllipse(QRectF(m, m, size - 2 * m, size - 2 * m))
    c = size / 2.0
    p.drawLine(QPointF(c, m * 0.5), QPointF(c, size - m * 0.5))
    p.drawLine(QPointF(m * 0.5, c), QPointF(size - m * 0.5, c))
    needle = QPolygonF([QPointF(c, m * 1.4), QPointF(c - size * 0.09, c), QPointF(c + size * 0.09, c)])
    p.setBrush(QBrush(QColor(color)))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawPolygon(needle)
    return _finish(pm, p)


def icon_table(color='#1f6fb2', size=28):
    pm, p = _new_painter(size)
    pen = QPen(QColor(color)); pen.setWidthF(1.4)
    p.setPen(pen)
    m = size * 0.16
    rect = QRectF(m, m, size - 2 * m, size - 2 * m)
    p.drawRect(rect)
    for i in range(1, 3):
        y = m + (rect.height() / 3.0) * i
        p.drawLine(QPointF(m, y), QPointF(size - m, y))
    x = m + rect.width() / 2.0
    p.drawLine(QPointF(x, m), QPointF(x, size - m))
    return _finish(pm, p)


def icon_kinematic(color='#c0392b', size=28):
    pm, p = _new_painter(size)
    pen = QPen(QColor(color)); pen.setWidthF(1.6)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    tri = QPolygonF([QPointF(size * 0.5, size * 0.12), QPointF(size * 0.90, size * 0.86),
                      QPointF(size * 0.10, size * 0.86)])
    p.drawPolygon(tri)
    pen2 = QPen(QColor(color)); pen2.setWidthF(2.0); pen2.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen2)
    p.drawLine(QPointF(size * 0.5, size * 0.40), QPointF(size * 0.5, size * 0.62))
    p.drawPoint(QPointF(size * 0.5, size * 0.73))
    return _finish(pm, p)


def icon_rosette(color='#8e44ad', size=28):
    pm, p = _new_painter(size)
    p.setPen(Qt.PenStyle.NoPen)
    c = size / 2.0
    n = 12
    for i in range(n):
        ang = math.pi * 2 * i / n
        r = size * (0.15 + 0.30 * abs(math.sin(ang * 2)))
        col = QColor(color)
        col.setAlpha(220 if i % 2 == 0 else 140)
        p.setBrush(QBrush(col))
        pts = QPolygonF([
            QPointF(c, c),
            QPointF(c + r * math.cos(ang - 0.20), c + r * math.sin(ang - 0.20)),
            QPointF(c + r * math.cos(ang + 0.20), c + r * math.sin(ang + 0.20)),
        ])
        p.drawPolygon(pts)
    return _finish(pm, p)


def icon_play(color='#2e8b57', size=22):
    pm, p = _new_painter(size)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor(color)))
    tri = QPolygonF([QPointF(size * 0.26, size * 0.16), QPointF(size * 0.26, size * 0.84),
                      QPointF(size * 0.86, size * 0.5)])
    p.drawPolygon(tri)
    return _finish(pm, p)


def icon_clear(color='#7f8c8d', size=22):
    pm, p = _new_painter(size)
    pen = QPen(QColor(color)); pen.setWidthF(1.7); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.drawLine(QPointF(size * 0.18, size * 0.28), QPointF(size * 0.82, size * 0.28))
    p.drawLine(QPointF(size * 0.38, size * 0.16), QPointF(size * 0.62, size * 0.16))
    p.drawRect(QRectF(size * 0.24, size * 0.30, size * 0.52, size * 0.56))
    for x in (0.38, 0.5, 0.62):
        p.drawLine(QPointF(size * x, size * 0.40), QPointF(size * x, size * 0.74))
    return _finish(pm, p)


def icon_export(color='#1f6fb2', size=22):
    pm, p = _new_painter(size)
    pen = QPen(QColor(color)); pen.setWidthF(1.8); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.drawLine(QPointF(size * 0.5, size * 0.12), QPointF(size * 0.5, size * 0.58))
    p.drawLine(QPointF(size * 0.32, size * 0.34), QPointF(size * 0.5, size * 0.12))
    p.drawLine(QPointF(size * 0.68, size * 0.34), QPointF(size * 0.5, size * 0.12))
    p.drawRect(QRectF(size * 0.16, size * 0.68, size * 0.68, size * 0.18))
    return _finish(pm, p)


def icon_add(color='#2e8b57', size=20):
    pm, p = _new_painter(size)
    pen = QPen(QColor(color)); pen.setWidthF(2.2); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    m = size * 0.18
    p.drawLine(QPointF(size / 2, m), QPointF(size / 2, size - m))
    p.drawLine(QPointF(m, size / 2), QPointF(size - m, size / 2))
    return _finish(pm, p)


def icon_remove(color='#c0392b', size=20):
    pm, p = _new_painter(size)
    pen = QPen(QColor(color)); pen.setWidthF(2.2); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    m = size * 0.22
    p.drawLine(QPointF(m, size / 2), QPointF(size - m, size / 2))
    return _finish(pm, p)


def icon_import(color='#1f6fb2', size=20):
    pm, p = _new_painter(size)
    pen = QPen(QColor(color)); pen.setWidthF(1.7); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.drawRect(QRectF(size * 0.20, size * 0.14, size * 0.60, size * 0.70))
    p.drawLine(QPointF(size * 0.5, size * 0.34), QPointF(size * 0.5, size * 0.68))
    p.drawLine(QPointF(size * 0.36, size * 0.52), QPointF(size * 0.5, size * 0.68))
    p.drawLine(QPointF(size * 0.64, size * 0.52), QPointF(size * 0.5, size * 0.68))
    return _finish(pm, p)


def icon_folder(color='#d4ac0d', size=20):
    pm, p = _new_painter(size)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor(color)))
    p.drawRoundedRect(QRectF(size * 0.10, size * 0.32, size * 0.80, size * 0.52), 2, 2)
    p.drawRoundedRect(QRectF(size * 0.10, size * 0.20, size * 0.42, size * 0.18), 2, 2)
    return _finish(pm, p)


def icon_layers(color='#16a085', size=20):
    pm, p = _new_painter(size)
    pen = QPen(QColor(color)); pen.setWidthF(1.4)
    p.setPen(pen)
    c = size / 2.0
    for dy in (-0.16, 0.0, 0.16):
        poly = QPolygonF([QPointF(c, size * (0.20 + dy)), QPointF(size * 0.88, size * (0.42 + dy)),
                           QPointF(c, size * (0.64 + dy)), QPointF(size * 0.12, size * (0.42 + dy))])
        p.drawPolygon(poly)
    return _finish(pm, p)


def icon_dot(color='#1f6fb2', size=16):
    pm, p = _new_painter(size)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor(color)))
    m = size * 0.2
    p.drawEllipse(QRectF(m, m, size - 2 * m, size - 2 * m))
    return _finish(pm, p)
