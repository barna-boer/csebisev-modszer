"""
A ponthalmaz-generátor ablaka.

Bal oldalon a generálás paraméterei, jobb oldalon a generált ponthalmaz rajza.
Megadható:
  - a pontok száma és a névleges kör sugara,
  - a lefedettség: teljes kör vagy ívdarab (kezdő- és végszög), és hogy a
    szögek véletlenek vagy egyenletes közűek legyenek,
  - az alakhiba (nincs / ellipszis / szabályos sokszög) és a paramétere,
  - a véletlen hiba mértéke (±e),
  - a kiugró pontok aránya,
  - a seed (ugyanazzal a seeddel mindig ugyanaz a ponthalmaz jön ki).

Bármelyik mező módosításakor a ponthalmaz azonnal újragenerálódik ugyanazzal
a seeddel, így csak a módosított paraméter hatása látszik. Az "Új véletlen
halmaz" gomb új seedet sorsol.

A "Vizsgálat indítása" gomb a ponthalmazt átadja a _main.py-nak, amely
megnyitja vele a vizsgáló ablakot (kiertekelo/vizsgalo_gui.py).
A pontokat a ponthalmaz_generator.py generate_points függvénye állítja elő.
"""

import math
import random
import tkinter as tk
from tkinter import ttk

from generator.ponthalmaz_generator import ANGLE_MODES, SHAPES, generate_points

# ===========================================================================
# Beállítások
# ===========================================================================
CANVAS_SIZE = 640          # a rajzterület kezdeti mérete (képpont)
MARGIN = 15                # üres sáv a rajz széle körül (képpont)
POINT_SIZE = 3             # egy pont sugara a rajzon (képpont)
POINT_COLOR = "#1f6fd0"    # a pontok színe (kék)
OUTLIER_COLOR = "#d03a1f"  # a kiugró pontok színe (piros)
GUIDE_COLOR = "#aaaaaa"    # a névleges kör és a segédvonalak színe (szürke)


# ===========================================================================
# Segédfüggvények: a mezők szövegének számmá alakítása
# ===========================================================================
def read_float(text, field_name):
    """Egy mező szövegét valós számmá alakítja (tizedesvesszőt is elfogad).
    Ha nem szám, ValueError-t dob a mező nevével."""
    try:
        value = float(text.strip().replace(",", "."))
    except ValueError:
        raise ValueError(f"{field_name}: szám kell.")
    # a float() a "nan" és "inf" szöveget is elfogadja, de ezek nem véges számok
    if not math.isfinite(value):
        raise ValueError(f"{field_name}: véges szám kell.")
    return value


def read_int(text, field_name):
    """Egy mező szövegét egész számmá alakítja.
    Ha nem egész szám, ValueError-t dob a mező nevével."""
    try:
        return int(text.strip())
    except ValueError:
        raise ValueError(f"{field_name}: egész szám kell.")


def new_seed():
    """Egy új, véletlen seed."""
    return random.randrange(2**31 - 1)


