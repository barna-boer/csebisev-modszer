"""
Ponthalmaz-generátor körillesztéshez (Csebisev-elv).

A generálás menete (minden pontra):
  1. pont szögének választása (a teljes körön vagy  ívdarabon)
  2. sugár kiszámolása: a névleges sugár, (az alakhibával torzítva ellipszis, sokszög),
  3. véletlen hiba hozzáadása (zaj),
  4. kiugró pont: a pont sugarát ±d távolsággal eltoljuk

Hibák csak a pont sugarát változtatják, a szögét nem - íven maradnak

Grafikus felület a gui.py-ban.
"""

import math
import random
import numpy as np


# ===========================================================================
#region A választható típusok és az alapértékek
# ===========================================================================

# a választható alakhibák 
# kulcs: a kódban használt név
# érték: magyar név
SHAPE_TYPES = {
    "none": "nincs (tökéletes kör)",
    "ellipse": "ellipszis",
    "polygon": "szabályos sokszög",
}

# a szögek eloszlása
ANGLE_MODES = {
    "random": "véletlen",
    "uniform": "egyenletes közű",
}

# az alakhibák paramétereinek alapértékei
SHAPE_DEFAULTS = {
    "none": {},
    "ellipse": {"ratio": 0.8},  # ratio = b / a; a = R az x tengely mentén, b = ratio * R az y tengely mentén
    "polygon": {"sides": 6},    # sides = oldalszám; az első csúcs a 0°-os irányban van
}
#endregion

# ===========================================================================
#region Segédfüggvények (paraméterek ellenőrzéséhez)
# ===========================================================================
def is_number(value):
    """Igaz, ha value egy véges szám (int vagy float, de nem True/False)."""
    
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    return math.isfinite(value)


def is_whole_number(value):
    """Igaz, ha value egész szám (int, de nem True/False)."""
    
    if isinstance(value, bool):
        return False
    return isinstance(value, int)


def check_number(value, name):
    """Ellenőrzi, hogy value véges szám, és float-ként adja vissza.
    Ha nem szám, ValueError-t dob a paraméter nevével (name)."""
    
    if not is_number(value):
        raise ValueError(f"{name}: véges szám kell (kapott érték: {value}).")
    return float(value)


def arc_length(start, end):
    """Az ív hossza fokban a kezdőszögtől pozitív irányban a végszögig.
    A 0°-on átforduló ív is megengedett (pl. 300° -> 60° = 120°)."""
    
    return (end - start) % 360


def check_shape_params(shape, shape_params):
    """Az alakhiba paraméterei: az alapértékekből indulunk, és felülírjuk őket
    a megadottakkal, majd ellenőrizzük őket. Visszaadja a paraméterszótárat."""
    
    params = {}     # paraméterek tároló dict (szótár)

    for key in SHAPE_DEFAULTS[shape]:
        params[key] = SHAPE_DEFAULTS[shape][key]

    if shape_params is not None:
        for key in shape_params:
            if key not in params:
                raise ValueError(f"Ismeretlen paraméter a(z) '{shape}' "
                                 f"alakhibához: {key}.")
            params[key] = shape_params[key]

    if shape == "ellipse":
        params["ratio"] = check_number(params["ratio"],
                                       "Az ellipszis félátlóinak aránya")
        if params["ratio"] <= 0:
            raise ValueError("Az ellipszis félátlóinak aránya pozitív kell legyen.")
    
    if shape == "polygon":
        if not is_whole_number(params["sides"]) or params["sides"] < 3:
            raise ValueError("A sokszög oldalszáma legalább 3 kell legyen.")
    
    return params

#endregion

# ===========================================================================
#region A szögek és a sugarak előállítása
# ===========================================================================
def make_angles(rnd, count, start, length, angle_mode, full_circle):
    """count darab szög (fokban) a [start, start + length] tartományban,
    egyenletes közzel vagy véletlenszerűen."""
    
    angles = []     # szögek listája
    for i in range(count):
        if angle_mode == "uniform":
            if full_circle:
                # teljes körön a 360° ugyanaz, mint a 0°, ezért azt kihagyjuk
                t = i / count
            elif count == 1:
                t = 0.5
            else:
                t = i / (count - 1)
            angles.append(start + t * length)
        
        else:   # véletlen szögek
            angles.append(start + rnd.uniform(0, length))
    
    return angles


def shape_radius(angle, radius, shape, params):
    """A pont sugara az alakhibával torzítva; angle a pont szöge radiánban."""
    
    if shape == "ellipse":
        a = radius                       # a félátló az x tengely mentén
        b = radius * params["ratio"]     # b félátló az y tengely mentén
        
        # az ellipszis egyenlete polárkoordinátákban
        return a * b / math.sqrt((b * math.cos(angle)) ** 2
                                 + (a * math.sin(angle)) ** 2)
    if shape == "polygon":
        sides = params["sides"]
        sector = 2 * math.pi / sides     # egy oldalhoz tartozó középponti szög
        phi = angle % sector             # a szög az adott oldalon belül
        #
        #  a csúcsok a névleges körön vannak, az oldalak felezőpontja beljebb
        return radius * math.cos(math.pi / sides) / math.cos(phi - math.pi / sides)
    
    return radius                        # ha nincs alakhiba: tökéletes kör

#endregion

