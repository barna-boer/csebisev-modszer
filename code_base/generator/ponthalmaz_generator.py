"""
Ponthalmaz-generátor a körillesztéshez.

A pontok egy névleges kör (középpont: CENTER, sugár: radius) mentén jönnek
létre. Minden pontra:
  1. választunk egy szöget (a teljes körön vagy egy ívdarabon),
  2. kiszámoljuk a sugarát: a névleges sugár, amit az alakhiba torzít
     (ellipszis vagy szabályos sokszög),
  3. hozzáadjuk a véletlen hibát (zaj, ±e),
  4. a pontok egy része kiugró pont: a sugara ±d..2d-vel eltolódik.
A hibák csak a pont sugarát változtatják, a szögét nem, így a pontok
mindig a megadott íven maradnak.

A grafikus felület a generator_gui.py-ban van.
"""

import math
import random

import numpy as np

# ===========================================================================
# A választható értékek és a névleges középpont
# ===========================================================================
SHAPES = ["nincs", "ellipszis", "sokszög"]      # az alakhiba típusa
ANGLE_MODES = ["véletlen", "egyenletes"]        # a szögek eloszlása

CENTER = (0.0, 0.0)     # a névleges kör középpontja


# ===========================================================================
# Segédfüggvények
# ===========================================================================
def make_angles(rng, n, arc_start, arc_span, angle_mode, full_circle):
    """n darab szög (fokban) az [arc_start, arc_start + arc_span] tartományban,
    véletlenszerűen vagy egyenletes közzel."""
    angles = []
    for i in range(n):
        if angle_mode == "egyenletes":
            if full_circle:
                # teljes körön a 360° ugyanaz, mint a 0°, ezért azt kihagyjuk
                fraction = i / n
            elif n == 1:
                fraction = 0.5
            else:
                fraction = i / (n - 1)
            angles.append(arc_start + fraction * arc_span)
        else:
            angles.append(arc_start + rng.uniform(0, arc_span))
    return angles


def shape_radius(angle, radius, shape, ellipse_ratio, polygon_sides):
    """A pont sugara az alakhibával torzítva (angle: a pont szöge radiánban)."""
    if shape == "ellipszis":
        a = radius                    # a félátló az x tengely mentén
        b = radius * ellipse_ratio    # a félátló az y tengely mentén
        # az ellipszis egyenlete polárkoordinátákban
        return a * b / math.sqrt((b * math.cos(angle)) ** 2 + (a * math.sin(angle)) ** 2)

    if shape == "sokszög":
        sector = 2 * math.pi / polygon_sides    # egy oldalhoz tartozó középponti szög
        angle_in_sector = angle % sector        # a szög az adott oldalon belül
        # a csúcsok a névleges körön vannak, az oldalak felezőpontja beljebb
        half_sector = math.pi / polygon_sides
        return radius * math.cos(half_sector) / math.cos(angle_in_sector - half_sector)

    return radius                               # nincs alakhiba: tökéletes kör


