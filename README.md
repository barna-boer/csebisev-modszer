# Körillesztés Csebisev elve szerint, keresőmódszerekkel

A projekt célja: ponthalmazra kört illeszteni Csebisev elve szerint (két koncentrikus kör, a sugarak különbsége minimális), keresőmódszerekkel.

> Adott egy ponthalmaz, amelyre regressziós kört kell illeszteni. A ponthalmaz alak-, véletlen- és egyéb hibákat is tartalmaz, valamint lefedhet egy teljes kört vagy annak csak egy ívdarabját.

## Fájlok

| Fájl | Tartalom |
|---|---|
| `ponthalmaz_generator.py` | a ponthalmaz generálása (tkinter nélkül) |
| `gui.py` | grafikus felület a generátorhoz, a „Vizsgálat indítása” gombbal |
| `korillesztes.py` | a körillesztés: célfüggvény és a négy keresőmódszer (tkinter és matplotlib nélkül) |
| `vizsgalo_gui.py` | a vizsgáló ablak: grafikon és összehasonlító táblázat |
| `teszt_korillesztes.py` | rövid, nem grafikus ellenőrző szkript |

## Követelmények

- Python 3.9 vagy újabb (tkinter-rel)
- NumPy, matplotlib

## Telepítés és futtatás

```bash
git clone <a-repo-url-je>
cd <a-repo-mappaja>

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python3 gui.py                   # generátor -> "Vizsgálat indítása"
python3 teszt_korillesztes.py    # ellenőrzés
```

## A generálás (gui.py)

1. Egy névleges kör (középpont + sugár R) a kiindulás.
2. **Lefedettség:** teljes kör vagy ívdarab (kezdő- és végszög fokban, a 0°-on át is), a szögek véletlenek vagy egyenletes közűek.
3. **Alakhiba:** nincs / ellipszis (b/a arány; a nagytengely az x tengely mentén) / szabályos sokszög (oldalszám; a csúcsok a névleges körön, az első a 0°-os irányban).
4. **Véletlen hiba:** sugárirányú, egyenletes eloszlású zaj a ±e tartományban (egyetlen paraméter: e; 0 = nincs zaj).
5. **Egyéb hibák:** kiugró pontok (adott arányuk d..2d távolságra kerül a helyétől), egyenetlen pontsűrűség (csak a kódból állítható).
6. **Reprodukálhatóság:** seed; ugyanazzal a seeddel mindig pontosan ugyanaz a ponthalmaz jön ki.

Bármelyik mező módosításakor a ponthalmaz automatikusan újragenerálódik ugyanazzal a seeddel; az „Új véletlen halmaz” gomb új seedet sorsol. Minden hiba csak a pont sugárirányú távolságát változtatja, a szögét nem, így a pontok mindig a megadott íven belül maradnak.

A **„Vizsgálat indítása”** gomb bezárja (elrejti) a generátorablakot, és megnyitja a vizsgáló ablakot, átadva neki a ponthalmazt és a generálás adatait.

## A körillesztés (korillesztes.py)

**Célfüggvény:** egy (a, b) középpontra r a pontok legkisebb, R a legnagyobb távolsága a középponttól; a minimalizálandó hiba a gyűrű szélessége, R − r.

**A négy keresőmódszer** (felületük: `f(points, max_iter, seed, bounds=None) -> FitResult`):

| Módszer | Egy iteráció | Kiértékelés / iteráció |
|---|---|---|
| Hegymászó véletlen újraindítással | egy lépés a 8 szomszéd legjobbjára | 8 |
| Szimulált hűtés | egy jelölt kipróbálása | 1 |
| Genetikus algoritmus (valós kódolás) | egy generáció | 40 |
| Részecskeraj-optimalizálás (PSO) | a raj egy lépése | 30 |

Mivel egy iteráció módszerenként más munka, a táblázat a célfüggvény-kiértékelések számát is mutatja. A `fit_all(points, max_iter, seed)` mind a négy módszert lefuttatja ugyanarra a ponthalmazra, ugyanazzal a max_iter értékkel és seeddel. A keresési tartomány a ponthalmaz befoglaló téglalapjának közepe körüli négyzet, amelynek oldala a hosszabbik oldal kétszerese.

## A vizsgáló ablak (vizsgalo_gui.py)

- Megnyitáskor a négy módszer egyszer automatikusan lefut (max_iter = 200, seed = 1).
- **Iterációk száma** mező és **Futtatás** gomb: ugyanarra a ponthalmazra más iterációszámmal újra lefuttathatók.
- **Grafikon:** a ponthalmaz (a kiugró pontok pirossal), a kiválasztott módszer két koncentrikus köre (r és R sugárral) és az illesztett kör ((r + R) / 2 sugárral, ugyanazzal a középponttal).
- **Táblázat:** Módszer, Szélesség (R − r), r, R, Középpont a, Középpont b, Futásidő (s), Célfüggvény-kiértékelések száma. A legkisebb szélességű sor ki van emelve; egy sorra kattintva annak a módszernek az eredménye látszik a grafikonon.

## Használat a kódból

```python
from ponthalmaz_generator import generate_points
import korillesztes as kor

pontok, ground_truth = generate_points(
    n=200, radius=100, arc=(30, 200),
    shape="ellipse", shape_params={"ratio": 0.9},
    noise_level=1.5, outlier_fraction=0.05, seed=42)

for eredmeny in kor.fit_all(pontok, max_iter=200, seed=1):
    print(eredmeny.method, eredmeny.width, eredmeny.center,
          eredmeny.evaluations, eredmeny.time_s)
```
