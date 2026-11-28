"""
A három keresőmódszer futásának grafikonja.

A korillesztes.py három módszere futás közben minden iteráció után
feljegyzi (result.history), hogy hol tart a keresés:
  - az aktuális állapot szélessége (genetikus algoritmusnál a populáció
    átlagos szélessége),
  - az eddig talált legjobb szélesség.
Ez az ablak lefuttatja a három módszert, és kirajzolja ezeket az adatsorokat.
Mindhárom módszer külön grafikont kap: vízszintesen az iteráció, függőlegesen
a gyűrű szélessége (R − r). A függőleges tengely logaritmikus, mert a
szélesség a futás során több nagyságrendet csökkenhet. A szürke szaggatott
vonal a névleges (várt) szélesség.

Megnyitása: a vizsgáló ablak "Futás grafikonjai" gombjával.
"""

import tkinter as tk
from tkinter import ttk

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from kiertekelo import korillesztes as kor

# ===========================================================================
# Beállítások
# ===========================================================================
SEED = 1                    # ugyanaz a seed, mint a vizsgáló ablakban
CURRENT_COLOR = "#1f6fd0"   # az aktuális állapot vonala (kék)
BEST_COLOR = "#2ca02c"      # az eddigi legjobb vonala (zöld)
NOMINAL_COLOR = "#888888"   # a névleges szélesség vonala (szürke)
SMALLEST = 1e-16            # logaritmikus tengelyen a 0 nem ábrázolható,
                            # ezért ennél kisebb értéket nem rajzolunk


