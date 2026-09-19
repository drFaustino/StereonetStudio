# -*- coding: utf-8 -*-
"""
StereonetStudio - stereonet_math.py

Funzioni matematiche per la proiezione stereografica:
- conversione dip/dip-direction <-> vettori 3D (convenzione N,E,Down positivo)
- proiezione equal-angle (Wulff) / equal-area (Schmidt), emisfero inf./sup.
- generazione del reticolo (equatoriale tipo Wulff/Schmidt, o polare)
- stima di densita' (tipo Kamb semplificato) per i contorni
- geometria per l'analisi cinematica (scivolamento planare/a cuneo,
  ribaltamento flessurale/diretto)

NOTA: la stima di densita' utilizzata per i contorni e' una versione
semplificata (kernel di von Mises-Fisher) e non una implementazione
rigorosa della statistica di Kamb; e' pensata per un uso speditivo/
qualitativo dei contorni di densita' sullo stereonet.
"""

import math
import numpy as np


# ----------------------------------------------------------------------
# Conversioni geometriche di base
# ----------------------------------------------------------------------

def deg2rad(x):
    return x * math.pi / 180.0


def rad2deg(x):
    return x * 180.0 / math.pi


def wrap360(az):
    az = az % 360.0
    if az < 0:
        az += 360.0
    return az


def trend_plunge_to_vector(trend_deg, plunge_deg):
    """Converte trend/plunge in vettore unitario (n, e, d) con d positivo verso il basso."""
    t = deg2rad(trend_deg)
    p = deg2rad(plunge_deg)
    n = math.cos(p) * math.cos(t)
    e = math.cos(p) * math.sin(t)
    d = math.sin(p)
    return np.array([n, e, d], dtype=float)


def vector_to_trend_plunge(v):
    """Converte un vettore (n,e,d) in trend/plunge (gradi). Assume d puo' essere negativo."""
    n, e, d = v
    plunge = rad2deg(math.asin(max(-1.0, min(1.0, d))))
    if abs(n) < 1e-12 and abs(e) < 1e-12:
        trend = 0.0
    else:
        trend = wrap360(rad2deg(math.atan2(e, n)))
    return trend, plunge


def pole_vector(dipdir_deg, dip_deg):
    """Vettore polo (normale al piano) di un piano dip/dipdir. Punta verso il basso."""
    trend = wrap360(dipdir_deg)
    plunge = 90.0 - dip_deg
    return trend_plunge_to_vector(trend, plunge)


def plane_from_pole(pole_v):
    """Dato il vettore polo, ricava dipdir/dip del piano."""
    trend, plunge = vector_to_trend_plunge(pole_v)
    dip = 90.0 - plunge
    dipdir = wrap360(trend)
    return dipdir, dip


def normalize(v):
    n = np.linalg.norm(v)
    if n < 1e-12:
        return v
    return v / n


# ----------------------------------------------------------------------
# Conversione formati di orientazione -> dip/dipdir interno
# ----------------------------------------------------------------------

def to_internal_dipdir_dip(value1, value2, fmt):
    """Converte una coppia di valori nel formato scelto in (dipdir, dip) interni.

    fmt in settings.ORIENTATION_FORMATS
    """
    if fmt == 'Dip / Direzione Immersione':
        dip, dipdir = value1, value2
    elif fmt == 'Direzione (destra) / Dip':
        # Regola mano destra: immersione = strike + 90
        strike, dip = value1, value2
        dipdir = wrap360(strike + 90.0)
    elif fmt == 'Direzione (sinistra) / Dip':
        # Regola mano sinistra: immersione = strike - 90
        strike, dip = value1, value2
        dipdir = wrap360(strike - 90.0)
    elif fmt == 'Trend / Plunge':
        # Interpretato come trend/plunge del POLO della discontinuita'
        trend, plunge = value1, value2
        dipdir = wrap360(trend)
        dip = 90.0 - plunge
    else:
        dip, dipdir = value1, value2
    return wrap360(dipdir), max(0.0, min(90.0, dip))


# ----------------------------------------------------------------------
# Proiezione stereografica di un vettore
# ----------------------------------------------------------------------

def _radius(d, projection):
    d = max(-1.0, min(1.0, d))
    if projection.startswith('Equal Angle'):
        return math.sqrt(max(0.0, (1.0 - d) / (1.0 + d))) if (1.0 + d) > 1e-9 else 1.0
    else:  # Equal Area
        return math.sqrt(max(0.0, 1.0 - d))