# ===========================================================================
#region A generáló függvény
# ===========================================================================
def generate_points(n, radius=100.0, center=(0.0, 0.0),
                    arc=None, angle_mode="random",
                    shape="none", shape_params=None,
                    noise_level=0.0,
                    outlier_fraction=0.0, outlier_distance=None,
                    seed=None):
    
    # -----------------------------------------------------------------------
    # paraméterek ellenőrzése
    # -----------------------------------------------------------------------

    # a pontok száma, a névleges sugár és a középpont
    if not is_whole_number(n) or n < 1:
        raise ValueError("A pontok száma legalább 1 kell legyen (egész szám).")

    radius = check_number(radius, "A névleges sugár")
    if radius <= 0:
        raise ValueError("A névleges sugár pozitív kell legyen.")

    if len(center) != 2:
        raise ValueError("A középpont egy (x, y) számpár legyen.")
    
    center_x = check_number(center[0], "A középpont x koordinátája")
    center_y = check_number(center[1], "A középpont y koordinátája")

    # a lefedettség: teljes kör vagy ívdarab
    if arc is None:
        full_circle = True
        arc_start = 0.0
        arc_end = 360.0
        span = 360.0
    else:
        if len(arc) != 2:
            raise ValueError("Az ív egy (kezdőszög, végszög) számpár legyen.")
        
        full_circle = False
        arc_start = check_number(arc[0], "Az ív kezdőszöge")
        arc_end = check_number(arc[1], "Az ív végszöge")
        span = arc_length(arc_start, arc_end)
        
        if span == 0:
            raise ValueError("Az ív kezdő- és végszöge nem lehet ugyanaz " 
                             "teljes körhöz válaszd a "
                             "teljes kört.")

    # a szögeloszlás és az alakhiba
    if angle_mode not in ANGLE_MODES:
        raise ValueError(f"Ismeretlen szögeloszlás: {angle_mode}.")
    if shape not in SHAPE_TYPES:
        raise ValueError(f"Ismeretlen alakhiba: {shape}.")
    params = check_shape_params(shape, shape_params)

    # a véletlen hiba
    noise_level = check_number(noise_level, "A véletlen hiba mértéke")
    if noise_level < 0:
        raise ValueError("A véletlen hiba mértéke (±e) nem lehet negatív.")

    # a kiugró pontok
    outlier_fraction = check_number(outlier_fraction, "A kiugró pontok aránya")
    if outlier_fraction < 0 or outlier_fraction > 1:
        raise ValueError("A kiugró pontok aránya 0 és 1 (0% és 100%) között legyen.")
    
    if outlier_distance is None:
        outlier_distance = max(0.2 * radius, 5 * noise_level)
    
    outlier_distance = check_number(outlier_distance, "A kiugró pontok távolsága")
    
    if outlier_distance <= 0:
        raise ValueError("A kiugró pontok távolsága pozitív legyen.")

    # a seed és a véletlenszám-generátor
    if seed is None:
        seed = random.randrange(2**31 - 1)
    elif not is_whole_number(seed) or seed < 0:
        raise ValueError("A seed nemnegatív egész szám legyen (vagy None).")

    # a véletlenszám-generátor: azonos seed -> ugyanazt a ponthalmazt adja
    rnd = random.Random(seed)

    # -----------------------------------------------------------------------
    # A pontok előállítása
    # -----------------------------------------------------------------------
    
    # Szögek
    angles = make_angles(rnd, n, arc_start, span, angle_mode, full_circle)

    # Sugarak: alakhiba + véletlen hiba (zaj ±e)
    radii = []
    for angle in angles:
        r = shape_radius(math.radians(angle), radius, shape, params)
        if noise_level > 0:
            r = r + rnd.uniform(-noise_level, noise_level)
        radii.append(r)

    # Kiugró pontok: kifelé vagy befelé
    outlier_count = round(outlier_fraction * n)
    outlier_indices = sorted(rnd.sample(range(n), outlier_count))
    
    for i in outlier_indices:
        direction = rnd.choice([-1, 1])           # befelé vagy kifelé
        distance = rnd.uniform(outlier_distance, 2 * outlier_distance)
        radii[i] = radii[i] + direction * distance

    # Pontok (x, y) koordinátái
    points = []
    for i in range(n):
        r = max(radii[i], 0)           # a sugár nem lehet negatív
        
        angle = math.radians(angles[i])
        
        x = center_x + r * math.cos(angle)
        y = center_y + r * math.sin(angle)
        points.append([x, y])
    
    points = np.array(points)

    # -----------------------------------------------------------------------
    # A generálás adatai (ground truth)
    # -----------------------------------------------------------------------
    
    # Minden adata (a GUI és a kiértékelés is ezeket használja)
    ground_truth = {
        "n": n,
        "center": [center_x, center_y],
        "radius": radius,
        "coverage": {
            "full_circle": full_circle,
            "start_deg": arc_start,
            "end_deg": arc_end,
            "span_deg": span,
            "angle_mode": angle_mode,
        },
        "shape_error": {"type": shape, "params": params},
        "random_error": {"level": noise_level},
        "outliers": {
            "fraction": outlier_fraction,
            "count": outlier_count,
            "distance": outlier_distance,
            "indices": outlier_indices,
        },
        "seed": seed,
    }

    # függvény visszatérési értéke:
    return points, ground_truth
#endregion