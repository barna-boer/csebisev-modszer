"""
A három keresőmódszer futásának grafikonja.

A korillesztes.py három módszerét lefuttatja ugyanarra a ponthalmazra.
Futás közben a módszerek minden iteráció után feljegyzik (history), hogy
éppen hol tart a keresés:
  - az aktuális állapot szélessége: hegymászónál és szimulált hűtésnél az
    éppen vizsgált s állapoté, genetikus algoritmusnál a populáció átlaga,
  - az eddigi legjobb szélesség.
Az iterációk végigfutása után ezt az eltárolt adatsort rajzolja ki.
Mindhárom módszer külön grafikont kap (vízszintesen az iteráció, függőlegesen
a gyűrű szélessége, R − r). A függőleges tengely logaritmikus, mert a
szélesség a futás során több nagyságrendet csökkenhet. A szürke szaggatott
vonal a névleges (várt) szélesség.

A "Futtatás" gomb más iterációszámmal újra lefuttatja és kirajzolja.

Indítás:
  - a vizsgáló ablak "Futás grafikonjai" gombjával (a vizsgált ponthalmazzal),
  - vagy önállóan, egy minta ponthalmazzal (a projekt gyökeréből):
        python3 code_base/futas_grafikon.py
"""

import os
import sys
import tkinter as tk
from tkinter import ttk

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# önálló indításnál a projekt mappáját (a code_base szülőjét) felvesszük a
# Python keresési útvonalára, hogy a code_base fájljai importálhatók legyenek
project_folder = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_folder not in sys.path:
    sys.path.insert(0, project_folder)

from code_base import korillesztes as kor
from code_base.ponthalmaz_generator import generate_points

# ===========================================================================
#region Beállítások és segédfüggvények
# ===========================================================================
SEED = 1                  # minden módszer ezt a seedet kapja (mint a
                          # vizsgáló ablakban), így ugyanaz az eredmény jön ki
DEFAULT_MAX_ITER = 200    # az iterációk száma önálló indításkor

CURRENT_COLOR = "#1f6fd0"   # az aktuális állapot vonala (kék)
BEST_COLOR = "#2ca02c"      # az eddigi legjobb vonala (zöld)
NOMINAL_COLOR = "#888888"   # a névleges (várt) szélesség vonala (szürke)

SMALLEST = 1e-16          # logaritmikus skálán a 0 nem ábrázolható, ezért
                          # ennél kisebb értéket nem rajzolunk

def fmt(value):
    """Szám a grafikon címébe: 6 tizedesjegy; a nagyon kicsi (0-hoz közeli,
    de nem 0) értékek normálalakban, pl. 1.23e-05."""

    if value != 0 and abs(value) < 0.001:
        return f"{value:.2e}"
    return f"{value:.6f}"

def positive(value):
    """A logaritmikus tengelyhez: a 0-t (és a nagyon kicsi értékeket)
    SMALLEST-re cseréli."""

    return max(value, SMALLEST)
#endregion

