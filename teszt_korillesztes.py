"""
Rövid, nem grafikus ellenőrző szkript a körillesztéshez (korillesztes.py).

Futtatás:  python3 teszt_korillesztes.py
Kilépési kód: 0, ha minden ellenőrzés sikeres, különben 1.

Ellenőrzi:
  1. ismert tökéletes körre (zaj nélkül) mind a négy módszer 0-hoz közeli
     szélességet ad,
  2. azonos seeddel azonos eredmény jön ki.
"""

import sys

import korillesztes as kor
from ponthalmaz_generator import generate_points

failures = 0


def check(condition, text):
    global failures
    print(("OK    " if condition else "HIBA  ") + text)
    if not condition:
        failures += 1


# 1. tökéletes kör: 100 pont pontosan az R = 100 sugarú körön.
#    A módszerek egy iterációja különböző munka (1-40 kiértékelés), ezért
#    nagyjából azonos kiértékelésszámot adunk nekik (kb. 8-12 ezret).
circle, _ = generate_points(100, radius=100, seed=1)
max_iter = {kor.hill_climbing: 1000, kor.simulated_annealing: 10000,
            kor.genetic_algorithm: 300, kor.particle_swarm: 300}
for method in kor.SEARCH_METHODS:
    widths = [method(circle, max_iter[method], seed).width for seed in range(5)]
    name = method(circle, 1, 0).method
    check(max(widths) < 1e-3,
          f"tökéletes kör, {name} ({max_iter[method]} iteráció, 5 seed): "
          f"legrosszabb szélesség {max(widths):.1e} (< 1e-3, R = 100)")

# 2. azonos seed -> azonos eredmény (a fit_all-on keresztül is)
points, _ = generate_points(100, radius=100, noise_level=1, seed=7)
first = kor.fit_all(points, 100, seed=42)
second = kor.fit_all(points, 100, seed=42)
for r1, r2 in zip(first, second):
    check(r1.center == r2.center and r1.width == r2.width
          and r1.evaluations == r2.evaluations,
          f"{r1.method}: azonos seed -> azonos eredmény")

print("\nÖSSZESEN:", "minden rendben" if failures == 0 else f"{failures} hiba")
sys.exit(1 if failures else 0)
