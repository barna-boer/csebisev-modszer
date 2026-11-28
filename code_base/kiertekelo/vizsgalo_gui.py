"""
A vizsgáló ablak: a Csebisev-körillesztés eredményei.

A generátorból ("Vizsgálat indítása" gomb) kapott ponthalmazra lefut a három
keresőmódszer (hegymászó, szimulált hűtés, genetikus algoritmus), mind
ugyanazzal az iterációszámmal és seeddel. Az ablakban látszik:
  - egy grafikon: a ponthalmaz, a névleges (várt) kör, és a táblázatban
    kiválasztott módszer két koncentrikus köre (r és R sugárral), valamint az
    illesztett kör ((r + R) / 2 sugárral),
  - egy táblázat: legfelül a névleges (várt) értékek, alatta a három módszer.
    A legkisebb szélességű módszer sora zöld. Egy sorra kattintva annak az
    eredménye látszik a grafikonon.

A "Futtatás" gombbal más iterációszámmal is újra lefuttathatók a módszerek.
A "Futás grafikonjai" gomb külön ablakban megmutatja, hogyan haladt a három
módszer iterációról iterációra (futas_grafikon.py).

A névleges sor a generálás középpontjából és sugarából jön. A szélesség, r és
R ennél a sornál a névleges középpontból mérve értendő: ekkora gyűrűt okoznak
a hibák (alakhiba, zaj, kiugró pontok). Egy jó módszer ennél nem ad nagyobb
szélességet.

A számítás a korillesztes.py-ban van, ez a fájl csak a megjelenítés.
"""

import math
import tkinter as tk
from tkinter import ttk

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.patches import Circle

from generator.generator_gui import refresh_widgets
from kiertekelo import korillesztes as kor
from kiertekelo.futas_grafikon import RunChartsWindow

# ===========================================================================
# Beállítások
# ===========================================================================
SEED = 1                  # minden módszer ezt a seedet kapja
DEFAULT_MAX_ITER = 50     # az iterációk száma az ablak megnyitásakor

BEST_ROW_COLOR = "#d6f0d6"       # a legjobb módszer sorának háttere (zöld)
NOMINAL_ROW_COLOR = "#eeeeee"    # a névleges sor háttere (szürke)
NOMINAL_COLOR = "#888888"        # a névleges kör színe a grafikonon

# a táblázat oszlopai: (azonosító, fejléc, szélesség képpontban)
COLUMNS = [
    ("method", "Módszer", 170),
    ("width", "Szélesség (R − r)", 120),
    ("r", "r", 85),
    ("R", "R", 85),
    ("radius", "Sugár, (r + R) / 2", 120),
    ("a", "Középpont a", 85),
    ("b", "Középpont b", 85),
    ("deviation", "Eltérés a névl. középponttól", 175),
    ("time", "Futásidő (s)", 80),
    ("evaluations", "Célfüggvény-kiértékelések száma", 200),
]


def format_number(value):
    """Szám a táblázatba: 6 tizedesjegy; a nagyon kicsi (de nem 0) értékek
    normálalakban, pl. 1.23e-05."""
    if value != 0 and abs(value) < 0.001:
        return f"{value:.2e}"
    return f"{value:.6f}"


