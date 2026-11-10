"""Comparison of the blind consumer panel with the independent organoleptic assessment
by four laboratories (order ODER 23/2026, August 2026).

Odour and taste descriptions are read directly from the comparison workbook
(data/Analiza_porownawcza_ODER_23_2026.xlsx, sheet "Macierz pełna"). The workbook
holds Polish translations of the laboratory reports, so the rule-based coding below
matches Polish keywords. Codes on the three-level typicality scale:
    2 = T, "typical for honey / source-specific"  ("typowy")
    1 = L, "slightly / weakly typical"            ("lekko / słabo typowy")
    0 = N, "not typical for honey"                ("nietypowy")
Laboratory result for a sample = minimum of the odour and taste codes (where a
typicality qualifier was given). Organoleptic objection = result 0.
The Puławy laboratory (Lab4) does not use a typicality qualifier (PN-88/A-77626);
its final verdict "ambiguous characteristics" ("cechy niejednoznaczne") is coded
1 (L), and the laboratory enters all measures on equal terms with the others.

Common reference for all comparisons with the panel: the majority verdict of the
laboratories (N in more than half of the laboratories).
"""

import itertools
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
from openpyxl import load_workbook
from scipy import stats

XLSX = Path(__file__).resolve().parent.parent / "data" / "Analiza_porownawcza_ODER_23_2026.xlsx"

# batch code in the laboratory workbook -> sample symbol
LAB_CODE_TO_P = {
    "250906": "P1", "25C062101": "P2", "4/02/2029": "P3", "CQ23120101-2": "P4",
    "CQ25111501-1": "P5", "02/09": "P6", "21/05": "P7",
}
# batch code in the panel data -> sample symbol
PANEL_LOT_TO_P = {
    "1-250906": "P1", "2-25c062101": "P2", "3-4/02/2020": "P3",
    "4-cq23120101-2": "P4", "5-cq25111501-1": "P5", "6-02/09": "P6",
    "7-4/21/05": "P7",
}
SAMPLES = ["P1", "P2", "P3", "P4", "P5", "P6", "P7"]
RATED_LABS = ["QSI", "Eurofins", "Intertek", "Puławy"]   # names as in the workbook
N_LABS = len(RATED_LABS)
LAB_NO = {"QSI": 1, "Eurofins": 2, "Intertek": 3, "Puławy": 4}
# Lab4 descriptors indicating a defect (sensitivity analysis only):
# fermentation, unnatural, fruit-drop (candy-like)
DEFECT_WORDS = ("fermentac", "nienatural", "landrynk")

# colours by number of laboratories with an objection: none / minority / majority
CLR_NONE, CLR_MINOR, CLR_MAJOR = "#2874A6", "#7F8C8D", "#CA6F1E"


def flag_color(k: int) -> str:
    return CLR_NONE if k == 0 else (CLR_MAJOR if k > N_LABS / 2 else CLR_MINOR)


# --------------------------------------------------------------------------- #
#  Loading and coding of laboratory descriptions
# --------------------------------------------------------------------------- #

def typicality_code(text: str | None) -> int | None:
    """Rule-based coding of a Polish descriptor (see module docstring)."""
    if not text:
        return None
    t = str(text).lower()
    if "nietypow" in t:                              # not typical
        return 0
    if re.search(r"(lekko|słabo)\s+typow", t):       # slightly / weakly typical
        return 1
    if "typow" in t:                                 # typical
        return 2
    return None


def load_lab_descriptions(path: Path = XLSX) -> pd.DataFrame:
    ws = load_workbook(path, data_only=True)["Macierz pełna"]
    rows = list(ws.iter_rows(values_only=True))
    codes_row = next(r for r in rows if r[0] == "Parametr")
    labs_row = rows[rows.index(codes_row) + 1]
    smell = next(r for r in rows if r[0] == "Zapach")       # odour
    taste = next(r for r in rows if r[0] == "Smak")         # taste
    verdict = next(r for r in rows if str(r[0]).startswith("Ocena końcowa"))  # final verdict

    out, code = [], None
    for j in range(1, len(codes_row)):
        if codes_row[j] is not None:
            code = str(codes_row[j])
        lab = labs_row[j]
        if lab is None or code not in LAB_CODE_TO_P:
            continue
        out.append({"P": LAB_CODE_TO_P[code], "lab": lab,
                    "smell": smell[j], "taste": taste[j], "verdict": verdict[j]})
    d = pd.DataFrame(out)
    d["smell_code"] = d["smell"].map(typicality_code)
    d["taste_code"] = d["taste"].map(typicality_code)
    d["score"] = d[["smell_code", "taste_code"]].min(axis=1, skipna=True)
    # "ambiguous characteristics" (PN-88/A-77626) -> L
    ambiguous = d["verdict"].astype(str).str.lower().str.contains("niejednoznaczn")
    d.loc[d["score"].isna() & ambiguous, "score"] = 1
    d["flag"] = (d["score"] == 0).astype(int)
    return d