# ===========================================================================
# A futás grafikonjainak ablaka
# ===========================================================================
class RunChartsWindow:
    """Felül az iterációszám és a Futtatás gomb, alatta a három módszer
    grafikonja egymás alatt."""

    # -----------------------------------------------------------------------
    # 1. Az ablak felépítése
    # -----------------------------------------------------------------------
    def __init__(self, window, points, generation_info, max_iter):
        """window: az ablak, amelybe a felület kerül.
        points: a ponthalmaz ((n, 2) alakú numpy tömb).
        generation_info: a generálás adatai (a névleges középponthoz).
        max_iter: az iterációk száma az ablak megnyitásakor."""
        self.window = window
        self.points = np.array(points, dtype=float)

        # a névleges (várt) szélesség: a névleges középpontból mért gyűrű
        center_a, center_b = generation_info["center"]
        self.nominal_width = kor.ring_width(self.points, center_a, center_b)

        window.title("Keresőmódszerek futása")
        window.geometry("1000x860")

        # --- felső sor: iterációszám, Futtatás gomb, üzenet ---
        top = ttk.Frame(window, padding=(10, 8))
        top.pack(fill="x")
        ttk.Label(top, text="Iterációk száma (max_iter):").pack(side="left")
        self.var_max_iter = tk.StringVar(value=str(max_iter))
        entry = ttk.Entry(top, textvariable=self.var_max_iter, width=8)
        entry.pack(side="left", padx=(4, 8))
        entry.bind("<Return>", self.on_enter)               # Enterre is fut
        ttk.Button(top, text="Futtatás", command=self.run).pack(side="left")
        self.var_status = tk.StringVar()
        self.status_label = ttk.Label(top, textvariable=self.var_status)
        self.status_label.pack(side="left", padx=12)

        # --- alul a magyarázat ---
        help_text = ("Kék: az aktuális állapot szélessége (genetikus algoritmusnál a "
                     "populáció átlaga). Zöld: az eddig talált legjobb szélesség. Szürke "
                     "szaggatott: a névleges (várt) szélesség. A függőleges tengely "
                     "logaritmikus.")
        ttk.Label(window, text=help_text, foreground="#666666", wraplength=960,
                  padding=(10, 0, 10, 10)).pack(side="bottom", fill="x")

        # --- középen a három grafikon egymás alatt ---
        self.figure = Figure(figsize=(9, 8), dpi=100, layout="constrained")
        self.axes = []
        for i in range(3):
            self.axes.append(self.figure.add_subplot(3, 1, i + 1))
        self.canvas = FigureCanvasTkAgg(self.figure, master=window)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10)

        # --- megnyitáskor egyszer automatikusan lefut ---
        self.run()

    # -----------------------------------------------------------------------
    # 2. A három módszer futtatása
    # -----------------------------------------------------------------------
    def run(self):
        """Beolvassa az iterációk számát, lefuttatja a három módszert, és
        kirajzolja a futásukat. Hibás iterációszámnál piros üzenetet ír ki."""
        try:
            max_iter = int(self.var_max_iter.get().strip())
        except ValueError:
            max_iter = 0
        if max_iter < 1:
            self.show_status("Az iterációk száma legalább 1 legyen (egész szám).", True)
            return

        self.show_status("Futtatás…", False)
        self.window.update_idletasks()          # az üzenet jelenjen meg a futás előtt
        results = kor.fit_all(self.points, max_iter, SEED)
        self.draw_charts(results)
        self.show_status(f"Kész: {max_iter} iteráció, seed = {SEED}, "
                         f"{len(self.points)} pont.", False)

    def on_enter(self, event):
        """Enter az iterációszám mezőben: ugyanaz, mint a Futtatás gomb."""
        self.run()

    def show_status(self, text, is_error):
        """Üzenet a Futtatás gomb mellett; hibánál piros betűvel."""
        self.var_status.set(text)
        if is_error:
            self.status_label.configure(foreground="red")
        else:
            self.status_label.configure(foreground="")

    # -----------------------------------------------------------------------
    # 3. A grafikonok kirajzolása
    # -----------------------------------------------------------------------
    def draw_charts(self, results):
        """Minden módszerhez egy grafikon: iterációnként az aktuális és az
        eddigi legjobb szélesség, valamint a névleges szélesség."""
        nominal = max(self.nominal_width, SMALLEST)

        for i in range(len(results)):
            result = results[i]
            ax = self.axes[i]
            ax.clear()
            ax.set_yscale("log")
            ax.grid(True, which="both", alpha=0.3)

            # a history (aktuális, legjobb) párjait két listába szedjük szét;
            # a 0-hoz túl közeli értékeket SMALLEST-re cseréljük (log skála)
            current_values = []
            best_values = []
            for current, best in result.history:
                current_values.append(max(current, SMALLEST))
                best_values.append(max(best, SMALLEST))
            iterations = range(len(current_values))   # 0 = a kezdőállapot

            if result.method_name == "Genetikus algoritmus":
                current_label = "aktuális (a populáció átlaga)"
            else:
                current_label = "aktuális állapot"
            # a vékony kék vonal a vastag zöld fölött van (zorder),
            # hogy akkor is látsszon, amikor az aktuális állapot épp a legjobb
            ax.plot(iterations, current_values, color=CURRENT_COLOR, lw=1,
                    label=current_label, zorder=3)
            ax.plot(iterations, best_values, color=BEST_COLOR, lw=2.5,
                    label="eddigi legjobb", zorder=2)
            ax.axhline(nominal, color=NOMINAL_COLOR, ls="--", lw=1, label="névleges (várt)")

            # a függőleges tengely: a legkisebb érték felétől a legnagyobb kétszereséig
            ax.set_xlim(0, len(current_values) - 1)
            ax.set_ylim(min(min(best_values), nominal) / 2, max(max(current_values), nominal) * 2)

            ax.set_title(f"{result.method_name}   –   {len(current_values) - 1} iteráció után:   "
                         f"aktuális = {current_values[-1]:.3e},   legjobb = {best_values[-1]:.3e}",
                         fontsize=10)
            ax.set_ylabel("szélesség (R − r)")
            ax.legend(loc="upper right", fontsize=8)

        self.axes[-1].set_xlabel("iteráció")   # csak a legalsó grafikon alatt
        self.canvas.draw_idle()
