"""
Grafikus felület a Csebisev-körillesztés vizsgálatához.

A generátorból (gui.py, "Vizsgálat indítása" gomb) átvett ponthalmazra
lefut a négy keresőmódszer (hegymászó, szimulált hűtés, genetikus
algoritmus, részecskeraj), mind ugyanazzal a max_iter értékkel és seeddel.
Az ablakban látszik:
  - egy grafikon: a ponthalmaz, a névleges (várt) kör, a kiválasztott
    módszer két koncentrikus köre (r és R sugárral) és az illesztett kör
    ((r + R) / 2 sugárral),
  - egy összehasonlító táblázat: legfelül a névleges (várt) értékek, alatta
    a négy módszer. A legkisebb szélességű módszer sora ki van emelve.
    Egy sorra kattintva annak az eredménye látszik a grafikonon.
A "Futtatás" gombbal ugyanarra a ponthalmazra más iterációszámmal is újra
lefuttathatók a módszerek. Az ablak megnyitásakor egyszer automatikusan
lefutnak.

A névleges (várt) értékek a generálásból jönnek: a névleges kör középpontja
és sugara. A szélesség, r és R ennél a sornál a névleges középpontból mérve
értendő; ez az a gyűrű, amelyet a hibák (alakhiba, zaj, kiugró pontok)
okoznak. Egy jó módszer ennél nem ad nagyobb szélességet, és a középpontja
közel van a névlegeshez.

A számítás a korillesztes.py-ban van; ez a fájl csak a megjelenítés.
Indítás: python3 main.py (a projekt gyökeréből), majd "Vizsgálat indítása".
Függőségek: numpy, matplotlib (pip install -r requirements.txt)
"""

import math
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.patches import Circle

from code_base import korillesztes as kor


# ===========================================================================
# 1. Beállítások (futtatás, színek, a táblázat oszlopai)
# ===========================================================================
SEED = 1                  # minden módszer ezt a seedet kapja: ugyanazzal a
                           # seeddel mindig ugyanaz az eredmény jön ki
DEFAULT_MAX_ITER = 200
BEST_ROW_COLOR = "#d6f0d6"     # a legkisebb szélességű sor háttérszíne
NOMINAL_ROW_COLOR = "#eeeeee"  # a névleges (várt) sor háttérszíne
NOMINAL_COLOR = "#888888"      # a névleges kör színe a grafikonon
NOMINAL_ID = "nominal"         # a névleges sor azonosítója a táblázatban

# a táblázat oszlopai: (kulcs, fejléc, szélesség képpontban)
COLUMNS = [
    ("method", "Módszer", 170),
    ("width", "Szélesség (R − r)", 120),
    ("r", "r", 85),
    ("R", "R", 85),
    ("radius", "Sugár, (r + R) / 2", 120),
    ("a", "Középpont a", 85),
    ("b", "Középpont b", 85),
    ("dev", "Eltérés a névl. középponttól", 175),
    ("time", "Futásidő (s)", 80),
    ("evals", "Célfüggvény-kiértékelések száma", 200),
]


# ===========================================================================
# 2. Segédfüggvények (számformázás, névleges értékek)
# ===========================================================================
def fmt(value):
    """Szám a táblázatba: 6 tizedesjegy, a nagyon kicsi (0-hoz közeli, de
    nem 0) értékek normálalakban."""
    if value != 0 and abs(value) < 1e-3:
        return f"{value:.2e}"
    return f"{value:.6f}"


def nominal_values(points, ground_truth):
    """A névleges (várt) értékek a generálás adataiból.

    Visszaad egy szótárt: a névleges középpont és sugár, valamint a
    névleges középpontból mért gyűrű (r, R, szélesség). Ha nincs generálási
    adat (ground_truth is None), None-t ad vissza."""
    if ground_truth is None:
        return None
    center = (float(ground_truth["center"][0]), float(ground_truth["center"][1]))
    r, big_r, width = kor.ring(points, center)
    return {"center": center, "radius": float(ground_truth["radius"]),
            "r": r, "R": big_r, "width": width}


