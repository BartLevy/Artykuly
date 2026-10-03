#!/usr/bin/env python3
"""Analiza odpowiedzi z platformy powtórek i przygotowanie wyników do artykułu.

Oprócz tabel roboczych (CSV) i raportu tekstowego skrypt tworzy katalog
<wyniki>/artykul z materiałami gotowymi do wklejenia do artykułu (po angielsku):
  tables/*.tex    tabele LaTeX (booktabs),
  figures/*.pdf   wykresy (oraz PNG 300 dpi),
  csv/*.csv       dane źródłowe tabel i wykresów (materiał uzupełniający),
  macros.tex      makra \\newcommand z liczbami używanymi w tekście,
  draft.tex       kompletny szkic artykułu (Methods, Results z tabelami i rycinami, Discussion),
  main.tex        dokument do samodzielnej kompilacji szkicu (pdflatex + bibtex),
  references.bib  literatura cytowana w szkicu.

W preambule artykułu: \\usepackage{booktabs,graphicx,natbib,doi} oraz \\input{macros.tex};
szkic wstawia się przez \\input{draft.tex} (zob. main.tex).

Instalacja: pip install pandas numpy scipy statsmodels matplotlib
Uruchomienie: python analiza_odpowiedzi_naukowa.py data.csv --wyniki wyniki_naukowe
"""

import argparse
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy.stats import binomtest, pearsonr, rankdata, wilcoxon
from statsmodels.stats.contingency_tables import mcnemar
from statsmodels.stats.multitest import multipletests

WYMAGANE = ["id", "room_Code", "question_id", "answer_id", "user_symbol", "create_time", "correct"]
KLUCZ = ["user_symbol", "question_id"]
PRZEDZIALY_DNI = [0, 14, 30, 60, 120, 240, np.inf]
ETYKIETY_DNI = ["<14", "14--29", "30--59", "60--119", "120--239", "$\\geq$240"]
KOLOR_1, KOLOR_2, SZARY = "#2a78d6", "#eb6834", "#8a8984"


# --------------------------------------------------------------------------- dane

