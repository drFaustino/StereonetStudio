# -*- coding: utf-8 -*-
"""StereonetStudio - style.py : foglio di stile (QSS) dell'interfaccia."""

STYLE_SHEET = """
QWidget#SNRoot { background: #eef1f5; }
QWidget#SNSidePanel { background: #f7f9fb; }

QTabWidget::pane {
    border: 1px solid #d5dbe2;
    background: #f7f9fb;
    top: -1px;
}
QTabBar::tab {
    background: #e7ecf1;
    border: 1px solid #d5dbe2;
    border-bottom: none;
    padding: 6px 6px;
    margin-right: 1px;
    font-size: 9pt;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: 600;
    color: #45505c;
}
QTabBar::tab:selected {
    background: #ffffff;
    color: #1f6fb2;
    border-bottom: 2px solid #1f6fb2;
}
QTabBar::tab:hover { color: #1f6fb2; }

QGroupBox {
    font-weight: 600;
    color: #2c3e50;
    border: 1px solid #d7dde4;
    border-radius: 6px;
    margin-top: 14px;
    background: #ffffff;
    padding-top: 8px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: #1f6fb2;
}

QPushButton {
    background: #eef2f6;
    border: 1px solid #ccd5df;
    border-radius: 5px;
    padding: 5px 12px;
    color: #2c3e50;
}
QPushButton:hover { background: #dfe8f1; border-color: #1f6fb2; }
QPushButton:pressed { background: #cddaea; }
QPushButton:disabled { color: #a7b0ba; background: #f2f4f7; }

QPushButton#SNPrimaryButton {
    background: #1f6fb2;
    color: white;
    font-weight: 600;
    border: 1px solid #175a92;
    padding: 7px 14px;
}
QPushButton#SNPrimaryButton:hover { background: #2680cc; }
QPushButton#SNPrimaryButton:pressed { background: #175a92; }

QPushButton#SNDangerButton {
    background: #ffffff;
    color: #c0392b;
    border: 1px solid #e2b4ac;
}
QPushButton#SNDangerButton:hover { background: #fdecea; }

QComboBox, QDoubleSpinBox, QSpinBox, QLineEdit {
    border: 1px solid #ccd5df;
    border-radius: 4px;
    padding: 3px 6px;
    background: white;
    min-height: 20px;
    selection-background-color: #1f6fb2;
}

QComboBox:hover, QDoubleSpinBox:hover, QSpinBox:hover, QLineEdit:hover {
    border-color: #1f6fb2;
}

QComboBox::drop-down {
    border: none;
    width: 18px;
}

/* --------------------------------------------------------------
   Frecce degli SpinBox
   -------------------------------------------------------------- */

QDoubleSpinBox::up-button,
QSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 17px;
    border-left: 1px solid #ccd5df;
    border-bottom: 1px solid #ccd5df;
    border-top-right-radius: 3px;
    background: #eef2f6;
}

QDoubleSpinBox::down-button,
QSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 17px;
    border-left: 1px solid #ccd5df;
    border-bottom-right-radius: 3px;
    background: #eef2f6;
}

QDoubleSpinBox::up-button:hover,
QDoubleSpinBox::down-button:hover,
QSpinBox::up-button:hover,
QSpinBox::down-button:hover {
    background: #dfe8f1;
}

QDoubleSpinBox::up-arrow,
QSpinBox::up-arrow {
    width: 0px;
    height: 0px;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 6px solid #45505c;
}

QDoubleSpinBox::down-arrow,
QSpinBox::down-arrow {
    width: 0px;
    height: 0px;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 6px solid #45505c;
}

QCheckBox { spacing: 6px; color: #2c3e50; }

QLabel#SNSectionHint { color: #8a94a0; font-style: italic; font-weight: normal; }
QLabel#SNStatusBar {
    background: #eef2f6;
    border-top: 1px solid #d5dbe2;
    padding: 5px 10px;
    color: #45505c;
}
QLabel#SNRosetteInfo { color: #2c3e50; font-weight: 600; }

QScrollArea { border: none; background: transparent; }

QToolButton { border: none; padding: 4px; border-radius: 4px; }
QToolButton:hover { background: #dfe8f1; }

QTableWidget {
    background: white;
    gridline-color: #e3e7ec;
    border: 1px solid #d7dde4;
    border-radius: 4px;
}
QHeaderView::section {
    background: #eef2f6;
    color: #2c3e50;
    padding: 4px;
    border: none;
    border-bottom: 1px solid #d5dbe2;
    font-weight: 600;
}
QWidget#SNTitleBar {
    background: #eef1f5;
    border-bottom: 1px solid #d5dbe2;
}
QLabel#SNTitleLabel {
    color: #2c3e50;
    font-weight: 600;
    padding-left: 4px;
}
QToolButton#SNWindowButton {
    color: #45505c;
    font-size: 12pt;
}
QToolButton#SNWindowButton:hover {
    background: #dfe8f1;
}

"""
