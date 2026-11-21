"""
Körillesztés Csebisev elve szerint, keresőmódszerekkel.

A feladat: adott ponthalmazhoz keressük azt a két koncentrikus kört, amelyek
közé minden pont befér, és a sugaraik különbsége (a gyűrű szélessége)
minimális. Egy (a, b) középpont esetén
    r = a pontok legkisebb távolsága a középponttól   (belső kör)
    R = a pontok legnagyobb távolsága a középponttól  (külső kör)
    célérték = R - r                                   (ezt minimalizáljuk)
A keresés tehát a kétdimenziós (a, b) síkon zajlik.

Tartalom:
  1. célfüggvény (Objective) és eredményobjektum (FitResult)
  2. négy keresőmódszer azonos felülettel: f(points, max_iter, seed, bounds=None)
       - hegymászó véletlen újraindítással
       - szimulált hűtés
       - genetikus algoritmus (valós kódolás)
       - részecskeraj-optimalizálás (PSO)
  3. fit_all: mind a négy módszer lefuttatása ugyanarra a ponthalmazra

Grafikus kódot (tkinter, matplotlib) nem importál. Csak a NumPy-t használja.
"""

import math
import time
from dataclasses import dataclass, field

import numpy as np


# ===========================================================================
# 1. Célfüggvény és eredményobjektum
# ===========================================================================
class Objective:
    """A Csebisev-célfüggvény egy ponthalmazra: középpont(ok) -> R - r.

    Egyszerre egy középpontot ((2,) alakú tömb) vagy sok középpontot ((m, 2)
    alakú tömb) is kiértékel vektorizáltan. Minden középpont egy
    kiértékelésnek számít; a számlálót az `evaluations` mező tárolja.
    """

    # ennyi távolságot számolunk egyszerre legfeljebb (memóriakorlát a nagy
    # rácsokhoz)
    CHUNK = 2_000_000

    def __init__(self, points):
        self.points = np.asarray(points, dtype=float)
        if self.points.ndim != 2 or self.points.shape[1] != 2 or len(self.points) == 0:
            raise ValueError("A pontok (n, 2) alakú, nem üres tömbben legyenek.")
        self.evaluations = 0

    def __call__(self, centers):
        centers = np.asarray(centers, dtype=float)
        single = centers.ndim == 1
        centers = np.atleast_2d(centers)
        self.evaluations += len(centers)

        widths = np.empty(len(centers))
        step = max(1, self.CHUNK // len(self.points))
        for start in range(0, len(centers), step):
            c = centers[start:start + step]
            # d[i, j] = a j-edik pont távolsága az i-edik középponttól
            d = np.hypot(self.points[:, 0] - c[:, :1], self.points[:, 1] - c[:, 1:])
            widths[start:start + step] = d.max(axis=1) - d.min(axis=1)
        return widths[0] if single else widths


def ring(points, center):
    """Egy középponthoz tartozó gyűrű: (r, R, R - r)."""
    points = np.asarray(points, dtype=float)
    d = np.hypot(points[:, 0] - center[0], points[:, 1] - center[1])
    return float(d.min()), float(d.max()), float(d.max() - d.min())


@dataclass
class FitResult:
    """Egy illesztés eredménye."""
    method: str                 # a módszer neve (magyarul)
    center: tuple               # a megtalált középpont (a, b)
    r_inner: float              # a belső kör sugara (r)
    r_outer: float              # a külső kör sugara (R)
    width: float                # a gyűrű szélessége: R - r (a célérték)
    history: np.ndarray         # a legjobb célérték az egyes iterációk végén
    history_evals: np.ndarray   # a kiértékelések száma az egyes iterációk végén
    evaluations: int            # a célfüggvény-kiértékelések száma összesen
    iterations: int             # a lefutott iterációk száma
    time_s: float               # futásidő másodpercben (time.perf_counter)
    seed: object = None         # a használt seed
    extra: dict = field(default_factory=dict)  # módszerfüggő adatok


def _finish(method, points, best_x, objective, history, history_evals, t0,
            seed=None, extra=None):
    """Összeállítja az eredményobjektumot a keresés végén."""
    elapsed = time.perf_counter() - t0
    r_in, r_out, width = ring(points, best_x)
    return FitResult(
        method=method, center=(float(best_x[0]), float(best_x[1])),
        r_inner=r_in, r_outer=r_out, width=width,
        history=np.asarray(history, dtype=float),
        history_evals=np.asarray(history_evals, dtype=int),
        evaluations=objective.evaluations, iterations=len(history),
        time_s=elapsed, seed=seed, extra=extra or {})


# ===========================================================================
# A keresési tartomány
# ===========================================================================
def default_bounds(points, scale=2.0):
    """A keresési tartomány: a ponthalmaz befoglaló téglalapjának közepe
    körüli négyzet, amelynek oldala a befoglaló téglalap hosszabbik
    oldalának `scale`-szerese.

    Azért négyzet, hogy egy keskeny ívdarabnál se legyen elfajult a
    tartomány. Rövid ívdarabnál az optimális középpont messze lehet a
    pontoktól, ilyenkor a `scale` értékét növelni kell.

    Visszatérés: (lo, hi), két (2,) alakú tömb: a tartomány bal alsó és
    jobb felső sarka.
    """
    points = np.asarray(points, dtype=float)
    if scale <= 0:
        raise ValueError("A keresési tartomány szorzója pozitív legyen.")
    lo, hi = points.min(axis=0), points.max(axis=0)
    mid = (lo + hi) / 2.0
    half = max(float((hi - lo).max()), 1e-9) * scale / 2.0
    return mid - half, mid + half


def _prepare(points, bounds, seed):
    """A módszerek közös előkészítése: célfüggvény, tartomány, véletlen-
    generátor, a tartomány mérete."""
    points = np.asarray(points, dtype=float)
    objective = Objective(points)
    if bounds is None:
        bounds = default_bounds(points)
    lo = np.asarray(bounds[0], dtype=float)
    hi = np.asarray(bounds[1], dtype=float)
    if lo.shape != (2,) or hi.shape != (2,) or np.any(hi <= lo):
        raise ValueError("A keresési tartomány ((a_min, b_min), (a_max, b_max)) legyen.")
    size = float((hi - lo).max())
    rng = np.random.default_rng(seed)
    return points, objective, lo, hi, size, rng


def _check_iter(max_iter):
    if isinstance(max_iter, bool) or not isinstance(max_iter, (int, np.integer)) or max_iter < 1:
        raise ValueError("Az iterációk száma legalább 1 legyen (egész szám).")
    return int(max_iter)


# ===========================================================================
# 2. Keresőmódszerek
#
# Mindegyik felülete: f(points, max_iter, seed, bounds=None) -> FitResult
# Az "iteráció" módszerenként mást jelent (lásd az egyes függvényeknél),
# ezért az eredményben a célfüggvény-kiértékelések számát is jelentjük:
# a módszerek igazságos összehasonlításához ez a jobb mérőszám.
# ===========================================================================
def hill_climbing(points, max_iter=200, seed=None, bounds=None,
                  step0=0.1, min_step=1e-10):
    """Hegymászó keresés véletlen újraindítással.

    Egy iteráció = egy lépés: a jelenlegi pont körül 8 szomszédot nézünk
    meg (8 irányban, `step` távolságra, véletlenül elforgatott
    irányokkal), és a legjobbra lépünk, ha az jobb a jelenleginél
    (8 kiértékelés / iteráció).
    Ha egyik szomszéd sem jobb, a lépésközt felezzük. Ha a lépésköz
    `min_step * tartományméret` alá csökken, egy lokális minimumba
    jutottunk: újraindulunk egy véletlen pontból (+1 kiértékelés).
    """
    max_iter = _check_iter(max_iter)
    t0 = time.perf_counter()
    points, objective, lo, hi, size, rng = _prepare(points, bounds, seed)

    angles = np.arange(8) * (np.pi / 4)
    x = rng.uniform(lo, hi)
    fx = objective(x)
    step = step0 * size
    best_x, best_f = x.copy(), fx
    restarts = 0
    history, history_evals = [], []

    for _ in range(max_iter):
        # 8 szomszéd, a irányokat véletlenül elforgatva (hogy ne csak a
        # tengelyek mentén lépjünk)
        rot = rng.uniform(0.0, np.pi / 4)
        dirs = np.column_stack((np.cos(angles + rot), np.sin(angles + rot)))
        neighbors = np.clip(x + step * dirs, lo, hi)
        f_neighbors = objective(neighbors)
        j = int(np.argmin(f_neighbors))
        if f_neighbors[j] < fx:
            x, fx = neighbors[j], f_neighbors[j]
        else:
            step /= 2.0
        if fx < best_f:
            best_x, best_f = x.copy(), fx
        if step < min_step * size:
            # elakadtunk: újraindítás véletlen pontból
            restarts += 1
            x = rng.uniform(lo, hi)
            fx = objective(x)
            step = step0 * size
            if fx < best_f:
                best_x, best_f = x.copy(), fx
        history.append(best_f)
        history_evals.append(objective.evaluations)

    return _finish("Hegymászó (újraindítással)", points, best_x, objective,
                   history, history_evals, t0, seed, {"restarts": restarts})


def simulated_annealing(points, max_iter=2000, seed=None, bounds=None,
                        sigma0=0.1, sigma_end=1e-9, temp_end_ratio=1e-6):
    """Szimulált hűtés.

    Egy iteráció = egy jelölt kipróbálása (1 kiértékelés / iteráció):
    a jelenlegi pontot normál eloszlású véletlen lépéssel elmozdítjuk.
    A jobb jelöltet mindig elfogadjuk, a rosszabbat exp(-Δ / T)
    valószínűséggel.
    A hőmérséklet (T) és a lépésköz (sigma) is csökken a keresés során
    (p = a futás előrehaladása 0-tól 1-ig):
        T     = T0 * temp_end_ratio ** p,      T0 = a kezdőpont célértéke / 10
        sigma = méret * sigma0 * (sigma_end / sigma0) ** (p ** 2)
    A lépésköz a p² miatt eleinte lassan, a végén gyorsan csökken: így a
    keresésnek van ideje kijutni a célfüggvény lapos részeiről (ha a
    középpont a ponthalmazon kívül van, a szélesség közel állandó), a végén
    pedig finoman pontosít.
    Mivel az ütemezés a max_iter-hez igazodik, egy rövidebb futás nem
    egyszerűen egy hosszabb futás eleje.
    """
    
    max_iter = _check_iter(max_iter)
    t0 = time.perf_counter()
    points, objective, lo, hi, size, rng = _prepare(points, bounds, seed)

    x = rng.uniform(lo, hi)
    fx = objective(x)
    best_x, best_f = x.copy(), fx
    temp0 = max(fx / 10.0, 1e-12 * size)
    accepted = 0
    history, history_evals = [], []

    for k in range(max_iter):
        progress = k / max(max_iter - 1, 1)          # 0 -> 1
        temp = temp0 * temp_end_ratio ** progress
        sigma = size * sigma0 * (sigma_end / sigma0) ** (progress ** 2)

        candidate = np.clip(x + rng.normal(0.0, sigma, size=2), lo, hi)
        f_candidate = objective(candidate)
        delta = f_candidate - fx
        if delta <= 0 or rng.random() < math.exp(-delta / temp):
            x, fx = candidate, f_candidate
            accepted += 1
            if fx < best_f:
                best_x, best_f = x.copy(), fx
        history.append(best_f)
        history_evals.append(objective.evaluations)

    return _finish("Szimulált hűtés", points, best_x, objective, history,
                   history_evals, t0, seed, {"accepted": accepted})


def genetic_algorithm(points, max_iter=200, seed=None, bounds=None,
                      pop_size=40, elite=2, tournament=3, crossover_rate=0.9,
                      mutation_rate=0.3, alpha=0.5):
    """Genetikus algoritmus valós kódolással.

    Egyed = egy középpont (a, b); a rátermettség a célérték (kisebb a jobb).
    Egy iteráció = egy generáció (pop_size kiértékelés / iteráció, plusz
    pop_size a kezdőpopulációra).
      - szelekció:      versengéses (tournament) kiválasztás
      - kereszteződés:  BLX-alfa (a gyermek a két szülő által kijelölt,
                        alfa-val kibővített téglalapból véletlen pont)
      - mutáció:        normál eloszlású elmozdítás, amelynek mérete a
                        generációk során lineárisan csökken
      - elitizmus:      a legjobb `elite` egyed változatlanul továbbjut
    """
    
    max_iter = _check_iter(max_iter)
    t0 = time.perf_counter()
    points, objective, lo, hi, size, rng = _prepare(points, bounds, seed)

    pop = rng.uniform(lo, hi, size=(pop_size, 2))
    fit = objective(pop)
    n_children = pop_size - elite
    history, history_evals = [], []

    for gen in range(max_iter):
        order = np.argsort(fit)
        elites = pop[order[:elite]]

        # szelekció: minden szülőhelyre `tournament` véletlen egyed közül
        # a legjobb
        contestants = rng.integers(0, pop_size, size=(n_children, 2, tournament))
        winners = np.take_along_axis(
            contestants, np.argmin(fit[contestants], axis=2)[..., None], axis=2)[..., 0]
        p1, p2 = pop[winners[:, 0]], pop[winners[:, 1]]

        # kereszteződés (BLX-alfa); ahol nincs kereszteződés, az első szülő
        # másolata a gyermek
        low, high = np.minimum(p1, p2), np.maximum(p1, p2)
        span = high - low
        children = rng.uniform(low - alpha * span, high + alpha * span)
        no_cross = rng.random(n_children) >= crossover_rate
        children[no_cross] = p1[no_cross]

        # mutáció
        sigma = size * (0.1 * (1.0 - gen / max_iter) + 1e-6)
        mutate = rng.random(n_children) < mutation_rate
        children[mutate] += rng.normal(0.0, sigma, size=(int(mutate.sum()), 2))
        children = np.clip(children, lo, hi)

        # új populáció: elitek + gyermekek
        pop = np.vstack((elites, children))
        fit = np.concatenate((fit[order[:elite]], objective(children)))
        history.append(float(fit.min()))
        history_evals.append(objective.evaluations)

    best = int(np.argmin(fit))
    return _finish("Genetikus algoritmus", points, pop[best], objective,
                   history, history_evals, t0, seed)


def particle_swarm(points, max_iter=200, seed=None, bounds=None,
                   swarm_size=30, w_start=0.9, w_end=0.4, c1=1.5, c2=1.5,
                   v_max=0.2):
    """Részecskeraj-optimalizálás (PSO).

    Minden részecske egy középpont, sebességgel. Egy iteráció = a raj egy
    lépése (swarm_size kiértékelés / iteráció, plusz swarm_size a
    kezdéshez):
        v = w*v + c1*r1*(saját legjobb - x) + c2*r2*(raj legjobbja - x)
        x = x + v
    A tehetetlenségi súly (w) lineárisan csökken w_start-ról w_end-re, a
    sebesség nagysága legfeljebb v_max * tartományméret.
    """
    max_iter = _check_iter(max_iter)
    t0 = time.perf_counter()
    points, objective, lo, hi, size, rng = _prepare(points, bounds, seed)

    vmax = v_max * size
    x = rng.uniform(lo, hi, size=(swarm_size, 2))
    v = rng.uniform(-vmax, vmax, size=(swarm_size, 2)) * 0.1
    f = objective(x)
    pbest, pbest_f = x.copy(), f.copy()
    g = int(np.argmin(pbest_f))
    history, history_evals = [], []

    for k in range(max_iter):
        w = w_start + (w_end - w_start) * k / max(max_iter - 1, 1)
        r1 = rng.random((swarm_size, 2))
        r2 = rng.random((swarm_size, 2))
        v = w * v + c1 * r1 * (pbest - x) + c2 * r2 * (pbest[g] - x)
        v = np.clip(v, -vmax, vmax)
        x = np.clip(x + v, lo, hi)
        f = objective(x)
        better = f < pbest_f
        pbest[better], pbest_f[better] = x[better], f[better]
        g = int(np.argmin(pbest_f))
        history.append(float(pbest_f[g]))
        history_evals.append(objective.evaluations)

    return _finish("Részecskeraj (PSO)", points, pbest[g], objective, history,
                   history_evals, t0, seed)


# a keresőmódszerek listája (ebben a sorrendben futnak és jelennek meg)
SEARCH_METHODS = [hill_climbing, simulated_annealing, genetic_algorithm,
                  particle_swarm]


# ===========================================================================
# 3. Mind a négy módszer egy ponthalmazon
# ===========================================================================
def fit_all(points, max_iter, seed=1, bounds=None):
    """A négy keresőmódszer lefuttatása ugyanarra a ponthalmazra, ugyanazzal
    a max_iter értékkel és seeddel. A módszerek egymás után futnak, hogy a
    futásidejük mérése ne zavarja egymást.
    Visszatérés: FitResult-ok listája a SEARCH_METHODS sorrendjében."""
    if bounds is None:
        bounds = default_bounds(points)
    return [method(points, max_iter, seed, bounds) for method in SEARCH_METHODS]