def wczytaj(plik):
    df = pd.read_csv(plik, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    brak = set(WYMAGANE) - set(df.columns)
    if brak:
        raise ValueError(f"Brak kolumn: {sorted(brak)}")
    df = df[WYMAGANE].copy()
    for col in ("id", "question_id", "answer_id", "correct"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["create_time"] = pd.to_datetime(df["create_time"], errors="coerce")
    valid = (df[["id", "question_id", "answer_id", "correct", "create_time"]].notna().all(axis=1)
             & df["correct"].isin([0, 1]) & df["room_Code"].ne("") & df["user_symbol"].ne(""))
    rejected = df.loc[~valid].copy()
    df = df.loc[valid].copy()
    for col in ("id", "question_id", "answer_id", "correct"):
        df[col] = df[col].astype("int64")
    df = df.sort_values(["create_time", "id"], kind="stable").reset_index(drop=True)
    df["blad"] = 1 - df["correct"]
    return df, rejected


def przygotuj(df):
    """Dodaje numer próby w sekwencji osoba–pytanie, odstęp od poprzedniej próby i staż."""
    g = df.groupby(KLUCZ)
    df["proba"] = g.cumcount() + 1
    df["liczba_prob"] = g["id"].transform("size")
    df["odstep_dni"] = g["create_time"].diff().dt.total_seconds() / 86400
    df["poprzednia"] = g["correct"].shift()
    df["poprzednia_odp"] = g["answer_id"].shift()
    start = df.groupby("user_symbol")["create_time"].transform("min")
    df["staz_lata"] = (df["create_time"] - start).dt.total_seconds() / 86400 / 365.25
    df["log2_proba"] = np.log2(df["proba"])
    df["log2_odstep"] = np.log2(df["odstep_dni"].clip(lower=1))
    return df


def agreguj(df, keys):
    out = df.groupby(keys, as_index=False).agg(
        n=("correct", "size"), bledy=("blad", "sum"),
        uzytkownicy=("user_symbol", "nunique"),
        od=("create_time", "min"), do=("create_time", "max"))
    out["bledy_proc"] = (100 * out["bledy"] / out["n"]).round(2)
    return out


# ------------------------------------------------------------ analizy robocze (CSV)

def pytania_w_dziesieciu_czesciach(df, min_odpowiedzi):
    counts = df.groupby("question_id")["id"].transform("size")
    x = df.loc[counts >= min_odpowiedzi].copy()
    if x.empty:
        return pd.DataFrame(), pd.DataFrame()
    x["kolejnosc"] = x.groupby("question_id").cumcount()
    x["liczba_w_pytaniu"] = x.groupby("question_id")["id"].transform("size")
    x["czesc"] = 1 + 10 * x["kolejnosc"] // x["liczba_w_pytaniu"]
    bins = agreguj(x, ["question_id", "czesc"]).sort_values(["question_id", "czesc"])
    result = []
    for q, g in bins.groupby("question_id"):
        slope = np.polyfit(g["czesc"], g["bledy_proc"], 1)[0]
        result.append({"question_id": q, "n": int(g["n"].sum()),
                       "bledy_proc_1": float(g["bledy_proc"].iloc[0]),
                       "bledy_proc_10": float(g["bledy_proc"].iloc[-1]),
                       "zmiana_10_minus_1_pp": round(float(g["bledy_proc"].iloc[-1] - g["bledy_proc"].iloc[0]), 2),
                       "nachylenie_pp_na_czesc": round(float(slope), 3),
                       "kierunek": "spadek" if slope < 0 else "wzrost" if slope > 0 else "bez_zmian"})
    return bins, pd.DataFrame(result)


def pary_minimum_trzy(df):
    keys = KLUCZ
    sizes = df.groupby(keys)["id"].transform("size")
    x = df.loc[sizes >= 3].copy()
    if x.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    x["proba"] = x.groupby(keys).cumcount() + 1
    x["poprzednia_data"] = x.groupby(keys)["create_time"].shift()
    x["odstep_godziny"] = (x["create_time"] - x["poprzednia_data"]).dt.total_seconds() / 3600
    x["etap"] = x["proba"].clip(upper=10).astype(str)
    x.loc[x["proba"] >= 10, "etap"] = "10+"
    etapy = agreguj(x, ["etap"])
    first = x.loc[x["proba"].isin([1, 2, 3])].pivot(index=keys, columns="proba", values="correct")
    first.columns = [f"poprawna_{i}" for i in first.columns]
    pairs = first.reset_index()
    pairs["poprawa_1_do_3"] = pairs["poprawna_3"] - pairs["poprawna_1"]
    pairs["poprawa_1_do_2"] = pairs["poprawna_2"] - pairs["poprawna_1"]
    details = x.groupby(keys, as_index=False).agg(
        liczba_prob=("correct", "size"), data_pierwsza=("create_time", "min"),
        data_ostatnia=("create_time", "max"), pokoje=("room_Code", "nunique"),
        poprawne_lacznie=("correct", "sum"))
    pairs = pairs.merge(details, on=keys, validate="one_to_one")
    third = x.loc[x["proba"] == 3, keys + ["odstep_godziny"]].rename(
        columns={"odstep_godziny": "odstep_2_do_3_godziny"})
    pairs = pairs.merge(third, on=keys, validate="one_to_one")
    pairs["odstep_1_do_ostatniej_dni"] = (
        (pairs["data_ostatnia"] - pairs["data_pierwsza"]).dt.total_seconds() / 86400).round(2)
    users = pairs.groupby("user_symbol", as_index=False).agg(
        pytania_min3=("question_id", "size"),
        poprawa_pytan=("poprawa_1_do_3", lambda v: int((v > 0).sum())),
        pogorszenie_pytan=("poprawa_1_do_3", lambda v: int((v < 0).sum())),
        bez_zmiany_pytan=("poprawa_1_do_3", lambda v: int((v == 0).sum())),
        poprawnych_1=("poprawna_1", "sum"), poprawnych_3=("poprawna_3", "sum"),
        wszystkie_proby=("liczba_prob", "sum"))
    users["zmiana_poprawnych_pp"] = (
        100 * (users["poprawnych_3"] - users["poprawnych_1"]) / users["pytania_min3"]).round(2)
    users["status"] = np.select(
        [users["zmiana_poprawnych_pp"] > 0, users["zmiana_poprawnych_pp"] < 0],
        ["poprawa", "pogorszenie"], default="bez_zmiany")
    questions = pairs.groupby("question_id", as_index=False).agg(
        uzytkownicy_min3=("user_symbol", "nunique"),
        poprawa_osob=("poprawa_1_do_3", lambda v: int((v > 0).sum())),
        pogorszenie_osob=("poprawa_1_do_3", lambda v: int((v < 0).sum())),
        poprawnych_1=("poprawna_1", "sum"), poprawnych_3=("poprawna_3", "sum"))
    questions["poprawnych_proc_1"] = (100 * questions["poprawnych_1"] / questions["uzytkownicy_min3"]).round(2)
    questions["poprawnych_proc_3"] = (100 * questions["poprawnych_3"] / questions["uzytkownicy_min3"]).round(2)
    return etapy, pairs, users, questions


# ------------------------------------------------------------ analizy do artykułu

def bootstrap_srednie(df, grupa, wartosc, B, rng):
    """95% CI średniej `wartosc` w grupach; bootstrap klastrowy (losowanie osób ze zwracaniem)."""
    tab = df.groupby(["user_symbol", grupa], observed=True)[wartosc].agg(["size", "sum"]).unstack(fill_value=0)
    n, k = tab["size"].to_numpy(float), tab["sum"].to_numpy(float)
    w = rng.multinomial(len(n), np.full(len(n), 1 / len(n)), size=B)
    with np.errstate(invalid="ignore", divide="ignore"):
        p = (w @ k) / (w @ n)
    lo, hi = np.nanpercentile(p, [2.5, 97.5], axis=0)
    return pd.DataFrame({grupa: tab["size"].columns, "ci_lo": lo, "ci_hi": hi})


def udzialy_z_ci(df, grupa, B, rng, wartosc="correct"):
    out = df.groupby(grupa, observed=True).agg(
        n=(wartosc, "size"), k=(wartosc, "sum"), osoby=("user_symbol", "nunique")).reset_index()
    out["p"] = out["k"] / out["n"]
    return out.merge(bootstrap_srednie(df, grupa, wartosc, B, rng), on=grupa, how="left")


def krzywa_uczenia(x, B, rng, max_proba, kohorta):
    a = x.assign(etap=x["proba"].clip(upper=max_proba))
    wszystkie = udzialy_z_ci(a, "etap", B, rng).assign(proba="all")
    c = a.loc[(a["liczba_prob"] >= kohorta) & (a["proba"] <= kohorta)]
    zbalansowana = udzialy_z_ci(c, "etap", B, rng).assign(proba="cohort")
    # prawo potęgowe praktyki: błąd = a * próba^(-b), bez skumulowanej kategorii max_proba+
    w = wszystkie.loc[wszystkie["etap"] < max_proba]
    b, log_a = np.polyfit(np.log(w["etap"]), np.log(1 - w["p"]), 1, w=np.sqrt(w["n"]))
    pred = log_a + b * np.log(w["etap"])
    r2 = 1 - np.sum((np.log(1 - w["p"]) - pred) ** 2) / np.sum((np.log(1 - w["p"]) - np.log(1 - w["p"]).mean()) ** 2)
    return pd.concat([wszystkie, zbalansowana], ignore_index=True), {"b": -b, "a": np.exp(log_a), "r2": r2}


def logit_fe(formula, dane):
    """Regresja logistyczna z efektami stałymi osoby i pytania, SE klastrowane po osobach."""
    d = dane.copy()
    while True:
        zm = (d.groupby("user_symbol")["correct"].transform("nunique") > 1) & \
             (d.groupby("question_id")["correct"].transform("nunique") > 1)
        if zm.all():
            break
        d = d.loc[zm]
    grupy = d["user_symbol"].astype("category").cat.codes
    r = smf.logit(f"{formula} + C(user_symbol) + C(question_id)", d).fit(
        disp=0, maxiter=300, cov_type="cluster", cov_kwds={"groups": grupy})
    terms = [t for t in r.params.index if not t.startswith("C(") and t != "Intercept"]
    ci = r.conf_int()
    rows = pd.DataFrame({"term": terms, "OR": np.exp(r.params[terms]).values,
                         "lo": np.exp(ci.loc[terms, 0]).values, "hi": np.exp(ci.loc[terms, 1]).values,
                         "p": r.pvalues[terms].values})
    info = {"n": len(d), "osoby": d["user_symbol"].nunique(), "pytania": d["question_id"].nunique(),
            "wykluczone": len(dane) - len(d), "zbiezny": bool(r.mle_retvals.get("converged", True))}
    return rows, info


def modele(x, kohorta):
    wyniki, info = {}, {}
    wyniki["M1"], info["M1"] = logit_fe("correct ~ log2_proba", x)
    wyniki["M2"], info["M2"] = logit_fe("correct ~ log2_proba + poprzednia + log2_odstep + staz_lata",
                                        x.loc[x["proba"] >= 2])
    wyniki["M3"], info["M3"] = logit_fe("correct ~ staz_lata", x.loc[x["proba"] == 1])
    # analizy wrażliwości dla efektu log2(próba)
    wrazliwosc = []
    m1 = wyniki["M1"].iloc[0]
    wrazliwosc.append(("main", "Fixed effects for employee and item (main model)", "Main model (fixed effects)",
                       m1.OR, m1.lo, m1.hi, info["M1"]["n"]))
    c = x.loc[(x["liczba_prob"] >= kohorta) & (x["proba"] <= kohorta)]
    r, i = logit_fe("correct ~ log2_proba", c)
    wrazliwosc.append(("cohort", f"Balanced cohort (sequences with $\\geq${kohorta} attempts, attempts 1--{kohorta})",
                       f"Balanced cohort (≥{kohorta} attempts)", r.OR[0], r.lo[0], r.hi[0], i["n"]))
    r, i = logit_fe("correct ~ log2_proba", x.loc[x["proba"] <= 10])
    wrazliwosc.append(("trunc", "Attempts truncated at 10", "Attempts ≤10", r.OR[0], r.lo[0], r.hi[0], i["n"]))
    for od, do in ((3, 4), (5, 7), (8, None)):
        s = x.loc[(x["liczba_prob"] >= od) & ((x["liczba_prob"] <= do) if do else True)]
        r, i = logit_fe("correct ~ log2_proba", s)
        et = f"{od}--{do}" if do else f"$\\geq${od}"
        krotko = f"{od}–{do}" if do else f"≥{od}"
        wrazliwosc.append((f"len{od}", f"Sequences of length {et} only", f"Sequence length {krotko}",
                           r.OR[0], r.lo[0], r.hi[0], i["n"]))
    aktywni = x.groupby("user_symbol")["id"].transform("size") >= 50
    r, i = logit_fe("correct ~ log2_proba", x.loc[aktywni])
    wrazliwosc.append(("active", "Employees with $\\geq$50 responses", "Employees with ≥50 responses",
                       r.OR[0], r.lo[0], r.hi[0], i["n"]))
    r, i = logit_fe("correct ~ log2_proba + staz_lata", x)
    wrazliwosc.append(("tenure", "Adjusted for employee tenure", "Adjusted for tenure",
                       r.OR[0], r.lo[0], r.hi[0], i["n"]))
    grupy = x["user_symbol"].astype("category").cat.codes
    g = smf.gee("correct ~ log2_proba", groups=grupy, data=x, family=sm.families.Binomial(),
                cov_struct=sm.cov_struct.Exchangeable()).fit()
    ci = g.conf_int().loc["log2_proba"]
    wrazliwosc.append(("gee", "GEE, exchangeable correlation within employee (population-averaged)",
                       "GEE (population-averaged)", np.exp(g.params["log2_proba"]), np.exp(ci[0]), np.exp(ci[1]),
                       len(x)))
    # model mieszany (MAP/Laplace): wariancje efektów losowych i ICC
    from statsmodels.genmod.bayes_mixed_glm import BinomialBayesMixedGLM
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        mm = BinomialBayesMixedGLM.from_formula(
            "correct ~ log2_proba", {"u": "0 + C(user_symbol)", "q": "0 + C(question_id)"}, x).fit_map()
    beta, se = mm.fe_mean[1], mm.fe_sd[1]
    wrazliwosc.append(("mixed", "Crossed random intercepts for employee and item (Laplace)",
                       "Mixed model (crossed random intercepts)",
                       np.exp(beta), np.exp(beta - 1.96 * se), np.exp(beta + 1.96 * se), len(x)))
    su, sq = np.exp(mm.vcp_mean)
    total = su ** 2 + sq ** 2 + np.pi ** 2 / 3
    var_f = np.var(beta * x["log2_proba"])
    icc = {"sd_u": su, "sd_q": sq, "icc_u": su ** 2 / total, "icc_q": sq ** 2 / total,
           "r2_m": var_f / (total + var_f), "r2_c": (var_f + su ** 2 + sq ** 2) / (total + var_f)}
    wrazliwosc = pd.DataFrame(wrazliwosc, columns=["key", "analysis", "short", "OR", "lo", "hi", "n"])
    return wyniki, info, wrazliwosc, icc


def przejscia(x, B, rng):
    p = x.loc[x["proba"] >= 2].copy()
    p["poprzednia"] = p["poprzednia"].astype(int)
    tab = udzialy_z_ci(p, "poprzednia", B, rng)
    bb = p.loc[(p["poprzednia"] == 0) & (p["correct"] == 0)].copy()
    bb["ten_sam"] = (bb["answer_id"] == bb["poprzednia_odp"]).astype(int)
    opcje = x.groupby("question_id")["answer_id"].nunique()
    oczek = (1 / (bb["question_id"].map(opcje) - 1).clip(lower=1)).mean()
    # wybór niezależny od poprzedniego, ale zgodny z popularnością dystraktorów w danym pytaniu
    s = x.loc[x["correct"] == 0].groupby("question_id")["answer_id"].value_counts(normalize=True)
    oczek_pop = bb["question_id"].map((s ** 2).groupby(level=0).sum()).mean()
    ci = bootstrap_srednie(bb.assign(g=1), "g", "ten_sam", B, rng).iloc[0]
    dystraktor = {"n": len(bb), "p": bb["ten_sam"].mean(), "lo": ci.ci_lo, "hi": ci.ci_hi,
                  "oczekiwane": oczek, "oczekiwane_pop": oczek_pop}
    return tab, dystraktor


def retencja_wg_odstepu(x, B, rng):
    p = x.loc[x["proba"] >= 2].copy()
    p["przedzial"] = pd.cut(p["odstep_dni"], PRZEDZIALY_DNI, right=False, labels=range(len(ETYKIETY_DNI)))
    out = []
    for prev, g in p.groupby("poprzednia"):
        out.append(udzialy_z_ci(g, "przedzial", B, rng).assign(poprzednia=int(prev)))
    out = pd.concat(out, ignore_index=True)
    out["przedzial_dni"] = out["przedzial"].astype(int).map(dict(enumerate(ETYKIETY_DNI)))
    return out


def zmiana_osob(pairs, users, B, rng):
    d = ((users["poprawnych_3"] - users["poprawnych_1"]) / users["pytania_min3"]).to_numpy()
    ui, uw = int((d > 0).sum()), int((d < 0).sum())
    znak = binomtest(ui, ui + uw, 0.5) if ui + uw else None
    nz = d[d != 0]
    w = wilcoxon(nz) if len(nz) else None
    r = rankdata(np.abs(nz))
    rb = (r[nz > 0].sum() - r[nz < 0].sum()) / r.sum() if len(nz) else np.nan
    boot = np.array([rng.choice(d, len(d)).mean() for _ in range(B)])
    b = int(((pairs["poprawna_1"] == 1) & (pairs["poprawna_3"] == 0)).sum())
    c = int(((pairs["poprawna_1"] == 0) & (pairs["poprawna_3"] == 1)).sum())
    mc = mcnemar([[0, b], [c, 0]], exact=False, correction=True)
    return {"osoby": len(d), "poprawa": ui, "pogorszenie": uw, "bez_zmian": len(d) - ui - uw,
            "sredni_pp": 100 * d.mean(), "sredni_lo": 100 * np.percentile(boot, 2.5),
            "sredni_hi": 100 * np.percentile(boot, 97.5), "mediana_pp": 100 * np.median(d),
            "znak_p": znak.pvalue if znak else np.nan,
            "znak_lo": znak.proportion_ci().low if znak else np.nan,
            "znak_hi": znak.proportion_ci().high if znak else np.nan,
            "wilcoxon_W": w.statistic if w else np.nan, "wilcoxon_p": w.pvalue if w else np.nan,
            "r_rb": rb, "pary": len(pairs), "mc_b": b, "mc_c": c, "mc_chi2": mc.statistic, "mc_p": mc.pvalue,
            "p1": pairs["poprawna_1"].mean(), "p3": pairs["poprawna_3"].mean()}, d


def analiza_pozycji(x, min_n, alfa):
    """Klasyczna analiza pozycji testowych na pierwszych próbach + trend w kolejnych próbach."""
    f = x.loc[x["proba"] == 1].copy()
    tot = f.groupby("user_symbol")["correct"].agg(["size", "sum"])
    f = f.join(tot, on="user_symbol")
    f = f.loc[f["size"] >= 10]
    f["reszta"] = (f["sum"] - f["correct"]) / (f["size"] - 1)
    wiersze = []
    for q, g in x.groupby("question_id"):
        fq = f.loc[f["question_id"] == q]
        pierwsze = g.loc[g["proba"] == 1]
        bledne = g.loc[g["correct"] == 0, "answer_id"].value_counts()
        wiersz = {"question_id": q, "room_Code": g["room_Code"].iloc[0], "n": len(g),
                  "osoby": g["user_symbol"].nunique(), "opcje_obserwowane": g["answer_id"].nunique(),
                  "p_pierwsza": pierwsze["correct"].mean(), "n_pierwsza": len(pierwsze),
                  "p_kolejne": g.loc[g["proba"] >= 2, "correct"].mean(),
                  "dominujacy_dystraktor_udzial": bledne.iloc[0] / bledne.sum() if len(bledne) else np.nan,
                  "dystraktory_obserwowane": len(bledne),
                  "dystraktory_niefunkcjonalne": int((bledne / len(g) < 0.05).sum()),
                  "dyskryminacja": np.nan, "OR_log2_proba": np.nan, "p_trend": np.nan}
        if len(fq) >= min_n and fq["correct"].nunique() > 1 and fq["reszta"].nunique() > 1:
            wiersz["dyskryminacja"] = pearsonr(fq["correct"], fq["reszta"])[0]
        if g["correct"].nunique() > 1 and g["proba"].nunique() > 1:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    r = smf.logit("correct ~ log2_proba", g).fit(
                        disp=0, cov_type="cluster",
                        cov_kwds={"groups": g["user_symbol"].astype("category").cat.codes})
                wiersz["OR_log2_proba"] = np.exp(r.params["log2_proba"])
                wiersz["p_trend"] = r.pvalues["log2_proba"]
            except Exception:
                pass
        wiersze.append(wiersz)
    out = pd.DataFrame(wiersze)
    ok = out["p_trend"].notna()
    out["q_fdr"] = np.nan
    if ok.any():
        out.loc[ok, "q_fdr"] = multipletests(out.loc[ok, "p_trend"], method="fdr_bh")[1]
    out["istotna_poprawa"] = (out["q_fdr"] < alfa) & (out["OR_log2_proba"] > 1)
    out["istotne_pogorszenie"] = (out["q_fdr"] < alfa) & (out["OR_log2_proba"] < 1)
    return out


# ------------------------------------------------------------ formatowanie LaTeX

def f_int(v):
    return f"{int(round(v)):,}"


def f_pct(p, d=1):
    return f"{100 * p:.{d}f}"


def f_ci(lo, hi, d=1, skala=100):
    return f"[{skala * lo:.{d}f}, {skala * hi:.{d}f}]"


def f_or(v):
    return f"{v:.2f}"


def f_p(p):
    if pd.isna(p):
        return "--"
    return "$<$0.001" if p < 0.001 else f"{p:.3f}"


def esc(s):
    return str(s).replace("\\", "\\textbackslash{}").replace("&", "\\&").replace("%", "\\%") \
        .replace("_", "\\_").replace("#", "\\#")


def tabela_tex(katalog, nazwa, df, podpis, wyrownanie=None, uwaga=None, szeroka=False):
    srod = "table*" if szeroka else "table"
    al = wyrownanie or "l" + "r" * (len(df.columns) - 1)
    lines = [f"\\begin{{{srod}}}[htbp]", "\\centering", f"\\caption{{{podpis}}}",
             f"\\label{{tab:{nazwa}}}", "\\small"] + (["\\setlength{\\tabcolsep}{3.5pt}"] if szeroka else []) + [
             f"\\begin{{tabular}}{{{al}}}", "\\toprule",
             " & ".join(df.columns) + " \\\\", "\\midrule"]
    for _, row in df.iterrows():
        if str(row.iloc[0]).startswith("\\midrule"):
            lines.append("\\midrule")
            continue
        lines.append(" & ".join(str(v) for v in row.values) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    if uwaga:
        lines += ["", "\\vspace{2pt}", f"\\parbox{{\\linewidth}}{{\\footnotesize {uwaga}}}"]
    lines.append(f"\\end{{{srod}}}")
    (katalog / f"{nazwa}.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")


def sep():
    return "\\midrule"


# ------------------------------------------------------------ wykresy

def styl_wykresow():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8, "legend.fontsize": 7,
        "xtick.labelsize": 7, "ytick.labelsize": 7, "axes.spines.top": False,
        "axes.spines.right": False, "axes.edgecolor": "#52514e", "axes.labelcolor": "#0b0b0b",
        "xtick.color": "#52514e", "ytick.color": "#52514e", "axes.grid": True, "axes.grid.axis": "y",
        "grid.color": "#e4e3df", "grid.linewidth": 0.6, "lines.linewidth": 1.5, "lines.markersize": 4.5,
        "legend.frameon": False, "axes.axisbelow": True, "savefig.bbox": "tight", "savefig.dpi": 300, "pdf.fonttype": 42})
    return plt


def zapisz(fig, katalog, nazwa):
    for ext in ("pdf", "png"):
        fig.savefig(katalog / f"{nazwa}.{ext}")
    fig.clf()


def wykres_krzywa(plt, katalog, krzywa, fit, max_proba, kohorta):
    fig, ax = plt.subplots(figsize=(3.5, 2.5))
    n_kohorta = f_int(krzywa.loc[krzywa["proba"] == "cohort", "n"].iloc[0])
    for proba, kolor, marker, etykieta in [
            ("all", KOLOR_1, "o", "All sequences"),
            ("cohort", KOLOR_2, "s", f"Same {n_kohorta} sequences, attempts 1\u2013{kohorta}")]:
        k = krzywa.loc[krzywa["proba"] == proba]
        off = -0.08 if proba == "all" else 0.08
        ax.errorbar(k["etap"] + off, 100 * k["p"], yerr=[100 * (k["p"] - k["ci_lo"]), 100 * (k["ci_hi"] - k["p"])],
                    color=kolor, marker=marker, capsize=2, elinewidth=0.8, label=etykieta)
    xs = np.linspace(1, max_proba - 1, 100)
    ax.plot(xs, 100 * (1 - fit["a"] * xs ** (-fit["b"])), ls="--", lw=1, color=SZARY,
            label=f"Power-law fit (error $\\propto$ attempt$^{{-{fit['b']:.2f}}}$)")
    ax.set_xticks(range(1, max_proba + 1))
    ax.set_xticklabels([str(i) for i in range(1, max_proba)] + [f"{max_proba}+"])
    ax.set_xlabel("Attempt number (same employee, same question)")
    ax.set_ylabel("Correct responses (%)")
    ax.legend(loc="lower right")
    zapisz(fig, katalog, "fig_learning_curve")


def wykres_odstep(plt, katalog, ret):
    fig, ax = plt.subplots(figsize=(3.5, 2.5))
    for prev, kolor, marker, etykieta in [(1, KOLOR_1, "o", "Previous attempt correct"),
                                          (0, KOLOR_2, "s", "Previous attempt incorrect")]:
        k = ret.loc[ret["poprzednia"] == prev]
        xs = k["przedzial"].astype(int) + (-0.08 if prev else 0.08)
        ax.errorbar(xs, 100 * k["p"], yerr=[100 * (k["p"] - k["ci_lo"]), 100 * (k["ci_hi"] - k["p"])],
                    color=kolor, marker=marker, capsize=2, elinewidth=0.8, label=etykieta)
    ax.set_xticks(range(len(ETYKIETY_DNI)))
    ax.set_xticklabels([e.replace("--", "–").replace("$\\geq$", "≥") for e in ETYKIETY_DNI])
    ax.set_xlabel("Days since previous attempt at the same question")
    ax.set_ylabel("Correct responses (%)")
    ax.legend(loc="center right")
    zapisz(fig, katalog, "fig_retention_interval")


def wykres_osoby(plt, katalog, d):
    fig, ax = plt.subplots(figsize=(3.5, 2.3))
    v = 100 * d
    kraw = np.arange(np.floor(v.min() / 5) * 5 - 2.5, np.ceil(v.max() / 5) * 5 + 5, 5)
    ax.hist(v, bins=kraw, color=KOLOR_1, edgecolor="white", linewidth=1)
    ax.axvline(0, color="#52514e", lw=0.8)
    ax.set_xlabel("Change in accuracy, attempt 3 − attempt 1 (pp)")
    ax.set_ylabel("Employees")
    zapisz(fig, katalog, "fig_employee_change")


def wykres_pozycje(plt, katalog, poz, alfa):
    fig, ax = plt.subplots(figsize=(3.5, 2.7))
    ax.grid(axis="x")
    k = poz.dropna(subset=["dyskryminacja"])
    sig = k["istotna_poprawa"]
    ax.scatter(100 * k.loc[~sig, "p_pierwsza"], k.loc[~sig, "dyskryminacja"], s=14, color=SZARY,
               marker="o", alpha=0.8, label="No significant trend", edgecolors="white", linewidths=0.5)
    ax.scatter(100 * k.loc[sig, "p_pierwsza"], k.loc[sig, "dyskryminacja"], s=16, color=KOLOR_1,
               marker="^", label=f"Improves (FDR q<{alfa})", edgecolors="white", linewidths=0.5)
    ax.axhline(0.2, color="#52514e", lw=0.7, ls=":")
    ax.axvline(90, color="#52514e", lw=0.7, ls=":")
    ax.set_xlabel("Item difficulty: correct at first attempt (%)")
    ax.set_ylabel("Discrimination (item–rest $r$)")
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1), ncol=2, borderaxespad=0.2, handletextpad=0.2)
    zapisz(fig, katalog, "fig_item_analysis")