# --------------------------------------------------------------------------- #
#  Measures
# --------------------------------------------------------------------------- #

def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    p = k / n
    den = 1 + z ** 2 / n
    c = (p + z ** 2 / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / den
    return c - h, c + h


def fleiss_kappa(table: np.ndarray) -> float:
    """table: n_items × n_categories (number of raters per category)."""
    n_raters = table.sum(axis=1)[0]
    p_j = table.sum(axis=0) / table.sum()
    P_i = ((table ** 2).sum(axis=1) - n_raters) / (n_raters * (n_raters - 1))
    P_bar, P_e = P_i.mean(), (p_j ** 2).sum()
    return float((P_bar - P_e) / (1 - P_e)) if P_e < 1 else float("nan")


def cochran_q(x: np.ndarray) -> tuple[float, float, int]:
    """x: n_respondents × k_samples (0/1). Returns Q, p, df."""
    k = x.shape[1]
    col, row, total = x.sum(axis=0), x.sum(axis=1), x.sum()
    q = (k - 1) * (k * (col ** 2).sum() - total ** 2) / (k * total - (row ** 2).sum())
    return float(q), float(stats.chi2.sf(q, k - 1)), k - 1


def paired_contrast(wide: pd.DataFrame, a: list[str], b: list[str]) -> dict:
    """Difference of means (a − b) per respondent: mean, 95% CI, Wilcoxon, d."""
    diff = wide[a].mean(axis=1) - wide[b].mean(axis=1)
    sd = diff.std(ddof=1)
    half = 1.96 * sd / np.sqrt(len(diff))
    return {"mean": diff.mean(), "lo": diff.mean() - half, "hi": diff.mean() + half,
            "p": stats.wilcoxon(diff[diff != 0]).pvalue, "d": diff.mean() / sd}


def _f(x: float, nd: int = 3) -> str:
    return f"{x:.{nd}f}"


def _p(p: float) -> str:
    return "< 0.001" if p < 0.001 else "= " + _f(p, 3)


def _pt(p: float) -> str:
    return "$<$0.001" if p < 0.001 else _f(p, 3)


def _pct(x: float) -> str:
    return f"{100 * x:.1f}"


def _join(items: list[str]) -> str:
    """English list: 'P1', 'P1 and P2', 'P1, P2 and P3'."""
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and~" + items[-1] if items else ""


# --------------------------------------------------------------------------- #
#  Main computations
# --------------------------------------------------------------------------- #

PANEL_UNDECIDED = "inc."   # inconclusive panel verdict


def panel_verdict(lo: float, hi: float) -> str:
    """Verdict of the panel as a whole from the 95% Wilson CI."""
    return "T" if lo > 0.5 else ("N" if hi < 0.5 else PANEL_UNDECIDED)


def n_to_decide(p: float, n_max: int = 1_000_000) -> int | None:
    """Smallest number of respondents for which the 95% Wilson CI for proportion p excludes 0.5."""
    if p == 0.5:
        return None
    lo_n, hi_n = 1, n_max
    excl = lambda n: (lambda ci: ci[0] > 0.5 or ci[1] < 0.5)(wilson_ci(p * n, n))
    if not excl(hi_n):
        return None
    while lo_n < hi_n:
        mid = (lo_n + hi_n) // 2
        lo_n, hi_n = (lo_n, mid) if excl(mid) else (mid + 1, hi_n)
    return lo_n


def pair_agreement(lab_typ: pd.DataFrame, wide: pd.DataFrame) -> dict:
    """Agreement of rater pairs on the typical / not typical scale (1 / 0), averaged over samples.

    lab_typ: samples × laboratories; wide: respondents × samples (complete answers).
    κ = (p_o − p_e) / (1 − p_e), p_e from the pooled proportions of "typical" answers.
    """
    m, n = lab_typ.shape[1], len(wide)
    q, kq = lab_typ.mean(axis=1), lab_typ.sum(axis=1)
    p, kp = wide.mean(axis=0), wide.sum(axis=0)
    po = {
        "ll": ((kq * (kq - 1) + (m - kq) * (m - kq - 1)) / (m * (m - 1))).mean(),
        "cc": ((kp * (kp - 1) + (n - kp) * (n - kp - 1)) / (n * (n - 1))).mean(),
        "cl": (p * q + (1 - p) * (1 - q)).mean(),
    }
    pe = {
        "ll": q.mean() ** 2 + (1 - q.mean()) ** 2,
        "cc": p.mean() ** 2 + (1 - p.mean()) ** 2,
        "cl": p.mean() * q.mean() + (1 - p.mean()) * (1 - q.mean()),
    }
    return {k: (po[k], (po[k] - pe[k]) / (1 - pe[k])) for k in po}


def compute_lab_comparison(df: pd.DataFrame, out_dir: str = "..") -> dict:
    from analysis import auc

    d = df.copy()
    d["P"] = d["lot"].map(PANEL_LOT_TO_P)
    labs = load_lab_descriptions()
    r: dict = {"n_labs": N_LABS}

    # --- panel: sample profile ---
    g = d.groupby("P")
    panel = pd.DataFrame({
        "n": g["is_typical"].count(),
        "k": g["is_typical"].sum().astype(int),
        "typ": g["is_typical"].mean(),
        "overall": g["overall_rate"].mean(),
        "sweet": g["sweetness"].mean(),
        "acid": g["acidity"].mean(),
        "intens": g["intensity"].mean(),
        "sweet3": g["sweetness"].apply(lambda s: (s.dropna() == 3).mean()),
    }).loc[SAMPLES]
    panel[["lo", "hi"]] = [wilson_ci(int(k), int(n)) for k, n in zip(panel.k, panel.n)]
    panel["p_binom"] = [stats.binomtest(int(k), int(n), 0.5).pvalue
                        for k, n in zip(panel.k, panel.n)]
    panel["verdict"] = [panel_verdict(lo, hi) for lo, hi in zip(panel.lo, panel.hi)]

    # --- laboratories: result and objections ---
    rated = labs[labs.lab.isin(RATED_LABS)]
    score = rated.pivot(index="P", columns="lab", values="score").loc[SAMPLES, RATED_LABS]
    flag = rated.pivot(index="P", columns="lab", values="flag").loc[SAMPLES, RATED_LABS]
    n_flags = flag.sum(axis=1).astype(int)
    lab_majority = (n_flags > N_LABS / 2).astype(int)   # 1 = majority of laboratories: N
    flagged = [p for p in SAMPLES if lab_majority[p] == 1]
    clean = [p for p in SAMPLES if lab_majority[p] == 0]
    clean_wo = [p for p in clean if p != "P3"]

    # agreement between laboratories
    cnt_bin = np.column_stack([(flag == 0).sum(axis=1), (flag == 1).sum(axis=1)])
    cnt_ord = np.column_stack([(score == c).sum(axis=1) for c in (0, 1, 2)])
    r["kappa_bin"] = _f(fleiss_kappa(cnt_bin), 2)
    r["kappa_ord"] = _f(fleiss_kappa(cnt_ord), 2)
    r["n_full_agree_bin"] = int(((n_flags == 0) | (n_flags == N_LABS)).sum())
    r["n_full_agree_ord"] = int((score.nunique(axis=1) == 1).sum())
    r["lab_flagged"] = _join(flagged)
    r["lab_clean"] = _join(clean)
    r["lab_clean_wo"] = _join(clean_wo)
    r["lab_none"] = _join(p for p in SAMPLES if n_flags[p] == 0)
    r["lab_minor"] = _join(p for p in SAMPLES if 0 < n_flags[p] <= N_LABS / 2)
    r["n_flags_major"] = " and~".join(sorted({f"{n_flags[p]}" for p in flagged}))

    # sensitivity: Lab4 defect descriptors coded as N
    alt = flag.copy()
    pul = labs[labs.lab == "Puławy"].set_index("P").loc[SAMPLES]
    alt["Puławy"] = [int(any(w in f"{s} {t}".lower() for w in DEFECT_WORDS))
                     for s, t in zip(pul.smell, pul.taste)]
    alt_n = alt.sum(axis=1)
    r["kappa_bin_alt"] = _f(fleiss_kappa(np.column_stack([N_LABS - alt_n, alt_n])), 2)
    r["alt_majority_same"] = "would remain unchanged" \
        if ((alt_n > N_LABS / 2) == (lab_majority == 1)).all() else "would change"

    # sensitivity: coding taste descriptions only (odour only where no qualifier was given)
    taste_only = rated.assign(s=rated.taste_code.fillna(rated.smell_code).fillna(rated.score))
    t_flags = (taste_only.pivot(index="P", columns="lab", values="s")
               .loc[SAMPLES, RATED_LABS] == 0).sum(axis=1)
    r["taste_only_same"] = "the same majority classification of the samples as" \
        if ((t_flags > N_LABS / 2) == (lab_majority == 1)).all() \
        else "a different majority classification of the samples than"

    # --- panel as a whole vs laboratories ---
    r["panel_T"] = _join(panel.index[panel.verdict == "T"]) or "none"
    r["n_panel_N"] = int((panel.verdict == "N").sum())
    for p in flagged:
        nd = n_to_decide(panel.loc[p, "typ"])
        r[f"n_decide_{p}"] = (f"{nd:,}".replace(",", "\\,") if nd >= 10_000 else str(nd)) if nd else "--"

    # --- ranking (n = 7 samples) ---
    no_flag = N_LABS - n_flags
    rho, p_rho = stats.spearmanr(panel["typ"], no_flag)
    r["rho_panel_lab"], r["p_rho_panel_lab"] = _f(rho, 2), _p(p_rho)
    rho_o, p_rho_o = stats.spearmanr(panel["overall"], no_flag)
    r["rho_overall_lab"], r["p_rho_overall_lab"] = _f(rho_o, 2), _p(p_rho_o)
    wo3 = [p for p in SAMPLES if p != "P3"]
    rho3, p_rho3 = stats.spearmanr(panel.loc[wo3, "typ"], no_flag[wo3])
    r["rho_panel_lab_wo3"], r["p_rho_panel_lab_wo3"] = _f(rho3, 2), _p(p_rho3)
    rho_m, p_rho_m = stats.spearmanr(panel["typ"], score.mean(axis=1))
    r["rho_meancode"], r["p_rho_meancode"] = _f(rho_m, 2), _p(p_rho_m)

    # --- agreement of rater pairs ---
    wide = d.pivot_table(index="id", columns="P", values="is_typical").dropna()
    pa = pair_agreement(1 - flag, wide[SAMPLES])
    for k, (po, kap) in pa.items():
        r[f"agree_{k}"], r[f"kappa_{k}"] = _pct(po), _f(kap, 2)
    full_pairs = [f"Lab{LAB_NO[a]}--Lab{LAB_NO[b]}"
                  for a, b in itertools.combinations(RATED_LABS, 2)
                  if (flag[a] == flag[b]).all()]
    r["full_agree_pairs"] = " and~".join(full_pairs) or "none"

    # --- single panelist rating (AUC with respondent bootstrap) ---
    dt = d.dropna(subset=["is_typical"]).reset_index(drop=True)
    y_lab = dt["P"].map(lab_majority).to_numpy()
    atyp = 1 - dt["is_typical"].astype(float).to_numpy()
    r["auc_lab"] = _f(auc(atyp, y_lab))
    rng = np.random.default_rng(2026)
    groups = [idx.to_numpy() for _, idx in dt.groupby("id").groups.items()]
    boot = []
    for _ in range(2000):
        idx = np.concatenate([groups[i] for i in rng.integers(0, len(groups), len(groups))])
        boot.append(auc(atyp[idx], y_lab[idx]))
    lo, hi = np.percentile(boot, [2.5, 97.5])
    r["auc_lab_lo"], r["auc_lab_hi"] = _f(lo), _f(hi)
    r["fp_lab_pct"] = _pct(atyp[y_lab == 0].mean())       # "not typical" although labs had no objection
    r["fn_lab_pct"] = _pct(1 - atyp[y_lab == 1].mean())   # "typical" although labs flagged the sample

    # --- Cochran Q: does the panel discriminate between samples (all / without P3) ---
    q7, pq7, df7 = cochran_q(wide[SAMPLES].to_numpy())
    q6, pq6, df6 = cochran_q(wide[wo3].to_numpy())
    r["n_complete_typ"] = len(wide)
    r.update(q_all=_f(q7, 2), p_q_all=_p(pq7), df_q_all=df7,
             q_rest=_f(q6, 2), p_q_rest=_p(pq6), df_q_rest=df6)
    wide_o = d.pivot_table(index="id", columns="P", values="overall_rate").dropna()
    r["n_complete_overall"] = len(wide_o)
    fr = stats.friedmanchisquare(*[wide_o[p] for p in SAMPLES])
    fr6 = stats.friedmanchisquare(*[wide_o[p] for p in wo3])
    r.update(fr_all=_f(fr.statistic, 2), p_fr_all=_p(fr.pvalue),
             fr_rest=_f(fr6.statistic, 2), p_fr_rest=_p(fr6.pvalue))

    # --- contrast: samples flagged by the majority vs the remaining ones ---
    c = paired_contrast(wide, clean, flagged)
    c2 = paired_contrast(wide, clean_wo, flagged)
    co = paired_contrast(wide_o, clean, flagged)
    r.update(
        typ_flagged=_f(d[d.P.isin(flagged)]["is_typical"].mean()),
        typ_clean=_f(d[d.P.isin(clean)]["is_typical"].mean()),
        diff_flag=_f(c["mean"]), diff_flag_lo=_f(c["lo"]), diff_flag_hi=_f(c["hi"]),
        p_diff_flag=_p(c["p"]), d_diff_flag=_f(c["d"], 2),
        diff_flag_wo=_f(c2["mean"]), p_diff_flag_wo=_p(c2["p"]),
        diff_overall_flag=_f(co["mean"], 2), p_diff_overall_flag=_p(co["p"]),
    )

    # per-sample values for the text
    for p in SAMPLES:
        r[f"typ_{p}"] = _f(panel.loc[p, "typ"])
        r[f"sweet3_{p}"] = _pct(panel.loc[p, "sweet3"])
        r[f"pbin_{p}"] = _p(panel.loc[p, "p_binom"])
        r[f"hi_{p}"] = _f(panel.loc[p, "hi"], 2)
    r["n_sig_binom"] = int((panel["p_binom"] < 0.05).sum())

    # --- table: organoleptic profile in the panel ---
    r["profile_rows"] = "\n".join(
        f"{p} & {int(panel.loc[p, 'n'])} & "
        f"{_f(panel.loc[p, 'overall'], 2)} & {_f(panel.loc[p, 'typ'])} & "
        f"{_f(panel.loc[p, 'sweet'], 2)} & {_f(panel.loc[p, 'acid'], 2)} & "
        f"{_f(panel.loc[p, 'intens'], 2)} \\\\"
        for p in SAMPLES)

    # --- table: panel vs laboratories ---
    def sym(v):
        return {0: "N", 1: "L", 2: "T"}.get(v, "--") if pd.notna(v) else "--"

    r["panel_lab_rows"] = "\n".join(
        f"{p} & {int(panel.loc[p, 'n'])} & {_f(panel.loc[p, 'typ'])} & "
        f"{_f(panel.loc[p, 'lo'], 2)}--{_f(panel.loc[p, 'hi'], 2)} & "
        f"{_pt(panel.loc[p, 'p_binom'])} & {panel.loc[p, 'verdict']} & "
        + " & ".join(sym(score.loc[p, lab]) for lab in RATED_LABS)
        + f" & {n_flags[p]}/{N_LABS} \\\\"
        for p in SAMPLES)

    save_panel_lab_figure(panel, n_flags, out_dir)
    save_contrast_figure(wide, clean, flagged, out_dir)
    return r


# --------------------------------------------------------------------------- #
#  Figures
# --------------------------------------------------------------------------- #

def _style() -> None:
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False})


