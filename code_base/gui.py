"""
Grafikus felület a ponthalmaz-generátorhoz (Csebisev-elv).

A program egy egyszerű ablakban megjeleníti a generált pontokat.
Megadható:
  - a pontok száma és a névleges kör sugara,
  - a lefedettség: teljes kör vagy ívdarab (kezdő- és végszög), valamint
    hogy a pontok szöge véletlen vagy egyenletes közű legyen,
  - az alakhiba típusa (nincs / ellipszis / szabályos sokszög)
    és paramétere,
  - a véletlen hiba mértéke (±e, egyenletes eloszlású sugárirányú zaj),
  - a kiugró pontok aránya,
  - a seed (ugyanazzal a seeddel mindig ugyanaz a ponthalmaz jön ki).

Bármelyik mező módosításakor a ponthalmaz automatikusan újragenerálódik
ugyanazzal a seeddel, így csak a módosított paraméter hatása látszik.
Az "Új véletlen halmaz" gomb új seedet sorsol.

A "Vizsgálat indítása" gomb az aktuális ponthalmazt átadja a main.py-nak,
amely megnyitja vele a vizsgáló felületet (vizsgalo_gui.py).

A pontokat a ponthalmaz_generator.py generate_points függvénye állítja elő.

Futtatás (a projekt gyökeréből):  python3 main.py
"""

import math
import random
import tkinter as tk
from tkinter import ttk

from code_base.ponthalmaz_generator import (ANGLE_MODES, SHAPE_DEFAULTS,
                                            SHAPE_TYPES, generate_points)


# ===========================================================================
# 1. Beállítások
# ===========================================================================
CANVAS_SIZE = 640          # a rajzterület kezdeti mérete képpontban
VIEW_MARGIN = 15           # üres sáv a rajz széle körül (képpontban)
POINT_RADIUS = 3           # egy pont kirajzolt mérete (képpontban)
POINT_COLOR = "#1f6fd0"    # a pontok színe (kék)
OUTLIER_COLOR = "#d03a1f"  # a kiugró pontok színe (piros)
GUIDE_COLOR = "#aaaaaa"    # a névleges kör és a segédvonalak színe (szürke)
AUTO_DELAY_MS = 150        # módosítás után ennyi ezredmásodperc múlva generál
                           # újra (gépelés közben ne minden egyes leütésre)


# ===========================================================================
# 2. Segédfüggvények
# ===========================================================================
def new_seed():
    """Új véletlen seed az "Új véletlen halmaz" gombhoz."""
    return random.randrange(2**31 - 1)


def read_float(text, name):
    """Egy mező szövegét valós számmá alakítja (tizedesvesszőt is elfogad).
    Hibás szövegnél ValueError, a hibaüzenetben a mező nevével (name)."""
    text = text.strip().replace(",", ".")
    try:
        return float(text)
    except ValueError:
        raise ValueError(f"{name}: szám kell.")


def read_int(text, name):
    """Egy mező szövegét egész számmá alakítja.
    Hibás szövegnél ValueError, a hibaüzenetben a mező nevével (name)."""
    try:
        return int(text.strip())
    except ValueError:
        raise ValueError(f"{name}: egész szám kell.")


def key_of_label(choices, label):
    """A legördülő listában látható magyar felirathoz tartozó kulcs
    (pl. "ellipszis" -> "ellipse"). A choices egy szótár: kulcs -> felirat."""
    for key in choices:
        if choices[key] == label:
            return key
    raise ValueError(f"Ismeretlen választás: {label}")