def wykres_wrazliwosc(plt, katalog, wraz):
    w = wraz.iloc[::-1].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(3.5, 0.26 * len(w) + 0.7))
    ax.grid(axis="x"); ax.grid(axis="y", visible=False)
    glowny = w["key"] == "main"
    for maska, kolor, marker in ((~glowny, SZARY, "o"), (glowny, KOLOR_1, "D")):
        k = w.loc[maska]
        ax.errorbar(k["OR"].to_numpy(), k.index.to_numpy(),
                    xerr=[(k["OR"] - k["lo"]).to_numpy(), (k["hi"] - k["OR"]).to_numpy()], fmt=marker, color=kolor,
                    capsize=2, elinewidth=1, markersize=4.5)
    ax.axvline(1, color="#52514e", lw=0.8)
    ax.set_xscale("log")
    ticks = [1, 1.2, 1.4, 1.6]
    ax.set_xticks(ticks); ax.set_xticklabels([f"{t:g}" for t in ticks]); ax.minorticks_off()
    ax.set_xlim(0.95, max(1.7, w["hi"].max() * 1.05))
    ax.set_yticks(w.index); ax.set_yticklabels(w["short"])
    ax.set_xlabel("Odds ratio per doubling of attempt number (log scale)")
    zapisz(fig, katalog, "fig_sensitivity")


def wykres_aktywnosc(plt, katalog, x):
    mies = x.groupby(x["create_time"].dt.to_period("M")).agg(n=("id", "size"), osoby=("user_symbol", "nunique"))
    mies = mies.reindex(pd.period_range(mies.index.min(), mies.index.max(), freq="M"), fill_value=0)
    fig, axs = plt.subplots(2, 1, figsize=(7, 3.4), sharex=True)
    xs = mies.index.to_timestamp()
    for ax, kol, et in [(axs[0], "n", "Responses per month"), (axs[1], "osoby", "Active employees")]:
        ax.bar(xs, mies[kol], width=24, color=KOLOR_1)
        ax.set_ylabel(et)
    fig.align_ylabels(axs)
    zapisz(fig, katalog, "fig_activity")


# ------------------------------------------------------------ artykuł: tabele, makra, szkic

