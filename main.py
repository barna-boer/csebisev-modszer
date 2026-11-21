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
# 1. A két ablak összekötése
# ===========================================================================
def open_analysis(root, points, ground_truth):
    """A generátorablakot elrejti, és megnyitja a vizsgáló ablakot.

    Egyetlen Tk gyökér van: a generátor a gyökérablak maga, a vizsgáló egy
    Toplevel ablak. A vizsgáló bezárásakor a gyökeret is megszüntetjük, így
    a program kilép, és nem marad rejtett ablak. A "Vissza a generátorhoz"
    gombra csak a vizsgáló ablak záródik be, a generátor újra megjelenik."""
    root.withdraw()
    window = tk.Toplevel(root)

    def back_to_generator():
        """Bezárja a vizsgáló ablakot, és újra megjeleníti a generátort."""
        window.destroy()
        root.deiconify()

    VizsgaloApp(window, points, ground_truth, on_close=root.destroy,
                on_back=back_to_generator)


# ===========================================================================
# 2. Indítás
# ===========================================================================
def main():
    """Elindítja a programot: létrehozza a Tk gyökérablakot, megnyitja benne
    a generátort, és elindítja az eseményhurkot (az ablak bezárásáig fut)."""
    root = tk.Tk()
    App(root, on_analyze=lambda points, gt: open_analysis(root, points, gt))
    root.mainloop()


if __name__ == "__main__":
    main()
