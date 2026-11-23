"""
Grafikus felület a Csebisev-körillesztés vizsgálatához.

A generátorból (gui.py, "Vizsgálat indítása" gomb) átvett ponthalmazra
lefut a három keresőmódszer (hegymászó, szimulált hűtés, genetikus
algoritmus), mind ugyanazzal a max_iter értékkel és seeddel.
Az ablakban látszik:
  - egy grafikon: a ponthalmaz, a névleges (várt) kör, a kiválasztott
    módszer két koncentrikus köre (r és R sugárral) és az illesztett kör
    ((r + R) / 2 sugárral),
  - egy összehasonlító táblázat: legfelül a névleges (várt) értékek, alatta
    a három módszer. A legkisebb szélességű módszer sora ki van emelve.
    Egy sorra kattintva annak az eredménye látszik a grafikonon.
A "Futtatás" gombbal ugyanarra a ponthalmazra más iterációszámmal is újra
lefuttathatók a módszerek. Az ablak megnyitásakor egyszer automatikusan
lefutnak. A "Futás grafikonjai" gomb külön ablakban megmutatja, hogyan
haladt a három módszer iterációról iterációra (futas_grafikon.py).

A névleges (várt) értékek a generálásból jönnek: a névleges kör középpontja
és sugara. A szélesség, r és R ennél a sornál a névleges középpontból mérve
értendő; ez az a gyűrű, amelyet a hibák (alakhiba, zaj, kiugró pontok)
okoznak. Egy jó módszer ennél nem ad nagyobb szélességet, és a középpontja
közel van a névlegeshez.

A számítás a korillesztes.py-ban van; ez a fájl csak a megjelenítés.
Indítás: python3 main.py (a projekt gyökeréből), majd "Vizsgálat indítása".
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
from code_base.futas_grafikon import FutasGrafikonApp

# ===========================================================================
#region Beállítások és segédfüggvények
# ===========================================================================
SEED = 1                  # minden módszer ezt a seedet kapja: ugyanazzal a
                          # seeddel mindig ugyanaz az eredmény jön ki
DEFAULT_MAX_ITER = 50     # az iterációk száma az ablak megnyitásakor

BEST_ROW_COLOR = "#d6f0d6"        # a legjobb sor háttérszíne (zöld)
NOMINAL_ROW_COLOR = "#eeeeee"     # a névleges (várt) sor háttérszíne (szürke)
HIGHLIGHT_TEXT_COLOR = "#1a1a1a"  # a két kiemelt sor betűszíne (sötét, hogy
                                  # sötét módban is olvasható legyen)
NOMINAL_COLOR = "#888888"         # a névleges kör színe a grafikonon

# a táblázat oszlopai: (azonosító, fejléc, szélesség képpontban)
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

def fmt(value):
    """Szám a táblázatba: 6 tizedesjegy; a nagyon kicsi (0-hoz közeli, de
    nem 0) értékek normálalakban, pl. 1.23e-05."""

    if value != 0 and abs(value) < 0.001:
        return f"{value:.2e}"
    return f"{value:.6f}"
#endregion

# ===========================================================================
#region A vizsgáló ablak
# ===========================================================================
class VizsgaloApp:
    """A vizsgáló ablak.

    Felül az iterációszám-mező és a Futtatás gomb, középen a grafikon, alul
    az összehasonlító táblázat a három keresőmódszer eredményével.

    Az osztály részei:
      1. GUI felépítése
      2. a három módszer futtatása
      3. az összehasonlító táblázat
      4. a grafikon
      5. vissza a generátorhoz, bezárás
      6. átméretezés"""

    # -----------------------------------------------------------------------
    #region 1. A GUI felépítése
    # -----------------------------------------------------------------------
    def __init__(self, window, points, ground_truth, on_close, on_back):
        """window: az ablak, amelybe a felület kerül.
        points: a generátortól átvett ponthalmaz ((n, 2) alakú tömb).
        ground_truth: a generálás adatai (névleges kör, kiugró pontok).
        on_close: az ablak bezárásakor (X) meghívandó függvény.
        on_back: a "Vissza a generátorhoz" gombra meghívandó függvény."""
        self.window = window
        self.points = np.array(points, dtype=float)
        self.ground_truth = ground_truth
        self.on_close = on_close
        self.on_back = on_back
        self.results = []           # a három módszer eredménye (FitResult-ok)
        self.refresh_job = None     # a késleltetett újrarajzolás azonosítója

        # --- a névleges (várt) értékek a generálás adataiból ---
        self.nominal_a = ground_truth["center"][0]
        self.nominal_b = ground_truth["center"][1]
        self.nominal_radius = ground_truth["radius"]
        # a névleges középpontból mért gyűrű
        r, big_r, width = kor.ring(self.points, (self.nominal_a, self.nominal_b))
        self.nominal_r = r
        self.nominal_big_r = big_r
        self.nominal_width = width

        # --- az ablak beállításai ---
        window.title("Csebisev-körillesztés – vizsgálat")
        window.geometry("1240x780")
        window.minsize(1100, 560)
        window.protocol("WM_DELETE_WINDOW", self.close)   # az X gomb

        # --- felső sor: Vissza gomb, iterációk száma, Futtatás és
        #     Futás grafikonjai gomb, üzenet ---
        top = ttk.Frame(window, padding=(10, 8))
        top.pack(fill="x")
        back_button = ttk.Button(top, text="← Vissza a generátorhoz",
                                 command=self.back)
        back_button.pack(side="left", padx=(0, 16))
        ttk.Label(top, text="Iterációk száma (max_iter):").pack(side="left")
        self.var_iter = tk.StringVar(value=str(DEFAULT_MAX_ITER))
        entry = ttk.Entry(top, textvariable=self.var_iter, width=8)
        entry.pack(side="left", padx=(4, 8))
        entry.bind("<Return>", self.on_enter)     # Enterre is fut
        self.run_button = ttk.Button(top, text="Futtatás", command=self.run)
        self.run_button.pack(side="left")
        charts_button = ttk.Button(top, text="Futás grafikonjai",
                                   command=self.open_run_charts)
        charts_button.pack(side="left", padx=(8, 0))
        self.var_status = tk.StringVar()
        self.status_label = ttk.Label(top, textvariable=self.var_status)
        self.status_label.pack(side="left", padx=12)

        # --- alul a táblázat (az alsó keretbe), fölötte a grafikon ---
        bottom = ttk.Frame(window, padding=(10, 0, 10, 10))
        bottom.pack(side="bottom", fill="x")
        self.figure = Figure(figsize=(8, 5), dpi=100, layout="constrained")
        self.ax = self.figure.add_subplot()
        self.canvas = FigureCanvasTkAgg(self.figure, master=window)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10)

        # --- a táblázat ---
        column_ids = []
        for column in COLUMNS:
            column_ids.append(column[0])
        self.tree = ttk.Treeview(bottom, columns=column_ids, show="headings",
                                 height=4, selectmode="browse")
        for column_id, title, width in COLUMNS:
            self.tree.heading(column_id, text=title)
            if column_id == "method":
                anchor = "w"          # a szöveg balra igazítva
            else:
                anchor = "e"          # a számok jobbra igazítva
            self.tree.column(column_id, width=width, minwidth=40, anchor=anchor)

        # a kiemelt sorok betűtípusa: félkövér (legjobb) és dőlt (névleges)
        bold_font = tkfont.nametofont("TkDefaultFont").copy()
        bold_font.configure(weight="bold")
        italic_font = tkfont.nametofont("TkDefaultFont").copy()
        italic_font.configure(slant="italic")
        # a kiemelt sorok betűszíne rögzített (sötét): a rendszer alapszíne
        # sötét módban fehér, ami a világos háttéren olvashatatlan lenne
        self.tree.tag_configure("best", background=BEST_ROW_COLOR,
                                foreground=HIGHLIGHT_TEXT_COLOR, font=bold_font)
        self.tree.tag_configure("nominal", background=NOMINAL_ROW_COLOR,
                                foreground=HIGHLIGHT_TEXT_COLOR, font=italic_font)
        self.tree.pack(fill="x")
        self.tree.bind("<<TreeviewSelect>>", self.on_row_selected)

        # --- magyarázat a táblázat alatt ---
        help_text = ("Az első (szürke) sor a névleges, várt érték: a generálás "
                     "középpontja és sugara; a szélesség, r és R ebből a "
                     "középpontból mérve. A zöld sor a legkisebb szélességű "
                     "(legjobb) módszer. Kattints egy sorra: a grafikonon "
                     "annak a körei látszanak.")
        help_label = ttk.Label(bottom, text=help_text, foreground="#666666",
                               wraplength=1180, justify="left")
        help_label.pack(fill="x", pady=(6, 0))

        # --- első futtatás: megnyitáskor egyszer automatikusan lefut ---
        window.bind("<Configure>", self.on_window_resize)
        self.run()
    #endregion

    # -----------------------------------------------------------------------
    #region 2. A három módszer futtatása
    # -----------------------------------------------------------------------
    def run(self):
        """Beolvassa az iterációk számát, lefuttatja vele a három módszert
        (seed = SEED), és frissíti a táblázatot meg a grafikont.
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

        # --- Futtatás ---
        # a számítás közben a gomb le van tiltva (nagyon nagy max_iter
        # esetén az ablak néhány másodpercre megakadhat)
        self.run_button.configure(state="disabled")
        self.show_status("Futtatás…", False)
        self.window.update_idletasks()
        self.results = kor.fit_all(self.points, max_iter, SEED)
        self.run_button.configure(state="normal")

        # --- Eredmény megjelenítése ---
        self.fill_table()
        self.show_status(f"Kész: {max_iter} iteráció, seed = {SEED}, "
                         f"{len(self.points)} pont.", False)

    def on_enter(self, event):
        """Enter a mezőben: ugyanaz, mint a Futtatás gomb."""

        self.run()

    def open_run_charts(self):
        """A "Futás grafikonjai" gomb: új ablakban megnyitja a három módszer
        futásának grafikonját (futas_grafikon.py), ugyanerre a ponthalmazra
        és a mezőben megadott iterációszámmal."""

        # --- Iterációszám beolvasása ---
        try:
            max_iter = int(self.var_iter.get().strip())
        except ValueError:
            max_iter = 0
        if max_iter < 1:
            self.show_status("Az iterációk száma legalább 1 legyen (egész szám).",
                             True)
            return

        # --- Az új ablak (a vizsgáló ablakkal együtt zárul be) ---
        charts_window = tk.Toplevel(self.window)
        FutasGrafikonApp(charts_window, self.points, self.ground_truth, max_iter)

    def show_status(self, text, is_error):
        """Üzenet a Futtatás gomb mellé; hibánál piros betűvel."""

        self.var_status.set(text)
        if is_error:
            self.status_label.configure(foreground="red")
        else:
            self.status_label.configure(foreground="")
    #endregion

    # -----------------------------------------------------------------------
    #region 3. Az összehasonlító táblázat
    # -----------------------------------------------------------------------
    def fill_table(self):
        """Újratölti a táblázatot: legfelül a névleges (várt) sor, alatta a
        három módszer. A legkisebb szélességű módszer sorát kiemeli és
        kijelöli, így a grafikonon alapból az látszik."""

        # --- Régi sorok törlése ---
        for row_id in self.tree.get_children():
            self.tree.delete(row_id)

        # --- Névleges (várt) sor ---
        nominal_values = ("Névleges (várt)", fmt(self.nominal_width),
                          fmt(self.nominal_r), fmt(self.nominal_big_r),
                          fmt(self.nominal_radius), fmt(self.nominal_a),
                          fmt(self.nominal_b), fmt(0.0), "–", "–")
        self.tree.insert("", "end", iid="nominal", tags=("nominal",),
                         values=nominal_values)

        # --- Legjobb módszer (legkisebb szélesség) ---
        best_index = 0
        for i in range(len(self.results)):
            if self.results[i].width < self.results[best_index].width:
                best_index = i

        # --- Módszerek sorai (a sor azonosítója a sorszám: "0", "1"...) ---
        for i in range(len(self.results)):
            result = self.results[i]
            a = result.center[0]
            b = result.center[1]
            fitted_radius = (result.r_inner + result.r_outer) / 2
            deviation = math.hypot(a - self.nominal_a, b - self.nominal_b)
            values = (result.method, fmt(result.width), fmt(result.r_inner),
                      fmt(result.r_outer), fmt(fitted_radius), fmt(a), fmt(b),
                      fmt(deviation), f"{result.time_s:.5f}", result.evaluations)
            if i == best_index:
                tags = ("best",)
            else:
                tags = ()
            self.tree.insert("", "end", iid=str(i), tags=tags, values=values)

        # --- Kijelölés: alapból a legjobb sor (ez újrarajzolja a grafikont) ---
        self.tree.selection_set(str(best_index))

    def on_row_selected(self, event):
        """Egy sorra kattintva újrarajzolja a grafikont."""

        self.draw()
    #endregion

    # -----------------------------------------------------------------------
    #region 4. A grafikon
    # -----------------------------------------------------------------------
    def draw(self):
        """Kirajzolja a grafikont:
        a ponthalmazt (kiugró pontok pirossal),
        a névleges kört (szürke, pontozott),
        a táblázatban kiválasztott sor köreit.
        Módszer soránál: belső kör (r), külső kör (R), illesztett kör
        ((r + R) / 2) és a középpont; a névleges sornál a névleges
        középpontból mért belső és külső kör."""

        ax = self.ax
        ax.clear()
        ax.set_aspect("equal", adjustable="box")    # a kör körnek látsszon
        ax.grid(True, alpha=0.3)

        # --- Pontok: normál pontok és kiugró pontok (piros) ---
        outlier_indices = self.ground_truth["outliers"]["indices"]
        normal_x = []
        normal_y = []
        outlier_x = []
        outlier_y = []
        for i in range(len(self.points)):
            x = self.points[i][0]
            y = self.points[i][1]
            if i in outlier_indices:
                outlier_x.append(x)
                outlier_y.append(y)
            else:
                normal_x.append(x)
                normal_y.append(y)
        ax.scatter(normal_x, normal_y, s=10, color="#1f6fd0", label="pontok",
                   zorder=3)
        if len(outlier_x) > 0:
            ax.scatter(outlier_x, outlier_y, s=14, color="#d03a1f",
                       label="kiugró pontok", zorder=3)

        # --- Névleges (várt) kör és középpontja (mindig látszik) ---
        nominal_circle = Circle((self.nominal_a, self.nominal_b),
                                self.nominal_radius, fill=False, lw=1.5, ls=":",
                                color=NOMINAL_COLOR, label="névleges (várt) kör")
        ax.add_patch(nominal_circle)
        ax.plot(self.nominal_a, self.nominal_b, marker="x", ms=9, mew=2,
                color=NOMINAL_COLOR, ls="none", label="névleges középpont")

        # a tengelyek határaihoz: a rajz széleinek x és y értékei
        x_values = normal_x + outlier_x
        y_values = normal_y + outlier_y
        x_values.append(self.nominal_a - self.nominal_radius)
        x_values.append(self.nominal_a + self.nominal_radius)
        y_values.append(self.nominal_b - self.nominal_radius)
        y_values.append(self.nominal_b + self.nominal_radius)

        # --- Kiválasztott sor körei ---
        title = ""
        selection = self.tree.selection()
        if len(selection) > 0:
            row_id = selection[0]
            if row_id == "nominal":
                name = "Névleges (várt)"
                a = self.nominal_a
                b = self.nominal_b
                r = self.nominal_r
                big_r = self.nominal_big_r
                width = self.nominal_width
            else:
                result = self.results[int(row_id)]
                name = result.method
                a = result.center[0]
                b = result.center[1]
                r = result.r_inner
                big_r = result.r_outer
                width = result.width

            # a belső (r) és a külső (R) kör
            ax.add_patch(Circle((a, b), r, fill=False, lw=1.2, color="#2ca02c",
                                label="belső kör (r)"))
            ax.add_patch(Circle((a, b), big_r, fill=False, lw=1.2,
                                color="#ff7f0e", label="külső kör (R)"))
            # módszernél az illesztett kör és a középpont is
            if row_id != "nominal":
                ax.add_patch(Circle((a, b), (r + big_r) / 2, fill=False, lw=2,
                                    ls="--", color="#000000",
                                    label="illesztett kör, (r + R) / 2"))
                ax.plot(a, b, marker="+", ms=12, mew=2, color="#000000",
                        ls="none", label="középpont")

            x_values.append(a - big_r)
            x_values.append(a + big_r)
            y_values.append(b - big_r)
            y_values.append(b + big_r)

            title = f"{name}:  R − r = {fmt(width)}"
            if row_id != "nominal":
                title += f"   (névleges: {fmt(self.nominal_width)})"
        ax.set_title(title, fontsize=10)

        # --- Tengelyek határai és jelmagyarázat ---
        # a két tengelyen azonos terjedelem, hogy a pontok és a körök is
        # beférjenek, és a kör körnek látsszon
        x_min = min(x_values)
        x_max = max(x_values)
        y_min = min(y_values)
        y_max = max(y_values)
        half = 0.55 * max(x_max - x_min, y_max - y_min, 1e-9)
        middle_x = (x_min + x_max) / 2
        middle_y = (y_min + y_max) / 2
        ax.set_xlim(middle_x - half, middle_x + half)
        ax.set_ylim(middle_y - half, middle_y + half)

        # a jelmagyarázat a grafikon mellett, hogy ne takarja a kör közepét
        ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=8,
                  frameon=False)
        self.canvas.draw_idle()
    #endregion

    # -----------------------------------------------------------------------
    #region 5. Vissza a generátorhoz, bezárás
    # -----------------------------------------------------------------------
    def back(self):
        """A "Vissza a generátorhoz" gomb: leállítja a várakozó időzítést, és
        meghívja az on_back függvényt (a main.py-ban ez bezárja ezt az
        ablakot, és újra megjeleníti a generátort)."""

        if self.refresh_job is not None:
            self.window.after_cancel(self.refresh_job)
        self.on_back()

    def close(self):
        """Az ablak bezárása (X): leállítja a várakozó időzítést, és meghívja
        az on_close függvényt (a main.py-ban ez kilépteti a programot)."""

        if self.refresh_job is not None:
            self.window.after_cancel(self.refresh_job)
        self.on_close()
    #endregion

    # -----------------------------------------------------------------------
    #region 6. Átméretezés
    # -----------------------------------------------------------------------
    def on_window_resize(self, event):
        """Az ablak átméretezésekor (kis késleltetéssel) újrarajzoltatja a
        gombokat. macOS-en ugyanis átméretezés után a gombok néha nem
        rajzolódnak újra (lásd gui.py, refresh_widgets)."""

        if event.widget is not self.window:
            return
        if self.refresh_job is not None:
            self.window.after_cancel(self.refresh_job)
        self.refresh_job = self.window.after(60, self.refresh_all_widgets)

    def refresh_all_widgets(self):
        """Az ablak összes gombját és mezőjét újrarajzoltatja."""

        self.refresh_job = None
        self.refresh_widgets(self.window)

    def refresh_widgets(self, widget):
        """Újrarajzolás
        Ha egy beállítást önmagára állítunk (ez semmit nem változtat), az
        újrarajzolja őket. A függvény saját magát hívja a belső elemekre is
        (rekurzió)."""

        for child in widget.winfo_children():
            if isinstance(child, ttk.Widget):
                child["cursor"] = child["cursor"]
            self.refresh_widgets(child)
    #endregion
#endregion