def project_vector(v, projection, hemisphere):
    """Proietta un vettore unitario (n,e,d) sul piano dello stereonet (x,y).

    Per dati (poli, linee) che possono trovarsi "naturalmente" in un
    emisfero: se l'emisfero richiesto non corrisponde, si usa il punto
    antipodale (stessa retta, verso opposto) - convenzione standard.
    """
    n, e, d = v
    if hemisphere == 'Inferiore':
        if d < 0:
            n, e, d = -n, -e, -d
        d_eff = d
    else:  # Superiore
        if d > 0:
            n, e, d = -n, -e, -d
        d_eff = -d
    rho = _radius(d_eff, projection)
    az = math.atan2(e, n)
    x = rho * math.sin(az)
    y = rho * math.cos(az)
    return x, y


def project_points_masked(vectors, projection, hemisphere):
    """Proietta una polilinea di vettori (Nx3) SENZA ribaltare all'emisfero opposto:
    i punti che non appartengono all'emisfero richiesto diventano NaN (interrompono
    la linea). Usato per disegnare il reticolo/grid in modo geometricamente corretto.
    """
    xs = np.full(len(vectors), np.nan)
    ys = np.full(len(vectors), np.nan)
    for i, v in enumerate(vectors):
        n, e, d = v
        if hemisphere == 'Inferiore':
            if d < -1e-9:
                continue
            d_eff = d
        else:
            if d > 1e-9:
                continue
            d_eff = -d
        rho = _radius(d_eff, projection)
        az = math.atan2(e, n)
        xs[i] = rho * math.sin(az)
        ys[i] = rho * math.cos(az)
    return xs, ys


def inverse_project(x, y, projection, hemisphere):
    """Da coordinate (x,y) sul disco unitario ricava il vettore 3D (n,e,d)
    riferito all'emisfero selezionato (per l'inversione usata nel calcolo densita').
    Restituisce None se (x,y) e' fuori dal cerchio primitivo.
    """
    rho2 = x * x + y * y
    if rho2 > 1.0 + 1e-9:
        return None
    rho = math.sqrt(rho2)
    az = math.atan2(x, y)
    if projection.startswith('Equal Angle'):
        d_eff = (1.0 - rho2) / (1.0 + rho2) if (1.0 + rho2) > 1e-12 else 0.0
    else:
        d_eff = 1.0 - rho2
    d_eff = max(-1.0, min(1.0, d_eff))
    horiz = math.sqrt(max(0.0, 1.0 - d_eff * d_eff))
    n = math.cos(az) * horiz
    e = math.sin(az) * horiz
    if hemisphere == 'Inferiore':
        d = d_eff
    else:
        d = -d_eff
    return np.array([n, e, d])


# ----------------------------------------------------------------------
# Generazione cerchi grandi/piccoli sulla sfera (per piani e reticolo)
# ----------------------------------------------------------------------

def great_circle_of_plane(dipdir_deg, dip_deg, n_pts=181):
    """Restituisce n_pts vettori (n,e,d) del cerchio massimo corrispondente
    al piano dip/dipdir (traccia del piano sulla sfera unitaria)."""
    pole = pole_vector(dipdir_deg, dip_deg)
    ref = np.array([0.0, 0.0, 1.0])
    if abs(np.dot(ref, pole)) > 0.98:
        ref = np.array([1.0, 0.0, 0.0])
    u = normalize(ref - np.dot(ref, pole) * pole)
    w = np.cross(pole, u)
    ts = np.linspace(0, 2 * math.pi, n_pts)
    pts = np.array([math.cos(t) * u + math.sin(t) * w for t in ts])
    return pts


def great_circle_through_axis(axis, angle_from_axis_deg, n_pts=181):
    """Cerchio massimo contenente l'asse `axis`, ruotato di un dato angolo
    (usato per generare i meridiani del reticolo equatoriale tipo Wulff)."""
    return great_circle_of_plane(*plane_from_pole(_pole_for_meridian(axis, angle_from_axis_deg)), n_pts=n_pts)


def _pole_for_meridian(axis, dip_deg):
    # Meridiano = piano contenente l'asse N-S (axis), con dip_dir perpendicolare ad axis
    trend_axis, _ = vector_to_trend_plunge(axis)
    dipdir = wrap360(trend_axis + 90.0)
    return pole_vector(dipdir, dip_deg)


