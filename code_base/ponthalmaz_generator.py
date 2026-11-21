"""
Ponthalmaz-generátor körillesztéshez (Csebisev-elv).

A feladat: adott egy ponthalmaz, amelyre regressziós kört kell illeszteni.
A ponthalmaz alak-, véletlen- és egyéb hibákat is tartalmaz, és lefedhet
egy teljes kört vagy annak csak egy ívdarabját.

A generálás menete:
  1. van egy "névleges" kör (középpont + sugár R),
  2. a pontok szögei a teljes körön vagy egy ívdarabon belül vannak
     (egyenletes közzel vagy véletlenszerűen, opcionálisan egy szögtartományba
     sűrítve),
  3. minden ponthoz kiszámoljuk a sugarat: alakhiba (ellipszis vagy
     sokszög) + véletlen hiba (zaj) + kiugró pontok eltolása.

Minden hiba csak a pont sugárirányú távolságát változtatja, a szögét nem,
így a pontok mindig a megadott íven belül maradnak.

Ez a modul csak a generálást tartalmazza, grafikus kód nélkül, így a
keresőmódszerek is közvetlenül importálhatják. A grafikus felület a
gui.py-ban van.

Csak a NumPy-t (és a Python alap könyvtárát) használja.
Telepítés, ha kell:  pip install numpy
"""

import math
import numbers

import numpy as np


# ===========================================================================
# 1. A választható típusok és az alapértékek
# ===========================================================================
# a választható típusok (a szótárak értéke a magyar megnevezés)
SHAPE_TYPES = {
    "none": "nincs (tökéletes kör)",
    "ellipse": "ellipszis",
    "polygon": "szabályos sokszög",
}
ANGLE_MODES = {
    "random": "véletlen",
    "uniform": "egyenletes közű",
}

# az alakhibák paramétereinek alapértékei
SHAPE_DEFAULTS = {
    "none": {},
    # ratio = b / a; a = R az x tengely mentén, b = ratio * R az y tengely mentén
    "ellipse": {"ratio": 0.8},
    # sides = oldalszám; az első csúcs a 0°-os irányban van
    "polygon": {"sides": 6},
}


# ===========================================================================
# 2. Segédfüggvények a paraméterek ellenőrzéséhez
# ===========================================================================
def _is_number(value):
    """Igaz, ha value véges valós szám (a bool nem számít számnak)."""
    return (isinstance(value, numbers.Real) and not isinstance(value, bool)
            and math.isfinite(value))


def _is_int(value):
    """Igaz, ha value egész szám (a bool nem számít egésznek)."""
    return isinstance(value, numbers.Integral) and not isinstance(value, bool)


def _check_number(value, name):
    """Ellenőrzi, hogy value véges szám, és float-ként adja vissza;
    különben ValueError a paraméter nevével (name)."""
    if not _is_number(value):
        raise ValueError(f"{name}: véges szám kell (kapott érték: {value!r}).")
    return float(value)


def _arc_span(start, end):
    """Az ív hossza fokban a kezdőszögtől pozitív irányban a végszögig.
    A 0°-on átforduló ív is megengedett (pl. 300° -> 60° = 120°)."""
    return (end - start) % 360.0


# ===========================================================================
# 3. A szögek és a sugarak előállítása
# ===========================================================================
def _make_offsets(rng, count, offset_start, length, mode, full_circle):
    """count darab szögeltolást (fokban) ad az [offset_start, offset_start +
    length] tartományban, egyenletes közzel vagy véletlenszerűen."""
    if count == 0:
        return np.empty(0)
    if mode == "uniform":
        if full_circle:
            # teljes körön a 360° ugyanaz, mint a 0°, ezért azt kihagyjuk
            t = np.arange(count) / count
        elif count == 1:
            t = np.array([0.5])
        else:
            t = np.linspace(0.0, 1.0, count)
        return offset_start + t * length
    return offset_start + rng.uniform(0.0, length, size=count)


def _shape_radius(theta, radius, shape, params):
    """A névleges sugár az alakhibával torzítva, a theta szög (radián)
    függvényében."""
    if shape == "none":
        return np.full_like(theta, radius)
    if shape == "ellipse":
        a = radius
        b = radius * params["ratio"]
        # az ellipszis polárkoordinátás egyenlete a középpontból nézve
        return a * b / np.sqrt((b * np.cos(theta)) ** 2 + (a * np.sin(theta)) ** 2)
    if shape == "polygon":
        k = params["sides"]
        sector = 2.0 * math.pi / k
        phi = np.mod(theta, sector)
        # csúcsok a névleges körön, az oldalak felezőpontja az apotémán
        return radius * math.cos(math.pi / k) / np.cos(phi - math.pi / k)
    raise AssertionError(shape)  # ide az ellenőrzés miatt nem juthatunk


