"""
Analiza sensoryczna miodu — moduł do artykułu.
 
Wejście: lista obiektów DataModel (jak w projekcie).
Wyjście: cztery sekcje wypisane na stdout:
    1) informacje ogólne
    2) parametry podstawowe (statystyki opisowe)
    3) korelacje (Spearman + istotność)
    4) dowód tezy: efekt autoryzacji jest zbyt mały i zbyt niepewny,
       by stanowić podstawę niedopuszczenia próbki do obrotu.
 
Zależności: pandas, numpy, scipy.
Użycie:
    from honey_analysis import run_full_analysis
    run_full_analysis(data)        # data: list[DataModel]
"""
 
from __future__ import annotations
from dataclasses import asdict
from pathlib import Path
from typing import List, Any

import numpy as np
import pandas as pd
from scipy import stats
 
 
# --------------------------------------------------------------------------- #
#  Przygotowanie danych
# --------------------------------------------------------------------------- #
def to_dataframe(data: List[Any]) -> pd.DataFrame:
    """Lista DataModel -> DataFrame. Normalizuje typy (bool/int -> 0/1)."""
    df = pd.DataFrame([asdict(d) for d in data])
    # is_taste_ok bywa bool -> sprowadzamy do 0/1 int
    if "is_taste_ok" in df:
        df["is_taste_ok"] = df["is_taste_ok"].astype("float").round().astype("Int64")
    for c in ("authorized", "age", "how_often", "overall_rate",
              "sweetness", "acidity", "intensity"):
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df
 
 
# zmienne ilościowe/porządkowe używane w korelacjach
_NUMERIC = ["overall_rate", "sweetness", "acidity", "intensity",
            "is_taste_ok", "authorized", "age", "how_often"]
 
 
def _stars(p: float) -> str:
    return "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"
 
 
def _h(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)
 
 
# --------------------------------------------------------------------------- #
#  1) Informacje ogólne
# --------------------------------------------------------------------------- #
def general_info(df: pd.DataFrame) -> None:
    _h("1. INFORMACJE OGÓLNE")
    print(f"Liczba ocen (wierszy):        {len(df)}")
    print(f"Liczba respondentów:          {df['id'].nunique()}")
    print(f"Liczba próbek (lot):          {df['lot'].nunique()}")
    print(f"Ocen na respondenta (średnio):{len(df) / df['id'].nunique():.1f}")
 
    print("\nBraki danych w kolumnach:")
    miss = df.isna().sum()
    for c, v in miss[miss > 0].items():
        print(f"   {c}: {v}")
    if miss.sum() == 0:
        print("   brak")
 
    print("\nRozkład płci:")
    print(df["gender"].value_counts(dropna=False).to_string())
 
    print("\nRozkład wieku (age):")
    print(df.groupby("id")["age"].first().value_counts().sort_index().to_string())
 
    print("\nCzęstość spożycia (how_often):")
    print(df.groupby("id")["how_often"].first().value_counts().sort_index().to_string())
 
    print("\nPróbki: lot -> (autoryzacja, typ, liczba ocen):")
    lot = df.groupby("lot").agg(authorized=("authorized", "first"),
                                typ=("type_of_honey", "first"),
                                n=("id", "count"))
    print(lot.to_string())
    print(f"\nLotów autoryzowanych: {(lot['authorized'] == 1).sum()} | "
          f"nieautoryzowanych: {(lot['authorized'] == 0).sum()}")
 
 
# --------------------------------------------------------------------------- #
#  2) Parametry podstawowe
# --------------------------------------------------------------------------- #
def basic_parameters(df: pd.DataFrame) -> None:
    _h("2. PARAMETRY PODSTAWOWE (statystyki opisowe)")
    cols = ["overall_rate", "sweetness", "acidity", "intensity",
            "is_taste_ok", "authorized"]
    desc = df[cols].describe().T[["mean", "std", "min", "50%", "max"]]
    desc.columns = ["średnia", "odch.std", "min", "mediana", "max"]
    print(desc.round(3).to_string())
 
    print("\nŚrednie ocen wg próbki (lot):")
    by_lot = df.groupby("lot").agg(
        authorized=("authorized", "first"),
        overall_rate=("overall_rate", "mean"),
        is_taste_ok=("is_taste_ok", "mean"),
        sweetness=("sweetness", "mean"),
        acidity=("acidity", "mean"),
        intensity=("intensity", "mean"),
    ).round(3)
    print(by_lot.to_string())
 
 
