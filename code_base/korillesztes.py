"""
Körillesztés Csebisev elve szerint, keresőmódszerekkel.

Adott ponthalmazhoz keressük azt a két koncentrikus kört, amelyek
közé minden pont befér, és a sugaraik különbsége (a gyűrű szélessége)
minimális. Egy (a, b) középpont esetén
    r = a pontok legkisebb távolsága a középponttól   (belső kör)
    R = a pontok legnagyobb távolsága a középponttól  (külső kör)
    célfüggvény: f(a, b) = R - r                       (ezt minimalizáljuk)
Egy állapot tehát egy (a, b) középpont, a keresés a síkon zajlik.

A négy keresőmódszer az előadások lépései alapján implementálva:
  - hegymászó algoritmus véletlen újraindítással (4. előadás, 45. és 50. dia)
  - szimulált hűtés (4. előadás, 51-53. dia)
  - genetikus algoritmus (4. előadás, 60-66. dia)
  - részecskeraj-optimalizálás, PSO (5. előadás, 22-23. dia)
Mivel minimalizálunk, az előadásbeli "f(s') >= f(s)" (jobb) feltétel itt
"f(s') < f(s)" lesz: a kisebb szélesség a jobb.

Az előadásokban a keresés célállapotnál áll meg. Itt nem tudjuk előre, mekkora
a legkisebb szélesség, ezért a leállási feltétel az iterációk száma (max_iter).

Grafikus kódot (tkinter, matplotlib) nem importál.
"""

import math
import random
import time

import numpy as np


# ===========================================================================
#region 1. Célfüggvény és eredmény
# ===========================================================================
def width_at(points, a, b):
    """A célfüggvény: az (a, b) középpontú gyűrű szélessége, R - r.
    A távolságokat a numpy egyszerre számolja ki az összes pontra."""
    
    distances = np.hypot(points[:, 0] - a, points[:, 1] - b)
    return float(distances.max() - distances.min())

def ring(points, center):
    """Egy középponthoz tartozó gyűrű: (r, R, R - r)."""
    
    points = np.asarray(points, dtype=float)
    distances = np.hypot(points[:, 0] - center[0], points[:, 1] - center[1])
    r = float(distances.min())
    big_r = float(distances.max())
    return r, big_r, big_r - r

class FitResult:
    """Egy keresés eredménye."""

    def __init__(self, method, center, r_inner, r_outer, width, evaluations,
                 time_s):
        """method: a módszer neve; 
        center: a talált középpont (a, b);
        r_inner, r_outer: a belső és a külső kör sugara; width: R - r;
        evaluations: a célfüggvény-kiértékelések száma;
        time_s: a futásidő másodpercben."""

        self.method = method
        self.center = center
        self.r_inner = r_inner
        self.r_outer = r_outer
        self.width = width
        self.evaluations = evaluations
        self.time_s = time_s


def make_result(method, points, a, b, evaluations, start_time):
    """A keresés végén összeállítja az eredményt a legjobb középpontból."""
    
    r, big_r, width = ring(points, (a, b))
    time_s = time.perf_counter() - start_time
    return FitResult(method, (float(a), float(b)), r, big_r, width,
                     evaluations, time_s)

#endregion

# ===========================================================================
#region 2. Közös segédfüggvények
# ===========================================================================
def default_bounds(points, scale=2.0):
    """A keresési tartomány: 
    egy négyzet a ponthalmaz közepe körül, amelynek
    oldala a ponthalmaz szélességének (vagy magasságának) `scale`-szerese.
    Visszatérés: (a_min, a_max, b_min, b_max)."""
    
    points = np.asarray(points, dtype=float)
    x_min, x_max = points[:, 0].min(), points[:, 0].max()
    y_min, y_max = points[:, 1].min(), points[:, 1].max()
    middle_x = (x_min + x_max) / 2
    middle_y = (y_min + y_max) / 2
    half = max(x_max - x_min, y_max - y_min, 1e-9) * scale / 2
    return (float(middle_x - half), float(middle_x + half),
            float(middle_y - half), float(middle_y + half))

