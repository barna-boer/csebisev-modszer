"""
Rövid, nem grafikus ellenőrző szkript a körillesztéshez (korillesztes.py).

Futtatás (a projekt gyökeréből):  python3 tests/teszt_korillesztes.py
Kilépési kód: 0, ha minden ellenőrzés sikeres, különben 1.

Ellenőrzi:
  1. ismert tökéletes körre (zaj nélkül) mind a négy módszer 0-hoz közeli
     szélességet ad,
  2. azonos seeddel azonos eredmény jön ki.
"""

import sys
from pathlib import Path

# ===========================================================================
# 1. Előkészítés: importok és az ellenőrző segédfüggvény
# ===========================================================================
# a projekt gyökerét felvesszük a keresési útvonalra, hogy a tests mappából
# indítva is látszódjon a code_base csomag
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from code_base import korillesztes as kor  # noqa: E402
from code_base.ponthalmaz_generator import generate_points  # noqa: E402

failures = 0


def check(condition, text):
    """Kiírja az ellenőrzés eredményét (OK / HIBA + leírás), és számolja a
    sikertelen ellenőrzéseket."""
    global failures
    print(("OK    " if condition else "HIBA  ") + text)
    if not condition:
        failures += 1


# ===========================================================================
# 2. Ellenőrzés: tökéletes kör -> 0-hoz közeli szélesség
# ===========================================================================
# 100 pont pontosan az R = 100 sugarú körön.
# A módszerek egy iterációja különböző munka (1-40 kiértékelés), ezért
# nagyjából azonos kiértékelésszámot adunk nekik (kb. 8-12 ezret).
circle, _ = generate_points(100, radius=100, seed=1)
max_iter = {kor.hill_climbing: 1000, kor.simulated_annealing: 10000,
            kor.genetic_algorithm: 300, kor.particle_swarm: 300}
for method in kor.SEARCH_METHODS:
    widths = [method(circle, max_iter[method], seed).width for seed in range(5)]
    name = method(circle, 1, 0).method
    check(max(widths) < 1e-3,
          f"tökéletes kör, {name} ({max_iter[method]} iteráció, 5 seed): "
          f"legrosszabb szélesség {max(widths):.1e} (< 1e-3, R = 100)")

# ===========================================================================
# 3. Ellenőrzés: azonos seed -> azonos eredmény (a fit_all-on keresztül)
# ===========================================================================
points, _ = generate_points(100, radius=100, noise_level=1, seed=7)
first = kor.fit_all(points, 100, seed=42)
second = kor.fit_all(points, 100, seed=42)
for r1, r2 in zip(first, second):
    check(r1.center == r2.center and r1.width == r2.width
          and r1.evaluations == r2.evaluations,
          f"{r1.method}: azonos seed -> azonos eredmény")

# ===========================================================================
# 4. Összesítés (kilépési kód: 0 = minden rendben, 1 = volt hiba)
# ===========================================================================
print("\nÖSSZESEN:", "minden rendben" if failures == 0 else f"{failures} hiba")
sys.exit(1 if failures else 0)
