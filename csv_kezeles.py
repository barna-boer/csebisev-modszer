"""
Ponthalmaz mentése CSV-be és betöltése CSV-ből.

A generált ponthalmazt teljes pontossággal menti, hogy betöltés után
pontosan ugyanaz a ponthalmaz jöjjön vissza; így a keresőmódszerek
mindig ugyanazt a ponthalmazt kaphatják, akkor is, ha a generátor később
változik. A generálás adatait (ground truth) is a fájlba írja.

A fájl formátuma:
  # ground_truth: {...JSON...}     (opcionális első sor)
  x,y
  12.345,67.89
  ...

Grafikus kód (tkinter) nélkül, a keresőmódszerek is közvetlenül
importálhatják. Csak a NumPy-t (és a Python alap könyvtárát) használja.
"""

import csv
import json

import numpy as np


GROUND_TRUTH_PREFIX = "# ground_truth: "


def save_csv(path, points, ground_truth=None):
    """Elmenti a pontokat CSV-be (teljes pontossággal, hogy betöltés után
    pontosan ugyanaz a ponthalmaz jöjjön vissza). A ground truth-ot, ha van,
    az első sorba írja egy # kezdetű JSON-kommentként."""
    points = np.asarray(points, dtype=float)
    if points.ndim != 2 or points.shape[1] != 2:
        raise ValueError("A pontok (n, 2) alakú tömbben legyenek.")
    with open(path, "w", newline="", encoding="utf-8") as f:
        if ground_truth is not None:
            f.write(GROUND_TRUTH_PREFIX
                    + json.dumps(ground_truth, ensure_ascii=False) + "\n")
        writer = csv.writer(f)
        writer.writerow(["x", "y"])
        for x, y in points:
            writer.writerow([repr(float(x)), repr(float(y))])


def load_csv(path):
    """Betölti a save_csv-vel mentett (vagy bármilyen x,y oszlopos) CSV-t.
    Visszatérés: (points, ground_truth), ahol ground_truth None, ha a fájlban
    nincs ilyen adat."""
    ground_truth = None
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith(GROUND_TRUTH_PREFIX.strip()):
                try:
                    ground_truth = json.loads(stripped[len(GROUND_TRUTH_PREFIX.strip()):])
                except json.JSONDecodeError:
                    raise ValueError(f"{line_no}. sor: hibás ground truth adat.")
                continue
            if stripped.startswith("#"):
                continue
            cells = next(csv.reader([stripped]))
            if [c.strip().lower() for c in cells] == ["x", "y"]:
                continue
            if len(cells) != 2:
                raise ValueError(f"{line_no}. sor: két oszlop (x, y) kell.")
            try:
                rows.append((float(cells[0]), float(cells[1])))
            except ValueError:
                raise ValueError(f"{line_no}. sor: az x és y számok legyenek.")
    if not rows:
        raise ValueError("A fájlban nincs egyetlen pont sem.")
    return np.array(rows, dtype=float), ground_truth
