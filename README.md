# Körillesztés Csebisev elve szerint, keresőmódszerekkel

A projekt célja: ponthalmazra kört illeszteni Csebisev elve szerint (két koncentrikus kör, a sugarak különbsége minimális), keresőmódszerekkel.

> Adott egy ponthalmaz, amelyre regressziós kört kell illeszteni. A ponthalmaz alak-, véletlen- és egyéb hibákat is tartalmaz, valamint lefedhet egy teljes kört vagy annak csak egy ívdarabját.

## Fájlok

| Fájl | Tartalom |
|---|---|
| `main.py` | a program indítója: megnyitja a generátort, és összeköti a két ablakot |
| `code_base/ponthalmaz_generator.py` | a ponthalmaz generálása (tkinter nélkül) |
| `code_base/gui.py` | a generátor ablaka, a „Vizsgálat indítása” gombbal |
| `code_base/korillesztes.py` | a körillesztés: célfüggvény és a négy keresőmódszer (tkinter és matplotlib nélkül) |
| `code_base/vizsgalo_gui.py` | a vizsgáló ablak: grafikon és összehasonlító táblázat |
| `tests/teszt_korillesztes.py` | rövid, nem grafikus ellenőrző szkript |

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

python3 main.py                        # generátor -> "Vizsgálat indítása"
python3 tests/teszt_korillesztes.py    # ellenőrzés
```

A parancsokat a projekt gyökeréből kell kiadni (ott van a `main.py`).

## A generálás (gui.py)

1. Egy névleges kör (középpont + sugár R) a kiindulás.
2. **Lefedettség:** teljes kör vagy ívdarab (kezdő- és végszög fokban, a 0°-on át is), a szögek véletlenek vagy egyenletes közűek.
3. **Alakhiba:** nincs / ellipszis (b/a arány; a nagytengely az x tengely mentén) / szabályos sokszög (oldalszám; a csúcsok a névleges körön, az első a 0°-os irányban).
4. **Véletlen hiba:** sugárirányú, egyenletes eloszlású zaj a ±e tartományban (egyetlen paraméter: e; 0 = nincs zaj).
5. **Egyéb hibák:** kiugró pontok (adott arányuk d..2d távolságra kerül a helyétől), egyenetlen pontsűrűség (csak a kódból állítható).
6. **Reprodukálhatóság:** seed; ugyanazzal a seeddel mindig pontosan ugyanaz a ponthalmaz jön ki.

Bármelyik mező módosításakor a ponthalmaz automatikusan újragenerálódik ugyanazzal a seeddel; az „Új véletlen halmaz” gomb új seedet sorsol. Minden hiba csak a pont sugárirányú távolságát változtatja, a szögét nem, így a pontok mindig a megadott íven belül maradnak.

A **„Vizsgálat indítása”** gomb bezárja (elrejti) a generátorablakot, és megnyitja a vizsgáló ablakot, átadva neki a ponthalmazt és a generálás adatait. A vizsgáló ablak **„← Vissza a generátorhoz”** gombja bezárja a vizsgáló ablakot, és újra megjeleníti a generátort a beállított mezőkkel és ponthalmazzal, így módosítás után új vizsgálat indítható. A két ablakot a `main.py` köti össze; a vizsgáló ablak bezárásakor (X) a program kilép.

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
- **Grafikon:** a ponthalmaz (a kiugró pontok pirossal), a névleges (várt) kör és középpont szürkével, a kiválasztott módszer két koncentrikus köre (r és R sugárral) és az illesztett kör ((r + R) / 2 sugárral, ugyanazzal a középponttal).
- **Táblázat:** Módszer, Szélesség (R − r), r, R, Sugár (r + R) / 2, Középpont a, Középpont b, Eltérés a névleges középponttól, Futásidő (s), Célfüggvény-kiértékelések száma. A legkisebb szélességű módszer sora ki van emelve; egy sorra kattintva annak az eredménye látszik a grafikonon.
- **Névleges (várt) sor** (a táblázat első, szürke sora): a generálás középpontja és sugara. A szélesség, r és R ennél a sornál a névleges középpontból mérve értendő, vagyis ekkora gyűrűt okoznak a generált hibák (pl. 0,9-es ellipszisnél kb. a két féltengely különbsége, ±e zajnál kb. 2e). Egy jó módszer ennél nem ad nagyobb szélességet. A kiugró pontok viszont a Csebisev-illesztést elhúzhatják a névleges középponttól.

## Használat a kódból

A projekt gyökeréből futtatva:

```python
from code_base.ponthalmaz_generator import generate_points
from code_base import korillesztes as kor

pontok, ground_truth = generate_points(
    n=200, radius=100, arc=(30, 200),
    shape="ellipse", shape_params={"ratio": 0.9},
    noise_level=1.5, outlier_fraction=0.05, seed=42)

for eredmeny in kor.fit_all(pontok, max_iter=200, seed=1):
    print(eredmeny.method, eredmeny.width, eredmeny.center,
          eredmeny.evaluations, eredmeny.time_s)
```
