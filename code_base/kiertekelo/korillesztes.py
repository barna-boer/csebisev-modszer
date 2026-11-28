"""
Körillesztés Csebisev elve szerint, keresőmódszerekkel.

A feladat: a ponthalmazhoz olyan (a, b) középpontot keresünk, amelyre a
pontokat közrefogó két koncentrikus kör közötti gyűrű a lehető legkeskenyebb.
Egy (a, b) középpontnál:
    r_inner = a legközelebbi pont távolsága     (a belső kör sugara)
    r_outer = a legtávolabbi pont távolsága     (a külső kör sugara)
    szélesség = r_outer - r_inner               (ezt minimalizáljuk)
A keresés egy állapota tehát egy (a, b) pont a síkon.

A három keresőmódszer (az előadás lépései alapján):
  - hegymászó algoritmus véletlen újraindítással (4. előadás, 45. és 50. dia)
  - szimulált hűtés                               (4. előadás, 51-53. dia)
  - genetikus algoritmus                          (4. előadás, 60-66. dia)
Mivel minimalizálunk, az előadásbeli "f(s') >= f(s)" (jobb) feltétel itt
"f(s') < f(s)" lesz: a kisebb szélesség a jobb.

Mindhárom módszer ugyanúgy hívható:
    result = hill_climbing(points, max_iter, seed)
A leállási feltétel az iterációk száma (max_iter), mert a legkisebb
szélességet előre nem ismerjük. Ugyanazzal a seeddel mindig ugyanaz az
eredmény jön ki.

Ebben a fájlban nincs grafikus kód.
"""

import math
import random
import time

import numpy as np


# ===========================================================================
# 1. A célfüggvény
# ===========================================================================
def distances_from(points, a, b):
    """Az összes pont távolsága az (a, b) ponttól.
    A numpy egyszerre számolja ki az összes pontra (gyorsabb, mint egy ciklus)."""
    return np.hypot(points[:, 0] - a, points[:, 1] - b)


def ring_width(points, a, b):
    """A célfüggvény: az (a, b) középpontú gyűrű szélessége (R - r)."""
    distances = distances_from(points, a, b)
    return float(distances.max() - distances.min())


def ring_radii(points, a, b):
    """Az (a, b) középpontú gyűrű két sugara: (belső sugár r, külső sugár R)."""
    distances = distances_from(points, a, b)
    return float(distances.min()), float(distances.max())


# ===========================================================================
# 2. Egy keresés eredménye
# ===========================================================================
class FitResult:
    """Egy keresőmódszer eredménye.

    method_name:  a módszer neve (a táblázatba)
    a, b:         a talált középpont
    r_inner:      a belső kör sugara (r)
    r_outer:      a külső kör sugara (R)
    width:        a gyűrű szélessége (R - r)
    evaluations:  hányszor számoltuk ki a célfüggvényt
    run_time:     a futásidő másodpercben
    history:      iterációnként egy (aktuális szélesség, eddigi legjobb
                  szélesség) pár; ebből készül a futás grafikonja
    """

    def __init__(self, method_name, points, a, b, evaluations, run_time, history):
        self.method_name = method_name
        self.a = a
        self.b = b
        self.r_inner, self.r_outer = ring_radii(points, a, b)
        self.width = self.r_outer - self.r_inner
        self.evaluations = evaluations
        self.run_time = run_time
        self.history = history


# ===========================================================================
# 3. Közös segédfüggvények
# ===========================================================================
def search_area(points):
    """A keresési tartomány: egy négyzet a ponthalmaz közepe körül, amelynek
    oldala a ponthalmaz szélességének (vagy magasságának) kétszerese.
    Visszatérés: (a_min, a_max, b_min, b_max)."""
    x_min, x_max = points[:, 0].min(), points[:, 0].max()
    y_min, y_max = points[:, 1].min(), points[:, 1].max()
    middle_x = (x_min + x_max) / 2
    middle_y = (y_min + y_max) / 2
    half_side = max(x_max - x_min, y_max - y_min)   # a négyzet oldalának fele
    return (middle_x - half_side, middle_x + half_side,
            middle_y - half_side, middle_y + half_side)


def keep_inside(value, low, high):
    """A value értéket a [low, high] tartományon belülre szorítja."""
    return max(low, min(value, high))


