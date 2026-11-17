# StereonetStudio

**StereonetStudio** is a QGIS plugin for professional stereographic projection and structural geology analysis.

It provides stereonet visualization, density analysis, rose diagrams and kinematic analysis for structural orientation data imported from CSV/TXT files or directly from vector layers loaded in the current QGIS project.

---

## Features

### Stereographic projection

StereonetStudio generates stereographic projections from structural orientation data such as:

* Dip / Dip Direction
* Strike / Dip
* Trend / Plunge

The stereonet supports:

* **Equal-angle (Wulff)** projection
* **Equal-area (Schmidt)** projection
* **Lower hemisphere**
* **Upper hemisphere**
* **Polar grid**
* **Equatorial grid**
* configurable angular spacing
* configurable outer grid and overlay line weights
* cardinal and degree labels
* optional exterior ticks
* optional center cross

---

## Fold analysis & interactive tools (v1.2.0)

Found in the **Folds** tab.

* **Pole density contours** – show or hide pole contours, with two sliders:
  * *Transparency* fades the contour fill so poles and great circles show through.
  * *Low-density emphasis* packs more contour levels into the low end of the scale and leaves zero density unfilled, so sparse concentrations become visible.
  * *Pole marker fade* makes the data poles semi-transparent so the contours under them can be seen. Picked, suggested and mean markers stay solid.
* **Suggested limb poles** – the poles of one set, or of all sets, are split into two limb populations by two-cluster axial k-means on the sphere. The mean pole of each cluster is marked **S1** / **S2**. *Use suggested limbs* computes the fold axis and axial plane straight away. The suggestions are also snap targets for manual picking.

* **β fold hinge** – when *Global Best Fit* is on, the pole to the best-fit (π) girdle is plotted as **β** and its orientation is listed in the legend as plunge→trend.
* **Axial plane from limbs** – press *Pick L1 / L2 limb poles*, then click the pole to each limb on the stereonet (snaps to the nearest pole, global mean or β). The plugin computes:
  * fold axis = L1 ∩ L2,
  * axial plane = plane through the fold axis bisecting the limbs, given as dip/dip direction, with the interlimb angle.
  The two limbs have two bisecting planes, 90° apart. The steeper one is used by default, which suits upright folds. Use *Swap bisector* for recumbent or reclined folds. The alternative plane can be shown dotted.
* **Live plane cursor** – move the cursor to a pole position: the pole and its great circle update live with a readout. **Left-click** saves the pole and plane, **right-click** exits.
* All picks (L1, L2, fold axis, axial plane, cursor planes) are written to the **StereonetStudio picks** table layer in the project. You can also export them with *Export picks CSV*.

---

## Data import

Structural data can be imported from:

* **CSV files**
* **TXT files**
* vector layers loaded in the current QGIS project
* manually entered data through the data interface

For vector layers, the required fields can be selected directly from the interface.

The plugin supports optional **Set/Group** information, allowing different structural populations to be analysed separately.

An optional **declination correction** can also be applied to orientation data.

---

## User interface

StereonetStudio uses a modern tabbed interface divided into four main sections:

### Stereonet

Main configuration panel for:

* input data;
* projection;
* hemisphere;
* grid;
* labels;
* plot elements;
* colours;
* contours;
* text sizes;
* kinematic analysis.

### Data

Displays the imported structural data and provides the interface for manual data entry and data management.

### Kinematics

Displays the results of the kinematic analysis, including the number of analysed and feasible measurements.

### Rosette

Provides configuration options for the rose diagram and its integration into the main stereonet plot.

The interface is fully translated into:

* **Italian**
* **English**

---

## Plot options

The plotting system provides independent controls for the main stereonet elements.

Available elements include:

* **Poles**
* **Planes**
* **Global Mean**
* **Global Best Fit**
* **Density Contours**
* **Rose Diagram**

Colours can be configured independently for poles, planes, global mean, background and grid.

---

## Density contours

StereonetStudio supports density contours based on:

* **poles**
* **intersections**
* **data column / structural set**

Contours can be displayed as:

* filled contours;
* line contours.

The filled density area is clipped to the primitive great circle boundary, so the coloured area reaches the stereonet border without leaving an unwanted gap.

The density scale is displayed in a **fixed position in the upper-right area of the main plot**, independently from the legend.

This keeps the area below the legend clear and prevents the density scale from overlapping the legend.

---

## Text and labels

Text sizes can be configured independently for:

* **Title**
* **Legend / Density**
* **Elements / Values**

The title is automatically fitted to the available figure width so that it remains fully visible when the window is resized.

---

## Legend

The plot legend is positioned in the **upper-left area of the main figure**, directly below the title.

Legend text can be controlled independently through the plot text settings.

The legend remains independent from the density scale, which is fixed on the opposite side of the plot.

---

## Rose diagram

StereonetStudio includes a directional **rose diagram** that can be displayed directly on the main plot.

The rose diagram is positioned in the **lower-right area** of the figure in order to:

* avoid covering the stereonet;
* avoid overlapping stereonet labels;
* preserve the main plotting area;
* keep the diagram title and angular labels fully visible.

The rose diagram title is displayed in **bold** and its angular labels are enlarged for improved readability.

---

## Kinematic analysis

StereonetStudio includes a complete kinematic analysis module for common structural failure mechanisms.

Supported analyses are:

### Planar Sliding

Evaluates the potential for planar sliding based on:

* slope dip;
* slope dip direction;
* joint dip;
* joint dip direction;
* friction angle;
* lateral limit.

### Wedge Sliding

Analyses intersections between structural planes and evaluates whether the resulting line falls within the appropriate kinematic envelope.

### Flexural Toppling