def materialy_artykulu(x, rejected, pairs, users, katalog, args):
    rng = np.random.default_rng(args.seed)
    tdir, fdir, cdir = katalog / "tables", katalog / "figures", katalog / "csv"
    for d in (tdir, fdir, cdir):
        d.mkdir(parents=True, exist_ok=True)
    B, K, MX = args.bootstrap, args.kohorta, args.max_proba
    ci_uwaga = (f"95\\% confidence intervals from a cluster bootstrap resampling employees "
                f"({B:,} replicates).")
    M = {}

    # --- Tabela 1: charakterystyka zbioru
    sek = x.groupby(KLUCZ).size()
    per_user = x.groupby("user_symbol").agg(n=("id", "size"), q=("question_id", "nunique"),
                                            dni=("create_time", lambda s: s.dt.normalize().nunique()))
    gap = x["odstep_dni"].dropna()
    dzienne = x.groupby(["user_symbol", x["create_time"].dt.normalize()]).size()
    opcje = x.groupby("question_id")["answer_id"].nunique()
    M.update(NResponses=f_int(len(x)), NEmployees=f_int(x["user_symbol"].nunique()),
             NItems=f_int(x["question_id"].nunique()), NModules=f_int(x["room_Code"].nunique()),
             NSequences=f_int(len(sek)), NRejected=f_int(len(rejected)),
             DateStart=x["create_time"].min().strftime("%B %Y"), DateEnd=x["create_time"].max().strftime("%B %Y"),
             AccOverall=f_pct(x["correct"].mean()), AccFirst=f_pct(x.loc[x["proba"] == 1, "correct"].mean()),
             AttemptsMedian=f"{sek.median():.0f}", AttemptsMax=f"{sek.max():.0f}",
             SeqRepeatedPct=f_pct((sek >= 2).mean()), SeqMinThreePct=f_pct((sek >= 3).mean()),
             GapMedian=f"{gap.median():.0f}", GapQOne=f"{gap.quantile(.25):.0f}", GapQThree=f"{gap.quantile(.75):.0f}",
             DailyMedian=f"{dzienne.median():.0f}",
             RespPerEmpMedian=f_int(per_user["n"].median()),
             RespPerEmpQOne=f_int(per_user["n"].quantile(.25)), RespPerEmpQThree=f_int(per_user["n"].quantile(.75)))
    wd = (x["create_time"].dt.dayofweek < 5).mean()
    zakres = x.groupby("user_symbol")["create_time"].agg(["min", "max"])
    staz_mies = (zakres["max"] - zakres["min"]).dt.days / 30.44
    koniec = x["create_time"].max() - pd.Timedelta(days=90)
    M.update(SpanMonthsMedian=f"{staz_mies.median():.0f}", ActiveLastQuarterPct=f_pct((zakres["max"] >= koniec).mean()),
             WeekdayPct=f_pct(wd), ItemsPerEmpMedian=f"{per_user['q'].median():.0f}",
             ActiveDaysMedian=f"{per_user['dni'].median():.0f}", OptionsMedian=f"{opcje.median():.0f}",
             NExcluded=f_int(args.wykluczone_n),
             ExcludedModules=", ".join(esc(k) for k in args.wyklucz_pokoje) or "none")
    t1 = [
        ("Responses", M["NResponses"]), ("Employees", M["NEmployees"]),
        ("Items (questions)", M["NItems"]), ("Modules", M["NModules"]),
        ("Observation period", f"{x['create_time'].min():%Y-%m-%d} -- {x['create_time'].max():%Y-%m-%d}"),
        ("Employee--item sequences", M["NSequences"]),
        ("Response options per item, median (range)", f"{opcje.median():.0f} ({opcje.min()}--{opcje.max()})"),
        (sep(), ""),
        ("Responses per employee, median [IQR]",
         f"{M['RespPerEmpMedian']} [{M['RespPerEmpQOne']}, {M['RespPerEmpQThree']}]"),
        ("Items per employee, median [IQR]",
         f"{per_user['q'].median():.0f} [{per_user['q'].quantile(.25):.0f}, {per_user['q'].quantile(.75):.0f}]"),
        ("Active days per employee, median [IQR]",
         f"{per_user['dni'].median():.0f} [{per_user['dni'].quantile(.25):.0f}, {per_user['dni'].quantile(.75):.0f}]"),
        ("Responses per active day, median [IQR]",
         f"{dzienne.median():.0f} [{dzienne.quantile(.25):.0f}, {dzienne.quantile(.75):.0f}]"),
        ("Responses on weekdays (\\%)", f_pct(wd)),
        ("Months between first and last response, median [IQR]",
         f"{staz_mies.median():.0f} [{staz_mies.quantile(.25):.0f}, {staz_mies.quantile(.75):.0f}]"),
        ("Employees active in the last 90 days of data (\\%)", M["ActiveLastQuarterPct"]),
        (sep(), ""),
        ("Attempts per sequence, median [IQR] (max)",
         f"{sek.median():.0f} [{sek.quantile(.25):.0f}, {sek.quantile(.75):.0f}] ({sek.max()})"),
        ("Sequences with $\\geq$2 / $\\geq$3 attempts (\\%)", f"{M['SeqRepeatedPct']} / {M['SeqMinThreePct']}"),
        ("Days between attempts, median [IQR]", f"{M['GapMedian']} [{M['GapQOne']}, {M['GapQThree']}]"),
        (sep(), ""),
        ("Correct responses, overall (\\%)", M["AccOverall"]),
        ("Correct responses, first attempts (\\%)", M["AccFirst"]),
    ]
    tabela_tex(tdir, "dataset", pd.DataFrame(t1, columns=["Characteristic", "Value"]),
               "Characteristics of the dataset.", "lr",
               "IQR, interquartile range. A sequence is the series of attempts by one employee at one item."
               + (f" Excluded test module(s): {M['ExcludedModules']} ({M['NExcluded']} responses)."
                  if args.wykluczone_n else ""))

    # --- czy harmonogram powtórek zależy od poprawności? (argument przeciw selekcji)
    nast = x.assign(ma_nast=x.groupby(KLUCZ)["id"].shift(-1).notna(),
                    nast_odstep=x.groupby(KLUCZ)["odstep_dni"].shift(-1))
    h = nast.groupby("correct").agg(p=("ma_nast", "mean"), gap=("nast_odstep", "median"))
    M.update(ReaskAfterCorrect=f_pct(h.loc[1, "p"]), ReaskAfterIncorrect=f_pct(h.loc[0, "p"]),
             GapAfterCorrect=f"{h.loc[1, 'gap']:.0f}", GapAfterIncorrect=f"{h.loc[0, 'gap']:.0f}")
    h.reset_index().to_csv(cdir / "schedule_by_correctness.csv", index=False)

    # --- Tabela 3 i wykres 1: krzywa uczenia
    krzywa, fit = krzywa_uczenia(x, B, rng, MX, K)
    krzywa.to_csv(cdir / "learning_curve.csv", index=False)
    a, c = krzywa.loc[krzywa["proba"] == "all"], krzywa.loc[krzywa["proba"] == "cohort"].set_index("etap")
    t3 = []
    for _, r in a.iterrows():
        e = int(r["etap"])
        row = [f"{e}+" if e == MX else str(e), f_int(r["n"]), f_int(r["osoby"]), f_pct(r["p"]),
               f_ci(r["ci_lo"], r["ci_hi"])]
        row += ([f_int(c.loc[e, "n"]), f_pct(c.loc[e, "p"]), f_ci(c.loc[e, "ci_lo"], c.loc[e, "ci_hi"])]
                if e in c.index else ["", "", ""])
        t3.append(row)
    tabela_tex(tdir, "learning_curve",
               pd.DataFrame(t3, columns=["Attempt", "$n$", "Employees", "\\%", "95\\% CI",
                                         "$n$ (cohort)", "\\% (cohort)", "95\\% CI (cohort)"]),
               "Accuracy by attempt number within employee--item sequences.", "lrrrlrrl",
               f"Cohort: sequences with $\\geq${K} attempts, which keeps the set of sequences constant across "
               f"attempts 1--{K} and removes survivorship bias. {ci_uwaga}", szeroka=True)
    a1, aM = a.iloc[0], a.iloc[-1]
    c1, cK = c.iloc[0], c.iloc[-1]
    M.update(AccAttOne=f_pct(a1["p"]), AccAttOneCI=f_ci(a1["ci_lo"], a1["ci_hi"]),
             AccAttMax=f_pct(aM["p"]), AccAttMaxCI=f_ci(aM["ci_lo"], aM["ci_hi"]), AttMax=f"{MX}",
             CohortK=f"{K}", CohortN=f_int(len(x.loc[x["liczba_prob"] >= K].groupby(KLUCZ))),
             CohortAccOne=f_pct(c1["p"]), CohortAccK=f_pct(cK["p"]),
             CohortAccOneCI=f_ci(c1["ci_lo"], c1["ci_hi"]), CohortAccKCI=f_ci(cK["ci_lo"], cK["ci_hi"]),
             PowerLawB=f"{fit['b']:.2f}", PowerLawRsq=f"{fit['r2']:.2f}")

    # --- Tabela 4: modele
    wyniki, info, wraz, icc = modele(x, K)
    nazwy = {"log2_proba": "Attempt number (per doubling)", "poprzednia": "Previous attempt correct",
             "log2_odstep": "Days since previous attempt (per doubling)",
             "staz_lata": "Employee tenure (per year)"}
    kolejnosc = ["log2_proba", "poprzednia", "log2_odstep", "staz_lata"]
    t4 = []
    for term in kolejnosc:
        row = [nazwy[term]]
        for m in ("M1", "M2", "M3"):
            w = wyniki[m].set_index("term")
            row.append(f"{f_or(w.loc[term, 'OR'])} [{f_or(w.loc[term, 'lo'])}, {f_or(w.loc[term, 'hi'])}]"
                       if term in w.index else "")
        t4.append(row)
    t4.append([sep(), "", "", ""])
    t4.append(["Sample"] + ["All attempts", "Attempts $\\geq$2", "First attempts"])
    t4.append(["Responses"] + [f_int(info[m]["n"]) for m in ("M1", "M2", "M3")])
    t4.append(["Employees / items"] + [f"{info[m]['osoby']} / {info[m]['pytania']}" for m in ("M1", "M2", "M3")])
    tabela_tex(tdir, "regression",
               pd.DataFrame(t4, columns=["Predictor", "Model 1", "Model 2", "Model 3"]),
               "Logistic regression of response correctness: odds ratios [95\\% CI].", "llll",
               "All models include fixed effects for employee and item; standard errors are clustered by employee. "
               "Employees or items with no variation in correctness are dropped by the conditional likelihood "
               f"(Model 1: {info['M1']['wykluczone']:,} responses). Model 3 tests whether accuracy on newly "
               "encountered items improves with time in the programme.", szeroka=True)
    pd.concat([w.assign(model=m) for m, w in wyniki.items()]).to_csv(cdir / "regression.csv", index=False)
    for m, pref in (("M1", "MOne"), ("M2", "MTwo"), ("M3", "MThree")):
        for _, r in wyniki[m].iterrows():
            nm = {"log2_proba": "Attempt", "poprzednia": "Prev", "log2_odstep": "Gap", "staz_lata": "Tenure"}[r.term]
            M[f"OR{pref}{nm}"] = f_or(r.OR)
            M[f"OR{pref}{nm}CI"] = f"[{f_or(r.lo)}, {f_or(r.hi)}]"
            M[f"P{pref}{nm}"] = f_p(r.p)
    M.update(ICCEmployee=f"{icc['icc_u']:.2f}", ICCItem=f"{icc['icc_q']:.2f}",
             SDEmployee=f"{icc['sd_u']:.2f}", SDItem=f"{icc['sd_q']:.2f}",
             RsqMarginal=f"{icc['r2_m']:.3f}", RsqConditional=f"{icc['r2_c']:.2f}")

    # --- Tabela 5: wrażliwość
    wraz.to_csv(cdir / "sensitivity.csv", index=False)
    t5 = pd.DataFrame({"Analysis": wraz["analysis"], "Responses": wraz["n"].map(f_int),
                       "OR [95\\% CI]": [f"{f_or(o)} [{f_or(l)}, {f_or(h)}]"
                                         for o, l, h in zip(wraz["OR"], wraz["lo"], wraz["hi"])]})
    tabela_tex(tdir, "sensitivity", t5,
               "Sensitivity analyses: odds ratio for correctness per doubling of the attempt number.", "p{8cm}rr",
               f"Variance of the random intercepts (logit scale): employee SD = {icc['sd_u']:.2f}, "
               f"item SD = {icc['sd_q']:.2f}; latent-scale ICC: employee = {icc['icc_u']:.2f}, "
               f"item = {icc['icc_q']:.2f}; Nakagawa $R^2$: marginal = {icc['r2_m']:.3f}, "
               f"conditional = {icc['r2_c']:.2f}. Sequence-length strata address pattern-mixture "
               "(attrition) bias in the learning curve.")
    M.update(ORRange=f"{wraz['OR'].min():.2f}--{wraz['OR'].max():.2f}")
    for _, r in wraz.iterrows():
        nm = "Sens" + "".join(ch for ch in r.key.title() if ch.isalpha()) + \
             {"len3": "Three", "len5": "Five", "len8": "Eight"}.get(r.key, "")
        M[f"OR{nm}"] = f_or(r.OR)
        M[f"OR{nm}CI"] = f"[{f_or(r.lo)}, {f_or(r.hi)}]"

    # --- Tabela 6: przejścia między kolejnymi próbami + dystraktory
    tr, dys = przejscia(x, B, rng)
    tr.to_csv(cdir / "transitions.csv", index=False)
    t6 = []
    for _, r in tr.sort_values("poprzednia", ascending=False).iterrows():
        et = "Correct" if r["poprzednia"] == 1 else "Incorrect"
        t6.append([et, f_int(r["n"]), f_pct(r["p"]), f_ci(r["ci_lo"], r["ci_hi"]), f_pct(1 - r["p"])])
    tabela_tex(tdir, "transitions",
               pd.DataFrame(t6, columns=["Previous attempt", "$n$", "Next correct (\\%)", "95\\% CI",
                                         "Next incorrect (\\%)"]),
               "Transitions between consecutive attempts at the same item.", "lrrlr",
               f"After two consecutive errors, the same distractor was chosen in {f_pct(dys['p'])}\\% "
               f"{f_ci(dys['lo'], dys['hi'])} of cases ($n$ = {dys['n']:,}); the value expected under random "
               f"choice among the observed distractors was {f_pct(dys['oczekiwane'])}\\%, and "
               f"{f_pct(dys['oczekiwane_pop'])}\\% when weighted by each distractor's overall popularity "
               f"for the item. {ci_uwaga}")
    r1, r0 = tr.set_index("poprzednia").loc[1], tr.set_index("poprzednia").loc[0]
    M.update(RetainPct=f_pct(r1["p"]), RetainCI=f_ci(r1["ci_lo"], r1["ci_hi"]),
             ForgetPct=f_pct(1 - r1["p"]), RecoverPct=f_pct(r0["p"]),
             RecoverCI=f_ci(r0["ci_lo"], r0["ci_hi"]), PersistPct=f_pct(1 - r0["p"]),
             SameDistractorPct=f_pct(dys["p"]), SameDistractorCI=f_ci(dys["lo"], dys["hi"]),
             SameDistractorN=f_int(dys["n"]), SameDistractorExpected=f_pct(dys["oczekiwane"]),
             SameDistractorExpectedPop=f_pct(dys["oczekiwane_pop"]))

    # --- Tabela 7 i wykres 2: retencja wg odstępu
    ret = retencja_wg_odstepu(x, B, rng)
    ret.to_csv(cdir / "retention_interval.csv", index=False)
    t7 = []
    piv = ret.set_index(["przedzial_dni", "poprzednia"])
    for e in ETYKIETY_DNI:
        row = [e]
        for prev in (1, 0):
            if (e, prev) in piv.index:
                r = piv.loc[(e, prev)]
                row += [f_int(r["n"]), f"{f_pct(r['p'])} {f_ci(r['ci_lo'], r['ci_hi'])}"]
            else:
                row += ["", ""]
        t7.append(row)
    rc, ri = piv.xs(1, level="poprzednia"), piv.xs(0, level="poprzednia")
    M.update(RetShortCorrect=f_pct(rc["p"].iloc[0]), RetLongCorrect=f_pct(rc["p"].iloc[-1]),
             RetShortIncorrect=f_pct(ri["p"].iloc[0]), RetLongIncorrect=f_pct(ri["p"].iloc[-1]))
    tabela_tex(tdir, "retention_interval",
               pd.DataFrame(t7, columns=["Days since previous", "$n$", "Correct, \\% [95\\% CI]",
                                         "$n$", "Correct, \\% [95\\% CI]"]),
               "Accuracy by interval since the previous attempt at the same item, "
               "for previously correct (left) and incorrect (right) responses.", "lrlrl", ci_uwaga)

    # --- Tabela 8 i wykres 3: zmiana na poziomie osób
    zo, dvec = zmiana_osob(pairs, users, B, rng)
    t8 = [
        ("Employees with $\\geq$1 sequence of $\\geq$3 attempts", f_int(zo["osoby"])),
        ("Improved / worsened / unchanged", f"{zo['poprawa']} / {zo['pogorszenie']} / {zo['bez_zmian']}"),
        ("Mean change, pp [95\\% CI]", f"{zo['sredni_pp']:.1f} {f_ci(zo['sredni_lo'], zo['sredni_hi'], 1, 1)}"),
        ("Median change, pp", f"{zo['mediana_pp']:.1f}"),
        ("Sign test, proportion improving [95\\% CI]; $p$",
         f"{zo['poprawa'] / (zo['poprawa'] + zo['pogorszenie']):.2f} "
         f"[{zo['znak_lo']:.2f}, {zo['znak_hi']:.2f}]; {f_p(zo['znak_p'])}"),
        ("Wilcoxon signed-rank $W$; $p$; rank-biserial $r$",
         f"{zo['wilcoxon_W']:,.0f}; {f_p(zo['wilcoxon_p'])}; {zo['r_rb']:.2f}"),
        (sep(), ""),
        ("Sequences (employee--item) with $\\geq$3 attempts", f_int(zo["pary"])),
        ("Correct at attempt 1 / attempt 3 (\\%)", f"{f_pct(zo['p1'])} / {f_pct(zo['p3'])}"),
        ("Incorrect$\\to$correct / correct$\\to$incorrect", f"{zo['mc_c']:,} / {zo['mc_b']:,}"),
        ("McNemar $\\chi^2$; $p$ (ignores clustering)", f"{zo['mc_chi2']:.1f}; {f_p(zo['mc_p'])}"),
    ]
    tabela_tex(tdir, "employee_change", pd.DataFrame(t8, columns=["Measure", "Value"]),
               "Change in accuracy between the first and third attempt at the same items.", "lr",
               "Employee-level change: difference in the proportion of correct answers between attempt 3 and "
               "attempt 1 across the employee's own sequences with $\\geq$3 attempts; ties excluded from the sign "
               "and Wilcoxon tests. pp, percentage points.")
    pd.DataFrame([zo]).to_csv(cdir / "employee_change.csv", index=False)
    M.update(EmpN=f_int(zo["osoby"]), EmpImproved=f_int(zo["poprawa"]), EmpWorsened=f_int(zo["pogorszenie"]),
             EmpUnchanged=f_int(zo["bez_zmian"]), EmpMeanChange=f"{zo['sredni_pp']:.1f}",
             EmpMeanChangeCI=f_ci(zo["sredni_lo"], zo["sredni_hi"], 1, 1), SignP=f_p(zo["znak_p"]),
             WilcoxonP=f_p(zo["wilcoxon_p"]), RankBiserial=f"{zo['r_rb']:.2f}",
             EmpSharePct=f_pct(zo["osoby"] / x["user_symbol"].nunique()))

    # --- Tabela 9 i wykres 4: analiza pozycji
    poz = analiza_pozycji(x, args.min_pozycja, args.alfa)
    poz.to_csv(cdir / "items.csv", index=False)
    dk = poz["dyskryminacja"]
    t9 = [
        ("Items analysed", f_int(len(poz))),
        ("Difficulty (first-attempt \\% correct), median [IQR]",
         f"{f_pct(poz['p_pierwsza'].median())} [{f_pct(poz['p_pierwsza'].quantile(.25))}, "
         f"{f_pct(poz['p_pierwsza'].quantile(.75))}]"),
        ("Items with $<$50\\% / 50--90\\% / $>$90\\% correct",
         f"{(poz['p_pierwsza'] < .5).sum()} / {poz['p_pierwsza'].between(.5, .9).sum()} / {(poz['p_pierwsza'] > .9).sum()}"),
        (f"Discrimination (item--rest $r$), median [IQR], items with $n\\geq${args.min_pozycja}",
         f"{dk.median():.2f} [{dk.quantile(.25):.2f}, {dk.quantile(.75):.2f}] ($k$ = {dk.notna().sum()})"),
        ("Items with $r<0.20$ / $0.20$--$0.29$ / $\\geq0.30$",
         f"{(dk < .2).sum()} / {dk.between(.2, .3, inclusive='left').sum()} / {(dk >= .3).sum()}"),
        ("Share of errors on the most frequent distractor, median [IQR]",
         f"{f_pct(poz['dominujacy_dystraktor_udzial'].median())} "
         f"[{f_pct(poz['dominujacy_dystraktor_udzial'].quantile(.25))}, "
         f"{f_pct(poz['dominujacy_dystraktor_udzial'].quantile(.75))}]"),
        ("Observed distractors chosen by $<$5\\% of responses (non-functioning)",
         f"{poz['dystraktory_niefunkcjonalne'].sum()} of {poz['dystraktory_obserwowane'].sum()} "
         f"({f_pct(poz['dystraktory_niefunkcjonalne'].sum() / poz['dystraktory_obserwowane'].sum())}\\%)"),
        (f"Items improving / worsening with repetition (FDR $q<{args.alfa}$)",
         f"{poz['istotna_poprawa'].sum()} / {poz['istotne_pogorszenie'].sum()} "
         f"(of {poz['p_trend'].notna().sum()} testable)"),
    ]
    tabela_tex(tdir, "items", pd.DataFrame(t9, columns=["Measure", "Value"]),
               "Item analysis (classical test theory).", "p{8.5cm}r",
               "Difficulty and discrimination computed on first attempts; item--rest correlation uses each "
               "employee's accuracy on the remaining items (employees with $\\geq$10 first attempts). Trend: per-item "
               "logistic regression of correctness on log$_2$(attempt) with employee-clustered SE, Benjamini--Hochberg "
               "correction. Distractors never chosen are not observable in the log and are not counted.")
    najtr = poz.sort_values("p_pierwsza").head(args.top_pozycje)
    t10 = pd.DataFrame({"Item": najtr["question_id"], "Module": najtr["room_Code"].map(esc),
                        "$n$": najtr["n"].map(f_int), "First (\\%)": najtr["p_pierwsza"].map(f_pct),
                        "Repeat (\\%)": najtr["p_kolejne"].map(lambda v: "--" if pd.isna(v) else f_pct(v)),
                        "Top distr.\\ (\\%)": najtr["dominujacy_dystraktor_udzial"].map(f_pct),
                        "$r_{\\mathrm{it}}$": najtr["dyskryminacja"].map(lambda v: "--" if pd.isna(v) else f"{v:.2f}"),
                        "OR trend": najtr["OR_log2_proba"].map(lambda v: "--" if pd.isna(v) else f_or(v)),
                        "$q$": najtr["q_fdr"].map(f_p)})
    tabela_tex(tdir, "hardest_items", t10, f"The {args.top_pozycje} most difficult items.", "rlrrrrrrr",
               "First/Repeat, accuracy at first vs later attempts; Top distr., share of errors falling on the most "
               "frequent distractor; $r_{\\mathrm{it}}$, item--rest correlation; OR trend, odds ratio per doubling of the attempt "
               "number; $q$, Benjamini--Hochberg adjusted $p$.", szeroka=True)
    ndys = poz["dystraktory_obserwowane"].sum()
    M.update(ItemDifficultyMedian=f_pct(poz["p_pierwsza"].median()),
             TopDistractorMedian=f_pct(poz["dominujacy_dystraktor_udzial"].median()),
             NDistractors=f_int(ndys), NNonFunctional=f_int(poz["dystraktory_niefunkcjonalne"].sum()),
             NonFunctionalPct=f_pct(poz["dystraktory_niefunkcjonalne"].sum() / ndys),
             ItemsModerate=f_int(poz["p_pierwsza"].between(.5, .9).sum()),
             ItemsGoodDisc=f_int((dk >= .3).sum()), ItemsDiscTested=f_int(dk.notna().sum()))
    M.update(ItemsImproving=f_int(poz["istotna_poprawa"].sum()), ItemsWorsening=f_int(poz["istotne_pogorszenie"].sum()),
             ItemsTestable=f_int(poz["p_trend"].notna().sum()), ItemDiscMedian=f"{dk.median():.2f}",
             ItemsLowDisc=f_int((dk < .2).sum()), ItemsEasy=f_int((poz["p_pierwsza"] > .9).sum()),
             ItemsHard=f_int((poz["p_pierwsza"] < .5).sum()))

    # --- wykresy
    plt = styl_wykresow()
    wykres_krzywa(plt, fdir, krzywa, fit, MX, K)
    wykres_odstep(plt, fdir, ret)
    wykres_osoby(plt, fdir, dvec)
    wykres_pozycje(plt, fdir, poz, args.alfa)
    wykres_aktywnosc(plt, fdir, x)
    wykres_wrazliwosc(plt, fdir, wraz)
    plt.close("all")

    # --- makra i szkic
    import platform, scipy, matplotlib
    M.update(BootReps=f_int(B), Alpha=f"{args.alfa}", MinItemN=f"{args.min_pozycja}", Seed=f"{args.seed}",
             MaxAttemptPooled=f"{MX}", VerPython=platform.python_version(), VerPandas=pd.__version__,
             VerNumpy=np.__version__, VerScipy=scipy.__version__, VerStatsmodels=sm.__version__,
             VerMatplotlib=matplotlib.__version__.split("+")[0])
    makra = ["% Wygenerowano automatycznie przez analiza_odpowiedzi_naukowa.py -- nie edytuj ręcznie.",
             "% Katalogi tabel i rycin można nadpisać przed \\input{macros.tex}.",
             "\\providecommand{\\TabDir}{tables/}", "\\providecommand{\\FigDir}{figures/}",
             "\\providecommand{\\fillin}[1]{\\textbf{[#1]}}"]
    makra += [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in M.items()]
    (katalog / "macros.tex").write_text("\n".join(makra) + "\n", encoding="utf-8")
    (katalog / "draft.tex").write_text(SZKIC, encoding="utf-8")
    if not (katalog / "main.tex").exists():  # nie nadpisuj ręcznie edytowanego main.tex
        (katalog / "main.tex").write_text(GLOWNY, encoding="utf-8")
    (katalog / "references.bib").write_text(BIBLIOGRAFIA, encoding="utf-8")
    return M, zo, wyniki, wraz, icc


