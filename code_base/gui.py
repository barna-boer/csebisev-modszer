"""
Grafikus felület a ponthalmaz-generátorhoz (Csebisev-elv).

A program egy egyszerű ablakban megjeleníti a generált pontokat.
Megadható:
  - a pontok száma és a névleges kör sugara,
  - a lefedettség: teljes kör vagy ívdarab (kezdő- és végszög), valamint
    hogy a pontok szöge véletlen vagy egyenletes közű legyen,
  - az alakhiba típusa (nincs / ellipszis / szabályos sokszög)
    és paraméterei,
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

import numpy as np

from code_base.ponthalmaz_generator import (ANGLE_MODES, SHAPE_DEFAULTS,
                                            SHAPE_TYPES, generate_points)


# ===========================================================================
# 1. Beállítások (a rajz és a mezők állandói)
# ===========================================================================
CANVAS_SIZE = 640          # a rajzterület kezdeti mérete képpontban
VIEW_MARGIN = 15           # üres sáv a rajz széle körül (képpontban)
POINT_RADIUS = 3           # egy pont kirajzolt mérete (képpontban, nem skálázódik)
POINT_COLOR = "#1f6fd0"
OUTLIER_COLOR = "#d03a1f"
GUIDE_COLOR = "#aaaaaa"

# az alakhibák GUI-ban állítható paraméterei: (kulcs, felirat, típus)
SHAPE_FIELDS = {
    "none": [],
    "ellipse": [("ratio", "Félátlók aránya (b/a):", float)],
    "polygon": [("sides", "Oldalszám:", int)],
}
AUTO_DELAY_MS = 150        # módosítás után ennyi idővel generál újra (gépelés
                           # közben ne minden egyes leütésre)


# ===========================================================================
# 2. Segédfüggvények (seed sorsolása, mezők beolvasása)
# ===========================================================================
def _new_seed():
    """Új véletlen seed az "Új véletlen halmaz" gombhoz."""
    return random.randrange(2**31 - 1)


def _parse_float(text, name):
    """Egy mező szövegét valós számmá alakítja (tizedesvesszőt is elfogad).
    Hibás szövegnél ValueError, a hibaüzenetben a mező nevével (name)."""
    try:
        return float(text.strip().replace(",", "."))
    except ValueError:
        raise ValueError(f"{name}: szám kell.")


def _parse_int(text, name):
    """Egy mező szövegét egész számmá alakítja.
    Hibás szövegnél ValueError, a hibaüzenetben a mező nevével (name)."""
    try:
        return int(text.strip())
    except ValueError:
        raise ValueError(f"{name}: egész szám kell.")


# ===========================================================================
# 3. A generátor ablaka
# ===========================================================================
class App:
    """A ponthalmaz-generátor ablaka.

    Bal oldalon a generálás paraméterei (mezők, választók, gombok), jobb
    oldalon a generált ponthalmaz rajza. Bármelyik mező módosításakor a
    ponthalmaz automatikusan újragenerálódik."""

    def __init__(self, root, on_analyze):
        """root: a Tk gyökérablak.
        on_analyze(points, ground_truth): a "Vizsgálat indítása" gombra
        hívódik a jelenlegi ponthalmazzal (lásd main.py)."""
        self.root = root
        self.on_analyze = on_analyze
        root.title("Ponthalmaz-generátor")

        self.points = None        # a legutóbb generált pontok
        self.ground_truth = None  # a hozzájuk tartozó generálási adatok
        self._redraw_job = None   # átméretezéskor késleltetett újrarajzolás
        self._generate_job = None # módosításkor késleltetett újragenerálás

        # --- az ablak elrendezése ---
        # az ablak átméretezésekor a rajzterület (1. oszlop) nőjön/zsugorodjon
        root.columnconfigure(1, weight=1)
        root.rowconfigure(0, weight=1)

        # --- bal oldali vezérlőpanel ---
        panel = ttk.Frame(root, padding=10)
        panel.grid(row=0, column=0, sticky="ns")

        # alapadatok
        box = self._add_group(panel, 0, "Alapadatok")
        self.var_n = tk.StringVar(value="50")
        self.var_radius = tk.StringVar(value="100")
        # a seed miatt minden módosításnál ugyanazok a véletlen szögek és zajok
        # maradnak, így csak a módosított paraméter hatása látszik
        self.var_seed = tk.StringVar(value=str(_new_seed()))
        self._add_field(box, 0, "Pontok száma:", self.var_n)
        self._add_field(box, 1, "Névleges sugár:", self.var_radius)
        self._add_field(box, 2, "Seed (üres = mindig új):", self.var_seed)

        # lefedettség
        box = self._add_group(panel, 1, "Lefedettség")
        self.var_full = tk.BooleanVar(value=True)
        ttk.Radiobutton(box, text="Teljes kör", variable=self.var_full,
                        value=True, command=self._update_arc_state).grid(
            row=0, column=0, sticky="w")
        ttk.Radiobutton(box, text="Ívdarab", variable=self.var_full,
                        value=False, command=self._update_arc_state).grid(
            row=0, column=1, sticky="w")
        # kezdő- és végszög egy sorban, hogy a panel ne legyen túl magas
        self.var_arc_start = tk.StringVar(value="30")
        self.var_arc_end = tk.StringVar(value="200")
        ttk.Label(box, text="Ív (°), kezdő → vég:").grid(
            row=1, column=0, sticky="w", pady=1)
        arc_row = ttk.Frame(box)
        arc_row.grid(row=1, column=1, padx=(8, 0), pady=1, sticky="e")
        self.arc_entries = [
            ttk.Entry(arc_row, textvariable=self.var_arc_start, width=6),
            ttk.Entry(arc_row, textvariable=self.var_arc_end, width=6),
        ]
        self.arc_entries[0].grid(row=0, column=0)
        ttk.Label(arc_row, text="→").grid(row=0, column=1, padx=4)
        self.arc_entries[1].grid(row=0, column=2)
        self.var_angle_mode = tk.StringVar()
        self._add_combo(box, 2, "Szögeloszlás:", self.var_angle_mode,
                        ANGLE_MODES, "random")
        self._update_arc_state()

        # alakhiba
        box = self._add_group(panel, 2, "Alakhiba")
        self.var_shape = tk.StringVar()
        self._add_combo(box, 0, "Típus:", self.var_shape, SHAPE_TYPES, "none",
                        on_change=self._update_shape_fields)
        # minden típus minden paraméteréhez saját változó, hogy típusváltáskor
        # se vesszenek el a beírt értékek
        self.shape_vars = {
            shape: {key: tk.StringVar(value=f"{SHAPE_DEFAULTS[shape][key]:g}")
                    for key, _label, _kind in fields}
            for shape, fields in SHAPE_FIELDS.items()
        }
        self.shape_param_frame = ttk.Frame(box)
        self.shape_param_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.shape_param_frame.columnconfigure(1, weight=1)
        self._update_shape_fields()

        # véletlen hiba
        box = self._add_group(panel, 3, "Véletlen hiba (sugárirányú)")
        self.var_noise_level = tk.StringVar(value="2")
        self._add_field(box, 0, "Mérték ±e (0 = nincs):", self.var_noise_level)

        # egyéb hibák
        box = self._add_group(panel, 4, "Egyéb hibák")
        self.var_outlier = tk.StringVar(value="0")
        self._add_field(box, 0, "Kiugró pontok aránya (%):", self.var_outlier)

        # gombok (egy sorban)
        buttons = ttk.Frame(panel)
        buttons.grid(row=5, column=0, pady=(6, 2), sticky="ew")
        buttons.columnconfigure((0, 1), weight=1)
        ttk.Button(buttons, text="Új véletlen halmaz",
                   command=lambda: self.var_seed.set(str(_new_seed()))).grid(
            row=0, column=0, padx=(0, 2), sticky="ew")
        ttk.Button(buttons, text="Vizsgálat indítása",
                   command=self.start_analysis).grid(
            row=0, column=1, padx=(2, 0), sticky="ew")

        # a hibaüzenet közvetlenül a gombok alatt, hogy mindig látsszon
        self.var_error = tk.StringVar(value="")
        ttk.Label(panel, textvariable=self.var_error, foreground="red",
                  wraplength=360, justify="left").grid(row=6, column=0,
                                                       sticky="w")

        self.var_info = tk.StringVar(value="")
        ttk.Label(panel, textvariable=self.var_info, wraplength=360,
                  justify="left").grid(row=7, column=0, pady=4, sticky="w")

        # --- jobb oldali rajzterület ---
        self.canvas = tk.Canvas(root, width=CANVAS_SIZE, height=CANVAS_SIZE,
                                bg="white", highlightthickness=1,
                                highlightbackground="gray")
        self.canvas.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        self.canvas.bind("<Configure>", self._on_resize)

        # --- első generálás és automatikus újragenerálás ---
        self.generate()  # induláskor rögtön rajzoljon valamit

        # bármelyik mező módosításakor automatikusan újragenerál
        variables = [self.var_n, self.var_radius, self.var_seed, self.var_full,
                     self.var_arc_start, self.var_arc_end, self.var_angle_mode,
                     self.var_shape, self.var_noise_level, self.var_outlier]
        variables += [var for shape_vars in self.shape_vars.values()
                      for var in shape_vars.values()]
        for var in variables:
            var.trace_add("write", self._schedule_generate)

        # --- legkisebb ablakméret ---
        # ne lehessen használhatatlanul kicsire húzni az ablakot
        root.update_idletasks()
        root.minsize(panel.winfo_reqwidth() + 200, panel.winfo_reqheight() + 20)

    # --- a vezérlőpanel elemei ---
    @staticmethod
    def _add_group(parent, row, title):
        """Egy címmel ellátott keretet (mezőcsoportot) tesz a panel adott
        sorába, és visszaadja, hogy a mezőket bele lehessen tenni."""
        box =ttk.LabelFrame(parent, text=title, padding=(8, 2))
        box.grid(row=row, column=0, sticky="ew", pady=(0, 4))
        box.columnconfigure(1, weight=1)
        return box

    @staticmethod
    def _add_field(parent, row, label, variable):
        """Egy felirat + beviteli mező párt tesz a keret adott sorába; a mező
        tartalma a variable változóban van. Visszaadja a beviteli mezőt."""
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w",
                                           pady=1)
        entry = ttk.Entry(parent, textvariable=variable, width=10)
        entry.grid(row=row, column=1, padx=(8, 0), pady=1, sticky="e")
        return entry

    @staticmethod
    def _add_combo(parent, row, label, variable, choices, default,
                   on_change=None):
        """Legördülő lista a choices szótár magyar megnevezéseivel; a
        kiválasztott kulcsot a _combo_key adja vissza."""
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w",
                                           pady=1)
        combo = ttk.Combobox(parent, textvariable=variable, state="readonly",
                             values=list(choices.values()), width=22)
        combo.grid(row=row, column=1, padx=(8, 0), pady=1, sticky="e")
        variable.set(choices[default])
        if on_change is not None:
            combo.bind("<<ComboboxSelected>>", lambda _e: on_change())
        return combo

    @staticmethod
    def _combo_key(variable, choices):
        """A legördülő listában kiválasztott magyar felirathoz tartozó belső
        kulcsot adja vissza (pl. "Ellipszis" -> "ellipse")."""
        label =variable.get()
        return next(key for key, text in choices.items() if text == label)

    def _update_arc_state(self):
        """Teljes kör esetén letiltja az ív kezdő- és végszögének mezőit,
        ívdarab esetén engedélyezi őket."""
        state ="disabled" if self.var_full.get() else "normal"
        for entry in self.arc_entries:
            entry.configure(state=state)

    def _update_shape_fields(self):
        """Az alakhiba típusához tartozó paramétermezők megjelenítése."""
        for child in self.shape_param_frame.winfo_children():
            child.destroy()
        shape = self._combo_key(self.var_shape, SHAPE_TYPES)
        for row, (key, label, _kind) in enumerate(SHAPE_FIELDS[shape]):
            self._add_field(self.shape_param_frame, row, label,
                            self.shape_vars[shape][key])

    def _schedule_generate(self, *_args):
        """Módosításkor újragenerál; rövid késleltetéssel, hogy gépelés
        közben ne generáljon minden egyes leütésre."""
        if self._generate_job is not None:
            self.root.after_cancel(self._generate_job)
        self._generate_job = self.root.after(AUTO_DELAY_MS, self.generate)

    # --- átméretezés ---
    def _on_resize(self, _event):
        """Átméretezéskor újrarajzol; rövid késleltetéssel, hogy húzás közben
        ne rajzoljon feleslegesen minden egyes képpontnyi változásnál."""
        if self._redraw_job is not None:
            self.root.after_cancel(self._redraw_job)
        self._redraw_job = self.root.after(30, self._redraw)

    def _redraw(self):
        """Átméretezés után (késleltetve) újrarajzolja a ponthalmazt."""
        self._redraw_job = None
        if self.points is not None:
            self.draw()
        self._refresh_widgets(self.root)

    def _refresh_widgets(self, widget):
        """macOS-en (Tk 9, aqua) átméretezés után a ttk gombok és legördülő
        listák néha nem rajzolódnak újra, csak ha fölé visszük az egeret.
        Egy semmit nem változtató configure-hívás kikényszeríti az
        újrarajzolásukat (ugyanúgy, mint az egér fölévitele)."""
        for child in widget.winfo_children():
            if isinstance(child, ttk.Widget):
                child["cursor"] = child["cursor"]
            self._refresh_widgets(child)

    # --- bemenet beolvasása (a tartalmi ellenőrzést a generátor végzi) ---
    def _read_inputs(self):
        """Visszaadja a generate_points paramétereit szótárban, vagy
        ValueError-t dob érthető hibaüzenettel."""
        kwargs = {
            "n": _parse_int(self.var_n.get(), "A pontok száma"),
            "radius": _parse_float(self.var_radius.get(), "A névleges sugár"),
            "angle_mode": self._combo_key(self.var_angle_mode, ANGLE_MODES),
            "noise_level": _parse_float(
                self.var_noise_level.get(), "A véletlen hiba mértéke"),
            "outlier_fraction": _parse_float(
                self.var_outlier.get(), "A kiugró pontok aránya") / 100.0,
        }
        if not self.var_full.get():
            kwargs["arc"] = (
                _parse_float(self.var_arc_start.get(), "A kezdőszög"),
                _parse_float(self.var_arc_end.get(), "A végszög"))

        shape = self._combo_key(self.var_shape, SHAPE_TYPES)
        kwargs["shape"] = shape
        params = {}
        for key, label, kind in SHAPE_FIELDS[shape]:
            parse = _parse_int if kind is int else _parse_float
            params[key] = parse(self.shape_vars[shape][key].get(),
                                label.rstrip(":"))
        kwargs["shape_params"] = params

        seed_text = self.var_seed.get().strip()
        if seed_text:
            kwargs["seed"] = _parse_int(seed_text, "A seed")
        return kwargs

    # --- generálás, a vizsgálat indítása ---
    def generate(self):
        """Beolvassa a mezőket, és legenerálja velük a ponthalmazt.

        Hibás mező esetén piros hibaüzenetet ír ki, és a régi ponthalmaz
        marad meg; siker esetén frissíti az összefoglalót és a rajzot."""
        self._generate_job = None
        try:
            kwargs = self._read_inputs()
            points, ground_truth = generate_points(**kwargs)
        except ValueError as e:
            self.var_error.set(str(e))
            return
        self.var_error.set("")
        self.points, self.ground_truth = points, ground_truth
        self.var_info.set(self._describe(ground_truth, len(points)))
        self.draw()

    def start_analysis(self):
        """A "Vizsgálat indítása" gomb: a jelenlegi ponthalmazt átadja az
        on_analyze függvénynek (azt a main.py adja meg: az nyitja meg a
        vizsgáló ablakot)."""
        # ha egy módosítás utáni újragenerálás még várakozik, most lefuttatjuk,
        # hogy a vizsgáló pontosan a mezőknek megfelelő ponthalmazt kapja
        if self._generate_job is not None:
            self.root.after_cancel(self._generate_job)
            self.generate()
        if self.var_error.get():
            return                      # hibás mező: a hibaüzenet már látszik
        if self.points is None:
            self.var_error.set("Még nincs ponthalmaz: előbb generálj egyet.")
            return
        if self._redraw_job is not None:
            self.root.after_cancel(self._redraw_job)
            self._redraw_job = None
        self.on_analyze(self.points.copy(), self.ground_truth)

    @staticmethod
    def _describe(gt, n_points):
        """Rövid szöveges összefoglaló a ponthalmazról."""
        cov = gt["coverage"]
        if cov["full_circle"]:
            coverage = "teljes kör"
        else:
            coverage = (f"ív {cov['start_deg']:g}° → {cov['end_deg']:g}° "
                        f"({cov['span_deg']:g}°)")
        shape = gt["shape_error"]
        shape_name = SHAPE_TYPES.get(shape["type"], shape["type"])
        params = ", ".join(f"{k} = {v:g}" for k, v in shape["params"].items())
        shape_text = f"{shape_name} ({params})" if params else f"{shape_name}"
        level = gt["random_error"]["level"]
        noise_text = f"±{level:g}" if level > 0 else "nincs"
        out = gt["outliers"]
        lines = [
            f"{n_points} pont, névleges sugár: {gt['radius']:g}",
            f"Lefedettség: {coverage}, "
            f"{ANGLE_MODES.get(cov['angle_mode'], cov['angle_mode'])} szögek",
            f"Alakhiba: {shape_text}",
            f"Véletlen hiba: {noise_text}",
            f"Kiugró pontok: {out['count']} db (piros)",
        ]
        if gt["density"]["cluster_count"]:
            lines.append(f"Sűrített pontok: {gt['density']['cluster_count']} db")
        lines.append(f"Seed: {gt['seed']}")
        return "\n".join(lines)

    # --- rajzolás ---
    def draw(self):
        """Kirajzolja a ponthalmazt a vászonra: a névleges kört (szaggatott),
        ív esetén a határoló sugarakat, a pontokat és pirossal a kiugró
        pontokat. A méretarány a vászon aktuális méretéhez igazodik."""
        c = self.canvas
        c.delete("all")
        gt = self.ground_truth
        points = self.points
        if gt is None or points is None:   # még nincs generált ponthalmaz
            return

        w, h = c.winfo_width(), c.winfo_height()
        if w <= 1 or h <= 1:          # még nincs megjelenítve az ablak
            w = h = CANVAS_SIZE

        # a nézet közepe a névleges kör középpontja; a skálát úgy választjuk,
        # hogy a névleges kör és minden pont beférjen. A tárolt koordináták
        # nem változnak, csak a megjelenítés skálázódik.
        center = np.asarray(gt["center"], dtype=float)
        radius = gt["radius"]
        extent = max(float(np.max(np.hypot(*(points - center).T))), radius, 1e-9)
        scale = (min(w, h) / 2.0 - VIEW_MARGIN) / extent
        cx, cy = w / 2.0, h / 2.0

        # a névleges kör (szaggatott) és az ív határai (pontozott sugarak)
        rs = radius * scale
        c.create_oval(cx - rs, cy - rs, cx + rs, cy + rs,
                      outline=GUIDE_COLOR, dash=(4, 4))
        cov = gt["coverage"]
        if not cov["full_circle"]:
            for deg in (cov["start_deg"], cov["end_deg"]):
                a = math.radians(deg)
                c.create_line(cx, cy, cx + extent * scale * math.cos(a),
                              cy - extent * scale * math.sin(a),
                              fill=GUIDE_COLOR, dash=(1, 3))
        # a kijelző közepe (= a névleges középpont)
        c.create_line(cx - 6, cy, cx + 6, cy, fill=GUIDE_COLOR)
        c.create_line(cx, cy - 6, cx, cy + 6, fill=GUIDE_COLOR)

        outliers = set(gt["outliers"]["indices"])

        # a pontok (a y tengelyt megfordítjuk, mert a képernyőn lefelé nő)
        for i, (x, y) in enumerate(points - center):
            px, py = cx + x * scale, cy - y * scale
            c.create_oval(px - POINT_RADIUS, py - POINT_RADIUS,
                          px + POINT_RADIUS, py + POINT_RADIUS,
                          fill=OUTLIER_COLOR if i in outliers else POINT_COLOR,
                          outline="")
