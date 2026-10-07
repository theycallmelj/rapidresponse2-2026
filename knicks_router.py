#!/usr/bin/env python3
"""
knicks_router.py -- rough prototype for "Challenge 2: Knicks Win Chaos".

Density-aware, closure-aware routing of fans leaving Madison Square Garden.
It implements the model in knicks_chaos_proof.tex:

  1. Street grid of Midtown Manhattan (5th-10th Ave x W 26th-W 45th St).
  2. Crowd DENSITY MAP: kernel density estimate of (simulated) phone pings /
     crowd reports around celebration hot spots.
  3. CLOSURE MAP: log-odds fusion (Lemma 1) of official alerts, social-media
     posts and public reports into a posterior mu_e = P(street e closed).
  4. Edge cost  = walking time under the pedestrian fundamental diagram
                  v(rho) = v_free * (1 - rho / rho_jam)   (Greenshields)
                + M * mu_e                                (closure penalty)
  5. Equilibrium assignment (Wardrop / Theorem 1) by the method of
     successive averages: fans routed onto streets add to density, which
     slows those streets, which pushes later fans elsewhere.
  6. Compares naive shortest-path routing with density+closure-aware
     routing under the TRUE closures, and draws a map.

All data are synthetic. Replace `simulate_*` functions with real feeds
(Notify NYC alerts, geotagged posts, 311 / navigation-app reports, and
anonymized phone-density counts) to use it for real.

Usage:  python3 knicks_router.py [--seed 7] [--out knicks_routes.png]
"""
import argparse
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from scipy.stats import gaussian_kde

# ----------------------------------------------------------------- geometry
AVENUES = [5, 6, 7, 8, 9, 10]           # west is larger number
STREETS = list(range(26, 46))           # W 26th .. W 45th
AVE_SPACING_M = 260.0                   # east-west block length (approx.)
ST_SPACING_M = 80.0                     # north-south block length (approx.)
SIDEWALK_W_M = 6.0                      # usable walking width incl. roadway spill


def xy(ave, st):
    """Map (avenue, street) to metres; x grows westward, y grows northward."""
    return ((ave - 5) * AVE_SPACING_M, (st - 26) * ST_SPACING_M)


def build_grid():
    g = nx.DiGraph()
    for a in AVENUES:
        for s in STREETS:
            g.add_node((a, s), pos=xy(a, s))
    for a in AVENUES:
        for s in STREETS:
            for nb in [(a + 1, s), (a, s + 1)]:
                if nb in g:
                    L = math.dist(xy(a, s), xy(*nb))
                    g.add_edge((a, s), nb, length=L)
                    g.add_edge(nb, (a, s), length=L)
    # W 32nd St does not run through the Garden
    g.remove_edges_from([((7, 32), (8, 32)), ((8, 32), (7, 32))])
    return g


# Origins: MSG exits (fans per exit). Destinations: transit hubs + share.
ORIGINS = {(7, 32): 6000, (8, 32): 6000, (8, 31): 4000, (7, 33): 4000}
DESTS = {
    "Port Authority (8th & 42nd)": ((8, 42), 0.25),
    "Grand Central side (5th & 42nd)": ((5, 42), 0.20),
    "Herald Sq / PATH (6th & 34th)": ((6, 34), 0.25),
    "28th St 1 train (7th & 28th)": ((7, 28), 0.15),
    "Hudson Yards 7 train (10th & 34th)": ((10, 34), 0.15),
}

# --------------------------------------------------------- synthetic world
HOTSPOTS = [  # (x, y, spread m, number of pings) celebration crowds
    (*xy(7.5, 32), 120, 2500),   # MSG plaza
    (*xy(7, 34), 100, 1500),     # 7th Ave & 34th
    (*xy(6, 34.5), 90, 1200),    # Herald Square
    (*xy(7, 43.5), 140, 2000),   # Times Square
]
TRUE_CLOSURES = [  # police barricades / parade (both directions)
    ((7, 31), (7, 32)), ((7, 32), (7, 33)), ((7, 33), (7, 34)),   # 7th Ave
    ((7, 34), (8, 34)),                                           # W 34th
    ((6, 34), (6, 35)), ((7, 42), (7, 43)), ((7, 43), (7, 44)),   # Times Sq
]