SZKIC = r"""% =============================================================================
% Szkic artykułu wygenerowany przez analiza_odpowiedzi_naukowa.py.
% Plik jest NADPISYWANY przy każdym uruchomieniu skryptu -- zmiany wprowadzaj w kopii.
% Liczby: macros.tex; tabele: \TabDir; ryciny: \FigDir; literatura: references.bib.
% Miejsca do uzupełnienia: \fillin{...}. Zdania interpretujące kierunek wyniku oznaczono
% komentarzem "% SPRAWDŹ" -- zweryfikuj je po zmianie danych lub parametrów.
% Kompilacja podglądu: pdflatex main && bibtex main && pdflatex main && pdflatex main
% =============================================================================

\begin{abstract}
\noindent\textbf{Background.} Spaced retrieval practice improves retention in laboratory and
educational settings, but evidence from long-running workplace programmes is scarce.
\textbf{Methods.} We analysed \NResponses{} responses given by \NEmployees{} employees to \NItems{}
multiple-choice items in \NModules{} modules of a quiz-based microlearning programme
(\DateStart--\DateEnd). Each item was re-presented to the same employee at a fixed, non-adaptive
interval (median \GapMedian{} days). Correctness was modelled with logistic regression including
employee and item fixed effects; descriptive estimates carry cluster-bootstrap confidence intervals.
\textbf{Results.} Accuracy rose from \AccAttOne\% at the first attempt to \AccAttMax\% at the
\AttMax{}th and later attempts. Each doubling of the number of attempts multiplied the odds of a
correct answer by \ORMOneAttempt{} (95\% CI \ORMOneAttemptCI; range across ten sensitivity analyses
\ORRange). Longer intervals since the previous attempt were associated with lower accuracy
(OR \ORMTwoGap{} per doubling of the interval). Repeated errors concentrated on the same distractor
(\SameDistractorPct\% vs \SameDistractorExpectedPop\% expected). Accuracy on newly encountered items
did not improve with tenure (OR \ORMThreeTenure{} per year). % SPRAWDŹ
\textbf{Conclusions.} Repeated retrieval in routine workplace training was accompanied by steady,
item-specific gains and measurable forgetting between repetitions. Adaptive scheduling, targeted
feedback on persistent misconceptions and revision of poorly functioning items could increase the
programme's effectiveness.

\medskip\noindent\textbf{Keywords:} spaced repetition; retrieval practice; microlearning;
workplace training; learning analytics; item analysis
\end{abstract}

% -----------------------------------------------------------------------------
\section{Introduction}

Retrieving information from memory strengthens its later retention more than restudying it
(the testing effect), and practice distributed over time is retained better than massed practice
(the spacing effect) \citep{roediger2006,cepeda2006,cepeda2008}. Spaced education, in which short
multiple-choice questions are delivered repeatedly over weeks or months, improved knowledge
acquisition and retention in randomised trials among medical trainees
\citep{kerfoot2007urology,kerfoot2007mededuc,kerfoot2009}, and systematic reviews report small to
moderate benefits for health professionals \citep{phillips2019,martinengo2024}.

In corporate settings, short quiz-based \emph{microlearning} formats are widely used, but the
evidence base is dominated by small or grey-literature studies \citep{taylor2022}. Evaluations of
mandatory organisational training, for example in security awareness, frequently report modest or
decaying effects \citep{reinheimer2020,lain2022,ho2025}. At the same time, the log data generated by
such platforms allow learning to be observed at the level of single responses, as in learner models
developed for intelligent tutoring and language-learning systems
\citep{corbett1994,pavlik2009,settles2016,tabibian2019,koedinger2023}.

\fillin{One or two sentences on the organisation and the training content.} We used three years of
response logs from a workplace microlearning programme to address the following questions:
(RQ1) does accuracy increase with repeated retrieval of the same item by the same employee;
(RQ2) how is accuracy related to the outcome of, and the time since, the previous attempt;
(RQ3) are repeated errors persistent, indicating misconceptions rather than guessing;
(RQ4) does improvement extend to newly encountered items; and
(RQ5) how well do the items function psychometrically?

% -----------------------------------------------------------------------------
\section{Methods}

\subsection{Setting and training programme}
\fillin{Organisation, sector, target group and training topic; whether participation was mandatory;
delivery channel (e-mail, app, intranet); whether the correct answer and an explanation were shown
after each response; how items were authored and reviewed.}
Employees were presented with short multiple-choice questions (median \OptionsMedian{} response
options per item) grouped into thematic modules. In the observed data employees answered a median of
\DailyMedian{} questions per active day, \WeekdayPct\% of responses were given on weekdays, and each
item was presented again to the same employee after a median of \GapMedian{} days
(IQR \GapQOne--\GapQThree).

\subsection{Data}
The platform log contained, for each response, a record identifier, the module, the item, the option
chosen, a pseudonymised employee identifier, a time stamp and the correctness of the response.
Records with missing or invalid values were removed (\NRejected{} records). Test module(s)
(\ExcludedModules; \NExcluded{} responses) were excluded. The analytic dataset comprised
\NResponses{} responses (Table~\ref{tab:dataset}). \fillin{Ethics approval or waiver; legal basis for
processing employee data (GDPR); how pseudonymisation was performed.}

\subsection{Definitions}
A \emph{sequence} is the chronologically ordered series of attempts of one employee at one item;
the \emph{attempt number} is the position of a response within its sequence (ties in time were
broken by record identifier). \emph{Accuracy} is the proportion of correct responses. The
\emph{interval} is the time in days since the previous attempt in the same sequence. \emph{Tenure} is
the time since the employee's first response in the programme. Employee-level change was defined as
the difference in the proportion of correct answers between attempt~3 and attempt~1, computed across
the employee's own sequences with at least three attempts.

\subsection{Statistical analysis}
Descriptive accuracy is reported with 95\% confidence intervals from a cluster bootstrap that
resampled employees (\BootReps{} replicates), which accounts for the dependence of responses within
persons. Because learners who continue to later attempts may differ from those who stop, aggregated
learning curves can be distorted by attrition \citep{murray2013,goutte2018}; learning curves were
therefore additionally computed for a balanced cohort of sequences with at least \CohortK{}
attempts. The relationship between error rate and attempt number was summarised by a power function
\citep{newell1981}. Because the scheduler was not adaptive, we checked whether re-presentation
depended on the previous outcome.

Correctness was modelled with logistic regression including fixed effects for employee and item and
with standard errors clustered by employee, so that the attempt effect is estimated within persons
and within items. Model~1 included the attempt number on the log$_2$ scale, so the odds ratio (OR)
refers to a doubling of the number of attempts. Model~2, fitted to repeated attempts, added the
outcome of the previous attempt, the interval since the previous attempt (log$_2$ days) and tenure,
analogous to performance-factors and half-life regression models of learner logs
\citep{pavlik2009,settles2016}. Model~3, fitted to first attempts only, tested whether accuracy on
newly encountered items changed with tenure (RQ4). Sensitivity analyses used a balanced cohort,
truncation at 10 attempts, strata of sequence length (addressing pattern-mixture bias), exclusion of
low-activity employees, adjustment for tenure, generalised estimating equations with an
exchangeable working correlation \citep{liang1986}, and a mixed model with crossed random
intercepts for employees and items \citep{baayen2008}, from which latent-scale intraclass
correlations (ICC) and marginal and conditional $R^2$ were derived \citep{nakagawa2013}.

Transitions between consecutive attempts were tabulated. For consecutive errors, the proportion of
repeated choices of the same distractor was compared with the proportion expected under random
choice among the observed distractors and under choice proportional to each distractor's popularity
for the item. Employee-level change was tested with the sign test and the Wilcoxon signed-rank test
(rank-biserial correlation as effect size). Items were described with classical test theory indices
computed on first attempts: difficulty (proportion correct), discrimination (item--rest correlation
with the employee's accuracy on the remaining items) and distractor functioning, with distractors
chosen by fewer than 5\% of respondents classified as non-functioning \citep{tarrant2009,gierl2017}.
Per-item trends across attempts were tested with logistic regression with employee-clustered
standard errors, controlling the false discovery rate at \Alpha{} \citep{benjamini1995}.
Analyses were performed in Python \VerPython{} with pandas \VerPandas, NumPy \VerNumpy,
SciPy \VerScipy, statsmodels \VerStatsmodels{} and Matplotlib \VerMatplotlib{} (random seed \Seed).

% -----------------------------------------------------------------------------
\section{Results}

\subsection{Sample and engagement}
The dataset comprised \NResponses{} responses from \NEmployees{} employees to \NItems{} items in
\NModules{} modules, collected between \DateStart{} and \DateEnd{} (Table~\ref{tab:dataset}).
Employees gave a median of \RespPerEmpMedian{} responses (IQR \RespPerEmpQOne--\RespPerEmpQThree)
to \ItemsPerEmpMedian{} different items on \ActiveDaysMedian{} active days, and remained in the
programme for a median of \SpanMonthsMedian{} months; \ActiveLastQuarterPct\% were active in the
last 90 days of observation. Activity varied over time, with periods without responses
(Figure~\ref{fig:activity}). \fillin{Explain the gaps, e.g. programme pauses or module launches.}
Overall accuracy was \AccOverall\% and first-attempt accuracy \AccFirst\%.

The re-presentation schedule did not depend on the previous outcome: the probability of a further
attempt was \ReaskAfterCorrect\% after a correct and \ReaskAfterIncorrect\% after an incorrect
response, and the median interval to the next attempt was \GapAfterCorrect{} and
\GapAfterIncorrect{} days, respectively. Continuation of sequences was therefore not selected on
performance. % SPRAWDŹ

\input{\TabDir dataset}

\begin{figure*}[tbp]
\centering
\includegraphics{\FigDir fig_activity}
\caption{Monthly number of responses (top) and of active employees (bottom) over the observation
period.}
\label{fig:activity}
\end{figure*}

\subsection{Learning across repeated attempts (RQ1)}
Accuracy increased steadily with the attempt number, from \AccAttOne\% \AccAttOneCI{} at the
first attempt to \AccAttMax\% \AccAttMaxCI{} at the \AttMax{}th and later attempts
(Figure~\ref{fig:learning_curve}, Table~\ref{tab:learning_curve}). The increase was of the same size
in the balanced cohort of \CohortN{} sequences with at least \CohortK{} attempts (\CohortAccOne\%
\CohortAccOneCI{} at attempt~1 vs \CohortAccK\% \CohortAccKCI{} at attempt~\CohortK), so it is not
explained by selective continuation of better-performing employees. The error rate followed a power
function of the attempt number (exponent \PowerLawB, $R^2$ = \PowerLawRsq), consistent with the power
law of practice \citep{newell1981}.

In Model~1, each doubling of the number of attempts was associated with \ORMOneAttempt-fold higher
odds of a correct answer (95\% CI \ORMOneAttemptCI; Table~\ref{tab:regression}). Items accounted for a
larger share of the variance than employees (latent ICC \ICCItem{} vs \ICCEmployee; marginal
$R^2$ = \RsqMarginal, conditional $R^2$ = \RsqConditional).

\begin{figure}[tbp]
\centering
\includegraphics{\FigDir fig_learning_curve}
\caption{Accuracy by attempt number within employee--item sequences. Circles: all sequences
available at each attempt (their number shrinks as attempts increase). Squares: balanced cohort,
i.e.\ the same \CohortN{} sequences that reached at least \CohortK{} attempts, followed over
attempts 1--\CohortK{} only, so that every point is based on identical sequences. Error bars: 95\% CI from a
cluster bootstrap over employees (\BootReps{} replicates). Dashed line: power-law fit to the error
rate. Attempts \MaxAttemptPooled{} and higher are pooled.}
\label{fig:learning_curve}
\end{figure}

\input{\TabDir learning_curve}

\input{\TabDir regression}

\subsection{Previous outcome, interval and forgetting (RQ2)}
Controlling for the attempt number, a correct previous response was associated with higher odds of a
correct answer (Model~2: OR \ORMTwoPrev, 95\% CI \ORMTwoPrevCI), and longer intervals since the
previous attempt with lower odds (OR \ORMTwoGap{} per doubling of the interval, 95\% CI
\ORMTwoGapCI; Table~\ref{tab:regression}). Among previously correct responses, accuracy decreased from
\RetShortCorrect\% when the item was repeated within 14 days to \RetLongCorrect\% after 240 days or
more; previously incorrect responses were corrected in \RetShortIncorrect\% and \RetLongIncorrect\% of
cases, respectively (Figure~\ref{fig:retention}, Table~\ref{tab:retention_interval}). This pattern is
consistent with forgetting between repetitions \citep{cepeda2006,cepeda2008}. % SPRAWDŹ

\begin{figure}[tbp]
\centering
\includegraphics{\FigDir fig_retention_interval}
\caption{Accuracy by the interval since the previous attempt at the same item, separately for
previously correct (circles) and previously incorrect (squares) responses. Error bars: 95\% CI from a
cluster bootstrap over employees.}
\label{fig:retention}
\end{figure}

\input{\TabDir retention_interval}

\subsection{Transitions and persistent errors (RQ3)}
Of previously correct responses, \RetainPct\% \RetainCI{} were correct again at the next attempt
(\ForgetPct\% were forgotten); of previously incorrect responses, \RecoverPct\% \RecoverCI{} were
corrected and \PersistPct\% remained incorrect (Table~\ref{tab:transitions}). When an error was
repeated (\SameDistractorN{} cases), employees chose the same distractor in \SameDistractorPct\%
\SameDistractorCI{} of cases, compared with \SameDistractorExpected\% expected under random choice
and \SameDistractorExpectedPop\% expected given the popularity of each distractor, indicating
stable misconceptions rather than guessing. % SPRAWDŹ

\input{\TabDir transitions}

\subsection{Employee-level change}
Among the \EmpN{} employees (\EmpSharePct\% of all) with at least one sequence of three or more
attempts, \EmpImproved{} improved, \EmpWorsened{} worsened and \EmpUnchanged{} did not change between
the first and third attempt (sign test $p$ \SignP; Wilcoxon $p$ \WilcoxonP; rank-biserial
$r$ = \RankBiserial). The mean change was \EmpMeanChange{} percentage points (95\% CI
\EmpMeanChangeCI; Figure~\ref{fig:employee_change}, Table~\ref{tab:employee_change}).

\begin{figure}[tbp]
\centering
\includegraphics{\FigDir fig_employee_change}
\caption{Distribution of the employee-level change in accuracy between attempt~3 and attempt~1
across the employee's own sequences with at least three attempts ($n$ = \EmpN{} employees; bins of
5 percentage points centred on zero).}
\label{fig:employee_change}
\end{figure}

\input{\TabDir employee_change}

\subsection{Transfer to new items (RQ4)}
Accuracy at the first encounter with a new item did not increase with tenure (Model~3: OR
\ORMThreeTenure{} per year, 95\% CI \ORMThreeTenureCI; Table~\ref{tab:regression}), and tenure was not
positively associated with accuracy on repeated attempts once the attempt number was controlled
(Model~2: OR \ORMTwoTenure, 95\% CI \ORMTwoTenureCI). The gains therefore appear to be specific to
the repeated items. % SPRAWDŹ

\subsection{Item analysis (RQ5)}
The median item difficulty was \ItemDifficultyMedian\% correct at the
first attempt: \ItemsHard{} items were answered correctly by fewer than 50\%, \ItemsModerate{} by
50--90\% and \ItemsEasy{} by more than 90\% of employees (Table~\ref{tab:items}). The median
item--rest correlation was \ItemDiscMedian; \ItemsLowDisc{} of \ItemsDiscTested{} items had
correlations below 0.20 and \ItemsGoodDisc{} of 0.30 or more (Figure~\ref{fig:items}). Errors
concentrated on one distractor (median \TopDistractorMedian\% of an item's errors), and
\NNonFunctional{} of \NDistractors{} observed distractors (\NonFunctionalPct\%) were
non-functioning. Accuracy improved significantly with repetition for \ItemsImproving{} of
\ItemsTestable{} testable items and deteriorated for \ItemsWorsening{} (FDR-adjusted). The most
difficult items are listed in Table~\ref{tab:hardest_items}.

\begin{figure}[tbp]
\centering
\includegraphics{\FigDir fig_item_analysis}
\caption{Item difficulty (accuracy at first attempt) versus discrimination (item--rest
correlation). Triangles: items whose accuracy increased significantly with repetition
(Benjamini--Hochberg $q<\Alpha$). Dotted lines: $r$ = 0.20 and 90\% correct.}
\label{fig:items}
\end{figure}

\input{\TabDir items}

\input{\TabDir hardest_items}

\subsection{Sensitivity analyses}
The attempt effect was stable across specifications, with ORs from \ORRange{}
(Figure~\ref{fig:sensitivity}, Table~\ref{tab:sensitivity}): \ORSensCohort{} in the balanced cohort,
\ORSensLenThree, \ORSensLenFive{} and \ORSensLenEight{} in sequences of 3--4, 5--7 and at least 8
attempts, \ORSensGee{} in the population-averaged GEE model and \ORSensMixed{} in the mixed model.
The estimate was larger after adjustment for tenure (\ORSensTenure), which is correlated with the
attempt number.

\begin{figure}[tbp]
\centering
\includegraphics{\FigDir fig_sensitivity}
\caption{Odds ratio (95\% CI) for a correct answer per doubling of the attempt number across model
specifications. Diamond: main model; vertical line: no effect.}
\label{fig:sensitivity}
\end{figure}

\input{\TabDir sensitivity}

% -----------------------------------------------------------------------------
\section{Discussion}

\subsection{Principal findings}
In three years of routine use of a workplace microlearning programme, accuracy on repeatedly
presented items rose steadily with the number of retrievals, following a power function, and the
effect was robust to attrition, model specification and clustering. Accuracy declined with the
interval since the previous retrieval, previous errors were only partly corrected at the next
attempt, and repeated errors mostly reproduced the same distractor. Accuracy on new items did not
increase with tenure. % SPRAWDŹ

\subsection{Comparison with previous research}
The gradual, regular gains resemble learning curves observed across educational datasets
\citep{koedinger2023} and are consistent with the testing and spacing effects
\citep{roediger2006,cepeda2006}. Randomised trials of spaced education found improved retention
\citep{kerfoot2007mededuc,kerfoot2009}; our observational data extend these findings to a
non-medical workplace setting with long inter-repetition intervals. The negative association between
interval and accuracy agrees with forgetting-curve models fitted to learner logs
\citep{settles2016,tabibian2019}. As in studies that re-used the same items repeatedly
\citep{donker2022}, improvement on repeated items cannot be separated from memory for the specific
question and its answer; the absence of a tenure effect on new items suggests limited transfer.

\subsection{Implications for practice}
The programme re-presented items at the same interval regardless of the previous outcome. Adaptive
schedules that shorten the interval after errors and lengthen it after correct answers use learner
history more efficiently \citep{lindsey2014,settles2016,tabibian2019}. The persistence of specific
distractors points to misconceptions that may call for explanatory feedback rather than repetition
alone. Item analysis identified candidates for revision: items with low discrimination, items
answered correctly by almost everyone at the first attempt (little room for learning) and
non-functioning distractors \citep{tarrant2009,gierl2017}.

\subsection{Limitations}
The study is observational and has no control group, so the gains cannot be attributed causally to
the programme; improvement on repeated items may partly reflect recognition of the item rather than
understanding. Participation and activity varied between employees, and results for sequences with
many attempts describe the more active participants, although the balanced-cohort and
sequence-length analyses did not suggest attrition bias. The high first-attempt accuracy
(\AccFirst\%) limits the room for improvement (ceiling effect). Distractors never chosen are not
visible in the log, so distractor functioning may be overestimated. No information on employees'
roles, prior knowledge or demographics was available. Time stamps carried no time-zone information.
The mixed model included random intercepts only; employee-specific learning rates were not
modelled. The data come from a single organisation. \fillin{Add context-specific limitations.}

% -----------------------------------------------------------------------------
\section{Conclusions}
Routine repeated retrieval in workplace training was accompanied by steady, item-specific
improvement and by forgetting between repetitions. Log data from such programmes can be used to
monitor learning, evaluate items and inform the design of adaptive repetition schedules.

% -----------------------------------------------------------------------------
\section*{Declarations}
\noindent\textbf{Ethics.} \fillin{Approval / waiver and data-protection basis.}\\
\textbf{Data availability.} \fillin{Availability of pseudonymised data and analysis code.}\\
\textbf{Funding.} \fillin{Funding sources.}\\
\textbf{Competing interests.} \fillin{Declaration.}\\
\textbf{Use of AI tools.} \fillin{Declaration of the use of generative AI, if required by the journal.}
"""