Evaluates structural orientations for possible flexural toppling according to the configured slope and friction parameters.

### Direct Toppling

Evaluates steep structural orientations that may be compatible with direct toppling.

---

## Kinematic parameters

The kinematic analysis panel provides independent rows for:

* **Slope Dip**
* **Slope Dip Direction**
* **Friction Angle**
* **Lateral Limit**

Additional options allow the user to display:

* construction lines;
* highlighted critical zones.

Depending on the selected analysis, the stereonet can display:

* slope great circle;
* friction envelope;
* lateral limit lines;
* highlighted sectors;
* critical poles;
* critical intersections.

The results are also shown in the dedicated **Kinematic Analysis** tab.

---

## Export

The generated figure can be exported directly from the **Export PNG** command.

Supported formats are:

* **PNG**
* **JPEG / JPG**
* **SVG**
* **PDF**

Raster export uses a high-resolution setting suitable for reports and documentation.

The export format is determined automatically from the selected file extension.

---

## Interface styling

The plugin uses a centralized Qt stylesheet to provide a consistent graphical appearance.

The interface includes:

* styled tabs;
* group boxes;
* combo boxes;
* line edits;
* spin boxes;
* check boxes;
* action buttons;
* tables;
* custom title bar.

The spin box controls include dedicated visible up/down arrows to remain readable across different QGIS themes and palettes.

---

## Window behaviour

The StereonetStudio panel can be used as a normal QGIS dock or as a floating window.

When floating, it behaves as a standard window and is **not forced to remain permanently on top of other windows**.

The custom title bar provides:

* maximize / restore;
* close.

---

## Project structure

The main components of the plugin are organized as follows:

| File                       | Description                                                   |
| -------------------------- | ------------------------------------------------------------- |
| `stereonet_dock.py`        | Main dock widget, plot rendering and application coordination |
| `tab_stereonet.py`         | Main stereonet interface and configuration controls           |
| `tab_data.py`              | Data display and manual data entry                            |
| `tab_kinematic_results.py` | Kinematic analysis results                                    |
| `tab_rosette.py`           | Rose diagram controls                                         |
| `stereonet_math.py`        | Stereographic calculations and kinematic algorithms           |
| `data_io.py`               | CSV/TXT and vector layer data loading                         |
| `settings.py`              | Plugin settings and default configuration                     |
| `style.py`                 | Qt stylesheet and interface styling                           |
| `icons.py`                 | Interface icons                                               |
| `i18n_labels.py`           | Translated interface labels                                   |
| `widgets_common.py`        | Reusable custom widgets                                       |

---

## Requirements

StereonetStudio requires:

* **QGIS 4.0 or later**
* **QGIS 4.x**
* Python environment provided by QGIS
* NumPy
* Matplotlib

The plugin metadata specifies:

```text
qgisMinimumVersion=4.0
qgisMaximumVersion=4.99
```

---

## Installation

### From a ZIP package

In QGIS:

1. Open **Plugins → Manage and Install Plugins**.
2. Select **Install from ZIP**.
3. Select the StereonetStudio ZIP package.
4. Confirm the installation.
5. Enable **StereonetStudio** from the installed plugins list.

### Manual installation

Copy the plugin folder into the QGIS plugins directory.


## Basic workflow

A typical workflow is:

1. Open **StereonetStudio**.
2. Select the input source.
3. Select the Dip and Dip Direction fields.
4. Optionally select the Set/Group field.
5. Choose projection and hemisphere.
6. Configure grid, labels and plot options.
7. Enable poles, planes, global mean and/or density contours as required.
8. Enable the rose diagram if required.
9. Enable kinematic analysis and set the required slope and friction parameters.
10. Generate the stereonet.
11. Review the structural and kinematic results.
12. Export the final figure to PNG, JPEG, SVG or PDF.

---

## Metadata

```text
name=StereonetStudio
qgisMinimumVersion=4.0
qgisMaximumVersion=4.99
```

### Description

> Professional stereographic projection (stereonet): polar/equatorial grid, poles, density contours, rose diagram, kinematic analysis (planar slide, wedge slide, flexural and direct toppling), with import from CSV/TXT files or project vector layers. User interface fully translated (Italian/English).

---

## About

StereonetStudio draws a stereographic projection (equal-angle / equal-area, lower/upper hemisphere, polar or equatorial grid) starting from structural data (dip/dip direction, strike/dip, trend/plunge), imported from CSV/TXT files or directly from vector layers loaded into the project.

The plugin provides a modern tabbed interface with:

* Stereonet;
* Data;
* Kinematic Analysis;
* Rosette.

The complete interface is available in Italian and English.

The plotting system includes comprehensive options for:

* labels;
* line weights;
* colours;
* poles;
* planes;
* global mean;
* density contours;
* data-column based density;
* intersection density;
* filled or line contour styles;
* directional rose diagrams.

The kinematic module supports:

* planar sliding;
* wedge sliding;
* flexural toppling;
* direct toppling;

with slope envelopes, friction cones, lateral limits and highlighted critical zones.

The main plot provides a configurable title, legend and density scale, while the rose diagram is positioned separately in the lower-right area to avoid interfering with the stereonet and its labels.

The density scale is fixed in the upper-right area of the plot, leaving the legend area clear.

Text sizes are configurable independently for the title, legend/density labels and plot elements/values.

The generated figures can be exported to PNG, JPEG, SVG and PDF.

---

## License

Specify the project license here.

---

## Author

Dr. Geol. Faustino Cetraro

---

## Interface

<img width="1603" height="897" alt="Immagine1" src="https://github.com/user-attachments/assets/1cb24bac-ef42-408b-b41c-30fcee8bcea0" />

