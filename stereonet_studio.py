# -*- coding: utf-8 -*-
"""StereonetStudio - stereonet_studio.py : registrazione del plugin in QGIS."""

import os

from qgis.PyQt.QtCore import Qt, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .stereonet_dock import StereonetDock
from .i18n_runtime import load_translator


class StereonetStudioPlugin:

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = 'StereonetStudio'
        self.dock = None
        self.translator = None

    def initGui(self):
        self.translator = load_translator(self.plugin_dir, QCoreApplication.instance())
        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

        self.action_show = QAction(icon, QCoreApplication.translate('StereonetStudioPlugin', 'Apri StereonetStudio'), self.iface.mainWindow())
        self.action_show.setCheckable(True)
        self.action_show.triggered.connect(self.toggle_dock)
        self.iface.addPluginToMenu(self.menu, self.action_show)
        self.iface.addToolBarIcon(self.action_show)
        self.actions.append(self.action_show)

    def unload(self):
        if self.translator is not None:
            QCoreApplication.instance().removeTranslator(self.translator)
            self.translator = None
        for action in self.actions:
            self.iface.removePluginMenu(self.menu, action)
            self.iface.removeToolBarIcon(action)
        if self.dock is not None:
            self.iface.removeDockWidget(self.dock)
            self.dock.deleteLater()
            self.dock = None

    def toggle_dock(self):
        if self.dock is None:
            self.dock = StereonetDock(self.iface, self.iface.mainWindow())
            self.dock.visibilityChanged.connect(self._on_visibility_changed)
            self.iface.addDockWidget(Qt.DockWidgetArea.TopDockWidgetArea, self.dock)
            # Apri il pannello come finestra "floating" gia' dimensionata in
            # modo che sia le schede laterali sia l'area grafica (incluso il
            # titolo sopra la proiezione) siano completamente visibili.
            self.dock.setFloating(True)
            self.dock.resize(1600, 900)
        else:
            self.dock.setVisible(not self.dock.isVisible())

    def _on_visibility_changed(self, visible):
        self.action_show.setChecked(visible)
