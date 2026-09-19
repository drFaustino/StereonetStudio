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
    """Vettore polo (normale al piano) di un piano dip/dipdir, orientato
    verso il BASSO (emisfero inferiore, convenzione standard/Dips):
    trend = dipdir + 180, plunge = 90 - dip.

    (Nella versione precedente il trend era = dipdir: il polo risultava
    ruotato di 180 gradi e "Inferiore" e "Superiore" apparivano scambiati
    rispetto a Dips.)"""
    trend = wrap360(dipdir_deg + 180.0)
    plunge = 90.0 - dip_deg
    return trend_plunge_to_vector(trend, plunge)


def plane_from_pole(pole_v):
    """Dato il vettore polo (verso il basso), ricava dipdir/dip del piano."""
    v = np.asarray(pole_v, dtype=float)
    if v[2] < 0:
        v = -v
    trend, plunge = vector_to_trend_plunge(v)
    dip = 90.0 - plunge
    dipdir = wrap360(trend + 180.0)
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
        # Interpretato come trend/plunge del POLO (verso il basso) della
        # discontinuita': dipdir = trend + 180
        trend, plunge = value1, value2
        dipdir = wrap360(trend + 180.0)
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
        # d = 0 (vettore orizzontale, es. polo di un piano verticale) viene
        # trattato come "verso il basso" e ribaltato: e' la scelta continua
        # con i punti vicini.
        if d > -1e-12:
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


def best_fit_pole_vector(pole_vectors):
    """Polo del piano di miglior adattamento ("Global Best Fit") ai poli:
    autovettore di minimo autovalore del tensore di orientazione
    T = sum(v v^T). Restituito verso il basso (d >= 0). None se < 3 poli."""
    if len(pole_vectors) < 3:
        return None
    arr = np.array(pole_vectors, dtype=float)
    t = arr.T @ arr
    w, vecs = np.linalg.eigh(t)          # autovalori crescenti
    v = vecs[:, 0]
    if v[2] < 0:
        v = -v
    return normalize(v)


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
# Densita' dei poli: conteggio "a cono flottante" sulla sfera (come Dips)
# ----------------------------------------------------------------------

def _fisher_kernel_k(alpha_rad):
    """Costante K del nucleo tipo Fisher usato da Dips: campana di altezza
    massima 1, raggio di base = 2 * raggio del cono di conteggio, e volume
    totale uguale a quello del cilindro di Schmidt (altezza 1, raggio alpha).
    Si risolve  (1 - exp(-K (1 - cos 2a))) / K = 1 - cos a  per bisezione."""
    target = 1.0 - math.cos(alpha_rad)
    c2 = 1.0 - math.cos(2.0 * alpha_rad)
    lo, hi = 1e-6, 1e6
    for _ in range(200):
        mid = math.sqrt(lo * hi)
        f = (1.0 - math.exp(-mid * c2)) / mid - target
        if f > 0:
            lo = mid
        else:
            hi = mid
    return math.sqrt(lo * hi)


