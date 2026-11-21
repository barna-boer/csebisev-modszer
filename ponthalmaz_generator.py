"""
Ponthalmaz-generátor körillesztéshez (Csebisev-elv).

A program egy egyszerű ablakban megjeleníti a generált pontokat.
Megadható:
  - a pontok száma,
  - a sáv belső és külső sugara (a sáv a kijelző közepe körül van),
  - opcionálisan egy seed (ugyanazzal a seeddel mindig ugyanaz a ponthalmaz jön ki).

Futtatás:  python ponthalmaz_generator.py
Csak a Python alap könyvtárát (tkinter) és a NumPy-t használja.
Telepítés, ha kell:  pip install numpy
"""

import tkinter as tk
from tkinter import ttk

import numpy as np


# ---------------------------------------------------------------------------
# 1. A generáló függvény (a GUI-tól független, később a keresőmódszerek is
#    ezt használhatják)
# ---------------------------------------------------------------------------
def generate_points(n, r_inner, r_outer, center=(0.0, 0.0), seed=None):
    """
    n darab pontot generál a (center) középpontú körgyűrűben.

    Minden pont:
      - szöge véletlen (0 és 360 fok között, egyenletesen),
      - középponttól mért távolsága véletlen r_inner és r_outer között.

    Visszatérés: (n, 2) alakú NumPy tömb, minden sor egy (x, y) pont.

    Fontos a későbbi vizsgálathoz: mivel minden pont az r_inner..r_outer
    gyűrűben van, az optimális Csebisev-gyűrű szélessége legfeljebb
    r_outer - r_inner lehet (ez ismert felső korlát).
    """
    rng = np.random.default_rng(seed)
    angles = rng.uniform(0.0, 2.0 * np.pi, size=n)
    radii = rng.uniform(r_inner, r_outer, size=n)
    x = center[0] + radii * np.cos(angles)
    y = center[1] + radii * np.sin(angles)
    return np.column_stack((x, y))


# ---------------------------------------------------------------------------
# 2. A grafikus felület
# ---------------------------------------------------------------------------
CANVAS_SIZE = 700          # a rajzterület logikai oldala (és kezdeti mérete)
                           # képpontban; átméretezéskor erre skálázunk
POINT_RADIUS = 3           # egy pont kirajzolt mérete (képpontban, nem skálázódik)


