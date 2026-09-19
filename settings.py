# -*- coding: utf-8 -*-
"""
StereonetStudio - settings.py
Costanti e impostazioni di default.
"""

OVERLAY_TYPES = ['Equatoriale', 'Polare']
PROJECTION_TYPES = ['Equal Angle (Wulff)', 'Equal Area (Schmidt)']
HEMISPHERE_TYPES = ['Inferiore', 'Superiore']
LABEL_MODES = ['NSEW', 'North', 'Nessuna', 'Gradi', 'NSEW+Gradi']
TICK_SPACINGS = [10, 15, 30, 45, 60, 90]
OUTER_GRID_WIDTHS = [1, 2, 3, 4, 5]
OVERLAY_WIDTHS = [1, 2, 3]

CONTOUR_MODES = ['Nessuno', 'Poli (Vettori)', 'Intersezioni', 'Colonna dati']
CONTOUR_STYLES = ['Filled', 'Line']

ORIENTATION_FORMATS = [
    'Dip / Direzione Immersione',
    'Direzione (destra) / Dip',
    'Direzione (sinistra) / Dip',
    'Trend / Plunge',
]

KINEMATIC_MODES = [
    'Scivolamento Planare',
    'Scivolamento a Cuneo',
    'Ribaltamento Flessurale',
    'Ribaltamento Diretto',
]

DATA_SOURCE_TYPES = ['File CSV/TXT', 'Vector Layer (Layer di progetto)']

ROSETTE_BIN_WIDTHS = [5, 10, 15, 30]

DEFAULT_SETTINGS = {
    # Input Data
    'data_source': 'File CSV/TXT',
    'csv_path': '',
    'csv_col_dip': '',
    'csv_col_dipdir': '',
    'csv_col_set': '',
    'vector_layer_id': '',
    'vector_field_dip': '',
    'vector_field_dipdir': '',
    'vector_field_set': '',
    'use_declination': False,
    'declination': 0.0,

    # Stereonet Options
    'overlay': 'Equatoriale',
    'projection': 'Equal Area (Schmidt)',
    'hemisphere': 'Inferiore',
    'labels': 'NSEW+Gradi',
    'exterior_ticks': True,
    'center_cross': True,
    'tick_spacing': 15,
    'outer_grid_width': 3,
    'overlay_width': 1,
    'color_background': '#ffffff',
    'color_grid_outer': '#1a1a1a',
    'color_global_mean': '#1b5e20',
    'color_best_fit': '#0000ff',

    # Plot Options
    'show_pole': True,
    'show_planes': False,
    'color_pole': '#1f6fb2',
    'color_plane': '#4a4a4a',
    'show_global_mean': True,
    'show_best_fit': False,
    'contour_mode': 'Nessuno',
    'contour_style': 'Filled',
    'contour_column': '',
    'orientation_format': 'Dip / Direzione Immersione',
    'show_rosette': False,
    'rosette_bin_width': 10,

    # Kinematic Analysis
    'kinematic_enabled': False,
    'kinematic_mode': 'Scivolamento Planare',
    'slope_dip': 45.0,
    'slope_dipdir': 135.0,
    'friction_angle': 30.0,
    'lateral_limit': 20.0,
    'show_construction_lines': True,
    'show_highlight': True,

    # Dimensioni testo (Titolo / Legenda-Densita' / Elementi-Valori)
    'font_size_title': 9.0,
    'font_size_label': 8.5,
    'font_size_elements': 7.0,
}


def new_settings():
    """Restituisce una copia indipendente delle impostazioni di default."""
    return dict(DEFAULT_SETTINGS)