GLOWNY = r"""% Dokument do podglądu szkicu: pdflatex main && bibtex main && pdflatex main && pdflatex main
\documentclass[11pt]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[margin=2.5cm]{geometry}
\usepackage{booktabs,graphicx,xcolor,amsmath}
\usepackage[numbers,sort&compress]{natbib}
\usepackage[hidelinks]{hyperref}
\usepackage{doi}
\extrafloats{100}
\newcommand{\fillin}[1]{\textcolor{red}{[#1]}}
\input{macros.tex}
\title{\fillin{Title, e.g.\ Spaced retrieval practice in workplace training:
evidence from three years of quiz logs}}
\author{\fillin{Authors}}
\date{}
\begin{document}
\maketitle
\input{draft.tex}
\bibliographystyle{plainnat}
\bibliography{references}
\end{document}
"""


BIBLIOGRAFIA = r"""% Pozycje z polem note: DOI niepotwierdzony automatycznie -- sprawdź w Crossref przed wysłaniem.
@article{kerfoot2007urology, author={Kerfoot, B. Price and Baker, Harley E. and Koch, Michael O. and Connelly, David and Joseph, David B. and Ritchey, Michael L.}, title={Randomized, controlled trial of spaced education to urology residents in the {United States} and {Canada}}, journal={Journal of Urology}, year={2007}, volume={177}, number={4}, pages={1481--1487}, doi={10.1016/j.juro.2006.11.074}}
@article{kerfoot2007mededuc, author={Kerfoot, B. Price and DeWolf, William C. and Masser, Barbara A. and Church, Paul A. and Federman, Daniel D.}, title={Spaced education improves the retention of clinical knowledge by medical students: a randomised controlled trial}, journal={Medical Education}, year={2007}, volume={41}, number={1}, pages={23--31}, doi={10.1111/j.1365-2929.2006.02644.x}}
@article{kerfoot2009, author={Kerfoot, B. Price}, title={Learning benefits of on-line spaced education persist for 2 years}, journal={Journal of Urology}, year={2009}, volume={181}, number={6}, pages={2671--2673}, doi={10.1016/j.juro.2009.02.024}}
@article{phillips2019, author={Phillips, Jane L. and Heneka, Nicole and Bhattarai, Priyanka and Fraser, Clare and Shaw, Tim}, title={Effectiveness of the spaced education pedagogy for clinicians' continuing professional development: a systematic review}, journal={Medical Education}, year={2019}, volume={53}, number={9}, pages={886--902}, doi={10.1111/medu.13895}}
@article{martinengo2024, author={Martinengo, Laura and Ng, Marcus Sheng Pin and Ng, Tabitha Dora Ruo and Ang, Yu-Ian and Jabir, Ahmad Ishqi and Kyaw, Bhone Myint and Tudor Car, Lorainne}, title={Spaced digital education for health professionals: systematic review and meta-analysis}, journal={Journal of Medical Internet Research}, year={2024}, volume={26}, pages={e57760}, doi={10.2196/57760}}
@article{cepeda2006, author={Cepeda, Nicholas J. and Pashler, Harold and Vul, Edward and Wixted, John T. and Rohrer, Doug}, title={Distributed practice in verbal recall tasks: a review and quantitative synthesis}, journal={Psychological Bulletin}, year={2006}, volume={132}, number={3}, pages={354--380}, doi={10.1037/0033-2909.132.3.354}}
@article{cepeda2008, author={Cepeda, Nicholas J. and Vul, Edward and Rohrer, Doug and Wixted, John T. and Pashler, Harold}, title={Spacing effects in learning: a temporal ridgeline of optimal retention}, journal={Psychological Science}, year={2008}, volume={19}, number={11}, pages={1095--1102}, doi={10.1111/j.1467-9280.2008.02209.x}}
@article{roediger2006, author={Roediger, Henry L. and Karpicke, Jeffrey D.}, title={Test-enhanced learning: taking memory tests improves long-term retention}, journal={Psychological Science}, year={2006}, volume={17}, number={3}, pages={249--255}, doi={10.1111/j.1467-9280.2006.01693.x}}
@article{lindsey2014, author={Lindsey, Robert V. and Shroyer, Jeffery D. and Pashler, Harold and Mozer, Michael C.}, title={Improving students' long-term knowledge retention through personalized review}, journal={Psychological Science}, year={2014}, volume={25}, number={3}, pages={639--647}, doi={10.1177/0956797613504302}}
@article{taylor2022, author={Taylor, Allison D. and Hung, Woei}, title={The effects of microlearning: a scoping review}, journal={Educational Technology Research and Development}, year={2022}, volume={70}, pages={363--395}, doi={10.1007/s11423-022-10084-1}}
@inproceedings{reinheimer2020, author={Reinheimer, Benjamin and Aldag, Lina and Mayer, Peter and Mossano, Mattia and Duezguen, Reyhan and Lofthouse, Bettina and von Landesberger, Tatiana and Volkamer, Melanie}, title={An investigation of phishing awareness and education over time: when and how to best remind users}, booktitle={Sixteenth Symposium on Usable Privacy and Security (SOUPS 2020)}, publisher={USENIX Association}, year={2020}}
@inproceedings{lain2022, author={Lain, Daniele and Kostiainen, Kari and {\v{C}}apkun, Srdjan}, title={Phishing in organizations: findings from a large-scale and long-term study}, booktitle={2022 IEEE Symposium on Security and Privacy (SP)}, year={2022}, pages={842--859}, note={DOI to verify; arXiv:2112.07498}}
@inproceedings{ho2025, author={Ho, Grant and Mirian, Ariana and Luo, Elisa and Tong, Khang and Lee, Euyhyun and Liu, Lin and Voelker, Geoffrey M.}, title={Understanding the efficacy of phishing training in practice}, booktitle={2025 IEEE Symposium on Security and Privacy (SP)}, year={2025}, pages={37--54}, note={DOI to verify}}
@article{corbett1994, author={Corbett, Albert T. and Anderson, John R.}, title={Knowledge tracing: modeling the acquisition of procedural knowledge}, journal={User Modeling and User-Adapted Interaction}, year={1994}, volume={4}, pages={253--278}, doi={10.1007/BF01099821}}
@inproceedings{pavlik2009, author={Pavlik, Philip I. and Cen, Hao and Koedinger, Kenneth R.}, title={Performance factors analysis -- a new alternative to knowledge tracing}, booktitle={Artificial Intelligence in Education (AIED 2009)}, series={Frontiers in Artificial Intelligence and Applications}, volume={200}, pages={531--538}, publisher={IOS Press}, year={2009}, note={DOI to verify}}
@inproceedings{settles2016, author={Settles, Burr and Meeder, Brendan}, title={A trainable spaced repetition model for language learning}, booktitle={Proceedings of the 54th Annual Meeting of the Association for Computational Linguistics}, pages={1848--1858}, year={2016}, url={https://aclanthology.org/P16-1174}}
@article{tabibian2019, author={Tabibian, Behzad and Upadhyay, Utkarsh and De, Abir and Zarezade, Ali and Sch{\"o}lkopf, Bernhard and Gomez-Rodriguez, Manuel}, title={Enhancing human learning via spaced repetition optimization}, journal={Proceedings of the National Academy of Sciences}, year={2019}, volume={116}, number={10}, pages={3988--3993}, doi={10.1073/pnas.1815156116}}
@article{koedinger2023, author={Koedinger, Kenneth R. and Carvalho, Paulo F. and Liu, Ran and McLaughlin, Elizabeth A.}, title={An astonishing regularity in student learning rate}, journal={Proceedings of the National Academy of Sciences}, year={2023}, volume={120}, number={13}, pages={e2221311120}, doi={10.1073/pnas.2221311120}}
@inproceedings{murray2013, author={Murray, R. Charles and Ritter, Steven and Nixon, Tristan and Schwiebert, Ryan and Hausmann, Robert G. M. and Towle, Brendon and Fancsali, Stephen E. and Vuong, Annalies}, title={Revealing the learning in learning curves}, booktitle={Artificial Intelligence in Education (AIED 2013)}, series={LNCS}, volume={7926}, year={2013}, doi={10.1007/978-3-642-39112-5_48}, note={author list to verify}}
@inproceedings{goutte2018, author={Goutte, Cyril and Durand, Guillaume and L{\'e}ger, Serge}, title={On the learning curve attrition bias in additive factor modeling}, booktitle={Artificial Intelligence in Education (AIED 2018)}, series={LNCS}, year={2018}, doi={10.1007/978-3-319-93846-2_21}}
@article{gierl2017, author={Gierl, Mark J. and Bulut, Okan and Guo, Qi and Zhang, Xinxin}, title={Developing, analyzing, and using distractors for multiple-choice tests in education: a comprehensive review}, journal={Review of Educational Research}, year={2017}, volume={87}, number={6}, pages={1082--1116}, doi={10.3102/0034654317726529}}
@article{tarrant2009, author={Tarrant, Marie and Ware, James and Mohammed, Ahmed M.}, title={An assessment of functioning and non-functioning distractors in multiple-choice questions: a descriptive analysis}, journal={BMC Medical Education}, year={2009}, volume={9}, pages={40}, doi={10.1186/1472-6920-9-40}}
@article{donker2022, author={Donker, Stella C. M. and Vorstenbosch, Marc A. T. M. and Gerhardus, Marie-Jos{\'e} T. and Thijssen, Dick H. J.}, title={Retrieval practice and spaced learning: preventing loss of knowledge in {Dutch} medical sciences students in an ecologically valid setting}, journal={BMC Medical Education}, year={2022}, volume={22}, pages={65}, doi={10.1186/s12909-021-03075-y}}
@article{baayen2008, author={Baayen, R. Harald and Davidson, Douglas J. and Bates, Douglas M.}, title={Mixed-effects modeling with crossed random effects for subjects and items}, journal={Journal of Memory and Language}, year={2008}, volume={59}, number={4}, pages={390--412}, doi={10.1016/j.jml.2007.12.005}}
@article{nakagawa2013, author={Nakagawa, Shinichi and Schielzeth, Holger}, title={A general and simple method for obtaining {$R^2$} from generalized linear mixed-effects models}, journal={Methods in Ecology and Evolution}, year={2013}, volume={4}, number={2}, pages={133--142}, doi={10.1111/j.2041-210x.2012.00261.x}}
@article{benjamini1995, author={Benjamini, Yoav and Hochberg, Yosef}, title={Controlling the false discovery rate: a practical and powerful approach to multiple testing}, journal={Journal of the Royal Statistical Society: Series B (Methodological)}, year={1995}, volume={57}, number={1}, pages={289--300}, doi={10.1111/j.2517-6161.1995.tb02031.x}}
@article{liang1986, author={Liang, Kung-Yee and Zeger, Scott L.}, title={Longitudinal data analysis using generalized linear models}, journal={Biometrika}, year={1986}, volume={73}, number={1}, pages={13--22}, doi={10.1093/biomet/73.1.13}}
@incollection{newell1981, author={Newell, Allen and Rosenbloom, Paul S.}, title={Mechanisms of skill acquisition and the law of practice}, booktitle={Cognitive Skills and Their Acquisition}, editor={Anderson, John R.}, publisher={Lawrence Erlbaum}, address={Hillsdale, NJ}, year={1981}, pages={1--55}}
"""