def _save(fig, out_dir: str, stem: str) -> None:
    p = Path(out_dir)
    fig.savefig(p / f"{stem}.pdf", bbox_inches="tight")
    fig.savefig(p / f"{stem}.png", bbox_inches="tight", dpi=600)   # MDPI: at least 300 dpi
    plt.close(fig)
    print(f"  Saved {stem}.pdf / .png")


def save_panel_lab_figure(panel: pd.DataFrame, n_flags: pd.Series,
                          out_dir: str = "..") -> None:
    """Typicality and overall acceptance in the panel, coloured by the laboratory verdict."""
    _style()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.4))
    x = np.arange(len(SAMPLES))
    for i, p in enumerate(SAMPLES):
        clr = flag_color(n_flags[p])
        y, lo, hi = panel.loc[p, ["typ", "lo", "hi"]]
        ax1.errorbar(i, y, yerr=[[y - lo], [hi - y]], fmt="o", color=clr,
                     ms=8, capsize=4, lw=1.4)
        ax1.text(i, 0.05, f"{n_flags[p]}/{N_LABS}", ha="center", va="center",
                 fontsize=9.5, fontweight="bold", color=clr)
        ax2.bar(i, panel.loc[p, "overall"], color=clr, width=0.6)
        ax2.text(i, panel.loc[p, "overall"] + 0.06, f"{panel.loc[p, 'overall']:.2f}",
                 ha="center", va="bottom", fontsize=8.5)
    labels = SAMPLES
    ax1.axhline(0.5, color="grey", ls="--", lw=0.8, zorder=0)
    ax1.set(xticks=x, ylim=(0, 1.0), title="Taste typicality (95% Wilson CI)",
            ylabel="Proportion of “typical taste” ratings")
    ax1.set_xticklabels(labels, fontsize=10)
    ax1.text(-0.45, 0.12, "laboratory objections", fontsize=7.5, color="#555555")
    ax2.axhline(3.0, color="grey", ls="--", lw=0.8, zorder=0)
    ax2.set(xticks=x, ylim=(1, 5), title="Overall acceptance",
            ylabel="Mean rating (1–5)")
    ax2.set_xticklabels(labels, fontsize=10)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    legend = {CLR_NONE: "no laboratory objections",
              CLR_MINOR: "objection by a minority of laboratories",
              CLR_MAJOR: "objection by a majority of laboratories"}
    present = [c for c in legend if c in {flag_color(v) for v in n_flags}]
    fig.legend(handles=[Line2D([], [], marker="o", ls="", color=c, label=legend[c])
                        for c in present],
               loc="lower center", ncol=len(present), frameon=False, fontsize=9)
    _save(fig, out_dir, "fig_panel_lab")


