# -*- coding: utf-8 -*-
"""
StereonetStudio - i18n_labels.py

Le combo box delle "liste chiuse" (Overlay, Projection, Hemisphere, ...)
mostrano un testo tradotto ma devono continuare a salvare/leggere in
'settings' lo stesso valore canonico (italiano) usato dalla logica interna
(stereonet_math.py) indipendentemente dalla lingua dell'interfaccia.

Questo modulo centralizza il pattern: testo visualizzato = tr(valore),
valore salvato (itemData) = valore canonico invariato.
"""


def populate_combo(combo, tr_func, values, current=None):
    """Svuota e ripopola 'combo' con voci tradotte (tr_func) mantenendo il
    valore canonico come userData di ciascuna voce."""
    combo.blockSignals(True)
    combo.clear()
    for value in values:
        combo.addItem(tr_func(value), value)
    if current is not None:
        set_combo_value(combo, current)
    combo.blockSignals(False)


def combo_value(combo):
    """Ritorna il valore canonico (userData) selezionato, con fallback al
    testo visualizzato se la voce non ha userData (es. voci digitate)."""
    data = combo.currentData()
    return data if data is not None else combo.currentText()


def set_combo_value(combo, value):
    """Seleziona la voce il cui userData corrisponde a 'value'."""
    idx = combo.findData(value)
    if idx >= 0:
        combo.setCurrentIndex(idx)
    else:
        combo.setCurrentText(value)