class App:
    def __init__(self, root):
        self.root = root
        root.title("Ponthalmaz-generátor")

        self.points = None  # a legutóbb generált pontok (a középponthoz képest)
        self.r_in = self.r_out = None  # a legutóbb kirajzolt sáv sugarai
        self._redraw_job = None        # átméretezéskor késleltetett újrarajzolás

        # az ablak átméretezésekor a rajzterület (1. oszlop) nőjön/zsugorodjon
        root.columnconfigure(1, weight=1)
        root.rowconfigure(0, weight=1)

        # --- bal oldali vezérlőpanel ---
        panel = ttk.Frame(root, padding=10)
        panel.grid(row=0, column=0, sticky="ns")

        self.var_n = tk.StringVar(value="50")
        self.var_rin = tk.StringVar(value="150")
        self.var_rout = tk.StringVar(value="170")
        self.var_seed = tk.StringVar(value="")

        self._add_field(panel, 0, "Pontok száma:", self.var_n)
        self._add_field(panel, 1, "Belső sugár:", self.var_rin)
        self._add_field(panel, 2, "Külső sugár:", self.var_rout)
        self._add_field(panel, 3, "Seed (üres = véletlen):", self.var_seed)

        ttk.Button(panel, text="Generálás", command=self.generate).grid(
            row=4, column=0, columnspan=2, pady=(12, 4), sticky="ew")

        self.var_info = tk.StringVar(value="")
        ttk.Label(panel, textvariable=self.var_info, wraplength=200,
                  justify="left").grid(row=5, column=0, columnspan=2, pady=6)

        self.var_error = tk.StringVar(value="")
        ttk.Label(panel, textvariable=self.var_error, foreground="red",
                  wraplength=200, justify="left").grid(
            row=6, column=0, columnspan=2)

        # --- jobb oldali rajzterület ---
        self.canvas = tk.Canvas(root, width=CANVAS_SIZE, height=CANVAS_SIZE,
                                bg="white", highlightthickness=1,
                                highlightbackground="gray")
        self.canvas.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        self.canvas.bind("<Configure>", self._on_resize)

        self.generate()  # induláskor rögtön rajzoljon valamit

        # ne lehessen használhatatlanul kicsire húzni az ablakot
        root.update_idletasks()
        root.minsize(panel.winfo_reqwidth() + 200, panel.winfo_reqheight() + 20)

    def _on_resize(self, _event):
        """Átméretezéskor újrarajzol; rövid késleltetéssel, hogy húzás közben
        ne rajzoljon feleslegesen minden egyes képpontnyi változásnál."""
        if self._redraw_job is not None:
            self.root.after_cancel(self._redraw_job)
        self._redraw_job = self.root.after(30, self._redraw)

    def _redraw(self):
        self._redraw_job = None
        if self.points is not None:
            self.draw(self.r_in, self.r_out)

    @staticmethod
    def _add_field(parent, row, label, variable):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w",
                                           pady=2)
        ttk.Entry(parent, textvariable=variable, width=10).grid(
            row=row, column=1, padx=(8, 0), pady=2)

    # --- bemenet beolvasása és ellenőrzése ---
    def _read_inputs(self):
        """Visszaadja (n, r_in, r_out, seed) értékeket, vagy hibát dob."""
        try:
            n = int(self.var_n.get())
        except ValueError:
            raise ValueError("A pontok száma egész szám legyen.")
        try:
            r_in = float(self.var_rin.get().replace(",", "."))
            r_out = float(self.var_rout.get().replace(",", "."))
        except ValueError:
            raise ValueError("A sugarak számok legyenek.")

        seed_text = self.var_seed.get().strip()
        if seed_text == "":
            seed = None
        else:
            try:
                seed = int(seed_text)
            except ValueError:
                raise ValueError("A seed egész szám legyen (vagy hagyd üresen).")

        if n < 1:
            raise ValueError("Legalább 1 pont kell.")
        if r_in < 0:
            raise ValueError("A belső sugár nem lehet negatív.")
        if r_out < r_in:
            raise ValueError("A külső sugár ne legyen kisebb a belsőnél.")
        if r_out > CANVAS_SIZE / 2 - 5:
            raise ValueError(
                f"A külső sugár legfeljebb {CANVAS_SIZE // 2 - 5} lehet, "
                "különben kilóg a rajzterületről.")
        return n, r_in, r_out, seed

    # --- generálás + rajzolás ---
    def generate(self):
        try:
            n, r_in, r_out, seed = self._read_inputs()
        except ValueError as e:
            self.var_error.set(str(e))
            return
        self.var_error.set("")

        self.points = generate_points(n, r_in, r_out, seed=seed)
        self.r_in, self.r_out = r_in, r_out
        self.var_info.set(
            f"{n} pont generálva.\n"
            f"A sáv szélessége: {r_out - r_in:g}")
        self.draw(r_in, r_out)

    def draw(self, r_in, r_out):
        c = self.canvas
        c.delete("all")

        # a rajzterület aktuális mérete; a logikai CANVAS_SIZE x CANVAS_SIZE
        # négyzetet a rövidebb oldalhoz skálázzuk, hogy mindig beférjen
        w, h = c.winfo_width(), c.winfo_height()
        if w <= 1 or h <= 1:          # még nincs megjelenítve az ablak
            w = h = CANVAS_SIZE
        scale = min(w, h) / CANVAS_SIZE
        cx, cy = w / 2, h / 2

        # a sáv határai (szaggatott körök) és a középpont
        for r in (r_in, r_out):
            rs = r * scale
            c.create_oval(cx - rs, cy - rs, cx + rs, cy + rs,
                          outline="#aaaaaa", dash=(4, 4))
        c.create_line(cx - 6, cy, cx + 6, cy, fill="#aaaaaa")
        c.create_line(cx, cy - 6, cx, cy + 6, fill="#aaaaaa")

        # a pontok (a y tengelyt megfordítjuk, mert a képernyőn lefelé nő)
        for x, y in self.points:
            px, py = cx + x * scale, cy - y * scale
            c.create_oval(px - POINT_RADIUS, py - POINT_RADIUS,
                          px + POINT_RADIUS, py + POINT_RADIUS,
                          fill="#1f6fd0", outline="")


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()