def clamp(value, low, high):
    """A value értéket a [low, high] tartományba szorítja."""

    return max(low, min(value, high))

def prepare(points, max_iter, bounds):
    """A módszerek közös előkészítése: ellenőrzi a bemenetet, és visszaadja
    a pontokat numpy tömbként + a keresési tartományt."""
    
    points = np.asarray(points, dtype=float)
    if points.ndim != 2 or points.shape[1] != 2 or len(points) == 0:
        raise ValueError("A pontok (n, 2) alakú, nem üres tömbben legyenek.")
    if max_iter < 1:
        raise ValueError("Az iterációk száma legalább 1 legyen.")
    if bounds is None:
        bounds = default_bounds(points)
    return points, bounds

#endregion

# ===========================================================================
#region 3. Keresőmódszerek

# Mindegyik felülete: f(points, max_iter, seed, bounds = None) -> FitResult
# A seed a véletlenszám-generátor kezdőértéke: ugyanazzal a seeddel mindig
# ugyanaz az eredmény jön ki.
# Egy "iteráció" módszerenként eltér, ezért a 
# célfüggvény- kiértékeléseket is számoljuk a módszerek összehasonlításához
# ===========================================================================

# -------------------------------------------------------------------------
#region 3.1 Hegymászó algoritmus véletlen újraindítással
# -------------------------------------------------------------------------
# a 8 szomszéd iránya: fel, le, jobbra, balra és a 4 átló

DIAG = math.sqrt(2) / 2     #(= cos 45°  ≈ 0.7071)
DIRECTIONS = [(1, 0), (-1, 0), (0, 1), (0, -1),
              (DIAG, DIAG), (DIAG, -DIAG),
              (-DIAG, DIAG), (-DIAG, -DIAG)]

HC_START_STEP = 0.1    # a kezdő lépésköz a tartomány méretéhez képest
HC_MIN_STEP = 1e-10    # ennél kisebb lépésköznél lokális optimumon vagyunk


def hill_climbing(points, max_iter=200, seed=None, bounds=None):
    """Hegymászó algoritmus véletlen újraindítással.

    1) Legyen s egy véletlen kezdeti állapot.
    2) Ha a leállási feltétel teljesül (elfogyott a max_iter), állj le.
    3) Állítsd elő s mind a 8 szomszédját (s-től `step` távolságra);
       ha a legjobb s' szomszéd jobb, mint s, akkor legyen s = s'.
       Ha egyik sem jobb, felezzük a lépésközt (közelebbi szomszédokat
       nézünk). Ha a lépésköz már nagyon kicsi, lokális optimumon vagyunk:
       véletlen újraindítás ("sörétes puska" elv, 50. dia).
    Egy iteráció = a 8 szomszéd megvizsgálása (8 kiértékelés).
    """
    start_time = time.perf_counter()
    points, (a_min, a_max, b_min, b_max) = prepare(points, max_iter, bounds)
    rnd = random.Random(seed)
    size = a_max - a_min
    evaluations = 0

    # 1) véletlen kezdeti állapot
    a = rnd.uniform(a_min, a_max)
    b = rnd.uniform(b_min, b_max)
    f = width_at(points, a, b)
    evaluations += 1
    step = HC_START_STEP * size

    # az eddigi legjobb állapot (újraindítások miatt kell külön tárolni)
    best_a, best_b, best_f = a, b, f

    # 2) leállási feltétel: max_iter iteráció után vége a keresésnek;
    #    addig ismételjük a 3) lépést
    for iteration in range(max_iter):
        # 3) s összes szomszédja közül a legjobb
        neighbor_a, neighbor_b, neighbor_f = a, b, math.inf
        for dx, dy in DIRECTIONS:
            new_a = clamp(a + step * dx, a_min, a_max)
            new_b = clamp(b + step * dy, b_min, b_max)
            new_f = width_at(points, new_a, new_b)
            evaluations += 1
            if new_f < neighbor_f:
                neighbor_a, neighbor_b, neighbor_f = new_a, new_b, new_f

        if neighbor_f < f:
            # a legjobb szomszéd jobb: odalépünk
            a, b, f = neighbor_a, neighbor_b, neighbor_f
        else:
            # egyik szomszéd sem jobb: közelebbi szomszédokat nézünk
            step = step / 2
            if step < HC_MIN_STEP * size:
                # lokális optimumon vagyunk: véletlen újraindítás
                a = rnd.uniform(a_min, a_max)
                b = rnd.uniform(b_min, b_max)
                f = width_at(points, a, b)
                evaluations += 1
                step = HC_START_STEP * size

        if f < best_f:
            best_a, best_b, best_f = a, b, f

    # az eredmény: a keresés során talált legjobb állapot
    return make_result("Hegymászó (újraindítással)", points, best_a, best_b,
                       evaluations, start_time)