def density_grid(data_vectors, projection, hemisphere, grid_n=110,
                 counting_fraction=0.01, distribution='Fisher'):
    """Griglia (X, Y, Z) di concentrazione dei poli sullo stereonet, con lo
    stesso schema di Dips:

    * il conteggio e' fatto sulla SFERA (non sulla proiezione), con un cono
      centrato su ciascun nodo della griglia;
    * il cono ha area pari a `counting_fraction` (default 1%) dell'emisfero:
      cos(alpha) = 1 - counting_fraction  (alpha ~ 8.11 gradi per l'1%);
    * 'Schmidt': ogni polo dentro il cono vale 1;
      'Fisher': ogni polo contribuisce con una campana exp(-K(1-cos t)) di
      altezza 1 e raggio di base 2*alpha (K calcolato in modo che il volume
      resti uguale a quello di Schmidt);
    * Z = somma dei contributi / N * 100  ->  % dei poli per 1% di area
      (cosi' il massimo e' confrontabile con "Maximum Density" di Dips).

    I poli sono dati assiali: si usa |cos| per gestire il bordo del cerchio
    primitivo."""
    if len(data_vectors) == 0:
        return None
    data = np.array([v if v[2] >= 0 else -v for v in data_vectors], dtype=float)
    n_data = len(data)

    lin = np.linspace(-1.02, 1.02, grid_n)
    X, Y = np.meshgrid(lin, lin)
    Z = np.full_like(X, np.nan)

    grid_vectors = []
    valid_idx = []
    for i in range(grid_n):
        for j in range(grid_n):
            x, y = X[i, j], Y[i, j]
            rho2 = x * x + y * y
            if rho2 > 1.06:
                continue
            if rho2 > 1.0:
                # appena oltre il cerchio primitivo: lo si riporta sul bordo
                # cosi' la mappa copre tutto il disco (ritaglio esatto in
                # StereonetDock._draw_contours)
                scale = 0.999 / math.sqrt(rho2)
                x, y = x * scale, y * scale
            v = inverse_project(x, y, projection, hemisphere)
            if v is None:
                continue
            grid_vectors.append(v if v[2] >= 0 else -v)
            valid_idx.append((i, j))

    if len(grid_vectors) == 0:
        return None
    grid_arr = np.array(grid_vectors)            # (M, 3)
    cos_t = np.abs(np.clip(grid_arr @ data.T, -1.0, 1.0))   # (M, N)

    alpha = math.acos(1.0 - counting_fraction)
    cos_a = math.cos(alpha)
    if str(distribution).lower().startswith('s'):
        weights = (cos_t >= cos_a).astype(float)
    else:
        k = _fisher_kernel_k(alpha)
        cos_2a = math.cos(2.0 * alpha)
        weights = np.where(cos_t >= cos_2a, np.exp(-k * (1.0 - cos_t)), 0.0)

    dens_pct = 100.0 * weights.sum(axis=1) / n_data
    for kx, (i, j) in enumerate(valid_idx):
        Z[i, j] = dens_pct[kx]
    return X, Y, Z


def nice_density_levels(z_max, n_intervals=10):
    """Livelli 'tondi' per la scala di densita', come in Dips
    (es. massimo 24.86% -> 0, 2.5, 5, ... 25)."""
    if not np.isfinite(z_max) or z_max <= 0:
        return np.linspace(0.0, 1.0, n_intervals + 1)
    raw = z_max / n_intervals
    base = 10.0 ** math.floor(math.log10(raw))
    for m in (1.0, 2.0, 2.5, 5.0, 10.0):
        step = m * base
        if step >= raw - 1e-12:
            break
    return np.arange(n_intervals + 1) * step


# ----------------------------------------------------------------------
# Rosetta delle direzioni (dip direction / strike)
# ----------------------------------------------------------------------

def rosette_angles(planes, mode='strike', min_dip=0.0, max_dip=90.0):
    """Angoli (gradi) da inserire nella rosetta.

    mode = 'strike'  -> direzione (strike, regola mano destra = dipdir - 90),
                        come "Apparent Strike" di Dips con normale verticale;
    mode = 'dipdir'  -> direzione di immersione.
    Vengono considerati solo i piani con min_dip <= dip <= max_dip
    (in Dips: "Minimum/Maximum Angle To Plot").
    """
    out = []
    for p in planes:
        if not (min_dip - 1e-9 <= p['dip'] <= max_dip + 1e-9):
            continue
        if mode == 'strike':
            out.append(wrap360(p['dipdir'] - 90.0))
        else:
            out.append(wrap360(p['dipdir']))
    return out


def axial_mean_deg(azimuths_deg):
    """Media di dati assiali (strike): angoli raddoppiati, risultato 0-180."""
    if not azimuths_deg:
        return None
    s = sum(math.sin(deg2rad(2 * a)) for a in azimuths_deg)
    c = sum(math.cos(deg2rad(2 * a)) for a in azimuths_deg)
    if abs(s) < 1e-9 and abs(c) < 1e-9:
        return 0.0
    return (rad2deg(math.atan2(s, c)) / 2.0) % 180.0


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
        self.friction_circle = None         # Nx3 vettori (piccola circonferenza) o None
        self.friction_kind = None           # 'friction' | 'limit' | None
        self.lateral_limit_lines = []       # azimuth (gradi) delle linee limite laterale
        self.highlight_polygon = None       # lista di (x, y) gia' proiettati (zona critica)
        self.daylight_envelope = None       # lista di (x, y): daylight envelope (poli)
        self.feasible_mask = None           # array bool
        self.n_feasible = 0
        self.description = ''