def simulate_pings(rng):
    pts = [rng.normal([x, y], s, size=(n, 2)) for x, y, s, n in HOTSPOTS]
    background = rng.uniform([0, 0], [xy(10, 45)[0], xy(10, 45)[1]],
                             size=(1500, 2))
    return np.vstack(pts + [background])


def density_field(pings, peak_density=3.8):
    """KDE of pings -> persons per m^2 of walkable street.

    Calibrated so the densest spot (MSG plaza right after the buzzer) is
    `peak_density`; with real data, calibrate with crowd counts instead.
    Returns callable rho(x, y).
    """
    kde = gaussian_kde(pings.T, bw_method=0.12)
    xmax, ymax = xy(10, 45)
    gx, gy = np.meshgrid(np.linspace(0, xmax, 120), np.linspace(0, ymax, 120))
    pdf_max = kde(np.vstack([gx.ravel(), gy.ravel()])).max()
    def rho(xq, yq):
        return peak_density * kde(np.vstack([xq, yq])) / pdf_max
    return rho, kde


def simulate_signals(g, closed, rng, alpha=0.5, p=0.7, q=0.15, r=0.8):
    """Per undirected edge: official alert, social posts (n,k), reports (m,j)."""
    sig = {}
    for u, v in g.edges:
        if (v, u) in sig:
            continue
        c = (u, v) in closed
        alert = c and rng.random() < alpha
        n = rng.poisson(4 if c else 1.5)              # posts near the street
        k = rng.binomial(n, p if c else q)
        m = rng.poisson(5 if c else 2)                # 311 / app reports
        j = rng.binomial(m, r if c else 1 - r)
        sig[(u, v)] = (alert, n, k, m, j)
    return sig


def fuse(sig, prior=0.05, alpha=0.5, p=0.7, q=0.15, r=0.8):
    """Lemma 1: additive log-odds fusion of the three channels."""
    mu = {}
    for e, (alert, n, k, m, j) in sig.items():
        if alert:
            post = 1.0
        else:
            lo = (math.log(prior / (1 - prior)) + math.log(1 - alpha)
                  + k * math.log(p / q) + (n - k) * math.log((1 - p) / (1 - q))
                  + (2 * j - m) * math.log(r / (1 - r)))
            post = 1 / (1 + math.exp(-lo))
        mu[e] = mu[e[::-1]] = post
    return mu


# ------------------------------------------------------------- edge costs
V_FREE, RHO_JAM, V_MIN = 1.34, 5.4, 0.08    # m/s, persons/m^2, m/s
M_PENALTY = 900.0                            # seconds lost at a barricade
PEAK_WINDOW_S = 1800.0                       # fans leave over ~30 minutes


def walk_time(L, rho):
    v = max(V_MIN, V_FREE * (1 - rho / RHO_JAM))
    return L / v


def edge_base_density(g, rho_fn):
    out = {}
    for u, v, d in g.edges(data=True):
        (x0, y0), (x1, y1) = g.nodes[u]["pos"], g.nodes[v]["pos"]
        t = np.linspace(0, 1, 7)
        out[(u, v)] = float(np.mean(rho_fn(x0 + t * (x1 - x0),
                                           y0 + t * (y1 - y0))))
    return out


def added_density(flow, L):
    """Fans per edge over the peak window -> extra persons/m^2 on it."""
    occupancy = flow * (L / V_FREE) / PEAK_WINDOW_S   # people on edge at once
    return occupancy / (L * SIDEWALK_W_M)


def set_costs(g, base_rho, flow, mu=None):
    for u, v, d in g.edges(data=True):
        e = (u, v)
        rho = base_rho[e] + added_density(flow.get(e, 0.0), d["length"])
        d["cost"] = walk_time(d["length"], rho)
        if mu is not None:
            d["cost"] += M_PENALTY * mu.get(e, 0.0)