def small_circle_about_axis(axis, beta_deg, n_pts=181):
    """Cerchio piccolo (piccola circonferenza) attorno all'asse `axis`
    con semi-apertura angolare beta_deg."""
    axis = normalize(np.array(axis, dtype=float))
    ref = np.array([0.0, 0.0, 1.0])
    if abs(np.dot(ref, axis)) > 0.98:
        ref = np.array([0.0, 1.0, 0.0])
    b = normalize(np.cross(axis, ref))
    c = np.cross(axis, b)
    beta = deg2rad(beta_deg)
    ts = np.linspace(0, 2 * math.pi, n_pts)
    pts = np.array([math.cos(beta) * axis + math.sin(beta) * (math.cos(t) * b + math.sin(t) * c) for t in ts])
    return pts


def generate_grid_lines(overlay, tick_spacing, projection, hemisphere):
    """Genera l'elenco di polilinee (ciascuna Nx3 vettori) che compongono il
    reticolo, in base al tipo di overlay ('Equatoriale' o 'Polare')."""
    lines = []
    if overlay == 'Equatoriale':
        # Reticolo equatoriale: la famiglia dei meridiani e' composta da
        # cerchi massimi che passano per N e S. Per ottenere entrambe le
        # meta' (destra e sinistra) del reticolo non basta variare il dip
        # con una sola direzione: bisogna generare le due direzioni opposte.
        #
        # La famiglia dei paralleli e' invece costituita da piccoli cerchi
        # centrati sull'asse N-S orizzontale. In precedenza veniva disegnata
        # solo la meta' nord (beta < 90), lasciando vuota la parte sud.
        ns_axis = trend_plunge_to_vector(0.0, 0.0)  # asse N-S orizzontale

        # MERIDIANI: archi N-S, a passo angolare tick_spacing.
        # Dip=0 e' il cerchio primitivo; dip=90 e' il meridiano centrale.
        dips = list(range(tick_spacing, 90, tick_spacing))
        for dip in dips:
            for dipdir in (90.0, 270.0):
                lines.append(great_circle_of_plane(dipdir, dip, n_pts=361))
        # Il meridiano centrale N-S va aggiunto una sola volta.
        lines.append(great_circle_of_plane(90.0, 90.0, n_pts=361))

        # PARALLELI: beta e' la distanza angolare dall'asse N-S.
        # beta=90 e' l'equatore E-W. Usiamo anche beta>90 per
        # disegnare esplicitamente la meta' meridionale del reticolo.
        for beta in range(tick_spacing, 180, tick_spacing):
            lines.append(small_circle_about_axis(ns_axis, float(beta), n_pts=361))
    else:  # Polare
        # cerchi concentrici (isolinee di plunge/dip) ogni tick_spacing
        for plunge in range(90 - tick_spacing, -1, -tick_spacing):
            pts = []
            for az in np.linspace(0, 360, 181):
                pts.append(trend_plunge_to_vector(az, plunge))
            lines.append(np.array(pts))
        # linee radiali ogni 10 gradi (o multiplo del tick se >10)
        radial_step = tick_spacing if tick_spacing <= 30 else 30
        for az in range(0, 360, radial_step):
            pts = []
            for plunge in np.linspace(0, 90, 91):
                pts.append(trend_plunge_to_vector(az, plunge))
            lines.append(np.array(pts))
    return lines


def primitive_circle(n_pts=361):
    pts = []
    for az in np.linspace(0, 360, n_pts):
        pts.append(trend_plunge_to_vector(az, 0.0))
    return np.array(pts)


# ----------------------------------------------------------------------
# Vettore medio (Global Mean)
# ----------------------------------------------------------------------

def mean_pole_vector(pole_vectors):
    """Vettore risultante normalizzato (somma vettoriale) - orientazione media."""
    if len(pole_vectors) == 0:
        return None
    s = np.sum(np.array(pole_vectors), axis=0)
    if np.linalg.norm(s) < 1e-9:
        return None
    return normalize(s)


def resultant_length_ratio(pole_vectors):
    """R/N: misura di concentrazione dei dati (1 = perfettamente concentrati)."""
    if len(pole_vectors) == 0:
        return 0.0
    s = np.sum(np.array(pole_vectors), axis=0)
    return float(np.linalg.norm(s) / len(pole_vectors))


