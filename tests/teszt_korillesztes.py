"""
Rövid, nem grafikus ellenőrző szkript a körillesztéshez (korillesztes.py).

Futtatás (a projekt gyökeréből):  python3 tests/teszt_korillesztes.py
Kilépési kód: 0, ha minden ellenőrzés sikeres, különben 1.

Ellenőrzi:
  1. ismert tökéletes körre (zaj nélkül) mindhárom módszer 0-hoz közeli
     szélességet ad,
  2. azonos seeddel azonos eredmény jön ki.
"""

import os
import sys

# ===========================================================================
# 1. Előkészítés
# ===========================================================================
# a projekt mappája (a tests mappa szülője): ezt felvesszük a Python
# keresési útvonalára, hogy a code_base mappa fájljai importálhatók legyenek
project_folder = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_folder)

from code_base import korillesztes as kor
from code_base.ponthalmaz_generator import generate_points

failures = 0     # a sikertelen ellenőrzések száma


def check(condition, text):
    """Kiírja az ellenőrzés eredményét (OK vagy HIBA + leírás), és számolja
    a sikertelen ellenőrzéseket."""
    global failures
    if condition:
        print("OK    " + text)
    else:
        print("HIBA  " + text)
        failures = failures + 1


# ===========================================================================
# 2. Ellenőrzés: tökéletes kör -> 0-hoz közeli szélesség
# ===========================================================================
# 100 pont pontosan az R = 100 sugarú körön.
# A módszerek egy iterációja különböző munka (1-40 kiértékelés), ezért
# nagyjából azonos kiértékelésszámot adunk nekik (kb. 8-12 ezret).
circle, ground_truth = generate_points(100, radius=100, seed=1)
tests = [
    (kor.hill_climbing, 1000),
    (kor.simulated_annealing, 10000),
    (kor.genetic_algorithm, 300),
]
for method, iterations in tests:
    # 5 különböző seeddel futtatjuk, és a legrosszabb eredményt nézzük
    worst = 0
    name = ""
    for seed in range(5):
        result = method(circle, iterations, seed)
        name = result.method
        if result.width > worst:
            worst = result.width
    check(worst < 0.001,
          f"tökéletes kör, {name} ({iterations} iteráció, 5 seed): "
          f"legrosszabb szélesség {worst:.1e} (< 1e-3, R = 100)")

# ===========================================================================
# 3. Ellenőrzés: azonos seed -> azonos eredmény
# ===========================================================================
points, ground_truth = generate_points(100, radius=100, noise_level=1, seed=7)
first = kor.fit_all(points, 100, seed=42)
second = kor.fit_all(points, 100, seed=42)
for i in range(len(first)):
    result1 = first[i]
    result2 = second[i]
    same = (result1.center == result2.center
            and result1.width == result2.width
            and result1.evaluations == result2.evaluations)
    check(same, f"{result1.method}: azonos seed -> azonos eredmény")

# ===========================================================================
# 4. Összesítés (kilépési kód: 0 = minden rendben, 1 = volt hiba)
# ===========================================================================
print()
if failures == 0:
    print("ÖSSZESEN: minden rendben")
    sys.exit(0)
else:
    print(f"ÖSSZESEN: {failures} hiba")
    sys.exit(1)