# ===========================================================================
#region A futás grafikonjainak ablaka
# ===========================================================================
class FutasGrafikonApp:
    """A futás grafikonjainak ablaka.

    Felül az iterációszám-mező és a Futtatás gomb, alatta egymás alatt a
    három módszer grafikonja (aktuális állapot és eddigi legjobb).

    Az osztály részei:
      1. GUI felépítése
      2. a három módszer futtatása és az adatok eltárolása
      3. a grafikonok kirajzolása"""

    # -----------------------------------------------------------------------
    #region 1. A GUI felépítése
    # -----------------------------------------------------------------------
    def __init__(self, window, points, ground_truth=None,
                 max_iter=DEFAULT_MAX_ITER):
        """window: az ablak, amelybe a felület kerül.
        points: a ponthalmaz ((n, 2) alakú tömb).
        ground_truth: a generálás adatai; ha megvan, a névleges (várt)
        szélesség is látszik a grafikonokon (None = nem látszik).
        max_iter: az iterációk száma az ablak megnyitásakor."""
        self.window = window
        self.points = np.array(points, dtype=float)

        # az eltárolt futási adatok (a run tölti fel, módszerenként egy elem)
        self.names = []             # a módszerek neve
        self.current_values = []    # iterációnként az aktuális szélesség
        self.best_values = []       # iterációnként az eddigi legjobb

        # --- a névleges (várt) szélesség: a névleges középpontból mérve ---
        if ground_truth is not None:
            center = ground_truth["center"]
            r, big_r, width = kor.ring(self.points, (center[0], center[1]))
            self.nominal_width = width
        else:
            self.nominal_width = None

        # --- az ablak beállításai ---
        window.title("Keresőmódszerek futása")
        window.geometry("1000x860")
        window.minsize(700, 600)

        # --- felső sor: iterációk száma, Futtatás gomb, üzenet ---
        top = ttk.Frame(window, padding=(10, 8))
        top.pack(fill="x")
        ttk.Label(top, text="Iterációk száma (max_iter):").pack(side="left")
        self.var_iter = tk.StringVar(value=str(max_iter))
        entry = ttk.Entry(top, textvariable=self.var_iter, width=8)
        entry.pack(side="left", padx=(4, 8))
        entry.bind("<Return>", self.on_enter)     # Enterre is fut
        run_button = ttk.Button(top, text="Futtatás", command=self.run)
        run_button.pack(side="left")
        self.var_status = tk.StringVar()
        self.status_label = ttk.Label(top, textvariable=self.var_status)
        self.status_label.pack(side="left", padx=12)

        # --- magyarázat alul ---
        help_text = ("Kék: az aktuális állapot szélessége (genetikus "
                     "algoritmusnál a populáció átlaga). Zöld: az eddig "
                     "talált legjobb szélesség. Szürke szaggatott: a névleges "
                     "(várt) szélesség. A függőleges tengely logaritmikus.")
        help_label = ttk.Label(window, text=help_text, foreground="#666666",
                               wraplength=960, justify="left",
                               padding=(10, 0, 10, 10))
        help_label.pack(side="bottom", fill="x")

        # --- a három grafikon egymás alatt ---
        self.figure = Figure(figsize=(9, 8), dpi=100, layout="constrained")
        self.axes = []
        for i in range(len(kor.SEARCH_METHODS)):
            self.axes.append(self.figure.add_subplot(len(kor.SEARCH_METHODS),
                                                     1, i + 1))
        self.canvas = FigureCanvasTkAgg(self.figure, master=window)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10)

        # --- első futtatás: megnyitáskor egyszer automatikusan lefut ---
        self.run()
    #endregion

    # -----------------------------------------------------------------------
    #region 2. A három módszer futtatása és az adatok eltárolása
    # -----------------------------------------------------------------------
    def run(self):
        """Beolvassa az iterációk számát, lefuttatja vele a három módszert
        (seed = SEED), eltárolja a futásuk adatait, majd kirajzolja őket.
        Hibás iterációszámnál piros üzenetet ír ki, és nem fut le."""

        # --- Iterációszám beolvasása ---
        try:
            max_iter = int(self.var_iter.get().strip())
        except ValueError:
            max_iter = 0
        if max_iter < 1:
            self.show_status("Az iterációk száma legalább 1 legyen (egész szám).",
                             True)
            return

        # --- Futtatás: a módszerek a history listába írják a futás adatait ---
        self.show_status("Futtatás…", False)
        self.window.update_idletasks()
        bounds = kor.default_bounds(self.points)   # mindháromnak ugyanaz
        self.names = []
        self.current_values = []
        self.best_values = []
        for method in kor.SEARCH_METHODS:
            history = []
            result = method(self.points, max_iter, SEED, bounds, history)

            # --- Eltárolás: az (aktuális, legjobb) párokat két listába ---
            current = []
            best = []
            for current_f, best_f in history:
                current.append(positive(current_f))
                best.append(positive(best_f))
            self.names.append(result.method)
            self.current_values.append(current)
            self.best_values.append(best)

        # --- Ábrázolás: a teljes futás egyszerre ---
        self.draw_charts()
        self.show_status(f"Kész: {max_iter} iteráció, seed = {SEED}, "
                         f"{len(self.points)} pont.", False)

    def on_enter(self, event):
        """Enter a mezőben: ugyanaz, mint a Futtatás gomb."""

        self.run()

    def show_status(self, text, is_error):
        """Üzenet a Futtatás gomb mellé; hibánál piros betűvel."""

        self.var_status.set(text)
        if is_error:
            self.status_label.configure(foreground="red")
        else:
            self.status_label.configure(foreground="")
    #endregion

    # -----------------------------------------------------------------------
    #region 3. A grafikonok kirajzolása
    # -----------------------------------------------------------------------
    def draw_charts(self):
        """Kirajzolja a három módszer eltárolt futását: iterációnként az
        aktuális és az eddigi legjobb szélességet, valamint a névleges
        (várt) szélességet. A címben a futás végén elért értékek."""

        for i in range(len(self.axes)):
            ax = self.axes[i]
            ax.clear()
            ax.set_yscale("log")
            ax.grid(True, which="both", alpha=0.3)

            current = self.current_values[i]
            best = self.best_values[i]
            last = len(current) - 1        # = max_iter (a 0. a kezdőállapot)
            x_values = list(range(last + 1))

            # --- Aktuális állapot és eddigi legjobb ---
            if self.names[i] == "Genetikus algoritmus":
                current_label = "aktuális (a populáció átlaga)"
            else:
                current_label = "aktuális állapot"
            # a vékony kék vonal a vastag zöld fölött van (zorder), hogy akkor
            # is látsszon, amikor az aktuális állapot épp a legjobb
            ax.plot(x_values, current, color=CURRENT_COLOR, lw=1,
                    label=current_label, zorder=3)
            ax.plot(x_values, best, color=BEST_COLOR, lw=2.5,
                    label="eddigi legjobb", zorder=2)

            # --- Névleges (várt) szélesség ---
            if self.nominal_width is not None:
                ax.axhline(positive(self.nominal_width), color=NOMINAL_COLOR,
                           ls="--", lw=1, label="névleges (várt)")

            # --- Tengelyek határai: a legkisebb érték fele és a legnagyobb
            #     kétszerese között (így a log skálán is van elég felirat) ---
            smallest = min(best)
            largest = max(current)
            if self.nominal_width is not None:
                smallest = min(smallest, positive(self.nominal_width))
                largest = max(largest, positive(self.nominal_width))
            ax.set_xlim(0, last)
            ax.set_ylim(smallest / 2, largest * 2)

            # --- Feliratok ---
            title = (f"{self.names[i]}   –   {last} iteráció után:   "
                     f"aktuális = {fmt(current[last])},   "
                     f"legjobb = {fmt(best[last])}")
            ax.set_title(title, fontsize=10)
            ax.set_ylabel("szélesség (R − r)")
            ax.legend(loc="upper right", fontsize=8)

        # vízszintes tengely felirata csak a legalsó grafikonon
        self.axes[-1].set_xlabel("iteráció")
        self.canvas.draw_idle()
    #endregion
#endregion

# ===========================================================================
#region Önálló indítás (egy minta ponthalmazzal)
# ===========================================================================
if __name__ == "__main__":
    sample_points, sample_ground_truth = generate_points(
        100, radius=100, arc=(30, 200), shape="ellipse",
        shape_params={"ratio": 0.95}, noise_level=1, outlier_fraction=0.05,
        seed=42)
    root = tk.Tk()
    FutasGrafikonApp(root, sample_points, sample_ground_truth)
    root.mainloop()
#endregion