# ----------------------------------------------------------------------
# Intersezioni fra piani (per Contorni "Intersezioni" e Scivolamento a Cuneo)
# ----------------------------------------------------------------------

def plane_intersections(planes_dipdir_dip, set_labels=None, min_angle_deg=3.0):
    """Calcola le intersezioni (come vettori 3D) fra coppie di piani forniti
    [(dipdir, dip), ...].

    Se set_labels e' fornito (stessa lunghezza di planes_dipdir_dip), vengono
    calcolate solo le intersezioni fra piani appartenenti a SET DIVERSI
    (comportamento corretto per lo scivolamento a cuneo, che richiede
    l'intersezione fra due differenti famiglie di discontinuita').
    Le coppie di piani quasi paralleli (angolo fra i poli < min_angle_deg)
    vengono scartate perche' producono intersezioni geometricamente
    mal condizionate (rumorose).
    """
    poles = [pole_vector(dd, dp) for dd, dp in planes_dipdir_dip]
    inters = []
    n = len(poles)
    for i in range(n):
        for j in range(i + 1, n):
            if set_labels is not None and set_labels[i] == set_labels[j]:
                continue
            cos_ang = max(-1.0, min(1.0, float(np.dot(poles[i], poles[j]))))
            ang = rad2deg(math.acos(abs(cos_ang)))
            if ang < min_angle_deg:
                continue
            v = np.cross(poles[i], poles[j])
            norm = np.linalg.norm(v)
            if norm < 1e-6:
                continue
            v = v / norm
            if v[2] < 0:
                v = -v
            inters.append(v)
    return inters


# ----------------------------------------------------------------------
# Stima di densita' (tipo Kamb semplificato) per i contorni
# ----------------------------------------------------------------------

def density_grid(data_vectors, projection, hemisphere, grid_n=70):
    """Calcola una griglia (X, Y, Z) di densita' percentuale sullo stereonet
    a partire da un elenco di vettori unitari (poli o intersezioni).

    Usa un kernel esponenziale tipo von Mises-Fisher come stima speditiva
    (non e' la statistica di Kamb rigorosa)."""
    data_vectors = [v if v[2] >= 0 else -v for v in data_vectors]  # riporta sempre nell'emisfero inferiore nativo
    if len(data_vectors) == 0:
        return None
    data = np.array(data_vectors)
    n_data = len(data)

    lin = np.linspace(-1.02, 1.02, grid_n)
    X, Y = np.meshgrid(lin, lin)
    Z = np.full_like(X, np.nan)

    # concentrazione tipo Kamb: piu' dati -> kernel piu' stretto
    kappa = max(3.0, 3.0 * math.sqrt(max(1, n_data)))

    grid_vectors = []
    valid_idx = []
    for i in range(grid_n):
        for j in range(grid_n):
            x, y = X[i, j], Y[i, j]
            rho2 = x * x + y * y
            if rho2 > 1.06:
                continue
            if rho2 > 1.0:
                # Punto appena oltre il cerchio primitivo: lo si riporta sul
                # bordo (invece di scartarlo) in modo che la mappa di densita'
                # copra l'intero disco fino al contorno del grande cerchio,
                # senza lasciare una fascia di sfondo non colorata vicino al
                # bordo. Il riempimento viene poi ritagliato esattamente sul
                # cerchio in fase di disegno (vedi StereonetDock._draw_contours).
                scale = 0.999 / math.sqrt(rho2)
                x, y = x * scale, y * scale
            v = inverse_project(x, y, projection, hemisphere)
            if v is None:
                continue
            v_native = v if v[2] >= 0 else -v
            grid_vectors.append(v_native)
            valid_idx.append((i, j))

    if len(grid_vectors) == 0:
        return None
    grid_arr = np.array(grid_vectors)  # (M,3)
    dots = grid_arr @ data.T  # (M, n_data)
    dots = np.clip(dots, -1.0, 1.0)
    weights = np.exp(kappa * (dots - 1.0))
    dens = weights.sum(axis=1)

    max_theoretical = n_data  # se tutti i punti coincidono con la cella
    dens_pct = 100.0 * dens / max(1e-9, dens.max())

    for k, (i, j) in enumerate(valid_idx):
        Z[i, j] = dens_pct[k]

    return X, Y, Z


# ----------------------------------------------------------------------
# Rosetta delle direzioni (dip direction / strike)
# ----------------------------------------------------------------------