def od_pairs():
    for o, n in ORIGINS.items():
        for name, (dnode, share) in DESTS.items():
            yield o, name, dnode, n * share


def all_or_nothing(g):
    flow, paths = {}, {}
    for o, name, dn, demand in od_pairs():
        path = nx.shortest_path(g, o, dn, weight="cost")
        paths[(o, name)] = path
        for e in zip(path[:-1], path[1:]):
            flow[e] = flow.get(e, 0.0) + demand
    return flow, paths


def msa_equilibrium(g, base_rho, mu, iters=40):
    """Method of successive averages -> approximate Wardrop equilibrium."""
    set_costs(g, base_rho, {}, mu)
    flow, _ = all_or_nothing(g)
    for n in range(2, iters + 1):
        set_costs(g, base_rho, flow, mu)
        aux, _ = all_or_nothing(g)
        keys = set(flow) | set(aux)
        flow = {e: flow.get(e, 0) + (aux.get(e, 0) - flow.get(e, 0)) / n
                for e in keys}
    set_costs(g, base_rho, flow, mu)
    # relative gap: (current cost - shortest-path cost) / current cost
    tt = sum(f * g.edges[e]["cost"] for e, f in flow.items())
    sp = sum(dem * nx.shortest_path_length(g, o, dn, weight="cost")
             for o, _, dn, dem in od_pairs())
    return flow, (tt - sp) / tt


def realized_time(g, base_rho, flow, closed):
    """Average trip time when evaluated under the TRUE closures."""
    true_mu = {e: (1.0 if e in closed else 0.0) for e in g.edges}
    set_costs(g, base_rho, flow, true_mu)
    total = sum(f * g.edges[e]["cost"] for e, f in flow.items())
    return total / sum(ORIGINS.values())


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="knicks_routes.png")
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)

    g = build_grid()
    closed = set(TRUE_CLOSURES) | {(v, u) for u, v in TRUE_CLOSURES}
    pings = simulate_pings(rng)
    rho_fn, _ = density_field(pings)
    base_rho = edge_base_density(g, rho_fn)
    mu = fuse(simulate_signals(g, closed, rng))

    # 1) Naive: shortest distance, ignores crowds and closures (everyone
    #    follows the same map app default).
    for _, _, d in g.edges(data=True):
        d["cost"] = d["length"]
    naive_flow, _ = all_or_nothing(g)

    # 2) Closure-aware only (fused map, no density).
    zero = {e: 0.0 for e in g.edges}
    closure_flow, _ = msa_equilibrium(g, zero, mu)

    # 3) Density + closure aware equilibrium.
    eq_flow, gap = msa_equilibrium(g, base_rho, mu)

    t_naive = realized_time(g, base_rho, naive_flow, closed)
    t_clos = realized_time(g, base_rho, closure_flow, closed)
    t_eq = realized_time(g, base_rho, eq_flow, closed)

    hits = lambda f: sum(v for e, v in f.items() if e in closed)

    def crowded(f, thresh=2.0):
        """Fan-blocks walked at density > thresh persons/m^2 (crush risk)."""
        return sum(v for e, v in f.items()
                   if base_rho[e] + added_density(v, g.edges[e]["length"]) > thresh)
    tp = sum(1 for e in closed if mu[e] > 0.5)
    fp = sum(1 for e in g.edges if e not in closed and mu[e] > 0.5)
    print("Closure map (directed edges): "
          f"{tp}/{len(closed)} closures detected, {fp} false alarms")
    print(f"Equilibrium relative gap: {gap:.3%}")
    print(f"{'strategy':38s}{'avg trip (min)':>15s}{'into barricades':>17s}"
          f"{'fan-blocks >2 p/m2':>20s}")
    for name, t, f in [("naive shortest path", t_naive, naive_flow),
                       ("closure-aware (fused signals)", t_clos, closure_flow),
                       ("closure + density-aware equilibrium", t_eq, eq_flow)]:
        print(f"{name:38s}{t / 60:15.1f}{hits(f):17,.0f}{crowded(f):20,.0f}")

    # recommended path per destination from the busiest exit
    set_costs(g, base_rho, eq_flow, mu)
    o = (8, 32)
    print(f"\nRecommended routes from MSG exit {o} (8th Ave & W 32nd):")
    for name, (dn, _) in DESTS.items():
        path = nx.shortest_path(g, o, dn, weight="cost")
        t = nx.shortest_path_length(g, o, dn, weight="cost") / 60
        turns = [path[0]] + [b for a, b, c in zip(path, path[1:], path[2:])
                             if (a[0] == b[0]) != (b[0] == c[0])] + [path[-1]]
        desc = " -> ".join(f"{a}th Ave/W{s}" for a, s in turns)
        print(f"  {name:36s} {t:5.1f} min  via {desc}")

    plot(g, pings, rho_fn, mu, closed, eq_flow, args.out)
    print(f"\nMap written to {args.out}")