#endregion

# -------------------------------------------------------------------------
#region 3.2 Szimulált hűtés
# -------------------------------------------------------------------------
SA_START_STEP = 0.1     # a kezdő lépésköz a tartomány méretéhez képest
SA_END_STEP = 1e-9      # a lépésköz a futás végén (a tartományhoz képest)
SA_END_RATIO = 1e-6     # a végső hőmérséklet a kezdőnek ekkora része


def simulated_annealing(points, max_iter=2000, seed=None, bounds=None):
    """Szimulált hűtés (4. előadás, 51-53. dia).

    1) Legyen s egy véletlenül választott kezdeti megoldás.
    2) Ha a leállási feltétel teljesül (elfogyott a max_iter), állj le.
    3) Állítsd elő s egy véletlen s' szomszédját;
       ha s' jobb (vagy ugyanolyan), akkor legyen s = s';
       egyébként exp(-(f(s') - f(s)) / T) valószínűséggel legyen s = s';
       csökkentsd a T hőmérsékletet.
    
    Hűtési ütemterv: T minden lépésben ugyanannyiszorosára csökken, úgy, hogy
    a futás végére a kezdőérték SA_END_RATIO-szorosa legyen.
    A szomszéd távolsága (a lépésköz) is csökken: eleinte lassan, a futás
    végén gyorsan. Így a keresésnek van ideje nagy lépésekkel kijutni a
    célfüggvény lapos részeiről (ha a középpont a ponthalmazon kívül van, a
    szélesség majdnem állandó), a végén pedig finoman pontosít.
    Egy iteráció = egy szomszéd kipróbálása (1 kiértékelés).
    """
    start_time = time.perf_counter()
    points, (a_min, a_max, b_min, b_max) = prepare(points, max_iter, bounds)
    rnd = random.Random(seed)
    size = a_max - a_min
    evaluations = 0

    # 1) véletlen kezdeti megoldás
    a = rnd.uniform(a_min, a_max)
    b = rnd.uniform(b_min, b_max)
    f = width_at(points, a, b)
    evaluations += 1
    best_a, best_b, best_f = a, b, f

    # a kezdő hőmérséklet a kezdőállapot szélességének tizede,
    # minden lépésben `cooling`-szorosára csökken
    start_temperature = max(f / 10, 1e-12)
    temperature = start_temperature
    cooling = SA_END_RATIO ** (1 / max_iter)

    # 2) leállási feltétel: max_iter iteráció után vége a keresésnek;
    #    addig ismételjük a 3) lépést
    for iteration in range(max_iter):
        # a lépésköz: a progress (0 -> 1) négyzete miatt eleinte lassan,
        # a végén gyorsan csökken SA_START_STEP-ről SA_END_STEP-re
        progress = iteration / max_iter
        step = size * SA_START_STEP * \
            (SA_END_STEP / SA_START_STEP) ** (progress ** 2)

        # 3) egy véletlen szomszéd: normál eloszlású elmozdulás
        new_a = clamp(a + rnd.gauss(0, step), a_min, a_max)
        new_b = clamp(b + rnd.gauss(0, step), b_min, b_max)
        new_f = width_at(points, new_a, new_b)
        evaluations += 1

        if new_f <= f:
            # jobb (vagy ugyanolyan): elfogadjuk
            a, b, f = new_a, new_b, new_f
        else:
            # rosszabb: csak bizonyos valószínűséggel fogadjuk el
            probability = math.exp(-(new_f - f) / temperature)
            if rnd.random() < probability:
                a, b, f = new_a, new_b, new_f

        if f < best_f:
            best_a, best_b, best_f = a, b, f

        # a hőmérséklet csökkentése
        temperature = temperature * cooling

    # az eredmény: a keresés során talált legjobb állapot
    return make_result("Szimulált hűtés", points, best_a, best_b, evaluations,
                       start_time)
