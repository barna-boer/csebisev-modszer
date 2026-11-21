"""
Grafikus felület a Csebisev-körillesztés vizsgálatához.

A generátorból (gui.py, "Vizsgálat indítása" gomb) átvett ponthalmazra
lefut a négy keresőmódszer (hegymászó, szimulált hűtés, genetikus
algoritmus, részecskeraj), mind ugyanazzal a max_iter értékkel és seeddel.
Az ablakban látszik:
  - egy grafikon: a ponthalmaz, a kiválasztott módszer két koncentrikus
    köre (r és R sugárral) és az illesztett kör ((r + R) / 2 sugárral),
  - egy összehasonlító táblázat a négy módszerrel; a legkisebb szélességű
    sor ki van emelve. Egy sorra kattintva annak a módszernek az eredménye
    látszik a grafikonon.
A "Futtatás" gombbal ugyanarra a ponthalmazra más iterációszámmal is újra
lefuttathatók a módszerek. Az ablak megnyitásakor egyszer automatikusan
lefutnak.

A számítás a korillesztes.py-ban van; ez a fájl csak a megjelenítés.
Indítás: python3 gui.py, majd "Vizsgálat indítása".
Függőségek: numpy, matplotlib (pip install -r requirements.txt)
"""

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.patches import Circle

import korillesztes as kor


SEED = 1                   # minden módszer ezt a seedet kapja: ugyanazzal a
                           # seeddel mindig ugyanaz az eredmény jön ki
DEFAULT_MAX_ITER = 200
BEST_ROW_COLOR = "#d6f0d6"  # a legkisebb szélességű sor háttérszíne

# a táblázat oszlopai: (kulcs, fejléc, szélesség képpontban)
COLUMNS = [
    ("method", "Módszer", 190),
    ("width", "Szélesség (R − r)", 120),
    ("r", "r", 95),
    ("R", "R", 95),
    ("a", "Középpont a", 95),
    ("b", "Középpont b", 95),
    ("time", "Futásidő (s)", 85),
    ("evals", "Célfüggvény-kiértékelések száma", 200),
]


def fmt(value):
    """Szám a táblázatba; a nagyon kicsi értékek normálalakban."""
    if value != 0 and abs(value) < 1e-3:
        return f"{value:.2e}"
    return f"{value:.6f}"


class VizsgaloApp:
    def __init__(self, master, points, ground_truth=None, on_close=None):
        """master: a Tk gyökér vagy egy Toplevel ablak.
        points: a generátortól átvett ponthalmaz ((n, 2) alakú tömb).
        ground_truth: a generálás adatai (a kiugró pontok kiemeléséhez).
        on_close: az ablak bezárásakor hívandó függvény (alapból
        master.destroy)."""
        self.master = master
        self.points = np.asarray(points, dtype=float)
        self.ground_truth = ground_truth
        self.on_close = on_close or master.destroy
        self.results = []
        self._refresh_job = None

        master.title("Csebisev-körillesztés – vizsgálat")
        master.geometry("1100x760")
        master.minsize(1000, 560)
        master.protocol("WM_DELETE_WINDOW", self.close)

        # --- felső sor: iterációk száma + Futtatás gomb + üzenet ---
        top = ttk.Frame(master, padding=(10, 8))
        top.pack(fill="x")
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

        self.tree = ttk.Treeview(bottom, columns=[c[0] for c in COLUMNS],
                                 show="headings", height=4,
                                 selectmode="browse")
        for key, title, width in COLUMNS:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=40,
                             anchor="w" if key == "method" else "e")
        bold = tkfont.nametofont("TkDefaultFont").copy()
        bold.configure(weight="bold")
        self.tree.tag_configure("best", background=BEST_ROW_COLOR, font=bold)
        self.tree.pack(fill="x")
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self.draw())
        ttk.Label(bottom, foreground="#666666",
                  text="A kiemelt sor a legkisebb szélességű (legjobb) eredmény. "
                       "Kattints egy sorra: a grafikonon annak a módszernek a "
                       "két koncentrikus köre és az illesztett köre látszik."
                  ).pack(fill="x", pady=(6, 0))

        master.bind("<Configure>", self._on_configure)
        self.run()          # megnyitáskor egyszer automatikusan lefut

    # --- futtatás ---
    def run(self):
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
        self.var_status.set(text)
        self.status_label.configure(foreground="red" if error else "")

    def _fill_table(self):
        self.tree.delete(*self.tree.get_children())
        best = min(range(len(self.results)), key=lambda i: self.results[i].width)
        for i, res in enumerate(self.results):
            self.tree.insert("", "end", iid=str(i),
                             tags=("best",) if i == best else (),
                             values=(res.method, fmt(res.width), fmt(res.r_inner),
                                     fmt(res.r_outer), fmt(res.center[0]),
                                     fmt(res.center[1]), f"{res.time_s:.5f}",
                                     res.evaluations))
        self.tree.selection_set(str(best))   # alapból a legjobb látszik

    # --- rajzolás ---
    def draw(self):
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

        # a kiválasztott módszer körei
        title = ""
        selection = self.tree.selection()
        if selection:
            res = self.results[int(selection[0])]
            (a, b), r, big_r = res.center, res.r_inner, res.r_outer
            ax.add_patch(Circle((a, b), r, fill=False, lw=1.2, color="#2ca02c",
                                label="belső kör (r)"))
            ax.add_patch(Circle((a, b), big_r, fill=False, lw=1.2, color="#ff7f0e",
                                label="külső kör (R)"))
            ax.add_patch(Circle((a, b), (r + big_r) / 2, fill=False, lw=2,
                                ls="--", color="#000000",
                                label="illesztett kör, (r + R) / 2"))
            ax.plot(a, b, marker="+", ms=12, mew=2, color="#000000",
                    label="középpont")
            xs += [a - big_r, a + big_r]
            ys += [b - big_r, b + big_r]
            title = f"{res.method}:  R − r = {fmt(res.width)}"
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
        self._refresh_job = None
        for child in (widget or self.master).winfo_children():
            if isinstance(child, ttk.Widget):
                child.configure(cursor=child.cget("cursor"))
            self._refresh_widgets(child)

    def close(self):
        if self._refresh_job is not None:
            self.master.after_cancel(self._refresh_job)
        self.on_close()


if __name__ == "__main__":
    print("A vizsgáló ablak a generátorból indul: python3 gui.py, "
          "majd \"Vizsgálat indítása\".")
