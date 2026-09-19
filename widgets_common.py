# -*- coding: utf-8 -*-
"""StereonetStudio - widgets_common.py : widget riutilizzabili nell'interfaccia."""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QPushButton, QColorDialog, QFrame, QLabel, QApplication
from qgis.PyQt.QtGui import QColor


class ColorButton(QPushButton):
    """Pulsante che mostra un colore e apre il selettore colori di sistema.

    Il dialog viene creato senza parent e senza stylesheet locale, così QGIS
    non gli trasferisce lo sfondo/colorazione del pulsante cliccato. Quando
    disponibile, Qt usa il color picker nativo del sistema operativo.
    """

    def __init__(self, color_hex='#ffffff', parent=None):
        super().__init__(parent)
        self.set_color(color_hex)
        self.clicked.connect(self._pick)
        self.setFixedWidth(64)
        self.setFixedHeight(22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_color(self, color_hex):
        self._color = QColor(color_hex)
        self.setStyleSheet(
            'background-color: {}; border: 1px solid #99a3ad; border-radius: 4px;'.format(self._color.name()))

    def _pick(self):
        # Non usare QColorDialog.getColor() con self come parent: in QGIS il
        # parent può trasmettere lo stylesheet del pannello al dialog.
        # Il dialog senza parent, con il native dialog consentito, lascia a Qt
        # la scelta del color picker di sistema e mantiene la palette di sistema.
        app = QApplication.instance()
        dlg = QColorDialog(self._color, None)
        dlg.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, False)
        dlg.setWindowTitle(self.tr('Scegli colore'))
        dlg.setStyleSheet('')
        if app is not None:
            dlg.setPalette(app.palette())
            dlg.setStyle(app.style())
        if dlg.exec():
            c = dlg.currentColor()
            if c.isValid():
                self.set_color(c.name())

    def color_hex(self):
        return self._color.name()


class HLine(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFrameShadow(QFrame.Shadow.Sunken)
        self.setStyleSheet('color: #d5dbe2;')


class HintLabel(QLabel):
    """Etichetta grigia/corsivo usata come suggerimento sotto ai controlli."""

    def __init__(self, text='', parent=None):
        super().__init__(text, parent)
        self.setObjectName('SNSectionHint')
        self.setWordWrap(True)
