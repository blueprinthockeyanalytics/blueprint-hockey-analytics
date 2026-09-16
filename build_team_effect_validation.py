#!/usr/bin/env python3
"""
build_team_effect_validation.py — real-data validation of the team-effect
term before it goes anywhere near production. Extends the real fitting
mechanism to a third block (team effects, separately regularized from
players), using real team codes already present in the stint data
(home_team/away_team, confirmed directly in nhl_scrape_stints_v2.py).

Real, proper cross-validated alpha_team this time -- not the fixed
synthetic-data candidates from the earlier prototype. Validates two
things directly: does this improve real, held-out prediction accuracy
at all (the honest bar an architectural change needs to clear), and what
happens to Bedard specifically.

Run from the project root:
    python3 build_team_effect_validation.py

Fair warning: real cross-validation across several alpha_team candidates
on the full pooled dataset -- meaningful real cost, not a quick script.
"""
import numpy as np
import pandas as pd
from scipy import sparse as sp

import nhl_model_v12 as m

HC = ["h1","h2","h3","h4","h5"]
AC = ["a1","a2","a3","a4","a5"]
XG60_CAP = 30.0
ZONE_FLIP = {"OZ": "DZ", "DZ": "OZ", "NZ": "NZ", "OTF": "OTF"}
RAPM_ALPHA_EVO = 15.0
ALPHA_TEAM_CANDIDATES = [1.0, 5.0, 15.0, 50.0, 200.0, np.inf]  # inf = team term fully suppressed (= current production)
N_CV_FOLDS = 4

print("Loading data...")
skaters = m.load_skaters()
stints_by_season = m.load_stints()
name_map = skaters[["playerId", "name"]].drop_duplicates("playerId").set_index("playerId")["name"].to_dict()
BEDARD_PID = [pid for pid, nm in name_map.items() if "bedard" in str(nm).lower()][0]

print("\nBuilding the real, pooled design matrix with real team columns...")
ev = skaters[(skaters["situation"] == "5on5") & (skaters["season"].isin(m.RECENT_SEASONS)) &
             (skaters["icetime"] >= m.MIN_5V5_TOI)]
pid_list = sorted(ev["playerId"].astype(int).unique().tolist())
pid_idx = {pid: i for i, pid in enumerate(pid_list)}
n_p = len(pid_list)

all_teams = sorted(set(skaters["team"].dropna().unique()) - {"", "nan"})
team_idx = {t: i for i, t in enumerate(all_teams)}
n_t = len(all_teams)
print(f"  {n_p} players, {n_t} real teams")

rows_p, cols_p, vals_p = [], [], []
rows_t, cols_t, vals_t = [], [], []
y_off, wts = [], []
for season in m.RECENT_SEASONS:
    if season not in stints_by_season:
        continue
    d = stints_by_season[season].copy()
    for c in HC + AC:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d[d["duration"] > 0].reset_index(drop=True)
    if d.empty or "home_team" not in d.columns:
        continue
    h_vals = d[HC].to_numpy(); a_vals = d[AC].to_numpy()
    xg_home = d["xg_home"].to_numpy(); duration = d["duration"].to_numpy()
    home_team_col = d["home_team"].to_numpy(); away_team_col = d["away_team"].to_numpy()

    for row_i in range(h_vals.shape[0]):
        hp = [int(p) for p in h_vals[row_i] if pd.notna(p) and int(p) in pid_idx]
        ap = [int(p) for p in a_vals[row_i] if pd.notna(p) and int(p) in pid_idx]
        if len(hp) < 4 or len(ap) < 4:
            continue
        ht, at = home_team_col[row_i], away_team_col[row_i]
        if ht not in team_idx or at not in team_idx:
            continue
        thr = duration[row_i] / 3600
        if thr <= 0:
            continue
        ri = len(y_off)
        for p in hp: rows_p.append(ri); cols_p.append(pid_idx[p]); vals_p.append(1.0)
        for p in ap: rows_p.append(ri); cols_p.append(pid_idx[p]); vals_p.append(-1.0)
        rows_t.append(ri); cols_t.append(team_idx[ht]); vals_t.append(1.0)
        rows_t.append(ri); cols_t.append(team_idx[at]); vals_t.append(-1.0)
        y_off.append(min(xg_home[row_i] / thr, XG60_CAP))
        wts.append(thr)

