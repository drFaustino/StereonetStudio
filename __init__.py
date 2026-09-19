# -*- coding: utf-8 -*-
"""
StereonetStudio - Plugin QGIS per proiezione stereografica e analisi cinematica
dei versanti rocciosi (QGIS 4.x, Qt6).
"""


def classFactory(iface):
    from .stereonet_studio import StereonetStudioPlugin
    return StereonetStudioPlugin(iface)