def _check_shape_params(shape, shape_params):
    """Kiegészíti az alakhiba paramétereit az alapértékekkel és ellenőrzi
    őket. Visszaadja a teljes paraméterszótárat."""
    params = dict(SHAPE_DEFAULTS[shape])
    if shape_params:
        unknown = set(shape_params) - set(params)
        if unknown:
            raise ValueError(
                f"Ismeretlen paraméter a(z) '{shape}' alakhibához: "
                f"{', '.join(sorted(unknown))}. "
                f"Lehetséges: {', '.join(params) or 'nincs'}.")
        params.update(shape_params)

    if shape == "ellipse":
        params["ratio"] = _check_number(params["ratio"], "Az ellipszis félátlóinak aránya")
        if params["ratio"] <= 0:
            raise ValueError("Az ellipszis félátlóinak aránya pozitív legyen.")
    elif shape == "polygon":
        if not _is_int(params["sides"]) or params["sides"] < 3:
            raise ValueError("A sokszög oldalszáma legalább 3 legyen (egész szám).")
        params["sides"] = int(params["sides"])
    return params


# ===========================================================================
# 4. A generáló függvény
# ===========================================================================
def generate_points(n, radius=100.0, center=(0.0, 0.0), *,
                    arc=None, angle_mode="random",
                    shape="none", shape_params=None,
                    noise_level=0.0,
                    outlier_fraction=0.0, outlier_distance=None,
                    cluster_fraction=0.0, cluster_range=None,
                    seed=None):
    """
    n darab pontot generál egy névleges kör (center, radius) mentén,
    alak-, véletlen- és egyéb hibákkal.

    Paraméterek:
      n                 a pontok száma (egész, >= 1)
      radius            a névleges kör sugara R (> 0)
      center            a névleges kör középpontja (x, y)
      arc               None = teljes kör, vagy (kezdőszög, végszög) fokban;
                        az ív a kezdőszögtől pozitív (óramutatóval ellentétes)
                        irányban tart a végszögig, átfordulhat a 0°-on is
      angle_mode        "random" = véletlen szögek az íven,
                        "uniform" = egyenletes közű szögek
      shape             alakhiba: "none", "ellipse" vagy "polygon"
      shape_params      az alakhiba paraméterei szótárban (ami hiányzik, az
                        alapértéket kapja, lásd SHAPE_DEFAULTS):
                          ellipse: ratio (b/a; a = R az x, b az y tengely
                                   mentén)
                          polygon: sides (oldalszám; a csúcsok a névleges
                                   körön vannak, az első a 0°-os irányban)
      noise_level       a véletlen hiba mértéke e (>= 0): minden pont sugara
                        egyenletes eloszlású zajt kap a [-e, +e] tartományból
                        (0 = nincs zaj). A zaj korlátos, így egy pont sem
                        kerül e-nél messzebb a zaj nélküli helyétől.
      outlier_fraction  a kiugró pontok aránya 0 és 1 között; ezek
                        sugárirányban véletlenül kifelé vagy befelé
                        d..2d távolságra kerülnek el a helyükről
      outlier_distance  a fenti d; alapértelmezés: max(0.2 * R, 5 * noise_level)
      cluster_fraction  egyenetlen pontsűrűség: a pontok ekkora hányada
                        (0..1) a cluster_range szögtartományba kerül
      cluster_range     (kezdőszög, végszög) fokban, az íven belül
      seed              egész szám (>= 0) a reprodukálhatósághoz; ha None,
                        a függvény sorsol egyet, és visszaadja a ground truth-ban

    A sugárirányú távolság sosem lesz negatív (ha egy nagy befelé mutató hiba
    miatt az lenne, 0-ra vágjuk), így a pont szöge mindig az íven belül marad.

    Visszatérés: (points, ground_truth)
      points        (n, 2) alakú NumPy tömb, minden sor egy (x, y) pont
      ground_truth  szótár a generálás összes adatával (névleges középpont és
                    sugár, lefedettség, hibatípusok és paramétereik, a kiugró
                    pontok indexei, seed), JSON-ba menthető formában
    """
    # --- paraméterek ellenőrzése ---
    if not _is_int(n) or n < 1:
        raise ValueError("A pontok száma legalább 1 legyen (egész szám).")
    n = int(n)
    radius = _check_number(radius, "A névleges sugár")
    if radius <= 0:
        raise ValueError("A névleges sugár pozitív legyen.")
    try:
        cx, cy = center
    except (TypeError, ValueError):
        raise ValueError("A középpont egy (x, y) számpár legyen.")
    cx = _check_number(cx, "A középpont x koordinátája")
    cy = _check_number(cy, "A középpont y koordinátája")

    if arc is None:
        full_circle = True
        arc_start, arc_end, span = 0.0, 360.0, 360.0
    else:
        try:
            arc_start, arc_end = arc
        except (TypeError, ValueError):
            raise ValueError("Az ív egy (kezdőszög, végszög) számpár legyen.")
        arc_start = _check_number(arc_start, "Az ív kezdőszöge")
        arc_end = _check_number(arc_end, "Az ív végszöge")
        span = _arc_span(arc_start, arc_end)
        if span == 0:
            raise ValueError(
                "Az ív kezdő- és végszöge nem lehet ugyanaz (360°-os eltérés "
                "is ennek számít); teljes körhöz válaszd a teljes kört.")
        full_circle = False

    if angle_mode not in ANGLE_MODES:
        raise ValueError(f"Ismeretlen szögeloszlás: {angle_mode!r} "
                         f"(lehetséges: {', '.join(ANGLE_MODES)}).")
    if shape not in SHAPE_TYPES:
        raise ValueError(f"Ismeretlen alakhiba: {shape!r} "
                         f"(lehetséges: {', '.join(SHAPE_TYPES)}).")
    params = _check_shape_params(shape, shape_params)

    noise_level = _check_number(noise_level, "A véletlen hiba mértéke")
    if noise_level < 0:
        raise ValueError("A véletlen hiba mértéke (±e) nem lehet negatív.")

    outlier_fraction = _check_number(outlier_fraction, "A kiugró pontok aránya")
    
    if not 0 <= outlier_fraction <= 1:
        raise ValueError("A kiugró pontok aránya 0 és 1 (0% és 100%) között legyen.")
    
    if outlier_distance is None:
        outlier_distance = max(0.2 * radius, 5.0 * noise_level)
    
    outlier_distance = _check_number(outlier_distance, "A kiugró pontok távolsága")
    
    if outlier_distance <= 0:
        raise ValueError("A kiugró pontok távolsága pozitív legyen.")

    cluster_fraction = _check_number(cluster_fraction, "A sűrített pontok aránya")
    if not 0 <= cluster_fraction <= 1:
        raise ValueError("A sűrített pontok aránya 0 és 1 között legyen.")
    cluster_offset = cluster_span = None
    if cluster_fraction > 0:
        missing_range = ("Egyenetlen sűrűséghez meg kell adni a sűrítés "
                         "szögtartományát (kezdőszög, végszög).")
        if cluster_range is None:
            raise ValueError(missing_range)
        try:
            c_start, c_end = cluster_range
        except (TypeError, ValueError):   # pl. nem két elemű a megadott érték
            raise ValueError(missing_range)
        
        c_start = _check_number(c_start, "A sűrítés kezdőszöge")
        c_end = _check_number(c_end, "A sűrítés végszöge")
        cluster_span = _arc_span(c_start, c_end)
        
        if cluster_span == 0:
            raise ValueError("A sűrítés kezdő- és végszöge nem lehet ugyanaz.")
        
        # a sűrítés tartománya az ív kezdetéhez képest
        cluster_offset = (c_start - arc_start) % 360.0
        
        if not full_circle and cluster_offset + cluster_span > span + 1e-9:
            raise ValueError("A sűrítés szögtartománya az íven belül legyen.")
        cluster_range = (c_start, c_end)
    else:
        cluster_range = None

    if seed is None:
        # sorsolunk egy seedet, hogy a "véletlen" halmaz is visszaállítható legyen
        seed = int(np.random.default_rng().integers(0, 2**31 - 1))
    elif not _is_int(seed) or seed < 0:
        raise ValueError("A seed nemnegatív egész szám legyen (vagy None).")
    seed = int(seed)
    rng = np.random.default_rng(seed)

    # --- 1. a szögek (az ív kezdetétől mért eltolás fokban) ---
    n_cluster = int(round(cluster_fraction * n))
    offsets = np.concatenate((
        _make_offsets(rng, n - n_cluster, 0.0, span, angle_mode, full_circle),
        _make_offsets(rng, n_cluster, cluster_offset, cluster_span, angle_mode,
                      full_circle and cluster_span == 360.0),
    ))
    angles_deg = arc_start + offsets
    theta = np.radians(angles_deg)

    # --- 2. alakhiba ---
    r = _shape_radius(theta, radius, shape, params)

    # --- 3. véletlen hiba (sugárirányú, egyenletes eloszlású zaj ±e) ---
    if noise_level > 0:
        r = r + rng.uniform(-noise_level, noise_level, size=n)

    # --- 4. kiugró pontok ---
    n_out = int(round(outlier_fraction * n))
    outlier_idx = np.sort(rng.choice(n, size=n_out, replace=False))
    if n_out:
        signs = rng.choice((-1.0, 1.0), size=n_out)
        r[outlier_idx] += signs * rng.uniform(outlier_distance,
                                              2.0 * outlier_distance, size=n_out)

    r = np.maximum(r, 0.0)
    points = np.column_stack((cx + r * np.cos(theta), cy + r * np.sin(theta)))

    ground_truth = {
        "n": n,
        "center": [cx, cy],
        "radius": radius,
        "coverage": {
            "full_circle": full_circle,
            "start_deg": arc_start,
            "end_deg": arc_end,
            "span_deg": span,
            "angle_mode": angle_mode,
        },
        "shape_error": {"type": shape, "params": params},
        "random_error": {"level": noise_level},  # egyenletes zaj ±level
        "outliers": {
            "fraction": outlier_fraction,
            "count": n_out,
            "distance": outlier_distance,
            "indices": outlier_idx.tolist(),
        },
        "density": {
            "cluster_fraction": cluster_fraction,
            "cluster_count": n_cluster,
            "cluster_range_deg": None if cluster_range is None else list(cluster_range),
        },
        "seed": seed,
    }
    return points, ground_truth