# ===========================================================================
# 3. A generátor ablaka
# ===========================================================================
class App:
    """A ponthalmaz-generátor ablaka.

    Bal oldalon a generálás paraméterei (mezők, választók, gombok), jobb
    oldalon a generált ponthalmaz rajza. Bármelyik mező módosításakor a
    ponthalmaz automatikusan újragenerálódik.

    Az osztály részei:
      3.1 az ablak felépítése
      3.2 a vezérlőpanel elemei (mezőcsoport, beviteli mező, legördülő lista)
      3.3 események (mezők változása, gombok)
      3.4 a ponthalmaz generálása és leírása
      3.5 rajzolás
      3.6 átméretezés"""

    # -----------------------------------------------------------------------
    # 3.1 Az ablak felépítése
    # -----------------------------------------------------------------------
    def __init__(self, root, on_analyze):
        """root: a Tk ablak.
        on_analyze: függvény, amelyet a "Vizsgálat indítása" gomb hív meg a
        ponthalmazzal és a generálás adataival (lásd main.py)."""
        self.root = root
        self.on_analyze = on_analyze
        root.title("Ponthalmaz-generátor")

        self.points = None         # a legutóbb generált pontok
        self.ground_truth = None   # a hozzájuk tartozó generálási adatok
        self.generate_job = None   # a késleltetett újragenerálás azonosítója
        self.redraw_job = None     # a késleltetett újrarajzolás azonosítója

        # --- az ablak elrendezése: bal oldalon a panel, jobb oldalon a rajz ---
        # az ablak átméretezésekor a rajzterület (1. oszlop) nőjön/zsugorodjon
        root.columnconfigure(1, weight=1)
        root.rowconfigure(0, weight=1)
        self.panel = ttk.Frame(root, padding=10)
        self.panel.grid(row=0, column=0, sticky="ns")

        # --- 1. csoport: alapadatok ---
        box = self.add_group(0, "Alapadatok")
        self.var_n = tk.StringVar(value="50")
        self.var_radius = tk.StringVar(value="100")
        # a seed miatt minden módosításnál ugyanazok a véletlen szögek és zajok
        # maradnak, így csak a módosított paraméter hatása látszik
        self.var_seed = tk.StringVar(value=str(new_seed()))
        self.add_field(box, 0, "Pontok száma:", self.var_n)
        self.add_field(box, 1, "Névleges sugár:", self.var_radius)
        self.add_field(box, 2, "Seed (üres = mindig új):", self.var_seed)

        # --- 2. csoport: lefedettség ---
        box = self.add_group(1, "Lefedettség")
        self.var_full = tk.BooleanVar(value=True)
        full_button = ttk.Radiobutton(box, text="Teljes kör",
                                      variable=self.var_full, value=True)
        full_button.grid(row=0, column=0, sticky="w")
        arc_button = ttk.Radiobutton(box, text="Ívdarab",
                                     variable=self.var_full, value=False)
        arc_button.grid(row=0, column=1, sticky="w")

        # kezdő- és végszög egy sorban, hogy a panel ne legyen túl magas
        self.var_arc_start = tk.StringVar(value="30")
        self.var_arc_end = tk.StringVar(value="200")
        ttk.Label(box, text="Ív (°), kezdő → vég:").grid(row=1, column=0,
                                                         sticky="w", pady=1)
        arc_row = ttk.Frame(box)
        arc_row.grid(row=1, column=1, padx=(8, 0), pady=1, sticky="e")
        self.arc_start_entry = ttk.Entry(arc_row, textvariable=self.var_arc_start,
                                         width=6)
        self.arc_start_entry.grid(row=0, column=0)
        ttk.Label(arc_row, text="→").grid(row=0, column=1, padx=4)
        self.arc_end_entry = ttk.Entry(arc_row, textvariable=self.var_arc_end,
                                       width=6)
        self.arc_end_entry.grid(row=0, column=2)

        self.var_angle_mode = tk.StringVar(value=ANGLE_MODES["random"])
        self.add_combo(box, 2, "Szögeloszlás:", self.var_angle_mode, ANGLE_MODES)

        # --- 3. csoport: alakhiba ---
        # mindkét paraméter mezője mindig látszik, de csak a kiválasztott
        # alakhibához tartozó írható
        box = self.add_group(2, "Alakhiba")
        self.var_shape = tk.StringVar(value=SHAPE_TYPES["none"])
        self.add_combo(box, 0, "Típus:", self.var_shape, SHAPE_TYPES)
        self.var_ratio = tk.StringVar(value=str(SHAPE_DEFAULTS["ellipse"]["ratio"]))
        self.var_sides = tk.StringVar(value=str(SHAPE_DEFAULTS["polygon"]["sides"]))
        self.ratio_entry = self.add_field(box, 1, "Ellipszis aránya (b/a):",
                                          self.var_ratio)
        self.sides_entry = self.add_field(box, 2, "Sokszög oldalszáma:",
                                          self.var_sides)

        # --- 4. csoport: véletlen hiba ---
        box = self.add_group(3, "Véletlen hiba (sugárirányú)")
        self.var_noise_level = tk.StringVar(value="2")
        self.add_field(box, 0, "Mérték ±e (0 = nincs):", self.var_noise_level)

        # --- 5. csoport: egyéb hibák ---
        box = self.add_group(4, "Egyéb hibák")
        self.var_outlier = tk.StringVar(value="0")
        self.add_field(box, 0, "Kiugró pontok aránya (%):", self.var_outlier)

        # --- gombok (egy sorban) ---
        buttons = ttk.Frame(self.panel)
        buttons.grid(row=5, column=0, pady=(6, 2), sticky="ew")
        buttons.columnconfigure(0, weight=1)
        buttons.columnconfigure(1, weight=1)
        new_button = ttk.Button(buttons, text="Új véletlen halmaz",
                                command=self.new_random_set)
        new_button.grid(row=0, column=0, padx=(0, 2), sticky="ew")
        analysis_button = ttk.Button(buttons, text="Vizsgálat indítása",
                                     command=self.start_analysis)
        analysis_button.grid(row=0, column=1, padx=(2, 0), sticky="ew")

        # --- hibaüzenet (piros) és a ponthalmaz rövid leírása ---
        self.var_error = tk.StringVar(value="")
        error_label = ttk.Label(self.panel, textvariable=self.var_error,
                                foreground="red", wraplength=360, justify="left")
        error_label.grid(row=6, column=0, sticky="w")
        self.var_info = tk.StringVar(value="")
        info_label = ttk.Label(self.panel, textvariable=self.var_info,
                               wraplength=360, justify="left")
        info_label.grid(row=7, column=0, pady=4, sticky="w")

        # --- jobb oldali rajzterület ---
        self.canvas = tk.Canvas(root, width=CANVAS_SIZE, height=CANVAS_SIZE,
                                bg="white", highlightthickness=1,
                                highlightbackground="gray")
        self.canvas.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        self.canvas.bind("<Configure>", self.on_resize)

        # --- első generálás ---
        self.update_entry_states()
        self.generate()

        # --- automatikus újragenerálás: minden mező változásakor ---
        variables = [self.var_n, self.var_radius, self.var_seed, self.var_full,
                     self.var_arc_start, self.var_arc_end, self.var_angle_mode,
                     self.var_shape, self.var_ratio, self.var_sides,
                     self.var_noise_level, self.var_outlier]
        for variable in variables:
            variable.trace_add("write", self.on_field_change)

        # --- legkisebb ablakméret (ne lehessen túl kicsire húzni) ---
        root.update_idletasks()
        root.minsize(self.panel.winfo_reqwidth() + 200,
                     self.panel.winfo_reqheight() + 20)

    # -----------------------------------------------------------------------
    # 3.2 A vezérlőpanel elemei
    # -----------------------------------------------------------------------
    def add_group(self, row, title):
        """Egy címmel ellátott keretet (mezőcsoportot) tesz a panel adott
        sorába, és visszaadja, hogy a mezőket bele lehessen tenni."""
        box = ttk.LabelFrame(self.panel, text=title, padding=(8, 2))
        box.grid(row=row, column=0, sticky="ew", pady=(0, 4))
        box.columnconfigure(1, weight=1)
        return box

    def add_field(self, box, row, label, variable):
        """Egy felirat + beviteli mező párt tesz a keret adott sorába; a mező
        tartalma a variable változóban van. Visszaadja a beviteli mezőt."""
        ttk.Label(box, text=label).grid(row=row, column=0, sticky="w", pady=1)
        entry = ttk.Entry(box, textvariable=variable, width=10)
        entry.grid(row=row, column=1, padx=(8, 0), pady=1, sticky="e")
        return entry

    def add_combo(self, box, row, label, variable, choices):
        """Egy felirat + legördülő lista a keret adott sorába; a listában a
        choices szótár magyar feliratai szerepelnek."""
        ttk.Label(box, text=label).grid(row=row, column=0, sticky="w", pady=1)
        combo = ttk.Combobox(box, textvariable=variable, state="readonly",
                             values=list(choices.values()), width=22)
        combo.grid(row=row, column=1, padx=(8, 0), pady=1, sticky="e")

    def update_entry_states(self):
        """Csak azok a mezők írhatók, amelyeknek most van szerepük: az ív
        mezői csak ívdarabnál, az ellipszis aránya csak ellipszisnél, a
        sokszög oldalszáma csak sokszögnél."""
        if self.var_full.get():
            self.arc_start_entry.configure(state="disabled")
            self.arc_end_entry.configure(state="disabled")
        else:
            self.arc_start_entry.configure(state="normal")
            self.arc_end_entry.configure(state="normal")

        shape = key_of_label(SHAPE_TYPES, self.var_shape.get())
        if shape == "ellipse":
            self.ratio_entry.configure(state="normal")
        else:
            self.ratio_entry.configure(state="disabled")
        if shape == "polygon":
            self.sides_entry.configure(state="normal")
        else:
            self.sides_entry.configure(state="disabled")

    # -----------------------------------------------------------------------
    # 3.3 Események: mezők változása, gombok
    # -----------------------------------------------------------------------
    def on_field_change(self, *args):
        """Bármelyik mező változásakor hívódik meg (az args-ot a tkinter
        adja, nem használjuk). Rövid késleltetéssel generál újra, hogy gépelés
        közben ne generáljon minden egyes leütésre: ha közben újabb változás
        jön, a korábbi időzítést töröljük."""
        self.update_entry_states()
        if self.generate_job is not None:
            self.root.after_cancel(self.generate_job)
        self.generate_job = self.root.after(AUTO_DELAY_MS, self.generate)

    def new_random_set(self):
        """Az "Új véletlen halmaz" gomb: új seedet sorsol (a seed mező
        változása miatt a ponthalmaz automatikusan újragenerálódik)."""
        self.var_seed.set(str(new_seed()))

    def start_analysis(self):
        """A "Vizsgálat indítása" gomb: a jelenlegi ponthalmazt átadja az
        on_analyze függvénynek (azt a main.py adja meg: az nyitja meg a
        vizsgáló ablakot)."""
        # ha egy módosítás utáni újragenerálás még várakozik, most lefuttatjuk,
        # hogy a vizsgáló pontosan a mezőknek megfelelő ponthalmazt kapja
        if self.generate_job is not None:
            self.root.after_cancel(self.generate_job)
            self.generate()
        if self.var_error.get() != "":
            return                      # hibás mező: a hibaüzenet már látszik
        if self.points is None:
            self.var_error.set("Még nincs ponthalmaz: előbb generálj egyet.")
            return
        if self.redraw_job is not None:
            self.root.after_cancel(self.redraw_job)
            self.redraw_job = None
        self.on_analyze(self.points.copy(), self.ground_truth)

    # -----------------------------------------------------------------------
    # 3.4 A ponthalmaz generálása és leírása
    # -----------------------------------------------------------------------
    def generate(self):
        """Beolvassa a mezőket, és legenerálja velük a ponthalmazt.

        Hibás mező esetén piros hibaüzenetet ír ki, és a régi ponthalmaz
        marad meg; siker esetén frissíti a leírást és a rajzot."""
        self.generate_job = None
        try:
            # --- 1) a mezők beolvasása (a tartalmi ellenőrzést a generátor
            #        végzi) ---
            n = read_int(self.var_n.get(), "A pontok száma")
            radius = read_float(self.var_radius.get(), "A névleges sugár")

            if self.var_full.get():
                arc = None
            else:
                arc_start = read_float(self.var_arc_start.get(), "A kezdőszög")
                arc_end = read_float(self.var_arc_end.get(), "A végszög")
                arc = (arc_start, arc_end)

            angle_mode = key_of_label(ANGLE_MODES, self.var_angle_mode.get())

            shape = key_of_label(SHAPE_TYPES, self.var_shape.get())
            if shape == "ellipse":
                ratio = read_float(self.var_ratio.get(), "Az ellipszis aránya")
                shape_params = {"ratio": ratio}
            elif shape == "polygon":
                sides = read_int(self.var_sides.get(), "A sokszög oldalszáma")
                shape_params = {"sides": sides}
            else:
                shape_params = {}

            noise_level = read_float(self.var_noise_level.get(),
                                     "A véletlen hiba mértéke")
            outlier_percent = read_float(self.var_outlier.get(),
                                         "A kiugró pontok aránya")

            seed_text = self.var_seed.get().strip()
            if seed_text == "":
                seed = None
            else:
                seed = read_int(seed_text, "A seed")

            # --- 2) a generálás ---
            points, ground_truth = generate_points(
                n, radius, arc=arc, angle_mode=angle_mode, shape=shape,
                shape_params=shape_params, noise_level=noise_level,
                outlier_fraction=outlier_percent / 100, seed=seed)
        except ValueError as error:
            self.var_error.set(str(error))
            return

        # --- 3) az eredmény megjelenítése ---
        self.var_error.set("")
        self.points = points
        self.ground_truth = ground_truth
        self.var_info.set(self.describe(ground_truth, len(points)))
        self.draw()

    def describe(self, ground_truth, point_count):
        """Rövid szöveges leírás a ponthalmazról (a panel alján látszik)."""
        coverage = ground_truth["coverage"]
        if coverage["full_circle"]:
            coverage_text = "teljes kör"
        else:
            coverage_text = (f"ív {coverage['start_deg']:g}° → "
                             f"{coverage['end_deg']:g}° ({coverage['span_deg']:g}°)")
        angle_text = ANGLE_MODES[coverage["angle_mode"]]

        shape = ground_truth["shape_error"]["type"]
        params = ground_truth["shape_error"]["params"]
        if shape == "ellipse":
            shape_text = f"ellipszis (b/a = {params['ratio']:g})"
        elif shape == "polygon":
            shape_text = f"szabályos sokszög ({params['sides']} oldal)"
        else:
            shape_text = "nincs"

        level = ground_truth["random_error"]["level"]
        if level > 0:
            noise_text = f"±{level:g}"
        else:
            noise_text = "nincs"

        text = f"{point_count} pont, névleges sugár: {ground_truth['radius']:g}\n"
        text += f"Lefedettség: {coverage_text}, {angle_text} szögek\n"
        text += f"Alakhiba: {shape_text}\n"
        text += f"Véletlen hiba: {noise_text}\n"
        text += f"Kiugró pontok: {ground_truth['outliers']['count']} db (piros)\n"
        text += f"Seed: {ground_truth['seed']}"
        return text

    # -----------------------------------------------------------------------
    # 3.5 Rajzolás
    # -----------------------------------------------------------------------
    def draw(self):
        """Kirajzolja a ponthalmazt a vászonra: a névleges kört (szaggatott),
        ív esetén a határoló sugarakat, a pontokat és pirossal a kiugró
        pontokat. A méretarány a vászon aktuális méretéhez igazodik."""
        canvas = self.canvas
        canvas.delete("all")
        points = self.points
        ground_truth = self.ground_truth
        if points is None or ground_truth is None:   # még nincs ponthalmaz
            return

        # --- 1) a méretarány: mekkora legyen a rajz a vásznon ---
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        if width <= 1 or height <= 1:     # az ablak még nem jelent meg
            width = CANVAS_SIZE
            height = CANVAS_SIZE

        # a rajz közepe a névleges kör középpontja; a méretarányt (scale) úgy
        # választjuk, hogy a névleges kör és minden pont beférjen
        center_x = ground_truth["center"][0]
        center_y = ground_truth["center"][1]
        radius = ground_truth["radius"]
        extent = radius                   # a legtávolabbi pont távolsága
        for point in points:
            distance = math.hypot(point[0] - center_x, point[1] - center_y)
            if distance > extent:
                extent = distance
        scale = (min(width, height) / 2 - VIEW_MARGIN) / extent
        middle_x = width / 2
        middle_y = height / 2

        # --- 2) segédvonalak: névleges kör, az ív határai, a középpont ---
        # a névleges kör (szaggatott)
        r = radius * scale
        canvas.create_oval(middle_x - r, middle_y - r, middle_x + r, middle_y + r,
                           outline=GUIDE_COLOR, dash=(4, 4))

        # ívdarabnál az ív két határa (pontozott sugarak)
        coverage = ground_truth["coverage"]
        if not coverage["full_circle"]:
            for angle_deg in [coverage["start_deg"], coverage["end_deg"]]:
                angle = math.radians(angle_deg)
                end_x = middle_x + extent * scale * math.cos(angle)
                end_y = middle_y - extent * scale * math.sin(angle)
                canvas.create_line(middle_x, middle_y, end_x, end_y,
                                   fill=GUIDE_COLOR, dash=(1, 3))

        # kis kereszt a névleges középpontban
        canvas.create_line(middle_x - 6, middle_y, middle_x + 6, middle_y,
                           fill=GUIDE_COLOR)
        canvas.create_line(middle_x, middle_y - 6, middle_x, middle_y + 6,
                           fill=GUIDE_COLOR)

        # --- 3) a pontok (az y-t kivonjuk, mert a képernyőn az y lefelé nő) ---
        outlier_indices = ground_truth["outliers"]["indices"]
        for i in range(len(points)):
            x = middle_x + (points[i][0] - center_x) * scale
            y = middle_y - (points[i][1] - center_y) * scale
            if i in outlier_indices:
                color = OUTLIER_COLOR
            else:
                color = POINT_COLOR
            canvas.create_oval(x - POINT_RADIUS, y - POINT_RADIUS,
                               x + POINT_RADIUS, y + POINT_RADIUS,
                               fill=color, outline="")

    # -----------------------------------------------------------------------
    # 3.6 Átméretezés
    # -----------------------------------------------------------------------
    def on_resize(self, event):
        """A rajzterület átméretezésekor újrarajzol; rövid késleltetéssel,
        hogy húzás közben ne rajzoljon minden képpontnyi változásnál."""
        if self.redraw_job is not None:
            self.root.after_cancel(self.redraw_job)
        self.redraw_job = self.root.after(30, self.redraw)

    def redraw(self):
        """Átméretezés után újrarajzolja a ponthalmazt és a gombokat."""
        self.redraw_job = None
        self.draw()
        self.refresh_widgets(self.root)

    def refresh_widgets(self, widget):
        """macOS-en átméretezés után a gombok és a legördülő listák néha nem
        rajzolódnak újra, csak ha fölé visszük az egeret. Ha egy beállítást
        önmagára állítunk (ez semmit nem változtat), az újrarajzolja őket.
        A függvény saját magát hívja a belső elemekre is (rekurzió)."""
        for child in widget.winfo_children():
            if isinstance(child, ttk.Widget):
                child["cursor"] = child["cursor"]
            self.refresh_widgets(child)