# ------------------------------------------------------------ raport tekstowy

def raport(df, rejected, bins, trends, pairs, users, katalog, threshold, art=None, wykluczenie=""):
    n = len(df)
    lines = ["RAPORT: ODPOWIEDZI I UCZENIE SIĘ (ANALIZA EKSPLORACYJNA)", "",
             f"Rekordy prawidłowe: {n}; odrzucone: {len(rejected)}", wykluczenie,
             f"Zakres: {df['create_time'].min()} — {df['create_time'].max()}",
             f"Pytania: {df['question_id'].nunique()}; użytkownicy: {df['user_symbol'].nunique()}; "
             f"pokoje: {df['room_Code'].nunique()}",
             f"Błędy: {df['blad'].sum()} / {n} ({100 * df['blad'].mean():.2f}%)",
             f"Powtórzone ID: {df['id'].duplicated().sum()} (nie usuwano)", "",
             "TREND PYTAŃ", f"Próg: {threshold} odpowiedzi na pytanie; kwalifikowane pytania: {len(trends)}."]
    if not trends.empty:
        a = bins.loc[bins["czesc"] == 1]
        z = bins.loc[bins["czesc"] == 10]
        lines += [f"Spadek nachylenia: {(trends['kierunek'] == 'spadek').sum()}; "
                  f"wzrost: {(trends['kierunek'] == 'wzrost').sum()}.",
                  f"Ważone udziałem odpowiedzi błędy w części 1: {100*a['bledy'].sum()/a['n'].sum():.2f}%; "
                  f"w części 10: {100*z['bledy'].sum()/z['n'].sum():.2f}%."]
    lines += ["", "POWTARZAJĄCY: TA SAMA OSOBA, TO SAMO PYTANIE, MINIMUM 3 PRÓBY",
              f"Pary: {len(pairs)}; osoby: {len(users)}; udział osób wśród wszystkich: "
              f"{100*len(users)/df['user_symbol'].nunique():.2f}%."]
    if not pairs.empty:
        imp = int((pairs["poprawa_1_do_3"] > 0).sum())
        worse = int((pairs["poprawa_1_do_3"] < 0).sum())
        ui = int((users["status"] == "poprawa").sum())
        uw = int((users["status"] == "pogorszenie").sum())
        lines += [f"Pary 1→3: poprawa {imp}, pogorszenie {worse}, bez zmian {len(pairs)-imp-worse}.",
                  f"Osoby (odsetek poprawnych na własnych powtarzanych pytaniach): "
                  f"poprawa {ui}, pogorszenie {uw}, bez zmian {len(users)-ui-uw}.",
                  f"Odsetek poprawnych w 1. próbie par: {100*pairs['poprawna_1'].mean():.2f}%; "
                  f"w 3. próbie: {100*pairs['poprawna_3'].mean():.2f}%."]
        if ui + uw:
            test = binomtest(ui, ui + uw, 0.5, alternative="two-sided")
            ci = test.proportion_ci(confidence_level=0.95)
            lines += [f"Eksploracyjny test znaków NA POZIOMIE OSÓB (bez remisów): "
                      f"poprawa {ui}/{ui+uw}; dwustronne p={test.pvalue:.5g}; "
                      f"95% CI udziału poprawiających się wśród osób ze zmianą: "
                      f"[{ci.low:.3f}, {ci.high:.3f}]."]
        else:
            lines += ["Test znaków: nie można policzyć (wszyscy użytkownicy bez zmiany)."]
        lines += [f"Mediana odstępu między 1. a ostatnią próbą pary: "
                  f"{pairs['odstep_1_do_ostatniej_dni'].median():.2f} dnia."]
    if art:
        M, zo, wyniki, wraz, icc = art
        lines += ["", "WYNIKI DO ARTYKUŁU (szczegóły: artykul/tables, artykul/macros.tex)",
                  f"Krzywa uczenia: próba 1 {M['AccAttOne']}% {M['AccAttOneCI']} → próba {M['AttMax']}+ "
                  f"{M['AccAttMax']}% {M['AccAttMaxCI']}; kohorta ≥{M['CohortK']} prób: "
                  f"{M['CohortAccOne']}% → {M['CohortAccK']}%.",
                  f"Harmonogram: kolejna próba po poprawnej {M['ReaskAfterCorrect']}%, po błędnej "
                  f"{M['ReaskAfterIncorrect']}% (harmonogram nieadaptacyjny → brak selekcji wg wyniku).",
                  f"Model 1 (FE osoba+pytanie): OR na podwojenie liczby prób {M['ORMOneAttempt']} "
                  f"{M['ORMOneAttemptCI']}; zakres w analizach wrażliwości {M['ORRange']}.",
                  f"Model 2: poprzednia poprawna OR {M['ORMTwoPrev']} {M['ORMTwoPrevCI']}; odstęp (×2) OR "
                  f"{M['ORMTwoGap']} {M['ORMTwoGapCI']}; staż OR {M['ORMTwoTenure']} {M['ORMTwoTenureCI']}.",
                  f"Model 3 (pierwsze próby): staż OR {M['ORMThreeTenure']} {M['ORMThreeTenureCI']}.",
                  f"ICC (skala latentna): pytania {M['ICCItem']}, osoby {M['ICCEmployee']}.",
                  f"Przejścia: poprawna→poprawna {M['RetainPct']}%, błędna→poprawna {M['RecoverPct']}%; "
                  f"ten sam dystraktor przy powtórzonym błędzie {M['SameDistractorPct']}% "
                  f"(losowo {M['SameDistractorExpected']}%).",
                  f"Osoby: średnia zmiana {M['EmpMeanChange']} pp {M['EmpMeanChangeCI']}; Wilcoxon p "
                  f"{M['WilcoxonP'].replace('$', '')}; r_rb {M['RankBiserial']}.",
                  f"Pytania: poprawa {M['ItemsImproving']} / pogorszenie {M['ItemsWorsening']} z "
                  f"{M['ItemsTestable']} (FDR); niska dyskryminacja (r<0.20): {M['ItemsLowDisc']}."]
    lines += ["", "OGRANICZENIA I DEFINICJE",
              "10 części ma podobną liczbę odpowiedzi w każdym pytaniu; nie są to równe okresy kalendarzowe.",
              "Za poprawę osoby uznano wzrost odsetka poprawnych między próbą 1 i 3 w jej własnych pytaniach min3.",
              "Użytkownik z jedną poprawą i jednym pogorszeniem jest klasyfikowany jako bez zmiany netto.",
              "Próg min3 selekcjonuje aktywnych; wyniki nie opisują automatycznie wszystkich użytkowników.",
              "Test znaków liczy jedną obserwację na osobę, lecz samoselekcja i zależności społeczne nadal mogą zniekształcać wnioski.",
              "Nie interpretuj wyników jako dowodu przyczynowego; brak grupy kontrolnej, możliwe efekty pamięci "
              "pytania (rozpoznawanie), czasu i zmiany składu użytkowników.",
              "Daty są bez strefy czasowej; przy remisach czasu kolejność wyznacza id. Nie usunięto zduplikowanych ID.",
              "Dystraktory: znane są tylko opcje wybrane choć raz; opcje nigdy niewybrane nie są widoczne w danych."]
    text = "\n".join(lines) + "\n"
    (katalog / "raport.txt").write_text(text, encoding="utf-8")
    print(text)


