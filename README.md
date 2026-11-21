# Ponthalmaz-generátor körillesztéshez (Csebisev-elv)

A projekt célja: ponthalmazra kört illeszteni Csebisev elve szerint (két koncentrikus kör, a sugarak különbsége minimális), keresőmódszerekkel.

> Adott egy ponthalmaz, amelyre regressziós kört kell illeszteni. A ponthalmaz alak-, véletlen- és egyéb hibákat is tartalmaz, valamint lefedhet egy teljes kört vagy annak csak egy ívdarabját.

## Fájlok

- `ponthalmaz_generator.py` – a ponthalmaz generálása (tkinter nélkül, a keresőmódszerek közvetlenül importálhatják)
- `csv_kezeles.py` – a ponthalmaz mentése CSV-be és betöltése CSV-ből (szintén tkinter nélkül)
- `gui.py` – grafikus felület a generátorhoz

## A generálás

1. Egy névleges kör (középpont + sugár R) a kiindulás.
2. **Lefedettség:** teljes kör vagy ívdarab (kezdő- és végszög fokban, a 0°-on át is), a szögek véletlenek vagy egyenletes közűek.
3. **Alakhiba:** nincs / ellipszis (b/a arány; a nagytengely az x tengely mentén) / szabályos sokszög (oldalszám; a csúcsok a névleges körön, az első a 0°-os irányban).
4. **Véletlen hiba:** sugárirányú, egyenletes eloszlású zaj a ±e tartományban (egyetlen paraméter: e; 0 = nincs zaj). A zaj korlátos, így egy pont sem kerül e-nél messzebb a zaj nélküli helyétől.
5. **Egyéb hibák:** kiugró pontok (adott arányuk d..2d távolságra kerül a helyétől), egyenetlen pontsűrűség (a pontok egy része egy szögtartományba sűrűsödik; ez csak a kódból állítható).
6. **Reprodukálhatóság:** seed; ugyanazzal a seeddel mindig pontosan ugyanaz a ponthalmaz jön ki, így a keresőmódszerek ugyanazon a halmazon hasonlíthatók össze, és egy kísérlet megismételhető. Ha nincs megadva, a generátor sorsol egyet, és visszaadja.

A grafikus felületen bármelyik mező módosításakor a ponthalmaz automatikusan újragenerálódik ugyanazzal a seeddel, így csak a módosított paraméter hatása látszik. Az „Új véletlen halmaz” gomb új seedet sorsol.

Minden hiba csak a pont sugárirányú távolságát változtatja, a szögét nem, így a pontok mindig a megadott íven belül maradnak.

## Követelmények

- Python 3.9 vagy újabb (tkinter-rel)
- NumPy

## Telepítés és futtatás

```bash
git clone <a-repo-url-je>
cd <a-repo-mappaja>

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python3 gui.py
```

## Használat a kódból

```python
from ponthalmaz_generator import generate_points
from csv_kezeles import save_csv, load_csv

pontok, ground_truth = generate_points(
    n=200, radius=100, arc=(30, 200),
    shape="ellipse", shape_params={"ratio": 0.9},
    noise_level=1.5,
    outlier_fraction=0.05,
    seed=42)
print(pontok.shape)                  # (200, 2) – minden sor egy (x, y) pont
print(ground_truth["radius"], ground_truth["outliers"]["indices"])

save_csv("halmaz.csv", pontok, ground_truth)
pontok2, gt2 = load_csv("halmaz.csv")    # pontosan ugyanaz a ponthalmaz
```

A `ground_truth` szótár tartalma: névleges középpont és sugár, lefedettség, alakhiba típusa és paraméterei, véletlen hiba mértéke, a kiugró pontok száma és indexei, a sűrítés adatai, a seed. A CSV első sora ezt egy `# ground_truth: {...}` kommentben JSON-ként tárolja, utána `x,y` oszlopok jönnek teljes pontossággal.