# ===========================================================================
# 4. Hegymászó algoritmus véletlen újraindítással
# ===========================================================================
# a 8 szomszéd iránya: jobbra, balra, fel, le és a 4 átló
# (az átlós irányok is 1 hosszúak: cos 45° = sin 45° ≈ 0.7071)
DIAGONAL = math.sqrt(2) / 2
DIRECTIONS = [(1, 0), (-1, 0), (0, 1), (0, -1),
              (DIAGONAL, DIAGONAL), (DIAGONAL, -DIAGONAL),
              (-DIAGONAL, DIAGONAL), (-DIAGONAL, -DIAGONAL)]

HC_START_STEP = 0.1     # a kezdő lépésköz a keresési tartomány méretéhez képest
HC_MIN_STEP = 1e-10     # ennél kisebb lépésköznél lokális optimumon vagyunk


def hill_climbing(points, max_iter, seed):
    """Hegymászó algoritmus véletlen újraindítással.

    1) Legyen s egy véletlen kezdeti állapot.
    2) Ha elfogyott a max_iter iteráció, állj le.
    3) Nézd meg s mind a 8 szomszédját (s-től `step` távolságra).
       Ha a legjobb szomszéd jobb, mint s, lépj oda.
       Ha egyik sem jobb, felezd a lépésközt (közelebbi szomszédok).
       Ha a lépésköz már nagyon kicsi, lokális optimumon vagyunk:
       véletlen újraindítás ("sörétes puska" elv, 50. dia).
    Egy iteráció = 8 szomszéd megvizsgálása (8 kiértékelés).
    """
    start_time = time.perf_counter()
    points = np.asarray(points, dtype=float)
    rng = random.Random(seed)                 # saját véletlenszám-generátor
    a_min, a_max, b_min, b_max = search_area(points)
    area_size = a_max - a_min
    evaluations = 0
    history = []

    # 1) véletlen kezdeti állapot
    a = rng.uniform(a_min, a_max)
    b = rng.uniform(b_min, b_max)
    width = ring_width(points, a, b)
    evaluations += 1
    step = HC_START_STEP * area_size

    # az eddigi legjobb állapot (az újraindítások miatt külön tároljuk)
    best_a, best_b, best_width = a, b, width
    history.append((width, best_width))

    # 2) max_iter iterációig ismételjük a 3) lépést
    for iteration in range(max_iter):
        # 3) a 8 szomszéd közül a legjobb megkeresése
        neighbor_a, neighbor_b, neighbor_width = a, b, math.inf
        for dx, dy in DIRECTIONS:
            new_a = keep_inside(a + step * dx, a_min, a_max)
            new_b = keep_inside(b + step * dy, b_min, b_max)
            new_width = ring_width(points, new_a, new_b)
            evaluations += 1
            if new_width < neighbor_width:
                neighbor_a, neighbor_b, neighbor_width = new_a, new_b, new_width

        if neighbor_width < width:
            # a legjobb szomszéd jobb: odalépünk
            a, b, width = neighbor_a, neighbor_b, neighbor_width
        else:
            # egyik szomszéd sem jobb: közelebbi szomszédokat nézünk
            step = step / 2
            if step < HC_MIN_STEP * area_size:
                # lokális optimumon vagyunk: véletlen újraindítás
                a = rng.uniform(a_min, a_max)
                b = rng.uniform(b_min, b_max)
                width = ring_width(points, a, b)
                evaluations += 1
                step = HC_START_STEP * area_size

        if width < best_width:
            best_a, best_b, best_width = a, b, width
        history.append((width, best_width))

    run_time = time.perf_counter() - start_time
    return FitResult("Hegymászó (újraindítással)", points, best_a, best_b,
                     evaluations, run_time, history)


# ===========================================================================
# 5. Szimulált hűtés
# ===========================================================================
SA_START_STEP = 0.1     # a kezdő lépésköz a keresési tartomány méretéhez képest
SA_END_STEP = 1e-9      # a lépésköz a futás végén (a tartomány méretéhez képest)
SA_END_RATIO = 1e-6     # a végső hőmérséklet a kezdő hőmérséklet ekkora része