#endregion

# -------------------------------------------------------------------------
#region 3.3 Genetikus algoritmus
# -------------------------------------------------------------------------
GA_POPULATION = 40       # a populáció mérete (az előadás példájában 30-50)
GA_CROSSOVER_RATE = 0.8  # ekkora eséllyel keresztezünk (különben másolat)
GA_MUTATION_RATE = 0.3   # ekkora eséllyel mutálódik egy gyermek
GA_START_MUTATION = 0.1  # a mutáció kezdeti mérete a tartományhoz képest
GA_END_MUTATION = 1e-7   # a mutáció mérete a futás végén (a tartományhoz képest)


def genetic_algorithm(points, max_iter=200, seed=None, bounds=None):
    """Genetikus algoritmus (4. előadás, 60-66. dia).

    Egyed = egy középpont (a, b), a "génjei" az a és a b koordináta.
    Rátermettség: a gyűrű szélessége (a kisebb a jobb).
    1) Töltsd fel a kezdeti populációt véletlen egyedekkel.
    2) Ha a leállási feltétel teljesül (elfogyott a max_iter), állj le,
       és add vissza a legjobb egyedet.
    3) Egyébként válassz ki szülőket a populációból (szelekció);
       alkalmazd rájuk a genetikus műveleteket (kereszteződés, mutáció);
       értékeld ki az új egyedeket;
       dobd el a legrosszabb egyedeket (a régi és az új egyedek közül a
       legjobb GA_POPULATION darab marad meg);
       menj vissza 2)-re.
    Egy iteráció = egy generáció (GA_POPULATION kiértékelés).
    """
    start_time = time.perf_counter()
    points, (a_min, a_max, b_min, b_max) = prepare(points, max_iter, bounds)
    rnd = random.Random(seed)
    size = a_max - a_min
    evaluations = 0

    # 1) kezdeti populáció: minden egyed egy (a, b, f) hármas, ahol f az
    #    egyed szélessége (a rátermettsége)
    population = []
    for i in range(GA_POPULATION):
        a = rnd.uniform(a_min, a_max)
        b = rnd.uniform(b_min, b_max)
        f = width_at(points, a, b)
        evaluations += 1
        population.append((a, b, f))

    # 2) leállási feltétel: max_iter iteráció után vége a keresésnek;
    #    addig ismételjük a 3) lépést
    for generation in range(max_iter):
        # a mutáció mérete generációról generációra csökken
        progress = generation / max_iter
        mutation_size = size * GA_START_MUTATION * \
            (GA_END_MUTATION / GA_START_MUTATION) ** progress

        children = []
        while len(children) < GA_POPULATION:
            # 3) szelekció: két-két véletlen egyed közül a jobbik lesz a
            # szülő (a rátermettebb nagyobb eséllyel, de nem biztosan)
            parent1_a, parent1_b, parent1_f = select_parent(population, rnd)
            parent2_a, parent2_b, parent2_f = select_parent(population, rnd)

            # kereszteződés: az a koordinátát az egyik, a b-t a másik
            # szülőtől örökli a gyermek
            if rnd.random() < GA_CROSSOVER_RATE:
                child_a = parent1_a
                child_b = parent2_b
            else:
                # nincs kereszteződés: a gyermek az első szülő másolata
                child_a = parent1_a
                child_b = parent1_b

            # mutáció: kis véletlen elmozdítás
            if rnd.random() < GA_MUTATION_RATE:
                child_a = child_a + rnd.gauss(0, mutation_size)
                child_b = child_b + rnd.gauss(0, mutation_size)
            child_a = clamp(child_a, a_min, a_max)
            child_b = clamp(child_b, b_min, b_max)

            # az új egyed kiértékelése
            child_f = width_at(points, child_a, child_b)
            evaluations += 1
            children.append((child_a, child_b, child_f))

        # a legrosszabbak eldobása: szélesség szerint sorba rendezzük a régi
        # és az új egyedeket, és csak a legjobbak maradnak
        everyone = population + children
        everyone.sort(key=get_width)
        population = everyone[:GA_POPULATION]

    # a sorba rendezés miatt az első egyed a legjobb
    best_a, best_b, best_f = population[0]
    # az eredmény: a keresés során talált legjobb állapot
    return make_result("Genetikus algoritmus", points, best_a, best_b,
                       evaluations, start_time)