def rosette_bins(dipdirs, bin_width=10):
    """Istogramma circolare (0-360) delle direzioni di immersione, in classi
    di bin_width gradi. Ogni misura contribuisce anche al bin opposto
    (+180) per ottenere una rosetta simmetrica tipo "strike rose"."""
    n_bins = int(360 / bin_width)
    counts = np.zeros(n_bins)
    for dd in dipdirs:
        idx = int(wrap360(dd) // bin_width) % n_bins
        counts[idx] += 1
        opp_idx = int(wrap360(dd + 180.0) // bin_width) % n_bins
        counts[opp_idx] += 1
    return counts, bin_width


# ----------------------------------------------------------------------
# Analisi cinematica (Markland / Hoek & Bray - costruzioni classiche)
# ----------------------------------------------------------------------

class KinematicResult:
    def __init__(self):
        self.slope_great_circle = None      # Nx3 vettori
        self.friction_circle = None         # Nx3 vettori (piccola circonferenza)
        self.lateral_limit_lines = []       # lista di coppie di punti (centro->bordo), vettori
        self.highlight_sector = None        # dict con az_min, az_max, rho_min, rho_max (per disegno a settore)
        self.feasible_mask = None           # array bool, stessa lunghezza dei poli in input
        self.n_feasible = 0
        self.description = ''


def _rho_for_dip_at(dipdir_for_pole, dip_value, projection, hemisphere):
    """Raggio (rho) sul grafico del polo di un piano immaginario con la
    stessa direzione di immersione dello sperone/scarpata e dip = dip_value."""
    v = pole_vector(dipdir_for_pole, dip_value)
    _, y = project_vector(v, projection, hemisphere)
    x, y = project_vector(v, projection, hemisphere)
    return math.hypot(x, y)


def kinematic_analysis(mode, poles_dipdir_dip, slope_dip, slope_dipdir,
                        friction_angle, lateral_limit, projection, hemisphere,
                        planes_for_intersections=None, sets_for_intersections=None):
    """Esegue una delle 4 analisi cinematiche classiche e restituisce un
    oggetto KinematicResult pronto per il disegno.

    poles_dipdir_dip: lista di tuple (dipdir, dip) delle discontinuita' misurate
    """
    res = KinematicResult()
    res.slope_great_circle = great_circle_of_plane(slope_dipdir, slope_dip)
    res.friction_circle = small_circle_about_axis(np.array([0, 0, 1.0]), 90.0 - friction_angle)

    az_min = wrap360(slope_dipdir - lateral_limit)
    az_max = wrap360(slope_dipdir + lateral_limit)

    if mode == 'Scivolamento Planare':
        rho_in = _rho_for_dip_at(slope_dipdir, friction_angle, projection, hemisphere)
        rho_out = _rho_for_dip_at(slope_dipdir, slope_dip, projection, hemisphere)
        res.highlight_sector = dict(az_center=slope_dipdir, half_width=lateral_limit,
                                     rho_min=min(rho_in, rho_out), rho_max=max(rho_in, rho_out))
        res.lateral_limit_lines = [az_min, az_max]
        mask = []
        for dd, dp in poles_dipdir_dip:
            ang = _angular_diff(dd, slope_dipdir)
            ok = (ang <= lateral_limit) and (friction_angle <= dp <= slope_dip)
            mask.append(ok)
        res.feasible_mask = np.array(mask, dtype=bool)
        res.description = ('Scivolamento planare possibile se: |DipDir_giunto - DipDir_scarpata| <= '
                            'Limite laterale, e Angolo attrito <= Dip_giunto <= Dip_scarpata.')

    elif mode == 'Scivolamento a Cuneo':
        planes = planes_for_intersections if planes_for_intersections else poles_dipdir_dip
        inters = plane_intersections(planes, set_labels=sets_for_intersections)
        rho_in = _rho_for_dip_at(slope_dipdir, friction_angle, projection, hemisphere)
        rho_out = _rho_for_dip_at(slope_dipdir, slope_dip, projection, hemisphere)
        res.highlight_sector = dict(az_center=slope_dipdir, half_width=lateral_limit,
                                     rho_min=min(rho_in, rho_out), rho_max=max(rho_in, rho_out))
        res.lateral_limit_lines = [az_min, az_max]
        mask = []
        for v in inters:
            trend, plunge = vector_to_trend_plunge(v)
            ang = _angular_diff(trend, slope_dipdir)
            ok = (ang <= lateral_limit) and (friction_angle <= plunge <= slope_dip)
            mask.append(ok)
        res.feasible_mask = np.array(mask, dtype=bool)
        res.intersections = inters
        res.n_feasible = int(np.sum(res.feasible_mask)) if len(mask) else 0
        res.description = ('Scivolamento a cuneo possibile se il trend/plunge della retta di '
                            'intersezione tra due discontinuita\' cade nel settore evidenziato '
                            '(tra il cono di attrito e la scarpata, entro i limiti laterali).')
        return res

    elif mode == 'Ribaltamento Flessurale':
        opp_dipdir = wrap360(slope_dipdir + 180.0)
        dip_limit = max(0.0, min(90.0, 90.0 - slope_dip + friction_angle))
        rho_in = _rho_for_dip_at(opp_dipdir, dip_limit, projection, hemisphere)
        rho_out = _rho_for_dip_at(opp_dipdir, 90.0, projection, hemisphere)
        res.highlight_sector = dict(az_center=opp_dipdir, half_width=lateral_limit,
                                     rho_min=min(rho_in, rho_out), rho_max=max(rho_in, rho_out))
        res.lateral_limit_lines = [wrap360(opp_dipdir - lateral_limit), wrap360(opp_dipdir + lateral_limit)]
        mask = []
        for dd, dp in poles_dipdir_dip:
            ang = _angular_diff(dd, opp_dipdir)
            ok = (ang <= lateral_limit) and (dp >= dip_limit)
            mask.append(ok)
        res.feasible_mask = np.array(mask, dtype=bool)
        res.description = ('Ribaltamento flessurale possibile se il giunto immerge (circa) in '
                            'direzione opposta alla scarpata, con Dip >= 90 - Dip_scarpata + Angolo attrito.')

    else:  # Ribaltamento Diretto
        dip_limit = max(0.0, min(90.0, 90.0 - friction_angle))
        rho_in = _rho_for_dip_at(slope_dipdir, dip_limit, projection, hemisphere)
        rho_out = _rho_for_dip_at(slope_dipdir, 90.0, projection, hemisphere)
        res.highlight_sector = dict(az_center=slope_dipdir, half_width=lateral_limit,
                                     rho_min=min(rho_in, rho_out), rho_max=max(rho_in, rho_out))
        res.lateral_limit_lines = [az_min, az_max]
        mask = []
        for dd, dp in poles_dipdir_dip:
            ang = _angular_diff(dd, slope_dipdir)
            ok = (ang <= lateral_limit) and (dp >= dip_limit)
            mask.append(ok)
        res.feasible_mask = np.array(mask, dtype=bool)
        res.description = ('Ribaltamento diretto (di blocco) possibile per giunti molto ripidi con '
                            'DipDir prossima a quella della scarpata: Dip >= 90 - Angolo attrito.')

    res.n_feasible = int(np.sum(res.feasible_mask)) if res.feasible_mask is not None and len(res.feasible_mask) else 0
    return res


def _angular_diff(a, b):
    d = abs(wrap360(a) - wrap360(b)) % 360.0
    return min(d, 360.0 - d)


def sector_boundary_points(az_center, half_width, rho_min, rho_max, n_pts=60):
    """Restituisce i vertici (x,y) di un settore anulare, per riempimento
    (matplotlib Polygon), dato centro azimutale, semiapertura e raggi."""
    az0 = az_center - half_width
    az1 = az_center + half_width
    azs = np.linspace(az0, az1, n_pts)
    outer = [(rho_max * math.sin(deg2rad(a)), rho_max * math.cos(deg2rad(a))) for a in azs]
    inner = [(rho_min * math.sin(deg2rad(a)), rho_min * math.cos(deg2rad(a))) for a in azs[::-1]]
    return outer + inner


# ----------------------------------------------------------------------
# Statistiche circolari ausiliarie (per il pannello Rosette)
# ----------------------------------------------------------------------

def circular_mean_deg(azimuths_deg):
    """Media circolare (gradi, 0-360) di un elenco di azimuth. None se vuoto."""
    if not azimuths_deg:
        return None
    s = sum(math.sin(deg2rad(a)) for a in azimuths_deg)
    c = sum(math.cos(deg2rad(a)) for a in azimuths_deg)
    if abs(s) < 1e-9 and abs(c) < 1e-9:
        return 0.0
    return wrap360(rad2deg(math.atan2(s, c)))