# ===========================================================================
# A generáló függvény
# ===========================================================================
def generate_points(n, radius=100.0, full_circle=True, arc_start=0.0, arc_end=360.0,
                    angle_mode="véletlen", shape="nincs", ellipse_ratio=0.8,
                    polygon_sides=6, noise=0.0, outlier_percent=0.0, seed=None):
    """Legenerálja a ponthalmazt.

    n:               a pontok száma
    radius:          a névleges kör sugara
    full_circle:     True = teljes kör, False = ívdarab (arc_start -> arc_end, fokban)
    angle_mode:      "véletlen" vagy "egyenletes" szögek
    shape:           alakhiba: "nincs", "ellipszis" (ellipse_ratio = b/a)
                     vagy "sokszög" (polygon_sides = oldalszám)
    noise:           a véletlen hiba mértéke: a sugár ±noise-zal változhat
    outlier_percent: a kiugró pontok aránya százalékban
    seed:            a véletlenszám-generátor kezdőértéke (None = véletlen);
                     ugyanazzal a seeddel mindig ugyanaz a ponthalmaz jön ki

    Visszatérés: (points, generation_info)
      points:          numpy tömb, (n, 2) alakú: soronként egy (x, y) pont
      generation_info: szótár a generálás adataival (névleges kör, kiugró
                       pontok sorszámai stb.), ezt a többi ablak is használja
    Hibás paraméternél ValueError (a hibaüzenetet a GUI kiírja).
    """
    # -----------------------------------------------------------------------
    # 1. A paraméterek ellenőrzése
    # -----------------------------------------------------------------------
    if n < 1:
        raise ValueError("A pontok száma legalább 1 legyen.")
    if radius <= 0:
        raise ValueError("A névleges sugár pozitív legyen.")
    if shape == "ellipszis" and ellipse_ratio <= 0:
        raise ValueError("Az ellipszis aránya pozitív legyen.")
    if shape == "sokszög" and polygon_sides < 3:
        raise ValueError("A sokszög oldalszáma legalább 3 legyen.")
    if noise < 0:
        raise ValueError("A véletlen hiba mértéke nem lehet negatív.")
    if outlier_percent < 0 or outlier_percent > 100:
        raise ValueError("A kiugró pontok aránya 0 és 100% között legyen.")
    if seed is not None and seed < 0:
        raise ValueError("A seed nemnegatív egész szám legyen.")

    # a lefedettség: teljes kör vagy ívdarab
    if full_circle:
        arc_start = 0.0
        arc_end = 360.0
        arc_span = 360.0
    else:
        # az ív hossza pozitív irányban, a 0°-on átfordulva is
        # (pl. 300° -> 60° = 120°)
        arc_span = (arc_end - arc_start) % 360
        if arc_span == 0:
            raise ValueError("Az ív kezdő- és végszöge nem lehet ugyanaz "
                             "(teljes körhöz válaszd a teljes kört).")

    # a seed és a véletlenszám-generátor
    if seed is None:
        seed = random.randrange(2**31 - 1)
    rng = random.Random(seed)

    # -----------------------------------------------------------------------
    # 2. A pontok előállítása
    # -----------------------------------------------------------------------
    # a szögek
    angles = make_angles(rng, n, arc_start, arc_span, angle_mode, full_circle)

    # a sugarak: alakhiba + véletlen hiba (±noise)
    radii = []
    for angle in angles:
        r = shape_radius(math.radians(angle), radius, shape, ellipse_ratio, polygon_sides)
        if noise > 0:
            r = r + rng.uniform(-noise, noise)
        radii.append(r)

    # a kiugró pontok: a sugaruk d..2d távolsággal kifelé vagy befelé tolódik
    outlier_distance = max(0.2 * radius, 5 * noise)
    outlier_count = round(outlier_percent / 100 * n)
    outlier_indices = sorted(rng.sample(range(n), outlier_count))
    for i in outlier_indices:
        direction = rng.choice([-1, 1])          # befelé (-1) vagy kifelé (+1)
        radii[i] = radii[i] + direction * rng.uniform(outlier_distance, 2 * outlier_distance)

    # a pontok (x, y) koordinátái
    points = []
    for i in range(n):
        r = max(radii[i], 0)                     # a sugár nem lehet negatív
        angle = math.radians(angles[i])
        x = CENTER[0] + r * math.cos(angle)
        y = CENTER[1] + r * math.sin(angle)
        points.append([x, y])
    points = np.array(points)

    # -----------------------------------------------------------------------
    # 3. A generálás adatai
    # -----------------------------------------------------------------------
    generation_info = {
        "n": n,
        "center": CENTER,
        "radius": radius,
        "full_circle": full_circle,
        "arc_start": arc_start,
        "arc_end": arc_end,
        "arc_span": arc_span,
        "angle_mode": angle_mode,
        "shape": shape,
        "ellipse_ratio": ellipse_ratio,
        "polygon_sides": polygon_sides,
        "noise": noise,
        "outlier_count": outlier_count,
        "outlier_indices": outlier_indices,
        "seed": seed,
    }
    return points, generation_info