# ===========================================================================
# A generátor ablaka
# ===========================================================================
class GeneratorWindow:
    """A ponthalmaz-generátor ablaka."""

    # -----------------------------------------------------------------------
    # 1. Az ablak felépítése
    # -----------------------------------------------------------------------
    def __init__(self, root, on_start_analysis):
        """root: a Tk ablak.
        on_start_analysis: a "Vizsgálat indítása" gomb ezt a függvényt hívja
        meg a ponthalmazzal és a generálás adataival (lásd _main.py)."""
        self.root = root
        self.on_start_analysis = on_start_analysis
        self.points = None            # a legutóbb generált pontok
        self.generation_info = None   # a hozzájuk tartozó generálási adatok
        self.resize_job = None        # az átméretezés utáni újrarajzolás időzítője
        root.title("Ponthalmaz-generátor")

        # az ablak két oszlopa: bal oldalon a panel, jobb oldalon a rajz;
        # átméretezéskor csak a rajz (1. oszlop) nő/zsugorodik
        root.columnconfigure(1, weight=1)
        root.rowconfigure(0, weight=1)
        self.panel = ttk.Frame(root, padding=10)
        self.panel.grid(row=0, column=0, sticky="ns")

        # --- 1. csoport: alapadatok ---
        group = self.add_group(0, "Alapadatok")
        self.var_n = tk.StringVar(value="50")
        self.var_radius = tk.StringVar(value="100")
        self.var_seed = tk.StringVar(value=str(new_seed()))
        self.add_field(group, 0, "Pontok száma:", self.var_n)
        self.add_field(group, 1, "Névleges sugár:", self.var_radius)
        self.add_field(group, 2, "Seed (üres = mindig új):", self.var_seed)

        # --- 2. csoport: lefedettség ---
        group = self.add_group(1, "Lefedettség")
        self.var_full_circle = tk.BooleanVar(value=True)
        ttk.Radiobutton(group, text="Teljes kör", variable=self.var_full_circle,
                        value=True).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(group, text="Ívdarab", variable=self.var_full_circle,
                        value=False).grid(row=0, column=1, sticky="w")
        self.var_arc_start = tk.StringVar(value="30")
        self.var_arc_end = tk.StringVar(value="200")
        self.arc_start_entry = self.add_field(group, 1, "Ív kezdőszöge (°):", self.var_arc_start)
        self.arc_end_entry = self.add_field(group, 2, "Ív végszöge (°):", self.var_arc_end)
        self.var_angle_mode = tk.StringVar(value=ANGLE_MODES[0])
        self.add_choice(group, 3, "Szögeloszlás:", self.var_angle_mode, ANGLE_MODES)

        # --- alakhiba ---
        group = self.add_group(2, "Alakhiba")
        self.var_shape = tk.StringVar(value=SHAPES[0])
        self.add_choice(group, 0, "Típus:", self.var_shape, SHAPES)
        self.var_ratio = tk.StringVar(value="0.8")
        self.var_sides = tk.StringVar(value="6")
        self.ratio_entry = self.add_field(group, 1, "Ellipszis aránya (b/a):", self.var_ratio)
        self.sides_entry = self.add_field(group, 2, "Sokszög oldalszáma:", self.var_sides)

        # --- véletlen hiba ---
        group = self.add_group(3, "Véletlen hiba (sugárirányú)")
        self.var_noise = tk.StringVar(value="2")
        self.add_field(group, 0, "Mérték ±e (0 = nincs):", self.var_noise)

        # --- egyéb hibák ---
        group = self.add_group(4, "Egyéb hibák")
        self.var_outlier = tk.StringVar(value="0")
        self.add_field(group, 0, "Kiugró pontok aránya (%):", self.var_outlier)

        # --- gombok ---
        buttons = ttk.Frame(self.panel)
        buttons.grid(row=5, column=0, pady=(6, 2), sticky="ew")
        ttk.Button(buttons, text="Új véletlen halmaz",
                   command=self.new_random_set).pack(side="left", expand=True, fill="x")
        ttk.Button(buttons, text="Vizsgálat indítása",
                   command=self.start_analysis).pack(side="left", expand=True, fill="x")

        # --- hibaüzenet + ponthalmaz leírása ---
        self.var_error = tk.StringVar()
        ttk.Label(self.panel, textvariable=self.var_error, foreground="red",
                  wraplength=360).grid(row=6, column=0, sticky="w")
        self.var_info = tk.StringVar()
        ttk.Label(self.panel, textvariable=self.var_info,
                  wraplength=360).grid(row=7, column=0, pady=4, sticky="w")

        # --- rajzterület ---
        self.canvas = tk.Canvas(root, width=CANVAS_SIZE, height=CANVAS_SIZE, bg="white")
        self.canvas.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        self.canvas.bind("<Configure>", self.on_resize)

        # --- első generálás ---
        self.update_field_states()
        self.generate()

        # --- mező változásakor újragenerálás ---
        all_variables = [self.var_n, self.var_radius, self.var_seed,
                         self.var_full_circle, self.var_arc_start, self.var_arc_end,
                         self.var_angle_mode, self.var_shape, self.var_ratio,
                         self.var_sides, self.var_noise, self.var_outlier]
        for variable in all_variables:
            variable.trace_add("write", self.on_field_change)

    # -----------------------------------------------------------------------
    # 2. A panel elemei (mezőcsoport, beviteli mező, legördülő lista)
    # -----------------------------------------------------------------------
    def add_group(self, row, title):
        """Egy címmel ellátott keret a panel adott sorában; ebbe kerülnek a mezők."""
        group = ttk.LabelFrame(self.panel, text=title, padding=(8, 2))
        group.grid(row=row, column=0, sticky="ew", pady=(0, 4))
        group.columnconfigure(1, weight=1)
        return group

    def add_field(self, group, row, label, variable):
        """Felirat + beviteli mező a csoport adott sorában.
        A mező tartalma a variable változóba kerül. Visszaadja a mezőt."""
        ttk.Label(group, text=label).grid(row=row, column=0, sticky="w", pady=1)
        entry = ttk.Entry(group, textvariable=variable, width=10)
        entry.grid(row=row, column=1, padx=(8, 0), pady=1, sticky="e")
        return entry

    def add_choice(self, group, row, label, variable, choices):
        """Felirat + legördülő lista a csoport adott sorában."""
        ttk.Label(group, text=label).grid(row=row, column=0, sticky="w", pady=1)
        ttk.Combobox(group, textvariable=variable, values=choices, state="readonly",
                     width=14).grid(row=row, column=1, padx=(8, 0), pady=1, sticky="e")

    def update_field_states(self):
        """Csak azok a mezők írhatók, amelyeknek most szerepük van:
        az ív mezői csak ívdarabnál, az ellipszis aránya csak ellipszisnél,
        a sokszög oldalszáma csak sokszögnél."""
        if self.var_full_circle.get():
            arc_state = "disabled"
        else:
            arc_state = "normal"
        self.arc_start_entry.configure(state=arc_state)
        self.arc_end_entry.configure(state=arc_state)

        if self.var_shape.get() == "ellipszis":
            self.ratio_entry.configure(state="normal")
        else:
            self.ratio_entry.configure(state="disabled")

        if self.var_shape.get() == "sokszög":
            self.sides_entry.configure(state="normal")
        else:
            self.sides_entry.configure(state="disabled")

    # -----------------------------------------------------------------------
    # 3. Események: mezők változása, gombok
    # -----------------------------------------------------------------------
    def on_field_change(self, *args):
        """Bármelyik mező változásakor hívódik meg (az args-ot a tkinter adja,
        nem használjuk): frissíti a mezők állapotát, és újragenerál."""
        self.update_field_states()
        self.generate()

    def new_random_set(self):
        """Az "Új véletlen halmaz" gomb: új seedet sorsol. A seed mező
        változása miatt a ponthalmaz magától újragenerálódik."""
        self.var_seed.set(str(new_seed()))

    def start_analysis(self):
        """A "Vizsgálat indítása" gomb: a ponthalmaz átadása a _main.py-nak."""
        if self.var_error.get() != "":
            return          # hibás mező van: a hibaüzenet már látszik
        # másolatot adunk át, hogy a vizsgálat ne módosíthassa az itteni pontokat
        self.on_start_analysis(self.points.copy(), self.generation_info)

    # -----------------------------------------------------------------------
    # 4. A ponthalmaz generálása és leírása
    # -----------------------------------------------------------------------
    def generate(self):
        """Beolvassa a mezőket, és legenerálja a ponthalmazt.
        Hibás mezőnél kiírja a hibát (pirossal), és a régi ponthalmaz marad."""
        try:
            # a mezők beolvasása
            n = read_int(self.var_n.get(), "A pontok száma")
            radius = read_float(self.var_radius.get(), "A névleges sugár")
            full_circle = self.var_full_circle.get()
            arc_start = 0.0
            arc_end = 360.0
            if not full_circle:
                arc_start = read_float(self.var_arc_start.get(), "Az ív kezdőszöge")
                arc_end = read_float(self.var_arc_end.get(), "Az ív végszöge")
            shape = self.var_shape.get()
            ellipse_ratio = 0.8
            polygon_sides = 6
            if shape == "ellipszis":
                ellipse_ratio = read_float(self.var_ratio.get(), "Az ellipszis aránya")
            if shape == "sokszög":
                polygon_sides = read_int(self.var_sides.get(), "A sokszög oldalszáma")
            noise = read_float(self.var_noise.get(), "A véletlen hiba mértéke")
            outlier_percent = read_float(self.var_outlier.get(), "A kiugró pontok aránya")
            if self.var_seed.get().strip() == "":
                seed = None         # üres mező: minden generálásnál új seed
            else:
                seed = read_int(self.var_seed.get(), "A seed")

            # a generálás (a tartalmi ellenőrzést a generátor végzi)
            points, generation_info = generate_points(
                n, radius, full_circle, arc_start, arc_end, self.var_angle_mode.get(),
                shape, ellipse_ratio, polygon_sides, noise, outlier_percent, seed)

        except ValueError as error:
            self.var_error.set(str(error))
            return

        self.var_error.set("")
        self.points = points
        self.generation_info = generation_info
        self.var_info.set(self.describe(generation_info))
        self.draw()

    def describe(self, info):
        """Rövid szöveges leírás a ponthalmazról (a panel alján)."""
        if info["full_circle"]:
            coverage = "teljes kör"
        else:
            coverage = f"ív {info['arc_start']:g}° → {info['arc_end']:g}° ({info['arc_span']:g}°)"

        if info["shape"] == "ellipszis":
            shape = f"ellipszis (b/a = {info['ellipse_ratio']:g})"
        elif info["shape"] == "sokszög":
            shape = f"szabályos sokszög ({info['polygon_sides']} oldal)"
        else:
            shape = "nincs"

        if info["noise"] > 0:
            noise = f"±{info['noise']:g}"
        else:
            noise = "nincs"

        return (f"{info['n']} pont, névleges sugár: {info['radius']:g}\n"
                f"Lefedettség: {coverage}, {info['angle_mode']} szögek\n"
                f"Alakhiba: {shape}\n"
                f"Véletlen hiba: {noise}\n"
                f"Kiugró pontok: {info['outlier_count']} db (piros)\n"
                f"Seed: {info['seed']}")

    # -----------------------------------------------------------------------
    # 5. Rajzolás
    # -----------------------------------------------------------------------
    def draw(self):
        """Kirajzolja a névleges kört (szaggatott), ívnél az ív két határát,
        a középpontot és a pontokat (a kiugró pontokat pirossal).
        A méretarány a rajzterület aktuális méretéhez igazodik."""
        canvas = self.canvas
        canvas.delete("all")
        if self.points is None:
            return
        info = self.generation_info
        center_x, center_y = info["center"]

        # a rajzterület mérete (ha az ablak még nem jelent meg, a kezdeti méret)
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        if width <= 1 or height <= 1:
            width = CANVAS_SIZE
            height = CANVAS_SIZE
        middle_x = width / 2
        middle_y = height / 2

        # méretarány: a névleges kör és a legtávolabbi pont is férjen be
        farthest = info["radius"]
        for x, y in self.points:
            farthest = max(farthest, math.hypot(x - center_x, y - center_y))
        scale = (min(width, height) / 2 - MARGIN) / farthest

        # a névleges kör (szaggatott)
        r = info["radius"] * scale
        canvas.create_oval(middle_x - r, middle_y - r, middle_x + r, middle_y + r,
                           outline=GUIDE_COLOR, dash=(4, 4))

        # ívdarabnál az ív két határa (pontozott sugarak)
        if not info["full_circle"]:
            for angle_deg in [info["arc_start"], info["arc_end"]]:
                angle = math.radians(angle_deg)
                end_x = middle_x + farthest * scale * math.cos(angle)
                end_y = middle_y - farthest * scale * math.sin(angle)
                canvas.create_line(middle_x, middle_y, end_x, end_y,
                                   fill=GUIDE_COLOR, dash=(1, 3))

        # kis kereszt a névleges középpontban
        canvas.create_line(middle_x - 6, middle_y, middle_x + 6, middle_y, fill=GUIDE_COLOR)
        canvas.create_line(middle_x, middle_y - 6, middle_x, middle_y + 6, fill=GUIDE_COLOR)

        # a pontok (a képernyőn az y lefelé nő, ezért a mínusz jel)
        for i in range(len(self.points)):
            x = middle_x + (self.points[i][0] - center_x) * scale
            y = middle_y - (self.points[i][1] - center_y) * scale
            if i in info["outlier_indices"]:
                color = OUTLIER_COLOR
            else:
                color = POINT_COLOR
            canvas.create_oval(x - POINT_SIZE, y - POINT_SIZE, x + POINT_SIZE, y + POINT_SIZE,
                               fill=color, outline="")

    # -----------------------------------------------------------------------
    # 6. Átméretezés
    # -----------------------------------------------------------------------
    def on_resize(self, event):
        """A rajzterület átméretezésekor újrarajzolunk. Húzás közben ez sokszor
        meghívódik, ezért csak 30 ms-mal az utolsó változás után rajzolunk."""
        if self.resize_job is not None:
            self.root.after_cancel(self.resize_job)
        self.resize_job = self.root.after(30, self.redraw_after_resize)

    def redraw_after_resize(self):
        """Átméretezés után újrarajzolja a ponthalmazt és a gombokat."""
        self.resize_job = None
        self.draw()
        refresh_widgets(self.root)


def refresh_widgets(widget):
    """macOS-en átméretezés után a gombok néha nem rajzolódnak újra.
    Ha egy beállítást önmagára állítunk (ez semmit nem változtat), a tkinter
    újrarajzolja az elemet. A függvény a belső elemekre is meghívja magát."""
    for child in widget.winfo_children():
        if isinstance(child, ttk.Widget):
            child["cursor"] = child["cursor"]
        refresh_widgets(child)