def apparent_dip_deg(slope_dip, delta_deg):
    """Dip apparente della scarpata lungo una direzione che forma l'angolo
    delta con la sua direzione di immersione: tan(dip_app) = tan(dip) cos(delta).
    Vale 0 per |delta| >= 90."""
    c = math.cos(deg2rad(delta_deg))
    if c <= 1e-12:
        return 0.0
    return rad2deg(math.atan(math.tan(deg2rad(min(slope_dip, 89.9999))) * c))


def _pole_xy(dipdir, dip, projection, hemisphere):
    return project_vector(pole_vector(dipdir, dip), projection, hemisphere)


def _line_xy(trend, plunge, projection, hemisphere):
    return project_vector(trend_plunge_to_vector(trend, plunge), projection, hemisphere)


def _pole_zone_polygon(dd_center, half_width, dip_in_fn, dip_out_fn, projection, hemisphere, n=61):
    """Poligono (x,y) della zona critica sul grafico dei POLI: per ogni
    direzione di immersione dd_center+delta (|delta| <= half_width) il dip del
    piano deve stare fra dip_in(delta) e dip_out(delta)."""
    deltas = np.linspace(-half_width, half_width, n)
    outer, inner = [], []
    for d in deltas:
        d_in = dip_in_fn(d)
        d_out = max(dip_out_fn(d), d_in)
        outer.append(_pole_xy(dd_center + d, d_out, projection, hemisphere))
        inner.append(_pole_xy(dd_center + d, d_in, projection, hemisphere))
    return outer + inner[::-1]