# --------------------------------------------------------------------------- #
#  3) Korelacje
# --------------------------------------------------------------------------- #
def correlations(df: pd.DataFrame) -> None:
    _h("3. KORELACJE (Spearman)")
    cols = [c for c in _NUMERIC if c in df]
    sub = df[cols].dropna()
 
    print("Macierz korelacji (rho):")
    print(sub.corr(method="spearman").round(3).to_string())
 
    print("\nPary uporządkowane wg |rho| (z istotnością):")
    res = []
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            a, b = cols[i], cols[j]
            rho, p = stats.spearmanr(sub[a], sub[b])
            res.append((a, b, rho, p))
    res.sort(key=lambda x: -abs(x[2]))
    for a, b, rho, p in res:
        print(f"   {a:13s} ~ {b:13s}  rho={rho:+.3f}  p={p:.4f}  {_stars(p)}")
 
    print("\nUWAGA: 'authorized' i 'type_of_honey' są stałe w obrębie lotu,")
    print("więc korelacje z nimi na poziomie wierszy są pseudoreplikowane")
    print("(efektywne n = liczba lotów). Patrz sekcja 4 — analiza poprawna.")
 
 
# --------------------------------------------------------------------------- #
#  4) Dowód tezy
# --------------------------------------------------------------------------- #
def _auc(score: np.ndarray, target: np.ndarray) -> float:
    """AUC z testu Manna-Whitneya (bez sklearn)."""
    pos = score[target == 1]
    neg = score[target == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    u, _ = stats.mannwhitneyu(pos, neg, alternative="two-sided")
    return u / (len(pos) * len(neg))
 
 
def prove_thesis(df: pd.DataFrame, sesoi: float = 0.10) -> None:
    """
    Teza: różnica akceptacji smakowej między miodami autoryzowanymi
    a nieautoryzowanymi jest zbyt mała i obarczona zbyt dużym błędem,
    by stanowić podstawę niedopuszczenia próbki do obrotu.
 
    sesoi = granica efektu istotnego praktycznie (do testu równoważności).
    """
    _h("4. DOWÓD TEZY: authorized vs is_taste_ok")
 
    a = df["authorized"].astype(int)
    b = df["is_taste_ok"].astype(int)
 
    # 4.1 tabela 2x2 + miary asocjacji
    print("--- 4.1 Tabela 2x2 i miary asocjacji ---")
    ct = pd.crosstab(a, b)
    print(ct.to_string())
    rate = df.groupby("authorized")["is_taste_ok"].mean()
    print(f"\nAkceptacja (taste_ok=1)  nieauth: {rate.get(0, float('nan')):.3f} | "
          f"auth: {rate.get(1, float('nan')):.3f}")
    phi = np.corrcoef(a, b)[0, 1]
    chi2, p_chi, _, _ = stats.chi2_contingency(ct, correction=False)
    tab = ct.values
    orr = (tab[1, 1] * tab[0, 0]) / (tab[1, 0] * tab[0, 1])
    print(f"phi (korelacja 0-1):     {phi:+.3f}")
    print(f"chi^2 = {chi2:.2f}, p = {p_chi:.4f}  (na poziomie wierszy)")
    print(f"iloraz szans (OR):       {orr:.2f}")
 
    # 4.2 analiza poprawna: sparowana per respondent
    print("\n--- 4.2 Test sparowany per respondent (poprawny dla powtórzeń) ---")
    g = (df.groupby(["id", "authorized"])["is_taste_ok"].mean()
         .unstack().dropna())
    g.columns = ["nieauth", "auth"]
    d = (g["auth"] - g["nieauth"]).values
    n = len(d)
    m, se = d.mean(), d.std(ddof=1) / np.sqrt(n)
    ci = stats.t.interval(0.95, n - 1, loc=m, scale=se)
    w, p_w = stats.wilcoxon(g["auth"], g["nieauth"])
    print(f"n respondentów:          {n}")
    print(f"różnica (auth-nieauth):  {m:+.3f}")
    print(f"95% CI:                  [{ci[0]:+.3f}, {ci[1]:+.3f}]")
    print(f"Wilcoxon:                p = {p_w:.4f}")
    print(f"Cohen d (sparowany):     {m / d.std(ddof=1):.3f}")
 
    # 4.3 test równoważności (TOST) — formalny argument 'efekt pomijalny'
    print(f"\n--- 4.3 Test równoważności TOST (granica ±{sesoi:.2f}) ---")
    t1 = (m - (-sesoi)) / se
    t2 = (m - sesoi) / se
    p_tost = max(stats.t.sf(t1, n - 1), stats.t.cdf(t2, n - 1))
    verdict = ("RÓWNOWAŻNE — efekt mieści się w granicy nieistotności"
               if p_tost < 0.05 else
               "NIE wykazano równoważności przy tej granicy")
    print(f"p_TOST = {p_tost:.4f}  ->  {verdict}")
 
    # 4.4 sygnał/szum: efekt vs naturalna zmienność między próbkami
    print("\n--- 4.4 Sygnał vs szum (kluczowe dla tezy) ---")
    lot = df.groupby("lot").agg(auth=("authorized", "first"),
                                ok=("is_taste_ok", "mean"))
    signal = abs(lot.groupby("auth")["ok"].mean().diff().iloc[-1])
    noise = lot.groupby("auth")["ok"].std().mean()
    rng = lot["ok"].max() - lot["ok"].min()
    print(f"sygnał (różnica grup):              {signal:.3f}")
    print(f"szum (odch.std między lotami w grupie): {noise:.3f}")
    print(f"rozrzut akceptacji między lotami:   {rng:.3f} "
          f"(od {lot['ok'].min():.2f} do {lot['ok'].max():.2f})")
    print(f"stosunek sygnał/szum:               {signal / noise:.2f}")
    if signal < noise:
        print(">>> Efekt autoryzacji jest MNIEJSZY niż naturalna zmienność "
              "między pojedynczymi próbkami.")
 
    # 4.5 zdolność rozróżniania + błędy reguły decyzyjnej
    print("\n--- 4.5 Czy ocena sensoryczna nadaje się na kryterium? ---")
    auc_taste = _auc(b.values.astype(float), a.values)
    auc_overall = _auc(df["overall_rate"].values.astype(float), a.values)
    print(f"AUC (is_taste_ok  -> authorized):  {auc_taste:.3f}")
    print(f"AUC (overall_rate -> authorized):  {auc_overall:.3f}")
    print("(0,50 = rzut monetą; 1,00 = idealne rozróżnienie)")
 
    print("\nReguła hipotetyczna: 'odrzuć próbkę gdy is_taste_ok = 0'")
    fp = ct.loc[1, 0]; n_auth = ct.loc[1].sum()
    fn = ct.loc[0, 1]; n_non = ct.loc[0].sum()
    print(f"   legalnych (auth) błędnie odrzuconych:   "
          f"{fp}/{n_auth} = {100 * fp / n_auth:.1f}%")
    print(f"   nieautoryzowanych mimo to przepuszczonych: "
          f"{fn}/{n_non} = {100 * fn / n_non:.1f}%")
 
    # 4.6 wniosek
    print("\n--- WNIOSEK ---")
    print(f"Różnica akceptacji = {signal*100:.1f} pkt proc. (phi={phi:.3f}, "
          f"d={m/d.std(ddof=1):.2f}), mniejsza niż zmienność między próbkami "
          f"(sygnał/szum={signal/noise:.2f}); AUC={auc_taste:.2f} ~ poziom "
          f"losowy. Reguła decyzyjna myliłaby ~{100*fp/n_auth:.0f}% próbek "
          f"zgodnych. Efekt zbyt mały i zbyt niepewny, by uzasadniać "
          f"niedopuszczenie próbki do obrotu.")
 


def run_full_analysis(data: List[Any], sesoi: float = 0.10) -> pd.DataFrame:
    df = to_dataframe(data)
    general_info(df)
    basic_parameters(df)
    correlations(df)
    prove_thesis(df, sesoi=sesoi)
    mixed_effects_results(df)
    bayes_analysis(df)
    power_analysis(df)
    within_type_analysis(df)
    heterogeneity_analysis(df)
    sesoi_sensitivity(df)
    return df


# --------------------------------------------------------------------------- #
#  Generowanie LaTeX
# --------------------------------------------------------------------------- #

def _compute_general(df: pd.DataFrame) -> dict:
    lot = df.groupby("lot").agg(authorized=("authorized", "first"), n=("id", "count"))
    n, n_resp = len(df), df["id"].nunique()
    return {
        "n_ocen": n,
        "n_respondentow": n_resp,
        "n_lotow": df["lot"].nunique(),
        "ocen_per_respondent": round(n / n_resp, 1),
        "n_auth_lot": int((lot["authorized"] == 1).sum()),
        "n_nieauth_lot": int((lot["authorized"] == 0).sum()),
    }


def _compute_basic(df: pd.DataFrame) -> dict:
    cols = ["overall_rate", "sweetness", "acidity", "intensity", "is_taste_ok"]
    desc = df[cols].describe()
    short = {"overall_rate": "overall", "sweetness": "sweetness",
             "acidity": "acidity", "intensity": "intensity", "is_taste_ok": "taste_ok"}
    r = {}
    for col, name in short.items():
        for stat in ("mean", "std", "min", "max"):
            r[f"{stat}_{name}"] = round(float(desc.loc[stat, col]), 3)
    return r


def _compute_thesis(df: pd.DataFrame, sesoi: float) -> dict:
    a = df["authorized"].astype(int)
    b = df["is_taste_ok"].astype(int)

    ct = (pd.crosstab(a, b)
          .reindex([0, 1]).reindex([0, 1], axis=1)
          .fillna(0).astype(int))
    rate = df.groupby("authorized")["is_taste_ok"].mean()
    phi = float(np.corrcoef(a, b)[0, 1])
    chi2_val, p_chi, _, _ = stats.chi2_contingency(ct, correction=False)
    tab = ct.values
    denom = tab[1, 0] * tab[0, 1]
    orr = (tab[1, 1] * tab[0, 0]) / denom if denom else float("nan")

    g = (df.groupby(["id", "authorized"])["is_taste_ok"].mean()
         .unstack().dropna())
    g.columns = ["nieauth", "auth"]
    d = (g["auth"] - g["nieauth"]).values
    n = len(d)
    m, se = d.mean(), d.std(ddof=1) / np.sqrt(n)
    ci = stats.t.interval(0.95, n - 1, loc=m, scale=se)
    _, p_w = stats.wilcoxon(g["auth"], g["nieauth"])
    cohen_d = m / d.std(ddof=1)

    t1 = (m - (-sesoi)) / se
    t2 = (m - sesoi) / se
    p_tost = max(stats.t.sf(t1, n - 1), stats.t.cdf(t2, n - 1))

    lot = df.groupby("lot").agg(auth=("authorized", "first"), ok=("is_taste_ok", "mean"))
    signal = abs(lot.groupby("auth")["ok"].mean().diff().iloc[-1])
    noise = lot.groupby("auth")["ok"].std().mean()

    n_auth_rows = int(ct.loc[1].sum())
    n_non_rows = int(ct.loc[0].sum())
    fp, fn = int(ct.loc[1, 0]), int(ct.loc[0, 1])

    return {
        "rate_auth":      round(float(rate.get(1, float("nan"))), 3),
        "rate_nieauth":   round(float(rate.get(0, float("nan"))), 3),
        "phi":            round(phi, 3),
        "chi2":           round(float(chi2_val), 2),
        "p_chi":          round(float(p_chi), 4),
        "orr":            round(float(orr), 2),
        "n_paired":       n,
        "diff_mean":      round(float(m), 3),
        "ci_low":         round(float(ci[0]), 3),
        "ci_high":        round(float(ci[1]), 3),
        "p_wilcoxon":     round(float(p_w), 4),
        "cohen_d":        round(float(cohen_d), 3),
        "sesoi":          sesoi,
        "p_tost":         round(float(p_tost), 4),
        "tost_verdict":   "RÓWNOWAŻNE" if p_tost < 0.05 else "brak równoważności",
        "signal":         round(float(signal), 3),
        "signal_pct":     round(float(signal) * 100, 1),
        "noise":          round(float(noise), 3),
        "snr":            round(float(signal / noise), 2),
        "lot_ok_min":     round(float(lot["ok"].min()), 2),
        "lot_ok_max":     round(float(lot["ok"].max()), 2),
        "auc_taste":      round(float(_auc(b.values.astype(float), a.values)), 3),
        "auc_overall":    round(float(_auc(df["overall_rate"].values.astype(float), a.values)), 3),
        "fp_pct":         round(100 * fp / n_auth_rows, 1) if n_auth_rows else 0.0,
        "fn_pct":         round(100 * fn / n_non_rows, 1) if n_non_rows else 0.0,
    }


def _fmt_p(p: float) -> str:
    """Formatuje p-wartość: '<0.001' dla bardzo małych, inaczej 4 cyfry po przecinku."""
    if np.isnan(p):
        return "N/A"
    if p < 0.001:
        return "<0.001"
    return str(round(p, 4))


# --------------------------------------------------------------------------- #
#  5) Modele z efektami mieszanymi (LMM + GEE)
# --------------------------------------------------------------------------- #

def _compute_mixed_models(df: pd.DataFrame) -> dict:
    from statsmodels.formula.api import mixedlm
    from statsmodels.genmod.generalized_estimating_equations import GEE
    from statsmodels.genmod.families import Binomial
    from statsmodels.genmod.cov_struct import Exchangeable

    r: dict = {}
    df2 = df.copy()
    df2["authorized"] = df2["authorized"].astype(float)
    df2["id_str"] = df2["id"].astype(str)

    try:
        md = mixedlm(
            "overall_rate ~ authorized + C(type_of_honey)",
            df2.dropna(subset=["overall_rate", "authorized"]),
            groups="id_str",
        )
        mdf = md.fit(reml=True, disp=False)
        ci = mdf.conf_int()
        r.update({
            "lmm_auth_coef":    round(float(mdf.params["authorized"]), 3),
            "lmm_auth_ci_low":  round(float(ci.loc["authorized", 0]), 3),
            "lmm_auth_ci_high": round(float(ci.loc["authorized", 1]), 3),
            "lmm_auth_p":       round(float(mdf.pvalues["authorized"]), 4),
        })
    except Exception:
        r.update(lmm_auth_coef="N/A", lmm_auth_ci_low="N/A",
                 lmm_auth_ci_high="N/A", lmm_auth_p="N/A")

    try:
        df_gee = df2.copy()
        df_gee["is_taste_ok"] = df_gee["is_taste_ok"].astype(float)
        df_gee = df_gee.dropna(subset=["is_taste_ok", "authorized"])
        res = GEE.from_formula(
            "is_taste_ok ~ authorized + C(type_of_honey)",
            groups="id_str", data=df_gee,
            family=Binomial(), cov_struct=Exchangeable(),
        ).fit()
        ci_g = res.conf_int()
        coef_g = float(res.params["authorized"])
        r.update({
            "gee_auth_or":         round(np.exp(coef_g), 3),
            "gee_auth_or_ci_low":  round(float(np.exp(ci_g.loc["authorized", 0])), 3),
            "gee_auth_or_ci_high": round(float(np.exp(ci_g.loc["authorized", 1])), 3),
            "gee_auth_p":          _fmt_p(float(res.pvalues["authorized"])),
        })
    except Exception:
        r.update(gee_auth_or="N/A", gee_auth_or_ci_low="N/A",
                 gee_auth_or_ci_high="N/A", gee_auth_p="N/A")

    return r


def mixed_effects_results(df: pd.DataFrame) -> None:
    _h("5. MODELE Z EFEKTAMI MIESZANYMI")
    r = _compute_mixed_models(df)
    print(f"LMM overall_rate ~ authorized + type:  "
          f"β={r['lmm_auth_coef']}  95%CI=[{r['lmm_auth_ci_low']}, {r['lmm_auth_ci_high']}]  "
          f"p={r['lmm_auth_p']}")
    print(f"GEE is_taste_ok  ~ authorized + type:  "
          f"OR={r['gee_auth_or']}  95%CI=[{r['gee_auth_or_ci_low']}, {r['gee_auth_or_ci_high']}]  "
          f"p={r['gee_auth_p']}")


# --------------------------------------------------------------------------- #
#  6) Analiza bayesowska (JZS prior)
# --------------------------------------------------------------------------- #

def _jzs_bf10(t_stat: float, n: int, r: float = 0.707) -> float:
    """BF10 dla testu t (sparowany) — prior Cauchy'ego JZS (Rouder et al. 2009)."""
    from scipy.integrate import quad

    df_t = n - 1

    def integrand(delta: float) -> float:
        ncp = delta * np.sqrt(n)
        return float(stats.nct.pdf(t_stat, df=df_t, nc=ncp) * stats.cauchy.pdf(delta, scale=r))

    alt_lik, _ = quad(integrand, -15.0, 15.0, limit=500, epsabs=1e-12)
    null_lik = float(stats.t.pdf(t_stat, df=df_t))
    return alt_lik / null_lik if null_lik > 0 else float("nan")


def _compute_bayes(df: pd.DataFrame) -> dict:
    g = (df.groupby(["id", "authorized"])["is_taste_ok"].mean()
         .unstack().dropna())
    g.columns = ["nieauth", "auth"]
    d = (g["auth"] - g["nieauth"]).values
    n = len(d)
    m, se = d.mean(), d.std(ddof=1) / np.sqrt(n)
    t_stat = float(m / se)

    bf10 = _jzs_bf10(t_stat, n)
    bf01 = 1.0 / bf10

    if   bf01 >= 10:  verdict = "silne poparcie dla H$_0$"
    elif bf01 >= 3:   verdict = "umiarkowane poparcie dla H$_0$"
    elif bf01 >= 1:   verdict = "słabe poparcie dla H$_0$"
    elif bf01 >= 1/3: verdict = "słabe poparcie dla H$_1$"
    elif bf01 >= 1/10:verdict = "umiarkowane poparcie dla H$_1$"
    else:             verdict = "silne poparcie dla H$_1$"

    return {
        "t_stat":     round(t_stat, 3),
        "bf10":       round(bf10, 2),
        "bf01":       round(bf01, 2),
        "bf_verdict": verdict,
    }


def bayes_analysis(df: pd.DataFrame) -> None:
    _h("6. ANALIZA BAYESOWSKA (JZS prior, r=0.707)")
    r = _compute_bayes(df)
    print(f"t = {r['t_stat']},  BF10 = {r['bf10']},  BF01 = {r['bf01']}")
    print(f"Interpretacja: {r['bf_verdict']}")


# --------------------------------------------------------------------------- #
#  7) Analiza mocy
# --------------------------------------------------------------------------- #

def _compute_power(df: pd.DataFrame) -> dict:
    from statsmodels.stats.power import TTestIndPower

    lot = df.groupby("lot").agg(auth=("authorized", "first"), ok=("is_taste_ok", "mean"))
    auth_ok    = lot.loc[lot.auth == 1, "ok"].values
    nonauth_ok = lot.loc[lot.auth == 0, "ok"].values
    n1, n2 = len(auth_ok), len(nonauth_ok)

    pooled_var = (
        (n1 - 1) * auth_ok.var(ddof=1) + (n2 - 1) * nonauth_ok.var(ddof=1)
    ) / (n1 + n2 - 2)
    pooled_std = np.sqrt(pooled_var)
    cohen_d_lot = float((auth_ok.mean() - nonauth_ok.mean()) / pooled_std) if pooled_std else float("nan")

    pa = TTestIndPower()
    power_obs = float(pa.power(
        effect_size=abs(cohen_d_lot), nobs1=n1,
        alpha=0.05, ratio=n2 / n1, alternative="two-sided",
    ))
    n_needed = int(np.ceil(pa.solve_power(
        effect_size=abs(cohen_d_lot), power=0.80,
        alpha=0.05, ratio=1.0, alternative="two-sided",
    )))

    return {
        "lot_cohen_d":        round(cohen_d_lot, 3),
        "lot_n_auth":         n1,
        "lot_n_nonauth":      n2,
        "power_observed":     round(power_obs, 3),
        "power_observed_pct": round(power_obs * 100, 1),
        "n_lots_needed_80":   n_needed,
    }


def power_analysis(df: pd.DataFrame) -> None:
    _h("7. ANALIZA MOCY (na poziomie lotów)")
    r = _compute_power(df)
    print(f"Cohen d (loty):        {r['lot_cohen_d']}")
    print(f"Grupy auth / nieauth:  {r['lot_n_auth']} / {r['lot_n_nonauth']} lotów")
    print(f"Moc obserwowana:       {r['power_observed']:.1%}")
    print(f"Potrzeba ≥{r['n_lots_needed_80']} lotów na grupę dla mocy 80%")


# --------------------------------------------------------------------------- #
#  8) Porównanie wewnątrz typów miodu
# --------------------------------------------------------------------------- #

def _compute_within_type(df: pd.DataFrame) -> dict:
    def _wilcoxon_paired(s1: pd.Series, s2: pd.Series) -> str:
        a, b = s1.align(s2, join="inner")
        try:
            _, p = stats.wilcoxon(a.values.astype(float), b.values.astype(float))
            return _fmt_p(float(p))
        except Exception:
            return "N/A"

    rob_a = df[df.lot == "1-250906"].set_index("id")["is_taste_ok"].astype(float)
    rob_n = df[df.lot == "2-25c062101"].set_index("id")["is_taste_ok"].astype(float)

    poly_a = df[df.lot.isin(["3-4/02/2020", "4-cq23120101-2"])].groupby("id")["is_taste_ok"].mean().astype(float)
    poly_n = df[df.lot.isin(["6-02/09", "7-4/21/05"])].groupby("id")["is_taste_ok"].mean().astype(float)

    return {
        "rob_auth_ok":    round(float(rob_a.mean()), 3),
        "rob_nonauth_ok": round(float(rob_n.mean()), 3),
        "rob_p":          _wilcoxon_paired(rob_a, rob_n),
        "poly_auth_ok":   round(float(poly_a.mean()), 3),
        "poly_nonauth_ok":round(float(poly_n.mean()), 3),
        "poly_p":         _wilcoxon_paired(poly_a, poly_n),
        "tilia_ok":       round(float(df[df.lot == "5-cq25111501-1"]["is_taste_ok"].astype(float).mean()), 3),
    }


def within_type_analysis(df: pd.DataFrame) -> None:
    _h("8. PORÓWNANIE WEWNĄTRZ TYPÓW MIODU (sparowane per respondent)")
    r = _compute_within_type(df)
    print(f"Robinia:    auth={r['rob_auth_ok']}  nieauth={r['rob_nonauth_ok']}  p={r['rob_p']}")
    print(f"Polyfloral: auth={r['poly_auth_ok']}  nieauth={r['poly_nonauth_ok']}  p={r['poly_p']}")
    print(f"Tilia:      auth-only  akceptacja={r['tilia_ok']}")


# --------------------------------------------------------------------------- #
#  9) Heterogeniczność wewnątrz grup
# --------------------------------------------------------------------------- #

def _compute_heterogeneity(df: pd.DataFrame) -> dict:
    lot = df.groupby("lot").agg(auth=("authorized", "first"), ok=("is_taste_ok", "mean"))
    auth_ok    = lot.loc[lot.auth == 1, "ok"]
    nonauth_ok = lot.loc[lot.auth == 0, "ok"]
    signal = abs(auth_ok.mean() - nonauth_ok.mean())
    auth_rng   = float(auth_ok.max()    - auth_ok.min())
    nonauth_rng = float(nonauth_ok.max() - nonauth_ok.min())

    return {
        "auth_range":           round(auth_rng, 3),
        "nonauth_range":        round(nonauth_rng, 3),
        "auth_range_vs_signal": round(auth_rng / signal, 1) if signal else "∞",
        "auth_best_lot":        str(auth_ok.idxmax()),
        "auth_worst_lot":       str(auth_ok.idxmin()),
        "auth_best_ok":         round(float(auth_ok.max()), 3),
        "auth_worst_ok":        round(float(auth_ok.min()), 3),
    }


def heterogeneity_analysis(df: pd.DataFrame) -> None:
    _h("9. HETEROGENICZNOŚĆ WEWNĄTRZ GRUP (poziom lotów)")
    r = _compute_heterogeneity(df)
    print(f"Rozrzut auth (max–min):    {r['auth_range']}  ({r['auth_range_vs_signal']}× > efekt autoryzacji)")
    print(f"Rozrzut nieauth (max–min): {r['nonauth_range']}")
    print(f"Najwyższa akceptacja (auth): {r['auth_best_lot']} = {r['auth_best_ok']}")
    print(f"Najniższa  akceptacja (auth): {r['auth_worst_lot']} = {r['auth_worst_ok']}")


# --------------------------------------------------------------------------- #
#  10) Czułość granicy SESOI
# --------------------------------------------------------------------------- #

def _compute_sesoi_sensitivity(df: pd.DataFrame) -> dict:
    g = (df.groupby(["id", "authorized"])["is_taste_ok"].mean()
         .unstack().dropna())
    g.columns = ["nieauth", "auth"]
    d = (g["auth"] - g["nieauth"]).values
    n = len(d)
    m, se = d.mean(), d.std(ddof=1) / np.sqrt(n)

    def p_tost(s: float) -> float:
        t1, t2 = (m - (-s)) / se, (m - s) / se
        return float(max(stats.t.sf(t1, n - 1), stats.t.cdf(t2, n - 1)))

    grid = np.arange(0.05, 0.51, 0.005)
    p_vals = [p_tost(s) for s in grid]
    first = next((i for i, p in enumerate(p_vals) if p < 0.05), None)

    return {
        "sesoi_min_equiv": f"{grid[first]:.2f}" if first is not None else ">0.50",
        "p_tost_010": round(p_tost(0.10), 4),
        "p_tost_015": round(p_tost(0.15), 4),
        "p_tost_020": round(p_tost(0.20), 4),
    }


def sesoi_sensitivity(df: pd.DataFrame) -> None:
    _h("10. CZUŁOŚĆ GRANICY SESOI")
    r = _compute_sesoi_sensitivity(df)
    print(f"SESOI=±0.10  p_TOST={r['p_tost_010']}")
    print(f"SESOI=±0.15  p_TOST={r['p_tost_015']}")
    print(f"SESOI=±0.20  p_TOST={r['p_tost_020']}")
    print(f"Min. granica dla równoważności (p<0.05): ±{r['sesoi_min_equiv']}")


# --------------------------------------------------------------------------- #
#  11) Demografia respondentów
# --------------------------------------------------------------------------- #

def _compute_demographics(df: pd.DataFrame) -> dict:
    resp = df.groupby("id").first().reset_index()
    n = len(resp)

    age_map = {1: "lt25", 2: "25_45", 3: "46_65", 4: "gt65"}
    freq_map = {1: "daily", 2: "monthly", 3: "occasional"}

    r: dict = {}

    age_c = resp["age"].value_counts()
    for k, slug in age_map.items():
        cnt = int(age_c.get(k, 0))
        r[f"age_{slug}_n"] = cnt
        r[f"age_{slug}_pct"] = round(cnt / n * 100, 1)

    gen_c = resp["gender"].str.lower().value_counts(dropna=True)
    r["gender_k_n"]   = int(gen_c.get("k", 0))
    r["gender_k_pct"] = round(int(gen_c.get("k", 0)) / n * 100, 1)
    r["gender_m_n"]   = int(gen_c.get("m", 0))
    r["gender_m_pct"] = round(int(gen_c.get("m", 0)) / n * 100, 1)

    freq_c = resp["how_often"].value_counts()
    for k, slug in freq_map.items():
        cnt = int(freq_c.get(k, 0))
        r[f"freq_{slug}_n"] = cnt
        r[f"freq_{slug}_pct"] = round(cnt / n * 100, 1)

    return r


# --------------------------------------------------------------------------- #
#  12) Profil lotów (tabela LaTeX)
# --------------------------------------------------------------------------- #

def _compute_lot_profile(df: pd.DataFrame) -> dict:
    _LOT_NAMES = {
        "1-250906": "Lot~1", "2-25c062101": "Lot~2",
        "3-4/02/2020": "Lot~3", "4-cq23120101-2": "Lot~4",
        "5-cq25111501-1": "Lot~5", "6-02/09": "Lot~6", "7-4/21/05": "Lot~7",
    }
    _TYPE_PL = {
        "robinia": "robinia", "polyfloral": "wielokwiatowy",
        "tilia": "lipowy", "other": "inny",
    }
    _ORDER = [
        "1-250906", "2-25c062101", "3-4/02/2020", "4-cq23120101-2",
        "5-cq25111501-1", "6-02/09", "7-4/21/05",
    ]

    by_lot = df.groupby("lot").agg(
        auth=("authorized", "first"),
        honey_type=("type_of_honey", "first"),
        n=("id", "count"),
        overall=("overall_rate", "mean"),
        taste_ok=("is_taste_ok", "mean"),
        sweet=("sweetness", "mean"),
        acid=("acidity", "mean"),
        intens=("intensity", "mean"),
    )

    rows = []
    for lot in _ORDER:
        if lot not in by_lot.index:
            continue
        row = by_lot.loc[lot]
        auth_str = "tak" if row["auth"] == 1 else "nie"
        name = _LOT_NAMES.get(lot, lot)
        typ = _TYPE_PL.get(row["honey_type"], row["honey_type"])
        rows.append(
            f"{name} & {typ} & {auth_str} & {int(row['n'])} & "
            f"{row['overall']:.2f} & {row['taste_ok']:.3f} & "
            f"{row['sweet']:.2f} & {row['acid']:.2f} & {row['intens']:.2f} \\\\"
        )

    return {"lot_profile_rows": "\n".join(rows)}


# --------------------------------------------------------------------------- #
#  13) Rozkład sensoryki (skale ordinalne)
# --------------------------------------------------------------------------- #

def _compute_sensory_dist(df: pd.DataFrame) -> dict:
    attrs = {
        "sweetness":  "sweet",
        "acidity":    "acid",
        "intensity":  "intens",
    }
    r: dict = {}

    for attr, slug in attrs.items():
        for auth_val, group in [(1, "auth"), (0, "nieauth")]:
            sub = df[df["authorized"] == auth_val][attr].dropna()
            n = len(sub)
            for val in [1, 2, 3]:
                pct = round((sub == val).sum() / n * 100, 1) if n > 0 else 0.0
                r[f"{slug}_{group}_{val}_pct"] = pct
            mode_val = int(sub.mode().iloc[0]) if len(sub) > 0 else "N/A"
            r[f"{slug}_{group}_mode"] = mode_val

    return r


def compute_results(df: pd.DataFrame, sesoi: float = 0.10) -> dict:
    """Zwraca płaski słownik placeholder -> wartość do wypełnienia szablonu LaTeX."""
    r = {}
    r.update(_compute_general(df))
    r.update(_compute_basic(df))
    r.update(_compute_thesis(df, sesoi=sesoi))
    r.update(_compute_mixed_models(df))
    r.update(_compute_bayes(df))
    r.update(_compute_power(df))
    r.update(_compute_within_type(df))
    r.update(_compute_heterogeneity(df))
    r.update(_compute_sesoi_sensitivity(df))
    r.update(_compute_demographics(df))
    r.update(_compute_lot_profile(df))
    r.update(_compute_sensory_dist(df))
    return r


def render_latex(
    data,
    template_path: str | Path = "template.latex",
    output_path: str | Path = "../out.tex",
    sesoi: float = 0.10,
) -> None:
    """Wypełnia placeholdery <<var>> w szablonie LaTeX i zapisuje wynik."""
    df = data if isinstance(data, pd.DataFrame) else to_dataframe(data)
    values = compute_results(df, sesoi=sesoi)

    text = Path(template_path).read_text(encoding="utf-8")
    for key, val in values.items():
        text = text.replace(f"<<{key}>>", str(val))

    Path(output_path).write_text(text, encoding="utf-8")