# ===========================================================================
# 3. A vizsgáló ablak
# ===========================================================================
class VizsgaloApp:
    """A vizsgáló ablak: iterációszám-mező és Futtatás gomb, grafikon és
    összehasonlító táblázat a négy keresőmódszer eredményével."""

    def __init__(self, master, points, ground_truth=None, on_close=None,
                 on_back=None):
        """master: a Tk gyökér vagy egy Toplevel ablak.
        points: a generátortól átvett ponthalmaz ((n, 2) alakú tömb).
        ground_truth: a generálás adatai (a névleges kör és a kiugró pontok
        megjelenítéséhez); None esetén ezek nem látszanak.
        on_close: az ablak bezárásakor hívandó függvény (alapból
        master.destroy).
        on_back: a "Vissza a generátorhoz" gombra hívandó függvény; ha
        None, a gomb nem jelenik meg."""
        self.master = master
        self.points = np.asarray(points, dtype=float)
        self.ground_truth = ground_truth
        self.nominal = nominal_values(self.points, ground_truth)
        self.on_close = on_close or master.destroy
        self.on_back = on_back
        self.results = []
        self._refresh_job = None

        # --- az ablak beállításai ---
        master.title("Csebisev-körillesztés – vizsgálat")
        master.geometry("1240x780")
        master.minsize(1100, 560)
        master.protocol("WM_DELETE_WINDOW", self.close)

        # --- felső sor: Vissza gomb, iterációk száma, Futtatás gomb, üzenet ---
        top = ttk.Frame(master, padding=(10, 8))
        top.pack(fill="x")
        if on_back is not None:
            ttk.Button(top, text="← Vissza a generátorhoz",
                       command=self.back).pack(side="left", padx=(0, 16))
        ttk.Label(top, text="Iterációk száma (max_iter):").pack(side="left")
        self.var_iter = tk.StringVar(value=str(DEFAULT_MAX_ITER))
        entry = ttk.Entry(top, textvariable=self.var_iter, width=8)
        entry.pack(side="left", padx=(4, 8))
        entry.bind("<Return>", lambda _e: self.run())
        self.run_button = ttk.Button(top, text="Futtatás", command=self.run)
        self.run_button.pack(side="left")
        self.var_status = tk.StringVar()
        self.status_label = ttk.Label(top, textvariable=self.var_status)
        self.status_label.pack(side="left", padx=12)

        # --- alul a táblázat (teljes szélességben), fölötte a grafikon ---
        bottom = ttk.Frame(master, padding=(10, 0, 10, 10))
        bottom.pack(side="bottom", fill="x")
        self.figure = Figure(figsize=(8, 5), dpi=100, layout="constrained")
        self.ax = self.figure.add_subplot()
        self.canvas = FigureCanvasTkAgg(self.figure, master=master)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10)

        # --- a táblázat és alatta a magyarázó szöveg ---
        self.tree = ttk.Treeview(bottom, columns=[c[0] for c in COLUMNS],
                                 show="headings", height=5,
                                 selectmode="browse")
        for key, title, width in COLUMNS:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=40,
                             anchor="w" if key == "method" else "e")
        bold = tkfont.nametofont("TkDefaultFont").copy()
        bold.configure(weight="bold")
        italic = tkfont.nametofont("TkDefaultFont").copy()
        italic.configure(slant="italic")
        self.tree.tag_configure("best", background=BEST_ROW_COLOR, font=bold)
        self.tree.tag_configure("nominal", background=NOMINAL_ROW_COLOR,
                                font=italic)
        self.tree.pack(fill="x")
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self.draw())
        ttk.Label(bottom, foreground="#666666", wraplength=1180, justify="left",
                  text="Az első (szürke) sor a névleges, várt érték: a generálás "
                       "középpontja és sugara; a szélesség, r és R ebből a "
                       "középpontból mérve. A zöld sor a legkisebb szélességű "
                       "(legjobb) módszer. Kattints egy sorra: a grafikonon "
                       "annak a körei látszanak."
                  ).pack(fill="x", pady=(6, 0))

        # --- indulás ---
        master.bind("<Configure>", self._on_configure)
        self.run()          # megnyitáskor egyszer automatikusan lefut

    # --- futtatás ---
    def run(self):
        """Beolvassa az iterációk számát, lefuttatja vele a négy módszert
        (seed = SEED), és frissíti a táblázatot meg a grafikont.
        Hibás iterációszámnál piros üzenetet ír ki, és nem fut le."""
        try:
            max_iter = int(self.var_iter.get().strip())
            if max_iter < 1:
                raise ValueError
        except ValueError:
            self._set_status("Az iterációk száma legalább 1 legyen (egész szám).",
                             error=True)
            return
        # a számítás a főszálon fut: közben a gomb le van tiltva (nagyon
        # nagy max_iter esetén az ablak néhány másodpercre megakadhat)
        self.run_button.configure(state="disabled")
        self._set_status("Futtatás…")
        self.master.update_idletasks()
        try:
            self.results = kor.fit_all(self.points, max_iter, SEED)
        finally:
            self.run_button.configure(state="normal")
        self._fill_table()
        self._set_status(f"Kész: {max_iter} iteráció, seed = {SEED}, "
                         f"{len(self.points)} pont.")

    def _set_status(self, text, error=False):
        """Üzenet a Futtatás gomb mellé; hibánál piros betűvel."""
        self.var_status.set(text)
        self.status_label.configure(foreground="red" if error else "")

    # --- táblázat ---
    def _deviation(self, center):
        """A középpont távolsága a névleges középponttól (szövegként a
        táblázatba); ha nincs névleges érték: "–"."""
        if self.nominal is None:
            return "–"
        a0, b0 = self.nominal["center"]
        return fmt(math.hypot(center[0] - a0, center[1] - b0))

    def _fill_table(self):
        """Újratölti a táblázatot: legfelül a névleges (várt) sor, alatta a
        négy módszer. A legkisebb szélességű módszer sorát kiemeli és
        kijelöli, így a grafikonon alapból az látszik."""
        self.tree.delete(*self.tree.get_children())
        if self.nominal is not None:
            nom = self.nominal
            self.tree.insert("", "end", iid=NOMINAL_ID, tags=("nominal",),
                             values=("Névleges (várt)", fmt(nom["width"]),
                                     fmt(nom["r"]), fmt(nom["R"]),
                                     fmt(nom["radius"]), fmt(nom["center"][0]),
                                     fmt(nom["center"][1]), fmt(0.0), "–", "–"))
        best = min(range(len(self.results)), key=lambda i: self.results[i].width)
        for i, res in enumerate(self.results):
            self.tree.insert("", "end", iid=str(i),
                             tags=("best",) if i == best else (),
                             values=(res.method, fmt(res.width), fmt(res.r_inner),
                                     fmt(res.r_outer),
                                     fmt((res.r_inner + res.r_outer) / 2),
                                     fmt(res.center[0]), fmt(res.center[1]),
                                     self._deviation(res.center),
                                     f"{res.time_s:.5f}", res.evaluations))
        self.tree.selection_set(str(best))   # alapból a legjobb látszik

    # --- rajzolás ---
    def draw(self):
        """Kirajzolja a grafikont: a ponthalmazt (kiugró pontok pirossal), a
        névleges kört (szürke, pontozott) és a táblázatban kiválasztott sor
        köreit. Módszer soránál: belső kör (r), külső kör (R), illesztett kör
        ((r + R) / 2) és a középpont; a névleges sornál a névleges
        középpontból mért belső és külső kör."""
        ax = self.ax
        ax.clear()
        ax.set_aspect("equal", adjustable="box")    # a kör körnek látsszon
        ax.grid(True, alpha=0.3)

        # a ponthalmaz (a kiugró pontok pirossal, ha a generátor megadta őket)
        pts = self.points
        outliers = np.zeros(len(pts), dtype=bool)
        if self.ground_truth is not None:
            outliers[self.ground_truth["outliers"]["indices"]] = True
        ax.scatter(pts[~outliers, 0], pts[~outliers, 1], s=10, color="#1f6fd0",
                   label="pontok", zorder=3)
        if outliers.any():
            ax.scatter(pts[outliers, 0], pts[outliers, 1], s=14, color="#d03a1f",
                       label="kiugró pontok", zorder=3)
        xs = [pts[:, 0].min(), pts[:, 0].max()]
        ys = [pts[:, 1].min(), pts[:, 1].max()]

        # a névleges (várt) kör és középpontja mindig látszik
        if self.nominal is not None:
            (a0, b0), rad0 = self.nominal["center"], self.nominal["radius"]
            ax.add_patch(Circle((a0, b0), rad0, fill=False, lw=1.5, ls=":",
                                color=NOMINAL_COLOR, label="névleges (várt) kör"))
            ax.plot(a0, b0, marker="x", ms=9, mew=2, color=NOMINAL_COLOR,
                    ls="none", label="névleges középpont")
            xs += [a0 - rad0, a0 + rad0]
            ys += [b0 - rad0, b0 + rad0]

        # a kiválasztott sor körei
        title = ""
        selection = self.tree.selection()
        if selection:
            if selection[0] == NOMINAL_ID:
                nom = self.nominal
                name, (a, b) = "Névleges (várt)", nom["center"]
                r, big_r, width = nom["r"], nom["R"], nom["width"]
            else:
                res = self.results[int(selection[0])]
                name, (a, b) = res.method, res.center
                r, big_r, width = res.r_inner, res.r_outer, res.width
            ax.add_patch(Circle((a, b), r, fill=False, lw=1.2, color="#2ca02c",
                                label="belső kör (r)"))
            ax.add_patch(Circle((a, b), big_r, fill=False, lw=1.2, color="#ff7f0e",
                                label="külső kör (R)"))
            if selection[0] != NOMINAL_ID:
                ax.add_patch(Circle((a, b), (r + big_r) / 2, fill=False, lw=2,
                                    ls="--", color="#000000",
                                    label="illesztett kör, (r + R) / 2"))
                ax.plot(a, b, marker="+", ms=12, mew=2, color="#000000",
                        ls="none", label="középpont")
            xs += [a - big_r, a + big_r]
            ys += [b - big_r, b + big_r]
            title = f"{name}:  R − r = {fmt(width)}"
            if self.nominal is not None and selection[0] != NOMINAL_ID:
                title += f"   (névleges: {fmt(self.nominal['width'])})"
        ax.set_title(title, fontsize=10)

        # a két tengelyen azonos terjedelem, hogy a pontok és a körök is
        # beférjenek, és az egyenlő méretarány ne ütközzön a határokkal
        half = 0.55 * max(max(xs) - min(xs), max(ys) - min(ys), 1e-9)
        mid_x, mid_y = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
        ax.set_xlim(mid_x - half, mid_x + half)
        ax.set_ylim(mid_y - half, mid_y + half)
        # a jelmagyarázat a grafikon mellett, hogy ne takarja a kör közepét
        ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=8,
                  frameon=False)
        self.canvas.draw_idle()

    # --- ablakkezelés ---
    def _on_configure(self, event):
        """macOS-en (Tk 9) átméretezés után a ttk gombok néha nem rajzolódnak
        újra; az átméretezés végén egy semmit nem változtató configure-hívás
        kikényszeríti az újrarajzolást (lásd gui.py)."""
        if event.widget is not self.master:
            return
        if self._refresh_job is not None:
            self.master.after_cancel(self._refresh_job)
        self._refresh_job = self.master.after(60, self._refresh_widgets)

    def _refresh_widgets(self, widget=None):
        """Az ablak összes ttk elemén végrehajt egy semmit nem változtató
        configure-hívást, hogy újrarajzolódjanak (rekurzívan bejárja az
        elemeket)."""
        self._refresh_job = None
        for child in (widget or self.master).winfo_children():
            if isinstance(child, ttk.Widget):
                child["cursor"] = child["cursor"]
            self._refresh_widgets(child)

    def close(self):
        """Az ablak bezárása: leállítja a függő időzítést, és meghívja az
        on_close függvényt (a main.py-ban ez kilépteti a programot)."""
        if self._refresh_job is not None:
            self.master.after_cancel(self._refresh_job)
        self.on_close()

    def back(self):
        """A "Vissza a generátorhoz" gomb: leállítja a függő időzítést, és
        meghívja az on_back függvényt (a main.py-ban ez bezárja ezt az
        ablakot, és újra megjeleníti a generátort)."""
        if self._refresh_job is not None:
            self.master.after_cancel(self._refresh_job)
        self.on_back()
