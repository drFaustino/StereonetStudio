# -*- coding: utf-8 -*-
"""
StereonetStudio - data_io.py

Lettura dei dati di giacitura da:
- file CSV/TXT (con selezione delle colonne da usare come Dip / Dip Direction / Set);
- layer vettoriali caricati nel progetto QGIS (con selezione dei campi).
"""

import csv


def sniff_delimiter(sample_line):
    for d in (';', '\t', ','):
        if d in sample_line:
            return d
    return ','


def _row_is_numeric(row):
    count = 0
    for c in row:
        try:
            float(str(c).strip().replace(',', '.'))
            count += 1
        except ValueError:
            pass
    return count >= max(1, len(row) - 1)


def read_header(path):
    """Ritorna (header, delimiter, has_header) analizzando le prime righe del file."""
    with open(path, newline='', encoding='utf-8-sig') as f:
        first_line = f.readline()
        delim = sniff_delimiter(first_line)
        f.seek(0)
        reader = csv.reader(f, delimiter=delim)
        try:
            first_rows = [next(reader) for _ in range(2)]
        except StopIteration:
            first_rows = []
    if not first_rows or not first_rows[0]:
        return [], delim, False
    first = first_rows[0]
    has_header = not _row_is_numeric(first)
    if has_header:
        header = [c.strip() for c in first]
    else:
        header = ['Colonna {}'.format(i + 1) for i in range(len(first))]
    return header, delim, has_header


def read_csv_rows(path, col_dip, col_dipdir, col_set=None):
    """Legge un file CSV/TXT e ritorna una lista di righe
    [{'v1': dip, 'v2': dipdir, 'set': nome_set}, ...].

    col_dip / col_dipdir / col_set possono essere nomi di colonna (se il file
    ha un'intestazione) oppure indici interi a base 0.
    """
    header, delim, has_header = read_header(path)
    with open(path, newline='', encoding='utf-8-sig') as f:
        reader = csv.reader(f, delimiter=delim)
        rows = list(reader)
    if has_header and rows:
        rows = rows[1:]

    def col_index(col):
        if col is None or col == '':
            return None
        if isinstance(col, int):
            return col
        try:
            return header.index(col)
        except ValueError:
            return None

    i_dip = col_index(col_dip)
    i_dipdir = col_index(col_dipdir)
    i_set = col_index(col_set)

    out = []
    if i_dip is None or i_dipdir is None:
        return out
    for row in rows:
        if not row or i_dip >= len(row) or i_dipdir >= len(row):
            continue
        try:
            v1 = float(row[i_dip].strip().replace(',', '.'))
            v2 = float(row[i_dipdir].strip().replace(',', '.'))
        except (ValueError, AttributeError):
            continue
        s = 'Set 1'
        if i_set is not None and i_set < len(row) and row[i_set].strip():
            s = row[i_set].strip()
        out.append({'v1': v1, 'v2': v2, 'set': s})
    return out


def read_vector_layer_rows(layer, field_dip, field_dipdir, field_set=None, prefer_selected=True):
    """Legge attributi da un QgsVectorLayer.

    Se prefer_selected=True e ci sono feature selezionate sul layer, vengono
    lette solo quelle (comportamento standard QGIS); altrimenti tutte le
    feature. Ritorna (rows, used_selection, n_features_source).
    """
    out = []
    if layer is None or not field_dip or not field_dipdir:
        return out, False, 0

    used_selection = prefer_selected and layer.selectedFeatureCount() > 0
    features = layer.getSelectedFeatures() if used_selection else layer.getFeatures()
    n_source = layer.selectedFeatureCount() if used_selection else layer.featureCount()

    for feat in features:
        try:
            raw_dip = feat[field_dip]
            raw_dipdir = feat[field_dipdir]
            if raw_dip is None or raw_dipdir is None:
                continue
            v1 = float(str(raw_dip).replace(',', '.'))
            v2 = float(str(raw_dipdir).replace(',', '.'))
        except (TypeError, ValueError, KeyError):
            continue
        s = 'Set 1'
        if field_set:
            try:
                sv = feat[field_set]
                if sv not in (None, ''):
                    s = str(sv)
            except KeyError:
                pass
        out.append({'v1': v1, 'v2': v2, 'set': s})
    return out, used_selection, n_source