def kinematic_analysis(mode, poles_dipdir_dip, slope_dip, slope_dipdir,
                        friction_angle, lateral_limit, projection, hemisphere,
                        planes_for_intersections=None, sets_for_intersections=None):
    """Analisi cinematica con gli stessi criteri di Dips (vettori polo).

    Scivolamento planare (poli): dip fra l'angolo di attrito e il DIP
    APPARENTE della scarpata nella direzione del giunto
    (tan dip < tan(slope dip) * cos(dipdir_giunto - dipdir_scarpata), cioe'
    polo dentro la "daylight envelope"), entro i limiti laterali. Il cono di
    attrito per i poli ha raggio = angolo di attrito misurato dal CENTRO.

    Scivolamento a cuneo: rette di intersezione con
    attrito <= plunge <= dip apparente della scarpata lungo il loro trend
    (senza limiti laterali, come il test di Markland in Dips).
    """
    res = KinematicResult()
    res.slope_great_circle = great_circle_of_plane(slope_dipdir, slope_dip)

    def _finish_counts():
        res.n_feasible = int(np.sum(res.feasible_mask)) if res.feasible_mask is not None and len(res.feasible_mask) else 0

    if mode == 'Scivolamento Planare':
        # cono di attrito dei poli: raggio angolare = attrito dal centro
        res.friction_circle = small_circle_about_axis(np.array([0, 0, 1.0]), friction_angle)
        res.friction_kind = 'friction'
        res.lateral_limit_lines = [wrap360(slope_dipdir - lateral_limit), wrap360(slope_dipdir + lateral_limit)]
        res.highlight_polygon = _pole_zone_polygon(
            slope_dipdir, lateral_limit,
            lambda d: friction_angle,
            lambda d: apparent_dip_deg(slope_dip, d),
            projection, hemisphere)
        env = [_pole_xy(slope_dipdir + d, apparent_dip_deg(slope_dip, d), projection, hemisphere)
               for d in np.linspace(-90.0, 90.0, 181)]
        res.daylight_envelope = env
        mask = []
        for dd, dp in poles_dipdir_dip:
            ang = _angular_diff(dd, slope_dipdir)
            ok = (ang <= lateral_limit) and (friction_angle <= dp <= apparent_dip_deg(slope_dip, ang))
            mask.append(ok)
        res.feasible_mask = np.array(mask, dtype=bool)
        res.description = ('Scivolamento planare possibile se: |DipDir_giunto - DipDir_scarpata| <= '
                            'Limite laterale, e Angolo attrito <= Dip_giunto <= Dip apparente della scarpata '
                            '(polo dentro la daylight envelope).')

    elif mode == 'Scivolamento a Cuneo':
        planes = planes_for_intersections if planes_for_intersections else poles_dipdir_dip
        inters = plane_intersections(planes, set_labels=sets_for_intersections)
        # cono di attrito per RETTE (dip vectors): plunge = attrito
        res.friction_circle = small_circle_about_axis(np.array([0, 0, 1.0]), 90.0 - friction_angle)
        res.friction_kind = 'friction'
        res.lateral_limit_lines = []
        # zona critica: fra il cerchio di attrito e il grande cerchio della scarpata
        polygon = None
        if slope_dip > friction_angle:
            dmax = rad2deg(math.acos(min(1.0, math.tan(deg2rad(friction_angle)) / math.tan(deg2rad(slope_dip)))))
            deltas = np.linspace(-dmax, dmax, 91)
            outer = [_line_xy(slope_dipdir + d, max(apparent_dip_deg(slope_dip, d), friction_angle),
                              projection, hemisphere) for d in deltas]
            inner = [_line_xy(slope_dipdir + d, friction_angle, projection, hemisphere) for d in deltas]
            polygon = outer + inner[::-1]
        res.highlight_polygon = polygon
        mask = []
        for v in inters:
            trend, plunge = vector_to_trend_plunge(v)
            ang = _angular_diff(trend, slope_dipdir)
            ok = (ang < 90.0) and (friction_angle <= plunge <= apparent_dip_deg(slope_dip, ang))
            mask.append(ok)
        res.feasible_mask = np.array(mask, dtype=bool)
        res.intersections = inters
        res.description = ('Scivolamento a cuneo possibile se il trend/plunge della retta di '
                            'intersezione tra due discontinuita\' cade nel settore evidenziato '
                            '(tra il cono di attrito e la scarpata, entro i limiti laterali).')

    elif mode == 'Ribaltamento Flessurale':
        opp_dipdir = wrap360(slope_dipdir + 180.0)
        dip_limit = max(0.0, min(90.0, 90.0 - slope_dip + friction_angle))
        res.friction_circle = None
        res.lateral_limit_lines = [wrap360(opp_dipdir - lateral_limit), wrap360(opp_dipdir + lateral_limit)]
        res.highlight_polygon = _pole_zone_polygon(
            opp_dipdir, lateral_limit, lambda d: dip_limit, lambda d: 90.0, projection, hemisphere)
        mask = []
        for dd, dp in poles_dipdir_dip:
            ang = _angular_diff(dd, opp_dipdir)
            mask.append((ang <= lateral_limit) and (dp >= dip_limit))
        res.feasible_mask = np.array(mask, dtype=bool)
        res.description = ('Ribaltamento flessurale possibile se il giunto immerge (circa) in '
                            'direzione opposta alla scarpata, con Dip >= 90 - Dip_scarpata + Angolo attrito.')

    else:  # Ribaltamento Diretto
        dip_limit = max(0.0, min(90.0, 90.0 - friction_angle))
        res.friction_circle = small_circle_about_axis(np.array([0, 0, 1.0]), dip_limit)
        res.friction_kind = 'friction'
        res.lateral_limit_lines = [wrap360(slope_dipdir - lateral_limit), wrap360(slope_dipdir + lateral_limit)]
        res.highlight_polygon = _pole_zone_polygon(
            slope_dipdir, lateral_limit, lambda d: dip_limit, lambda d: 90.0, projection, hemisphere)
        mask = []
        for dd, dp in poles_dipdir_dip:
            ang = _angular_diff(dd, slope_dipdir)
            mask.append((ang <= lateral_limit) and (dp >= dip_limit))
        res.feasible_mask = np.array(mask, dtype=bool)
        res.description = ('Ribaltamento diretto (di blocco) possibile per giunti molto ripidi con '
                            'DipDir prossima a quella della scarpata: Dip >= 90 - Angolo attrito.')

    _finish_counts()
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
