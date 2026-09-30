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

            # Il pannello deve comportarsi sempre come una finestra
            # indipendente ("floating") e non deve MAI poter essere
            # agganciato dentro la finestra principale di QGIS: se venisse
            # anche solo temporaneamente inserito nel layout del
            # QMainWindow (es. in TopDockWidgetArea prima di diventare
            # floating), QGIS ridimensiona/ricalcola la finestra principale
            # e questo puo' far scomparire o spostare la barra di stato in
            # basso. Per evitarlo del tutto:
            # 1) rendiamo il dock floating PRIMA di aggiungerlo a QGIS;
            # 2) vietiamo qualsiasi area di aggancio, cosi' non puo' essere
            #    "riattaccato" alla finestra principale nemmeno trascinandolo.
            self.dock.setAllowedAreas(Qt.DockWidgetArea.NoDockWidgetArea)
            self.dock.setFloating(True)

            self.iface.addDockWidget(Qt.DockWidgetArea.TopDockWidgetArea, self.dock)

            # Qt puo' comunque ri-agganciare per un istante durante
            # l'aggiunta: forziamo di nuovo lo stato floating subito dopo,
            # cosi' la finestra principale di QGIS non viene mai toccata.
            self.dock.setFloating(True)

            # Apri il pannello come finestra "floating" gia' dimensionata in
            # modo che sia le schede laterali sia l'area grafica (incluso il
            # titolo sopra la proiezione) siano completamente visibili, e
            # sempre centrata al centro dello schermo.
            self.dock.resize(1600, 900)
            self.dock.center_on_screen()
        else:
            will_show = not self.dock.isVisible()
            self.dock.setVisible(will_show)
            if will_show:
                # Anche quando il pannello viene semplicemente riaperto
                # (non ricreato), deve ricomparire sempre centrato.
                self.dock.center_on_screen()

    def _on_visibility_changed(self, visible):
        self.action_show.setChecked(visible)