def save_contrast_figure(wide: pd.DataFrame, clean: list[str], flagged: list[str],
                         out_dir: str = "..") -> None:
    """Mean typicality per respondent: samples flagged by the majority vs the remaining ones."""
    _style()
    xs, ys = wide[flagged].mean(axis=1), wide[clean].mean(axis=1)
    pts = pd.DataFrame({"x": xs.round(3), "y": ys.round(3)}).value_counts().reset_index(name="n")
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.scatter(pts.x, pts.y, s=pts.n * 28, color="#2874A6", alpha=0.6, edgecolor="white")
    ax.plot([0, 1], [0, 1], ls="--", color="grey", lw=0.8)
    ax.set(xlim=(-0.05, 1.05), ylim=(-0.05, 1.05), aspect="equal",
           xlabel=f"Typicality of flagged samples ({', '.join(flagged)})",
           ylabel=f"Typicality of the remaining samples ({', '.join(clean)})")
    for n in (1, 5, 10):
        ax.scatter([], [], s=n * 28, color="#2874A6", alpha=0.6, label=f"n = {n}")
    ax.legend(frameon=False, fontsize=8, loc="lower right", title="respondents",
              title_fontsize=8)
    fig.tight_layout()
    _save(fig, out_dir, "fig_contrast_lab")


if __name__ == "__main__":
    from prepare_data import load_and_merge
    from analysis import to_dataframe
    data = Path(__file__).resolve().parent.parent / "data" / "badania-2.xlsx"
    res = compute_lab_comparison(to_dataframe(load_and_merge(data)))
    for k, v in res.items():
        print(k, "=", v)
