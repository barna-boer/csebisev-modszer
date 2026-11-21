"""
Csebisev-körillesztés keresőmódszerekkel – a program indítója.

Futtatás (a projekt gyökeréből):  python3 main.py

A program menete:
  1. megnyílik a ponthalmaz-generátor ablaka (code_base/gui.py),
  2. a "Vizsgálat indítása" gombra a generátor elrejtőzik, és megnyílik a
     vizsgáló ablak (code_base/vizsgalo_gui.py) a generált ponthalmazzal,
  3. a "Vissza a generátorhoz" gombra a vizsgáló ablak bezárul, és újra a
     generátor látszik (a beállított mezőkkel és ponthalmazzal),
  4. a vizsgáló ablak bezárásakor (az ablak X gombjával) a program kilép.

A két ablakot ez a fájl köti össze, így egyik sem kell, hogy tudjon a
másikról.
"""

import tkinter as tk

from code_base.gui import App
from code_base.vizsgalo_gui import VizsgaloApp


# ===========================================================================
# 1. A program: a két ablak és az átváltás közöttük
# ===========================================================================
class Program:
    """A program két ablaka: a generátor (ez a fő ablak) és a vizsgáló
    ablak, amely csak a "Vizsgálat indítása" gomb után nyílik meg."""

    def __init__(self):
        """Létrehozza a fő ablakot, és megnyitja benne a generátort."""
        self.root = tk.Tk()
        self.analysis_window = None     # a vizsgáló ablak (ha nyitva van)
        App(self.root, self.open_analysis)

    def open_analysis(self, points, ground_truth):
        """A "Vizsgálat indítása" gomb: elrejti a generátort, és megnyitja a
        vizsgáló ablakot a ponthalmazzal."""
        self.root.withdraw()                         # a generátor elrejtése
        self.analysis_window = tk.Toplevel(self.root)
        VizsgaloApp(self.analysis_window, points, ground_truth,
                    self.close_program, self.back_to_generator)

    def back_to_generator(self):
        """A "Vissza a generátorhoz" gomb: bezárja a vizsgáló ablakot, és
        újra megjeleníti a generátort."""
        if self.analysis_window is not None:
            self.analysis_window.destroy()
            self.analysis_window = None
        self.root.deiconify()                        # a generátor megjelenítése

    def close_program(self):
        """A vizsgáló ablak bezárása (X): a fő ablakot is bezárja, így a
        program kilép (nem marad rejtett ablak)."""
        self.root.destroy()

    def run(self):
        """Elindítja az eseményhurkot: a program addig fut, amíg be nem
        zárják."""
        self.root.mainloop()


# ===========================================================================
# 2. Indítás
# ===========================================================================
if __name__ == "__main__":
    program = Program()
    program.run()