def simulated_annealing(points, max_iter, seed):
    """Szimulált hűtés.

    1) Legyen s egy véletlen kezdeti állapot.
    2) Ha elfogyott a max_iter iteráció, állj le.
    3) Válassz s-nek egy véletlen s' szomszédját.
       Ha s' jobb (vagy ugyanolyan), legyen s = s';
       ha rosszabb, csak exp(-(f(s') - f(s)) / T) valószínűséggel.
       Csökkentsd a T hőmérsékletet.

    A hőmérséklet minden lépésben ugyanannyiszorosára csökken, úgy, hogy a
    futás végére a kezdőérték SA_END_RATIO-szorosa legyen.
    A lépésköz (a szomszéd távolsága) is csökken: eleinte lassan, a végén
    gyorsan. Így eleinte nagy lépésekkel bejárja a síkot, a végén pontosít.
    Egy iteráció = egy szomszéd kipróbálása (1 kiértékelés).
    """
    start_time = time.perf_counter()
    points = np.asarray(points, dtype=float)
    rng = random.Random(seed)
    a_min, a_max, b_min, b_max = search_area(points)
    area_size = a_max - a_min
    evaluations = 0
    history = []

    # 1) véletlen kezdeti állapot
    a = rng.uniform(a_min, a_max)
    b = rng.uniform(b_min, b_max)
    width = ring_width(points, a, b)
    evaluations += 1
    best_a, best_b, best_width = a, b, width
    history.append((width, best_width))

    # a kezdő hőmérséklet a kezdőállapot szélességének tizede;
    # minden lépésben `cooling`-szorosára csökken
    temperature = max(width / 10, 1e-12)
    cooling = SA_END_RATIO ** (1 / max_iter)

    # 2) max_iter iterációig ismételjük a 3) lépést
    for iteration in range(max_iter):
        # a lépésköz: progress 0-ról 1-re nő; a négyzete miatt a lépésköz
        # eleinte lassan, a végén gyorsan csökken SA_START_STEP-ről SA_END_STEP-re
        progress = iteration / max_iter
        step = area_size * SA_START_STEP * (SA_END_STEP / SA_START_STEP) ** (progress ** 2)

        # 3) egy véletlen szomszéd (normális eloszlású elmozdulás)
        new_a = keep_inside(a + rng.gauss(0, step), a_min, a_max)
        new_b = keep_inside(b + rng.gauss(0, step), b_min, b_max)
        new_width = ring_width(points, new_a, new_b)
        evaluations += 1

        if new_width <= width:
            # jobb (vagy ugyanolyan): elfogadjuk
            a, b, width = new_a, new_b, new_width
        else:
            # rosszabb: csak bizonyos valószínűséggel fogadjuk el
            probability = math.exp(-(new_width - width) / temperature)
            if rng.random() < probability:
                a, b, width = new_a, new_b, new_width

        if width < best_width:
            best_a, best_b, best_width = a, b, width

        temperature = temperature * cooling      # hűtés
        history.append((width, best_width))

    run_time = time.perf_counter() - start_time
    return FitResult("Szimulált hűtés", points, best_a, best_b,
                     evaluations, run_time, history)


# ===========================================================================
# 6. Genetikus algoritmus
# ===========================================================================
GA_POPULATION = 40        # a populáció mérete (az előadás példájában 30-50)
GA_CROSSOVER_RATE = 0.8   # ekkora eséllyel keresztezünk (különben másolat)
GA_MUTATION_RATE = 0.3    # ekkora eséllyel mutálódik egy gyermek
GA_START_MUTATION = 0.1   # a mutáció kezdeti mérete a tartomány méretéhez képest
GA_END_MUTATION = 1e-7    # a mutáció mérete a futás végén


def crossover_weight(width1, width2):
    """A gyermek helye a szülőket összekötő szakaszon:
    gyermek = szülő1 + t * (szülő2 - szülő1),
    ahol t = 0 az 1. szülő, t = 1 a 2. szülő.

    A súlyt a szülők jósága adja: t = width1 / (width1 + width2).
    Így a gyermek a jobb (kisebb szélességű) szülőhöz kerül közelebb,
    pl. width1 = 2, width2 = 6 esetén t = 0.25.
    Ha mindkét szülő tökéletes (szélesség 0), a gyermek a felezőpont."""
    if width1 + width2 > 0:
        return width1 / (width1 + width2)
    return 0.5