# ===========================================================================
# A vizsgáló ablak
# ===========================================================================
class AnalysisWindow:
    """A vizsgáló ablak: felül a gombok és az iterációszám, középen a
    grafikon, alul az összehasonlító táblázat."""

    # -----------------------------------------------------------------------
    # 1. Az ablak felépítése
    # -----------------------------------------------------------------------
    def __init__(self, window, points, generation_info, on_close, on_back):
        """window: az ablak, amelybe a felület kerül.
        points: a generátortól kapott ponthalmaz ((n, 2) alakú numpy tömb).
        generation_info: a generálás adatai (névleges kör, kiugró pontok).
        on_close: az ablak bezárásakor (X) ezt hívjuk meg (lásd _main.py).
        on_back: a "Vissza a generátorhoz" gomb ezt hívja meg (lásd _main.py)."""
        self.window = window
        self.points = np.array(points, dtype=float)
        self.generation_info = generation_info
        self.on_close = on_close
        self.on_back = on_back
        self.results = []            # a három módszer eredménye (FitResult-ok)
        self.resize_job = None       # az átméretezés utáni frissítés időzítője

        # a névleges (várt) értékek: a generálás középpontja és sugara,
        # valamint a névleges középpontból mért gyűrű
        self.nominal_a, self.nominal_b = generation_info["center"]
        self.nominal_radius = generation_info["radius"]
        self.nominal_r, self.nominal_R = kor.ring_radii(self.points, self.nominal_a, self.nominal_b)
        self.nominal_width = self.nominal_R - self.nominal_r

        window.title("Csebisev-körillesztés – vizsgálat")
        window.geometry("1240x780")
        window.protocol("WM_DELETE_WINDOW", self.close)   # az ablak X gombja

        # --- felső sor: gombok, iterációszám, üzenet ---
        top = ttk.Frame(window, padding=(10, 8))
        top.pack(fill="x")
        ttk.Button(top, text="← Vissza a generátorhoz",
                   command=self.back).pack(side="left", padx=(0, 16))
        ttk.Label(top, text="Iterációk száma (max_iter):").pack(side="left")
        self.var_max_iter = tk.StringVar(value=str(DEFAULT_MAX_ITER))
        entry = ttk.Entry(top, textvariable=self.var_max_iter, width=8)
        entry.pack(side="left", padx=(4, 8))
        entry.bind("<Return>", self.on_enter)               # Enterre is fut
        ttk.Button(top, text="Futtatás", command=self.run).pack(side="left")
        ttk.Button(top, text="Futás grafikonjai",
                   command=self.open_run_charts).pack(side="left", padx=(8, 0))
        self.var_status = tk.StringVar()
        self.status_label = ttk.Label(top, textvariable=self.var_status)
        self.status_label.pack(side="left", padx=12)

        # --- alul a táblázat és a magyarázat ---
        bottom = ttk.Frame(window, padding=(10, 0, 10, 10))
        bottom.pack(side="bottom", fill="x")
        column_ids = [column[0] for column in COLUMNS]
        self.table = ttk.Treeview(bottom, columns=column_ids, show="headings",
                                  height=4, selectmode="browse")
        for column_id, header, width in COLUMNS:
            self.table.heading(column_id, text=header)
            self.table.column(column_id, width=width, anchor="e")
        self.table.column("method", anchor="w")      # a módszer neve balra igazítva
        # a kiemelt sorok színei (a betű fekete, hogy sötét módban is olvasható legyen)
        self.table.tag_configure("best", background=BEST_ROW_COLOR, foreground="black")
        self.table.tag_configure("nominal", background=NOMINAL_ROW_COLOR, foreground="black")
        self.table.pack(fill="x")
        self.table.bind("<<TreeviewSelect>>", self.on_row_selected)

        # --- középen a grafikon (matplotlib) ---
        self.figure = Figure(figsize=(8, 5), dpi=100, layout="constrained")
        self.ax = self.figure.add_subplot()
        self.canvas = FigureCanvasTkAgg(self.figure, master=window)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10)

        window.bind("<Configure>", self.on_resize)

        # --- megnyitáskor egyszer automatikusan lefut ---
        self.run()

    # -----------------------------------------------------------------------
    # 2. A három módszer futtatása
    # -----------------------------------------------------------------------
    def read_max_iter(self):
        """Beolvassa az iterációk számát. Hibás értéknél piros üzenetet ír ki,
        és None-t ad vissza."""
        try:
            max_iter = int(self.var_max_iter.get().strip())
        except ValueError:
            max_iter = 0
        if max_iter < 1:
            self.show_status("Az iterációk száma legalább 1 legyen (egész szám).", True)
            return None
        return max_iter

    def run(self):
        """Lefuttatja a három módszert, és frissíti a táblázatot és a grafikont."""
        max_iter = self.read_max_iter()
        if max_iter is None:
            return
        self.show_status("Futtatás…", False)
        self.window.update_idletasks()          # az üzenet jelenjen meg a futás előtt
        self.results = kor.fit_all(self.points, max_iter, SEED)
        self.fill_table()
        self.show_status(f"Kész: {max_iter} iteráció, seed = {SEED}, "
                         f"{len(self.points)} pont.", False)

    def on_enter(self, event):
        """Enter az iterációszám mezőben: ugyanaz, mint a Futtatás gomb."""
        self.run()

    def open_run_charts(self):
        """A "Futás grafikonjai" gomb: új ablakban megnyitja a három módszer
        futásának grafikonját ugyanerre a ponthalmazra."""
        max_iter = self.read_max_iter()
        if max_iter is None:
            return
        RunChartsWindow(tk.Toplevel(self.window), self.points, self.generation_info, max_iter)

    def show_status(self, text, is_error):
        """Üzenet a gombok mellett; hibánál piros betűvel."""
        self.var_status.set(text)
        if is_error:
            self.status_label.configure(foreground="red")
        else:
            self.status_label.configure(foreground="")

    # -----------------------------------------------------------------------
    # 3. A táblázat
    # -----------------------------------------------------------------------
    def fill_table(self):
        """Újratölti a táblázatot: legfelül a névleges sor, alatta a három
        módszer. A legjobb (legkisebb szélességű) módszer sorát kijelöli, így
        a grafikonon alapból az látszik."""
        # a régi sorok törlése
        for row_id in self.table.get_children():
            self.table.delete(row_id)

        # a névleges (várt) sor
        self.table.insert("", "end", iid="nominal", tags=("nominal",), values=(
            "Névleges (várt)", format_number(self.nominal_width),
            format_number(self.nominal_r), format_number(self.nominal_R),
            format_number(self.nominal_radius), format_number(self.nominal_a),
            format_number(self.nominal_b), format_number(0), "–", "–"))

        # a legjobb módszer sorszáma (a legkisebb szélesség)
        best_index = 0
        for i in range(len(self.results)):
            if self.results[i].width < self.results[best_index].width:
                best_index = i

        # a módszerek sorai (a sor azonosítója a sorszám: "0", "1", "2")
        for i in range(len(self.results)):
            result = self.results[i]
            fitted_radius = (result.r_inner + result.r_outer) / 2
            deviation = math.hypot(result.a - self.nominal_a, result.b - self.nominal_b)
            if i == best_index:
                tags = ("best",)
            else:
                tags = ()
            self.table.insert("", "end", iid=str(i), tags=tags, values=(
                result.method_name, format_number(result.width),
                format_number(result.r_inner), format_number(result.r_outer),
                format_number(fitted_radius), format_number(result.a),
                format_number(result.b), format_number(deviation),
                f"{result.run_time:.5f}", result.evaluations))

        # a legjobb sor kijelölése (ez újrarajzolja a grafikont)
        self.table.selection_set(str(best_index))

    def on_row_selected(self, event):
        """Egy sorra kattintva újrarajzoljuk a grafikont."""
        self.draw()

    # -----------------------------------------------------------------------
    # 4. A grafikon
    # -----------------------------------------------------------------------
    def draw(self):
        """Kirajzolja a ponthalmazt (a kiugró pontokat pirossal), a névleges
        kört és a táblázatban kiválasztott sor köreit."""
        ax = self.ax
        ax.clear()
        ax.set_aspect("equal", adjustable="datalim")   # a kör körnek látsszon
        ax.grid(True, alpha=0.3)

        # --- a pontok: normál pontok kékkel, kiugró pontok pirossal ---
        outlier_indices = self.generation_info["outlier_indices"]
        normal_x, normal_y = [], []
        outlier_x, outlier_y = [], []
        for i in range(len(self.points)):
            x, y = self.points[i]
            if i in outlier_indices:
                outlier_x.append(x)
                outlier_y.append(y)
            else:
                normal_x.append(x)
                normal_y.append(y)
        ax.scatter(normal_x, normal_y, s=10, color="#1f6fd0", label="pontok", zorder=3)
        if len(outlier_x) > 0:
            ax.scatter(outlier_x, outlier_y, s=14, color="#d03a1f",
                       label="kiugró pontok", zorder=3)

        # --- a névleges (várt) kör és középpontja (mindig látszik) ---
        ax.add_patch(Circle((self.nominal_a, self.nominal_b), self.nominal_radius,
                            fill=False, lw=1.5, ls=":", color=NOMINAL_COLOR,
                            label="névleges (várt) kör"))
        ax.plot(self.nominal_a, self.nominal_b, marker="x", ms=9, mew=2,
                color=NOMINAL_COLOR, ls="none", label="névleges középpont")

        # --- a kiválasztott sor körei ---
        selection = self.table.selection()
        if len(selection) > 0:
            row_id = selection[0]
            if row_id == "nominal":
                name = "Névleges (várt)"
                a, b = self.nominal_a, self.nominal_b
                r, R, width = self.nominal_r, self.nominal_R, self.nominal_width
            else:
                result = self.results[int(row_id)]
                name = result.method_name
                a, b = result.a, result.b
                r, R, width = result.r_inner, result.r_outer, result.width

            # a belső (r) és a külső (R) kör
            ax.add_patch(Circle((a, b), r, fill=False, lw=1.2, color="#2ca02c",
                                label="belső kör (r)"))
            ax.add_patch(Circle((a, b), R, fill=False, lw=1.2, color="#ff7f0e",
                                label="külső kör (R)"))
            title = f"{name}:  R − r = {format_number(width)}"

            # módszernél az illesztett kör és a középpont is
            if row_id != "nominal":
                ax.add_patch(Circle((a, b), (r + R) / 2, fill=False, lw=2, ls="--",
                                    color="black", label="illesztett kör, (r + R) / 2"))
                ax.plot(a, b, marker="+", ms=12, mew=2, color="black", ls="none",
                        label="középpont")
                title += f"   (névleges: {format_number(self.nominal_width)})"
            ax.set_title(title, fontsize=10)

        # a tengelyek igazodjanak a pontokhoz és a körökhöz;
        # a jelmagyarázat a grafikon mellett van, hogy ne takarja a köröket
        ax.autoscale_view()
        ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=8, frameon=False)
        self.canvas.draw_idle()

    # -----------------------------------------------------------------------
    # 5. Vissza a generátorhoz, bezárás
    # -----------------------------------------------------------------------
    def back(self):
        """A "Vissza a generátorhoz" gomb (a _main.py bezárja ezt az ablakot,
        és újra megjeleníti a generátort)."""
        self.cancel_resize_job()
        self.on_back()

    def close(self):
        """Az ablak X gombja (a _main.py kilépteti a programot)."""
        self.cancel_resize_job()
        self.on_close()

    def cancel_resize_job(self):
        """Ha még várakozik egy frissítés, töröljük, hogy ne fusson le a
        már bezárt ablakon."""
        if self.resize_job is not None:
            self.window.after_cancel(self.resize_job)

    # -----------------------------------------------------------------------
    # 6. Átméretezés
    # -----------------------------------------------------------------------
    def on_resize(self, event):
        """Az ablak átméretezése után (60 ms-mal az utolsó változás után)
        újrarajzoltatjuk a gombokat (macOS-hiba, lásd refresh_widgets)."""
        if event.widget is not self.window:
            return        # a belső elemek átméreteződése nem érdekes
        if self.resize_job is not None:
            self.window.after_cancel(self.resize_job)
        self.resize_job = self.window.after(60, self.refresh_after_resize)

    def refresh_after_resize(self):
        """Az ablak összes gombját és mezőjét újrarajzoltatja."""
        self.resize_job = None
        refresh_widgets(self.window)