def get_width(individual):
    """Egy (a, b, f) egyed szélessége (f); a populáció sorba rendezéséhez."""
    a, b, f = individual
    return f


def select_parent(population, rnd):
    """Szelekció versengéssel: két véletlen egyed közül a jobbik (a kisebb
    szélességű) lesz a szülő. Visszatérés: (a, b, f)."""
    first_a, first_b, first_f = rnd.choice(population)
    second_a, second_b, second_f = rnd.choice(population)
    if first_f < second_f:
        return first_a, first_b, first_f
    return second_a, second_b, second_f
    
#endregion

# -------------------------------------------------------------------------
#region 3.4 Részecskeraj-optimalizálás (PSO)
# -------------------------------------------------------------------------
PSO_SWARM = 30      # a részecskék száma
PSO_INERTIA = 0.7   # w: mennyire tartja meg a részecske az előző sebességét
PSO_C1 = 1.5        # c1: mennyire húz a részecske saját legjobb helye felé
PSO_C2 = 1.5        # c2: mennyire húz a raj legjobb helye felé


def particle_swarm(points, max_iter=200, seed=None, bounds=None):
    """Részecskeraj-optimalizálás

    Minden részecskének van helye (x = egy középpont), sebessége (v),
    és megjegyzi a saját eddigi legjobb helyét (p). A raj az összes
    részecske legjobb helyét is ismeri (g).
    1) A részecskék véletlen helyről, kis véletlen sebességgel indulnak.
    2) Ha a leállási feltétel teljesül (elfogyott a max_iter), állj le, és
       add vissza g-t.
    3) Egyébként minden részecskére:
           v = w*v + c1*r1*(p - x) + c2*r2*(g - x)    (r1, r2 véletlen 0-1)
           x = x + v
       értékeld ki az új helyet; ha jobb, mint p, legyen p = x;
       ha jobb, mint g, legyen g = x;
       menj vissza 2)-re.
    Egy iteráció = a raj egy lépése (PSO_SWARM kiértékelés).
    """
    start_time = time.perf_counter()
    points, (a_min, a_max, b_min, b_max) = prepare(points, max_iter, bounds)
    rnd = random.Random(seed)
    size = a_max - a_min
    evaluations = 0

    # 1) a pontok kezdeti helye és sebessége
    #    (az i-edik részecske adatai minden listában az i-edik helyen vannak)
    pos_a = []         # a részecskék helye (x)
    pos_b = []
    vel_a = []         # a részecskék sebessége (v)
    vel_b = []
    own_best_a = []    # a részecskék saját eddigi legjobb helye (p)
    own_best_b = []
    own_best_f = []    # és ott a szélesség
    for i in range(PSO_SWARM):
        a = rnd.uniform(a_min, a_max)
        b = rnd.uniform(b_min, b_max)
        f = width_at(points, a, b)
        evaluations += 1
        pos_a.append(a)
        pos_b.append(b)
        vel_a.append(rnd.uniform(-0.01, 0.01) * size)
        vel_b.append(rnd.uniform(-0.01, 0.01) * size)
        own_best_a.append(a)
        own_best_b.append(b)
        own_best_f.append(f)

    # a raj legjobbja (g): a legkisebb szélességű saját legjobb
    swarm_best_a, swarm_best_b, swarm_best_f = own_best_a[0], own_best_b[0], own_best_f[0]
    for i in range(1, PSO_SWARM):
        if own_best_f[i] < swarm_best_f:
            swarm_best_a, swarm_best_b, swarm_best_f = own_best_a[i], own_best_b[i], own_best_f[i]

    # 2) leállási feltétel: max_iter iteráció után vége a keresésnek;
    #    addig ismételjük a 3) lépést
    for iteration in range(max_iter):
        for i in range(PSO_SWARM):
            # 3) az új sebesség: v = w*v + c1*r1*(p - x) + c2*r2*(g - x)
            r1 = rnd.random()
            r2 = rnd.random()
            vel_a[i] = (PSO_INERTIA * vel_a[i]
                        + PSO_C1 * r1 * (own_best_a[i] - pos_a[i])
                        + PSO_C2 * r2 * (swarm_best_a - pos_a[i]))
            r1 = rnd.random()
            r2 = rnd.random()
            vel_b[i] = (PSO_INERTIA * vel_b[i]
                        + PSO_C1 * r1 * (own_best_b[i] - pos_b[i])
                        + PSO_C2 * r2 * (swarm_best_b - pos_b[i]))

            # az új hely: x = x + v (a keresési tartományon belül)
            pos_a[i] = clamp(pos_a[i] + vel_a[i], a_min, a_max)
            pos_b[i] = clamp(pos_b[i] + vel_b[i], b_min, b_max)

            # az új hely kiértékelése
            a = pos_a[i]
            b = pos_b[i]
            f = width_at(points, a, b)
            evaluations += 1

            # ha jobb, mint a saját legjobb (p), az lesz az új p;
            # ha jobb, mint a raj legjobbja (g), az lesz az új g
            if f < own_best_f[i]:
                own_best_a[i], own_best_b[i], own_best_f[i] = a, b, f
                
                if f < swarm_best_f:
                    swarm_best_a, swarm_best_b, swarm_best_f = a, b, f

    # az eredmény: a keresés során talált legjobb állapot
    return make_result("Részecskeraj (PSO)", points, swarm_best_a,
                       swarm_best_b, evaluations, start_time)
#endregion

# --- A módszerek listája ---
# ebben a sorrendben futnak és jelennek meg a táblázatban
SEARCH_METHODS = [hill_climbing, simulated_annealing, genetic_algorithm,
                  particle_swarm]

#endregion

# ===========================================================================
#region 4. Négy módszer megjelenítése egy ponthalmazon
# ===========================================================================
def fit_all(points, max_iter, seed=1, bounds=None):
    """A négy keresőmódszer lefuttatása ugyanarra a ponthalmazra, ugyanazzal
    a max_iter értékkel és seeddel. A módszerek egymás után futnak, hogy a
    futásidejük mérése ne zavarja egymást.
    Visszatérés: FitResult-ok listája a SEARCH_METHODS sorrendjében."""
    
    if bounds is None:
        bounds = default_bounds(points)
    results = []
    for method in SEARCH_METHODS:
        results.append(method(points, max_iter, seed, bounds))
    return results

#endregion