def genetic_algorithm(points, max_iter, seed):
    """Genetikus algoritmus.

    Egy egyed egy (szélesség, a, b) hármas: a "génjei" az a és a b koordináta,
    a rátermettsége a szélesség (a kisebb a jobb). A szélesség áll elöl, így
    a populáció sorba rendezésekor (sort) a legjobb egyed kerül előre.

    1) Töltsd fel a kezdeti populációt véletlen egyedekkel.
    2) Ha elfogyott a max_iter iteráció, állj le, és add vissza a legjobbat.
    3) Válassz véletlenül szülőket, hozz létre belőlük gyermekeket
       (kereszteződés, mutáció), értékeld ki őket, majd a régi és az új
       egyedek közül csak a legjobb GA_POPULATION darab maradjon meg.
    Egy iteráció = egy generáció (GA_POPULATION kiértékelés).
    A history-ba "aktuális" értékként a populáció átlagos szélessége kerül.
    """
    start_time = time.perf_counter()
    points = np.asarray(points, dtype=float)
    rng = random.Random(seed)
    a_min, a_max, b_min, b_max = search_area(points)
    area_size = a_max - a_min
    evaluations = 0
    history = []

    # 1) kezdeti populáció véletlen egyedekből
    population = []
    for i in range(GA_POPULATION):
        a = rng.uniform(a_min, a_max)
        b = rng.uniform(b_min, b_max)
        width = ring_width(points, a, b)
        evaluations += 1
        population.append((width, a, b))
    population.sort()
    history.append((average_width(population), population[0][0]))

    # 2) max_iter generációig ismételjük a 3) lépést
    for generation in range(max_iter):
        # a mutáció mérete generációról generációra csökken
        progress = generation / max_iter
        mutation_size = area_size * GA_START_MUTATION * (GA_END_MUTATION / GA_START_MUTATION) ** progress

        children = []
        while len(children) < GA_POPULATION:
            # 3) két véletlen szülő a populációból (a populációban a túlélés
            # miatt eleve csak a legjobb egyedek vannak)
            parent1 = rng.choice(population)
            parent2 = rng.choice(population)

            # kereszteződés: a gyermek a két szülőt összekötő szakaszon van,
            # a jobb (kisebb szélességű) szülőhöz közelebb;
            # ha nincs kereszteződés, az első szülő másolata
            width1, a1, b1 = parent1
            width2, a2, b2 = parent2
            if rng.random() < GA_CROSSOVER_RATE:
                t = crossover_weight(width1, width2)
                child_a = a1 + t * (a2 - a1)
                child_b = b1 + t * (b2 - b1)
            else:
                child_a = a1
                child_b = b1

            # mutáció: kis véletlen elmozdítás
            if rng.random() < GA_MUTATION_RATE:
                child_a = child_a + rng.gauss(0, mutation_size)
                child_b = child_b + rng.gauss(0, mutation_size)
            child_a = keep_inside(child_a, a_min, a_max)
            child_b = keep_inside(child_b, b_min, b_max)

            # a gyermek kiértékelése
            child_width = ring_width(points, child_a, child_b)
            evaluations += 1
            children.append((child_width, child_a, child_b))

        # a régi és az új egyedek közül csak a legjobbak maradnak meg
        everyone = population + children
        everyone.sort()
        population = everyone[:GA_POPULATION]

        history.append((average_width(population), population[0][0]))

    # a sorba rendezés miatt az első egyed a legjobb
    best_width, best_a, best_b = population[0]
    run_time = time.perf_counter() - start_time
    return FitResult("Genetikus algoritmus", points, best_a, best_b,
                     evaluations, run_time, history)


def average_width(population):
    """A populáció átlagos szélessége (a futás grafikonjához)."""
    total = 0
    for individual in population:
        total = total + individual[0]
    return total / len(population)


# ===========================================================================
# 7. Mindhárom módszer futtatása
# ===========================================================================
# a módszerek listája: ebben a sorrendben futnak és jelennek meg a táblázatban
SEARCH_METHODS = [hill_climbing, simulated_annealing, genetic_algorithm]


def fit_all(points, max_iter, seed):
    """A három keresőmódszer lefuttatása ugyanarra a ponthalmazra,
    ugyanazzal a max_iter értékkel és seeddel.
    Visszatérés: a három FitResult listája (SEARCH_METHODS sorrendjében)."""
    results = []
    for method in SEARCH_METHODS:
        results.append(method(points, max_iter, seed))
    return results
