"""
A program indítója.

Futtatás (a projekt gyökeréből):  python3 code_base/_main.py
(vagy VS Code-ban a ▶ gombbal, amikor ez a fájl van megnyitva)

A program menete:
  1. megnyílik a ponthalmaz-generátor ablaka (generator/generator_gui.py),
  2. a "Vizsgálat indítása" gombra a generátor elrejtőzik, és megnyílik a
     vizsgáló ablak (kiertekelo/vizsgalo_gui.py) a generált ponthalmazzal,
  3. a "Vissza a generátorhoz" gombra a vizsgáló ablak bezárul, és újra a
     generátor látszik (a beállított mezőkkel és ponthalmazzal),
  4. a vizsgáló ablak bezárásakor (az ablak X gombjával) a program kilép.

A két ablakot ez a fájl köti össze: mindkét ablak egy-egy függvényt kap
innen, amelyet a megfelelő gomb megnyomásakor meghív.
"""

import tkinter as tk

from generator.generator_gui import GeneratorWindow
from kiertekelo.vizsgalo_gui import AnalysisWindow


class Program:
    """A program két ablaka: a generátor (a fő ablak) és a vizsgáló ablak,
    amely csak a "Vizsgálat indítása" gomb után nyílik meg."""

    def __init__(self):
        """Létrehozza a fő ablakot, és megnyitja benne a generátort."""
        self.root = tk.Tk()
        self.analysis_window = None      # a vizsgáló ablak (ha nyitva van)
        # a generátor az open_analysis függvényt hívja a "Vizsgálat indítása" gombra
        GeneratorWindow(self.root, self.open_analysis)

    def open_analysis(self, points, generation_info):
        """A "Vizsgálat indítása" gomb: elrejti a generátort, és megnyitja a
        vizsgáló ablakot a ponthalmazzal."""
        self.root.withdraw()                              # a generátor elrejtése
        self.analysis_window = tk.Toplevel(self.root)     # új ablak
        AnalysisWindow(self.analysis_window, points, generation_info,
                       self.close_program, self.back_to_generator)

    def back_to_generator(self):
        """A "Vissza a generátorhoz" gomb: bezárja a vizsgáló ablakot, és
        újra megjeleníti a generátort."""
        if self.analysis_window is not None:
            self.analysis_window.destroy()
            self.analysis_window = None
        self.root.deiconify()                             # a generátor megjelenítése

    def close_program(self):
        """A vizsgáló ablak X gombja: a fő ablakot is bezárja, így a program
        kilép (nem marad rejtett ablak)."""
        self.root.destroy()

    def run(self):
        """Elindítja az eseményhurkot: a program addig fut, amíg be nem zárják."""
        self.root.mainloop()


# ===========================================================================
# Indítás
# ===========================================================================
if __name__ == "__main__":
    program = Program()
    program.run()