X_p = sp.csr_matrix((vals_p, (rows_p, cols_p)), shape=(len(y_off), n_p))
X_t = sp.csr_matrix((vals_t, (rows_t, cols_t)), shape=(len(y_off), n_t))
y = np.array(y_off)
w = np.array(wts)
print(f"  {len(y_off):,} real stints with real team codes attached")


def fit_three_block(Xp, Xt, y, w, alpha_p, alpha_t):
    """Real three-block ridge: players (alpha_p), teams (alpha_t, separate),
    intercept (unpenalized). Core math verified earlier this session."""
    n_p_local, n_t_local = Xp.shape[1], Xt.shape[1]
    Xfull = sp.hstack([Xp, Xt]).tocsr()
    intercept_col = np.ones((Xfull.shape[0], 1))
    Xw = Xfull.multiply(w[:, None])
    XtWX = np.asarray((Xw.T @ Xfull).todense())
    XtWi = np.asarray(Xw.T @ intercept_col)
    iWi = np.array([[np.sum(w)]])
    A = np.block([[XtWX, XtWi], [XtWi.T, iWi]])
    if np.isinf(alpha_t):
        penalty = np.concatenate([np.full(n_p_local, alpha_p), np.full(n_t_local, 1e12), [0.0]])
    else:
        penalty = np.concatenate([np.full(n_p_local, alpha_p), np.full(n_t_local, alpha_t), [0.0]])
    A[np.diag_indices_from(A)] += penalty
    XtWy = Xfull.T.dot(w * y)
    b = np.concatenate([XtWy, [np.sum(w * y)]])
    beta = np.linalg.solve(A, b)
    return beta[:n_p_local], beta[n_p_local:n_p_local + n_t_local]


print(f"\n{'=' * 78}\nReal cross-validation across alpha_team candidates\n{'=' * 78}")
rng = np.random.default_rng(42)
fold_id = rng.integers(0, N_CV_FOLDS, size=len(y))

results = []
for alpha_t in ALPHA_TEAM_CANDIDATES:
    fold_scores = []
    for fold in range(N_CV_FOLDS):
        train = fold_id != fold
        test = fold_id == fold
        pc, tc = fit_three_block(X_p[train], X_t[train], y[train], w[train], RAPM_ALPHA_EVO, alpha_t)
        pred = X_p[test].dot(pc) + X_t[test].dot(tc)
        fold_scores.append(np.average((y[test] - pred) ** 2, weights=w[test]))
    mean_score = np.mean(fold_scores)
    results.append({"alpha_team": alpha_t, "cv_mse": mean_score})
    label = "current production (team term suppressed)" if np.isinf(alpha_t) else ""
    print(f"  alpha_team={alpha_t:>8}   real held-out MSE={mean_score:.5f}  {label}")

results_df = pd.DataFrame(results)
best_alpha_t = results_df.loc[results_df["cv_mse"].idxmin(), "alpha_team"]
baseline_mse = results_df[results_df["alpha_team"] == np.inf]["cv_mse"].values[0]
best_mse = results_df["cv_mse"].min()

print(f"\n  Best real alpha_team: {best_alpha_t}")
print(f"  Real improvement over current production (no team term): "
      f"{(baseline_mse - best_mse) / baseline_mse * 100:+.3f}%")

print(f"\n{'=' * 78}\nFinal fit at the best real alpha_team -- Bedard's real result\n{'=' * 78}")
final_p, final_t = fit_three_block(X_p, X_t, y, w, RAPM_ALPHA_EVO, best_alpha_t)
bedard_coef = final_p[pid_idx[BEDARD_PID]]
bedard_pctile = (final_p < bedard_coef).mean() * 100
print(f"  Bedard's coefficient with team term: {bedard_coef:+.4f}  ({bedard_pctile:.1f}th percentile)")

final_p_baseline, _ = fit_three_block(X_p, X_t, y, w, RAPM_ALPHA_EVO, np.inf)
bedard_baseline = final_p_baseline[pid_idx[BEDARD_PID]]
bedard_baseline_pctile = (final_p_baseline < bedard_baseline).mean() * 100
print(f"  Bedard's coefficient WITHOUT team term (current production): {bedard_baseline:+.4f}  "
      f"({bedard_baseline_pctile:.1f}th percentile)")

print("\nWhat this tells us:")
print("  - If the best alpha_team beats the current-production baseline on real, held-out")
print("    accuracy, that's genuine, real-data evidence this is worth building into production.")
print("  - Compare Bedard's real percentile shift here against the honest, partial improvement")
print("    the earlier SYNTHETIC test found -- this confirms whether that holds on real data.")