def plot(g, pings, rho_fn, mu, closed, flow, out):
    xmax, ymax = xy(10, 45)
    X, Y = np.meshgrid(np.linspace(-60, xmax + 60, 220),
                       np.linspace(-60, ymax + 60, 220))
    Z = rho_fn(X.ravel(), Y.ravel()).reshape(X.shape)
    fig, ax = plt.subplots(figsize=(8, 9.5))
    im = ax.imshow(Z, origin="lower", cmap="magma", alpha=0.85,
                   extent=[X.min(), X.max(), Y.min(), Y.max()])
    fig.colorbar(im, ax=ax, shrink=0.6, label="crowd density (persons / m$^2$)")
    fmax = max(flow.values())
    for u, v in g.edges:
        (x0, y0), (x1, y1) = g.nodes[u]["pos"], g.nodes[v]["pos"]
        ax.plot([x0, x1], [y0, y1], color="#666", lw=0.4, zorder=1)
    for (u, v), f in flow.items():
        if f < 50:
            continue
        (x0, y0), (x1, y1) = g.nodes[u]["pos"], g.nodes[v]["pos"]
        ax.plot([x0, x1], [y0, y1], color="#4fc3f7", lw=0.6 + 6 * f / fmax,
                alpha=0.85, zorder=3, solid_capstyle="round")
    for u, v in g.edges:
        if mu[(u, v)] > 0.5:
            (x0, y0), (x1, y1) = g.nodes[u]["pos"], g.nodes[v]["pos"]
            ax.plot([x0, x1], [y0, y1], color="red", lw=3, zorder=4)
            ax.plot((x0 + x1) / 2, (y0 + y1) / 2, "x", color="white",
                    ms=7, mew=2, zorder=5)
    msg = np.array([xy(7, 31), xy(8, 33)])
    ax.add_patch(plt.Rectangle(msg[0] + [20, 0], *(msg[1] - msg[0] - [40, 0]),
                               fc="#f58426", ec="white", zorder=6))
    ax.text(*(msg.mean(0)), "MSG", ha="center", va="center", color="white",
            weight="bold", zorder=7)
    for name, (dn, _) in DESTS.items():
        x, y = xy(*dn)
        ax.plot(x, y, "o", ms=9, mfc="#006bb6", mec="white", zorder=7)
        east_edge = dn[0] == 5
        ax.annotate(name.split(" (")[0], (x, y),
                    xytext=(-6 if east_edge else 6, 6),
                    ha="right" if east_edge else "left",
                    textcoords="offset points", color="white", fontsize=8,
                    weight="bold", zorder=8)
    ax.set_xticks([xy(a, 26)[0] for a in AVENUES])
    ax.set_xticklabels([f"{a}th Ave" for a in AVENUES], fontsize=8)
    ax.set_yticks([xy(5, s)[1] for s in STREETS[::2]])
    ax.set_yticklabels([f"W {s}th" for s in STREETS[::2]], fontsize=8)
    ax.invert_xaxis()                        # west on the left, like a map
    ax.set_title("Knicks Win Chaos: crowd density, inferred closures (red),\n"
                 "and equilibrium walking flows (blue, width = fans)")
    fig.tight_layout()
    fig.savefig(out, dpi=150)


if __name__ == "__main__":
    main()
