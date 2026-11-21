# Ponthalmaz-generátor körillesztéshez (Csebisev-elv)

Egyszerű Python program, amely egy ablakban megjeleníti egy körgyűrű (sáv) alakú területen generált véletlen pontokat. A generáló függvény független a grafikus felülettől, így később keresőmódszerek (pl. Csebisev-körillesztés) is használhatják.

## Funkciók

- a pontok számának megadása
- a sáv belső és külső sugarának megadása (a sáv a kijelző közepe körül van)
- opcionális seed: ugyanazzal a seeddel mindig ugyanaz a ponthalmaz jön ki
- az ablak átméretezhető, a rajz vele skálázódik

Mivel minden pont az `r_inner .. r_outer` gyűrűben van, az optimális Csebisev-gyűrű szélessége legfeljebb `r_outer - r_inner` lehet.

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

python ponthalmaz_generator.py
```

## Használat a kódból

```python
from ponthalmaz_generator import generate_points

pontok = generate_points(n=50, r_inner=150, r_outer=170, seed=42)
print(pontok.shape)  # (50, 2) – minden sor egy (x, y) pont
```