def main():
    parser = argparse.ArgumentParser(description="Analiza odpowiedzi i materiały do artykułu")
    parser.add_argument("plik", nargs="?", default="data.csv")
    parser.add_argument("--wyniki", default="wyniki_naukowe")
    parser.add_argument("--minimum", type=int, default=20, help="Min. odpowiedzi na pytanie do podziału na 10 części")
    parser.add_argument("--wyklucz-pokoje", nargs="*", default=["mnk-tst"],
                        help="Kody pokoi pomijane w analizie (domyślnie testowy mnk-tst; "
                             "sam przełącznik bez wartości = bez wykluczeń)")
    parser.add_argument("--bootstrap", type=int, default=2000, help="Liczba replikacji bootstrapu klastrowego")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--kohorta", type=int, default=5, help="Min. liczba prób w kohorcie zbalansowanej")
    parser.add_argument("--max-proba", type=int, default=10, help="Próby od tej wartości łączone w kategorię N+")
    parser.add_argument("--min-pozycja", type=int, default=30, help="Min. pierwszych prób do dyskryminacji pytania")
    parser.add_argument("--top-pozycje", type=int, default=10, help="Liczba najtrudniejszych pytań w tabeli")
    parser.add_argument("--alfa", type=float, default=0.05, help="Próg FDR")
    parser.add_argument("--bez-artykulu", action="store_true", help="Tylko tabele robocze i raport")
    args = parser.parse_args()
    if args.minimum < 10:
        parser.error("--minimum musi wynosić co najmniej 10")
    if args.kohorta < 2 or args.max_proba < 3:
        parser.error("--kohorta musi wynosić co najmniej 2, a --max-proba co najmniej 3")
    out = Path(args.wyniki)
    data, rejected = wczytaj(args.plik)
    n0 = len(data)
    if args.wyklucz_pokoje:
        data = data.loc[~data["room_Code"].isin(args.wyklucz_pokoje)].reset_index(drop=True)
    args.wykluczone_n = n0 - len(data)
    if data.empty:
        parser.error("Brak prawidłowych rekordów")
    out.mkdir(parents=True, exist_ok=True)
    if not rejected.empty:
        rejected.to_csv(out / "odrzucone.csv", index=True, index_label="indeks_0")
    data = przygotuj(data)
    data["miesiac"] = data["create_time"].dt.to_period("M").astype(str)
    data["dzien"] = data["create_time"].dt.strftime("%Y-%m-%d")
    data["godzina"] = data["create_time"].dt.hour
    bins, trends = pytania_w_dziesieciu_czesciach(data, args.minimum)
    stages, pairs, users, questions = pary_minimum_trzy(data)
    tables = {
        "pytania.csv": agreguj(data, ["question_id"]),
        "uzytkownicy.csv": agreguj(data, ["user_symbol"]),
        "odpowiedzi.csv": agreguj(data, ["question_id", "answer_id"]),
        "miesiace.csv": agreguj(data, ["miesiac"]),
        "dni.csv": agreguj(data, ["dzien"]),
        "godziny.csv": agreguj(data, ["godzina"]),
        "pytania_miesiecznie.csv": agreguj(data, ["question_id", "miesiac"]),
        "pytania_10_czesci.csv": bins, "trendy_pytan.csv": trends,
        "powtorki_etapy.csv": stages, "pary_min3.csv": pairs,
        "uzytkownicy_min3.csv": users, "pytania_min3.csv": questions,
    }
    for name, table in tables.items():
        table.to_csv(out / name, index=False, encoding="utf-8-sig")
    art = None
    if not args.bez_artykulu and not pairs.empty:
        art = materialy_artykulu(data, rejected, pairs, users, out / "artykul", args)
    raport(data, rejected, bins, trends, pairs, users, out, args.minimum, art,
           f"Wykluczone pokoje: {', '.join(args.wyklucz_pokoje) or 'brak'} ({args.wykluczone_n} rekordów)")
    print(f"Pliki zapisano w: {out.resolve()}")


if __name__ == "__main__":
    main()
