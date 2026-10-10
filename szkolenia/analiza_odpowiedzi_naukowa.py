#!/usr/bin/env python3
"""Analiza odpowiedzi z platformy powtórek i przygotowanie wyników do artykułu.

Oprócz tabel roboczych (CSV) i raportu tekstowego skrypt tworzy katalog
<wyniki>/artykul z danymi do artykułu (po polsku); skrypt NADPISUJE wyłącznie:
  definicje.tex   stałe liczbowe (\\newcommand) używane w tekście + polecenie \\tabelacsv,
  tabele/*.csv    zawartość tabel (separator ';', komórki w składni LaTeX) wczytywana przez \\tabelacsv,
  rysunki/*.pdf   wykresy (oraz PNG 300 dpi),
  dane/*.csv      surowe dane źródłowe tabel i wykresów (materiał uzupełniający).
Opcja --osoby (domyślnie people.csv) dodaje analizę demograficzną (płeć, wiek w przedziałach 10-letnich)
pracowników objętych analizą; osoby łączone przez MD5 imie.nazwisko = user_symbol, bez zapisu nazwisk.
Tekst artykułu (main.tex, sekcja-*.tex, references.bib) jest edytowany ręcznie i skrypt go nie zmienia;
podpisy i uwagi do tabel znajdują się w plikach sekcji.

W preambule artykułu: \\usepackage{graphicx,natbib} oraz \\input{definicje.tex} (zob. main.tex).

Instalacja: pip install pandas numpy scipy statsmodels matplotlib
Uruchomienie: python analiza_odpowiedzi_naukowa.py data.csv --wyniki wyniki_naukowe
"""

import argparse
import hashlib
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
    wrazliwosc.append(("main", "Efekty stałe pracownika i pytania (model główny)", "Model główny (efekty stałe)",
                       m1.OR, m1.lo, m1.hi, info["M1"]["n"]))
    c = x.loc[(x["liczba_prob"] >= kohorta) & (x["proba"] <= kohorta)]
    r, i = logit_fe("correct ~ log2_proba", c)
    wrazliwosc.append(("cohort", f"Kohorta zbalansowana (sekwencje z $\\geq${kohorta} próbami, próby 1--{kohorta})",
                       f"Kohorta zbalansowana (≥{kohorta} prób)", r.OR[0], r.lo[0], r.hi[0], i["n"]))
    r, i = logit_fe("correct ~ log2_proba", x.loc[x["proba"] <= 10])
    wrazliwosc.append(("trunc", "Próby obcięte do 10", "Próby ≤10", r.OR[0], r.lo[0], r.hi[0], i["n"]))
    for od, do in ((3, 4), (5, 7), (8, None)):
        s = x.loc[(x["liczba_prob"] >= od) & ((x["liczba_prob"] <= do) if do else True)]
        r, i = logit_fe("correct ~ log2_proba", s)
        et = f"{od}--{do}" if do else f"$\\geq${od}"
        krotko = f"{od}–{do}" if do else f"≥{od}"
        wrazliwosc.append((f"len{od}", f"Wyłącznie sekwencje o długości {et}", f"Długość sekwencji {krotko}",
                           r.OR[0], r.lo[0], r.hi[0], i["n"]))
    aktywni = x.groupby("user_symbol")["id"].transform("size") >= 50
    r, i = logit_fe("correct ~ log2_proba", x.loc[aktywni])
    wrazliwosc.append(("active", "Pracownicy z $\\geq$50 odpowiedziami", "Pracownicy z ≥50 odpowiedziami",
                       r.OR[0], r.lo[0], r.hi[0], i["n"]))
    r, i = logit_fe("correct ~ log2_proba + staz_lata", x)
    wrazliwosc.append(("tenure", "Z korektą o staż pracownika", "Korekta o staż",
                       r.OR[0], r.lo[0], r.hi[0], i["n"]))
    grupy = x["user_symbol"].astype("category").cat.codes
    g = smf.gee("correct ~ log2_proba", groups=grupy, data=x, family=sm.families.Binomial(),
                cov_struct=sm.cov_struct.Exchangeable()).fit()
    ci = g.conf_int().loc["log2_proba"]
    wrazliwosc.append(("gee", "GEE, korelacja wymienna w obrębie pracownika (efekt uśredniony populacyjnie)",
                       "GEE (uśredniony populacyjnie)", np.exp(g.params["log2_proba"]), np.exp(ci[0]), np.exp(ci[1]),
                       len(x)))
    # model mieszany (MAP/Laplace): wariancje efektów losowych i ICC
    from statsmodels.genmod.bayes_mixed_glm import BinomialBayesMixedGLM
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        mm = BinomialBayesMixedGLM.from_formula(
            "correct ~ log2_proba", {"u": "0 + C(user_symbol)", "q": "0 + C(question_id)"}, x).fit_map()
    beta, se = mm.fe_mean[1], mm.fe_sd[1]
    wrazliwosc.append(("mixed", "Skrzyżowane losowe wyrazy wolne pracownika i pytania (aproksymacja Laplace'a)",
                       "Model mieszany (efekty losowe)",
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


# ------------------------------------------------------------ demografia (people.csv)

PLCI = {"k": "kobieta", "m": "mężczyzna"}
BRAK = "brak danych"


def demografia(x, plik):
    """Wiek i płeć pracowników objętych analizą (jeden wiersz na osobę z logu).

    people.csv (separator ';'): Odpowiadajacy = imie.nazwisko, wiek, Plec (k/m). Osoby są łączone z logiem
    przez MD5 identyfikatora imie.nazwisko (= user_symbol); imiona i nazwiska nie trafiają do wyników.
    """
    p = pd.read_csv(plik, sep=";", dtype=str, keep_default_na=False, encoding="utf-8-sig")
    brak = {"Odpowiadajacy", "wiek", "Plec"} - set(p.columns)
    if brak:
        raise ValueError(f"{plik}: brak kolumn {sorted(brak)}")
    p["user_symbol"] = p["Odpowiadajacy"].str.strip().map(lambda s: hashlib.md5(s.encode("utf-8")).hexdigest())
    p["wiek"] = pd.to_numeric(p["wiek"], errors="coerce")
    p["plec"] = p["Plec"].str.strip().str.lower().map(PLCI)
    osoby = p.groupby("user_symbol").agg(wiek=("wiek", "first"), plec=("plec", "first"))  # first pomija braki
    o = pd.DataFrame(index=pd.Index(x["user_symbol"].unique(), name="user_symbol")).join(osoby)
    o["dopasowana"] = o.index.isin(osoby.index)
    o["plec"] = o["plec"].fillna(BRAK)
    o["dekada"] = (o["wiek"] // 10 * 10).astype("Int64")
    return o


def podsumuj_demografie(o):
    """Liczebności: osoby, płeć, wiek (mediana, IQR, zakres) i przedziały 10-letnie z podziałem na płeć."""
    w = o["wiek"].dropna()
    znana = o["plec"] != BRAK
    wiek_plec = pd.crosstab(o["dekada"], o["plec"]).reindex(columns=["kobieta", "mężczyzna", BRAK], fill_value=0)
    wiek_plec = wiek_plec.loc[:, (wiek_plec.sum() > 0) | (wiek_plec.columns != BRAK)]
    return {"osoby": len(o), "dopasowane": int(o["dopasowana"].sum()),
            "kobiety": int((o["plec"] == "kobieta").sum()), "mezczyzni": int((o["plec"] == "mężczyzna").sum()),
            "plec_znana": int(znana.sum()), "plec_brak": int((~znana).sum()),
            "wiek_n": len(w), "wiek_brak": int(o["wiek"].isna().sum()),
            "wiek_med": w.median(), "wiek_q1": w.quantile(.25), "wiek_q3": w.quantile(.75),
            "wiek_min": w.min(), "wiek_max": w.max(), "wiek_sr": w.mean(), "wiek_sd": w.std(),
            "wiek_plec": wiek_plec}


# ------------------------------------------------------------ formatowanie (polska notacja, składnia LaTeX)

PRZECINEK = "{,}"  # przecinek dziesiętny poprawny zarówno w trybie tekstowym, jak i matematycznym
MINUS = "\\ensuremath{-}"
SEP = "\\midrule"  # wiersz-separator grup w tabeli
MIESIACE = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia",
            "września", "października", "listopada", "grudnia"]


def f_num(v, d=2):
    return (MINUS if round(v, d) < 0 else "") + f"{abs(v):.{d}f}".replace(".", PRZECINEK)


def f_int(v):
    n = int(round(v))
    s = f"{abs(n):,}".replace(",", "\\,") if abs(n) >= 10000 else str(abs(n))
    return (MINUS if n < 0 else "") + s


def f_pct(p, d=1):
    return f_num(100 * p, d)


def f_ci(lo, hi, d=1, skala=100):
    return f"[{f_num(skala * lo, d)}; {f_num(skala * hi, d)}]"


def f_or(v):
    return f_num(v, 2)


def f_p(p):
    if pd.isna(p):
        return "--"
    return "$<$0{,}001" if p < 0.001 else f_num(p, 3)


def f_p_rel(p):
    """Wartość p z relacją, do trybu matematycznego: $p \\SignP$ -> p = 0,003 albo p < 0,001."""
    if pd.isna(p):
        return "= \\textrm{--}"
    return "< 0{,}001" if p < 0.001 else "= " + f_num(p, 3)


def f_data(t):
    return f"{MIESIACE[t.month - 1]} {t.year}"  # dopełniacz: ,,od stycznia 2023''


def bez_latexu(s):
    """Usuwa składnię LaTeX z wartości makr (do raportu tekstowego)."""
    return str(s).replace(PRZECINEK, ",").replace(MINUS, "-").replace("\\,", " ").replace("$", "") \
        .replace("--", "–")


def esc(s):
    return str(s).replace("\\", "\\textbackslash{}").replace("&", "\\&").replace("%", "\\%") \
        .replace("_", "\\_").replace("#", "\\#")


def tabela_csv(katalog, nazwa, df):
    """Zapisuje tabelę do <nazwa>.csv wczytywanego w LaTeX-u przez \\tabelacsv (csvsimple-l3).

    Separator ';', pierwszy wiersz to nagłówek, komórki w składni LaTeX. Komórki zawierające ';'
    są ujmowane w klamry. Wiersz z SEP w pierwszej kolumnie oznacza linię \\midrule przed kolejnym wierszem.
    """
    def kom(v):
        s = str(v)
        return "{" + s + "}" if ";" in s else s
    linie, grupa = [";".join(kom(c) for c in df.columns)], False
    for wiersz in df.itertuples(index=False):
        if str(wiersz[0]) == SEP:
            grupa = True
            continue
        komorki = [kom(v) for v in wiersz]
        if grupa:
            komorki[0], grupa = f"{SEP} {komorki[0]}", False
        linie.append(";".join(komorki))
    (katalog / f"{nazwa}.csv").write_text("\n".join(linie) + "\n", encoding="utf-8")


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


def przecinek(*osie):
    """Etykiety osi z przecinkiem dziesiętnym."""
    from matplotlib.ticker import FuncFormatter
    for o in osie:
        o.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}".replace(".", ",").replace("-", "−")))


def zapisz(fig, katalog, nazwa):
    for ext in ("pdf", "png"):
        fig.savefig(katalog / f"{nazwa}.{ext}")
    fig.clf()


def wykres_krzywa(plt, katalog, krzywa, fit, max_proba, kohorta):
    fig, ax = plt.subplots(figsize=(3.5, 2.5))
    n_kohorta = f"{int(krzywa.loc[krzywa['proba'] == 'cohort', 'n'].iloc[0]):,}".replace(",", "\u2009")
    for proba, kolor, marker, etykieta in [
            ("all", KOLOR_1, "o", "Wszystkie sekwencje"),
            ("cohort", KOLOR_2, "s", f"Kohorta zbalansowana ($n$ = {n_kohorta}), próby 1–{kohorta}")]:
        k = krzywa.loc[krzywa["proba"] == proba]
        off = -0.08 if proba == "all" else 0.08
        ax.errorbar(k["etap"] + off, 100 * k["p"], yerr=[100 * (k["p"] - k["ci_lo"]), 100 * (k["ci_hi"] - k["p"])],
                    color=kolor, marker=marker, capsize=2, elinewidth=0.8, label=etykieta)
    xs = np.linspace(1, max_proba - 1, 100)
    wyk = f"{fit['b']:.2f}".replace(".", "{,}")
    ax.plot(xs, 100 * (1 - fit["a"] * xs ** (-fit["b"])), ls="--", lw=1, color=SZARY,
            label=f"Dopasowanie potęgowe (błąd $\\propto$ próba$^{{-{wyk}}}$)")
    ax.set_xticks(range(1, max_proba + 1))
    ax.set_xticklabels([str(i) for i in range(1, max_proba)] + [f"{max_proba}+"])
    przecinek(ax.yaxis)
    ax.set_xlabel("Numer próby (ten sam pracownik, to samo pytanie)")
    ax.set_ylabel("Odpowiedzi poprawne (%)")
    ax.legend(loc="lower right")
    zapisz(fig, katalog, "rys_krzywa_uczenia")


def wykres_odstep(plt, katalog, ret):
    fig, ax = plt.subplots(figsize=(3.5, 2.5))
    for prev, kolor, marker, etykieta in [(1, KOLOR_1, "o", "Poprzednia próba poprawna"),
                                          (0, KOLOR_2, "s", "Poprzednia próba błędna")]:
        k = ret.loc[ret["poprzednia"] == prev]
        xs = k["przedzial"].astype(int) + (-0.08 if prev else 0.08)
        ax.errorbar(xs, 100 * k["p"], yerr=[100 * (k["p"] - k["ci_lo"]), 100 * (k["ci_hi"] - k["p"])],
                    color=kolor, marker=marker, capsize=2, elinewidth=0.8, label=etykieta)
    ax.set_xticks(range(len(ETYKIETY_DNI)))
    ax.set_xticklabels([e.replace("--", "–").replace("$\\geq$", "≥") for e in ETYKIETY_DNI])
    przecinek(ax.yaxis)
    ax.set_xlabel("Dni od poprzedniej próby tego samego pytania")
    ax.set_ylabel("Odpowiedzi poprawne (%)")
    ax.legend(loc="center right")
    zapisz(fig, katalog, "rys_odstep")


def wykres_osoby(plt, katalog, d):
    fig, ax = plt.subplots(figsize=(3.5, 2.3))
    v = 100 * d
    kraw = np.arange(np.floor(v.min() / 5) * 5 - 2.5, np.ceil(v.max() / 5) * 5 + 5, 5)
    ax.hist(v, bins=kraw, color=KOLOR_1, edgecolor="white", linewidth=1)
    ax.axvline(0, color="#52514e", lw=0.8)
    przecinek(ax.xaxis)
    ax.set_xlabel("Zmiana odsetka poprawnych, próba 3 − próba 1 (p.p.)")
    ax.set_ylabel("Pracownicy")
    zapisz(fig, katalog, "rys_zmiana_pracownikow")


def wykres_pozycje(plt, katalog, poz, alfa):
    fig, ax = plt.subplots(figsize=(3.5, 2.7))
    ax.grid(axis="x")
    k = poz.dropna(subset=["dyskryminacja"])
    sig = k["istotna_poprawa"]
    ax.scatter(100 * k.loc[~sig, "p_pierwsza"], k.loc[~sig, "dyskryminacja"], s=14, color=SZARY,
               marker="o", alpha=0.8, label="Brak istotnego trendu", edgecolors="white", linewidths=0.5)
    ax.scatter(100 * k.loc[sig, "p_pierwsza"], k.loc[sig, "dyskryminacja"], s=16, color=KOLOR_1,
               marker="^", label=f"Poprawa (FDR $q$ < {alfa:g})".replace(".", ","),
               edgecolors="white", linewidths=0.5)
    ax.axhline(0.2, color="#52514e", lw=0.7, ls=":")
    ax.axvline(90, color="#52514e", lw=0.7, ls=":")
    przecinek(ax.xaxis, ax.yaxis)
    ax.set_xlabel("Trudność pytania: poprawne w pierwszej próbie (%)")
    ax.set_ylabel("Dyskryminacja (korelacja pytanie–reszta $r$)")
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1), ncol=2, borderaxespad=0.2, handletextpad=0.2)
    zapisz(fig, katalog, "rys_analiza_pytan")


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
    ax.set_xticks(ticks); ax.set_xticklabels([f"{t:g}".replace(".", ",") for t in ticks]); ax.minorticks_off()
    ax.set_xlim(0.95, max(1.7, w["hi"].max() * 1.05))
    ax.set_yticks(w.index); ax.set_yticklabels(w["short"])
    ax.set_xlabel("Iloraz szans na podwojenie numeru próby (skala log.)")
    zapisz(fig, katalog, "rys_wrazliwosc")


def wykres_demografia(plt, katalog, d):
    t = d["wiek_plec"]
    fig, ax = plt.subplots(figsize=(3.5, 2.4))
    xs, dol = np.arange(len(t)), np.zeros(len(t))
    for kol, kolor, et in (("kobieta", KOLOR_1, "Kobiety"), ("mężczyzna", KOLOR_2, "Mężczyźni"),
                           (BRAK, SZARY, "Brak danych o płci")):
        if kol in t.columns:
            ax.bar(xs, t[kol], bottom=dol, color=kolor, width=0.7, label=et, edgecolor="white", linewidth=0.5)
            dol += t[kol].to_numpy()
    for xi, n in zip(xs, dol):
        ax.text(xi, n, f"{int(n)}", ha="center", va="bottom", fontsize=7, color="#52514e")
    ax.set_xticks(xs)
    ax.set_xticklabels([f"{d}–{d + 9}" for d in t.index])
    ax.set_ylim(0, dol.max() * 1.15)
    ax.set_xlabel("Wiek (lata)")
    ax.set_ylabel("Pracownicy")
    ax.legend(loc="upper left")
    zapisz(fig, katalog, "rys_demografia")


def wykres_aktywnosc(plt, katalog, x):
    import matplotlib.dates as mdates
    mies = x.groupby(x["create_time"].dt.to_period("M")).agg(n=("id", "size"), osoby=("user_symbol", "nunique"))
    mies = mies.reindex(pd.period_range(mies.index.min(), mies.index.max(), freq="M"), fill_value=0)
    fig, axs = plt.subplots(2, 1, figsize=(7, 3.4), sharex=True)
    xs = mies.index.to_timestamp()
    for ax, kol, et in [(axs[0], "n", "Odpowiedzi w miesiącu"), (axs[1], "osoby", "Aktywni pracownicy")]:
        ax.bar(xs, mies[kol], width=24, color=KOLOR_1)
        ax.set_ylabel(et)
    axs[1].xaxis.set_major_locator(mdates.YearLocator())
    axs[1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.align_ylabels(axs)
    zapisz(fig, katalog, "rys_aktywnosc")


# ------------------------------------------------------------ artykuł: definicje, tabele (CSV), rysunki

def materialy_artykulu(x, rejected, pairs, users, katalog, args, demo=None):
    rng = np.random.default_rng(args.seed)
    tdir, fdir, ddir = katalog / "tabele", katalog / "rysunki", katalog / "dane"
    for d in (tdir, fdir, ddir):
        d.mkdir(parents=True, exist_ok=True)
    B, K, MX = args.bootstrap, args.kohorta, args.max_proba
    M = {}

    # --- Tabela: charakterystyka zbioru
    sek = x.groupby(KLUCZ).size()
    per_user = x.groupby("user_symbol").agg(n=("id", "size"), q=("question_id", "nunique"),
                                            dni=("create_time", lambda s: s.dt.normalize().nunique()))
    gap = x["odstep_dni"].dropna()
    dzienne = x.groupby(["user_symbol", x["create_time"].dt.normalize()]).size()
    opcje = x.groupby("question_id")["answer_id"].nunique()
    M.update(NResponses=f_int(len(x)), NEmployees=f_int(x["user_symbol"].nunique()),
             NItems=f_int(x["question_id"].nunique()), NModules=f_int(x["room_Code"].nunique()),
             NSequences=f_int(len(sek)), NRejected=f_int(len(rejected)),
             DateStart=f_data(x["create_time"].min()), DateEnd=f_data(x["create_time"].max()),
             AccOverall=f_pct(x["correct"].mean()), AccFirst=f_pct(x.loc[x["proba"] == 1, "correct"].mean()),
             AttemptsMedian=f_num(sek.median(), 0), AttemptsMax=f_int(sek.max()),
             SeqRepeatedPct=f_pct((sek >= 2).mean()), SeqMinThreePct=f_pct((sek >= 3).mean()),
             GapMedian=f_num(gap.median(), 0), GapQOne=f_num(gap.quantile(.25), 0),
             GapQThree=f_num(gap.quantile(.75), 0), DailyMedian=f_num(dzienne.median(), 0),
             RespPerEmpMedian=f_int(per_user["n"].median()),
             RespPerEmpQOne=f_int(per_user["n"].quantile(.25)), RespPerEmpQThree=f_int(per_user["n"].quantile(.75)))
    wd = (x["create_time"].dt.dayofweek < 5).mean()
    zakres = x.groupby("user_symbol")["create_time"].agg(["min", "max"])
    staz_mies = (zakres["max"] - zakres["min"]).dt.days / 30.44
    koniec = x["create_time"].max() - pd.Timedelta(days=90)
    M.update(SpanMonthsMedian=f_num(staz_mies.median(), 0),
             ActiveLastQuarterPct=f_pct((zakres["max"] >= koniec).mean()),
             WeekdayPct=f_pct(wd), ItemsPerEmpMedian=f_num(per_user["q"].median(), 0),
             ActiveDaysMedian=f_num(per_user["dni"].median(), 0), OptionsMedian=f_num(opcje.median(), 0),
             NExcluded=f_int(args.wykluczone_n), NExcludedItems=f_int(args.wykluczone_pytania),
             NExcludedItemResp=f_int(args.wykluczone_pytania_n),
             ExcludedModules=", ".join(esc(k) for k in args.wyklucz_pokoje) or "brak")

    def med_iqr(s, d=0):
        return f"{f_num(s.median(), d)} {f_ci(s.quantile(.25), s.quantile(.75), d, 1)}"

    t1 = [
        ("Odpowiedzi", M["NResponses"]), ("Pracownicy", M["NEmployees"]),
        ("Pytania", M["NItems"]),
        ("Okres obserwacji", f"{x['create_time'].min():%Y-%m-%d} -- {x['create_time'].max():%Y-%m-%d}"),
        ("Sekwencje pracownik--pytanie", M["NSequences"]),
        ("Zaobserwowane opcje odpowiedzi na pytanie, mediana (zakres)",
         f"{f_num(opcje.median(), 0)} ({opcje.min()}--{opcje.max()})"),
        (SEP, ""),
        ("Odpowiedzi na pracownika, mediana [IQR]",
         f"{M['RespPerEmpMedian']} [{M['RespPerEmpQOne']}; {M['RespPerEmpQThree']}]"),
        ("Pytania na pracownika, mediana [IQR]", med_iqr(per_user["q"])),
        ("Dni aktywności na pracownika, mediana [IQR]", med_iqr(per_user["dni"])),
        ("Odpowiedzi na dzień aktywności, mediana [IQR]", med_iqr(dzienne)),
        ("Miesiące między pierwszą a ostatnią odpowiedzią, mediana [IQR]", med_iqr(staz_mies)),
        #("Pracownicy aktywni w ostatnich 90 dniach danych (\\%)", M["ActiveLastQuarterPct"]),
        (SEP, ""),
        ("Próby w sekwencji, mediana [IQR] (maks.)", f"{med_iqr(sek)} ({f_int(sek.max())})"),
        ("Sekwencje z $\\geq$2 / $\\geq$3 próbami (\\%)", f"{M['SeqRepeatedPct']} / {M['SeqMinThreePct']}"),
        ("Dni między próbami, mediana [IQR]", f"{M['GapMedian']} [{M['GapQOne']}; {M['GapQThree']}]"),
        (SEP, ""),
        ("Odpowiedzi poprawne, ogółem (\\%)", M["AccOverall"]),
        ("Odpowiedzi poprawne, pierwsze próby (\\%)", M["AccFirst"]),
    ]
    tabela_csv(tdir, "zbior_danych", pd.DataFrame(t1, columns=["Cecha", "Wartość"]))

    # --- czy harmonogram powtórek zależy od poprawności? (argument przeciw selekcji)
    nast = x.assign(ma_nast=x.groupby(KLUCZ)["id"].shift(-1).notna(),
                    nast_odstep=x.groupby(KLUCZ)["odstep_dni"].shift(-1))
    h = nast.groupby("correct").agg(p=("ma_nast", "mean"), gap=("nast_odstep", "median"))
    M.update(ReaskAfterCorrect=f_pct(h.loc[1, "p"]), ReaskAfterIncorrect=f_pct(h.loc[0, "p"]),
             GapAfterCorrect=f_num(h.loc[1, "gap"], 0), GapAfterIncorrect=f_num(h.loc[0, "gap"], 0))
    h.reset_index().to_csv(ddir / "harmonogram_wg_poprawnosci.csv", index=False)

    # --- Tabela i wykres: krzywa uczenia
    krzywa, fit = krzywa_uczenia(x, B, rng, MX, K)
    krzywa.to_csv(ddir / "krzywa_uczenia.csv", index=False)
    a, c = krzywa.loc[krzywa["proba"] == "all"], krzywa.loc[krzywa["proba"] == "cohort"].set_index("etap")
    t3 = []
    for _, r in a.iterrows():
        e = int(r["etap"])
        row = [f"{e}+" if e == MX else str(e), f_int(r["n"]), f_int(r["osoby"]), f_pct(r["p"]),
               f_ci(r["ci_lo"], r["ci_hi"])]
        row += ([f_int(c.loc[e, "n"]), f_pct(c.loc[e, "p"]), f_ci(c.loc[e, "ci_lo"], c.loc[e, "ci_hi"])]
                if e in c.index else ["", "", ""])
        t3.append(row)
    tabela_csv(tdir, "krzywa_uczenia",
               pd.DataFrame(t3, columns=["Próba", "$n$", "Pracownicy", "\\%", "95\\% PU",
                                         "$n$ (kohorta)", "\\% (kohorta)", "95\\% PU (kohorta)"]))
    a1, aM = a.iloc[0], a.iloc[-1]
    c1, cK = c.iloc[0], c.iloc[-1]
    M.update(AccAttOne=f_pct(a1["p"]), AccAttOneCI=f_ci(a1["ci_lo"], a1["ci_hi"]),
             AccAttMax=f_pct(aM["p"]), AccAttMaxCI=f_ci(aM["ci_lo"], aM["ci_hi"]), AttMax=f"{MX}",
             CohortK=f"{K}", CohortN=f_int(len(x.loc[x["liczba_prob"] >= K].groupby(KLUCZ))),
             CohortAccOne=f_pct(c1["p"]), CohortAccK=f_pct(cK["p"]),
             CohortAccOneCI=f_ci(c1["ci_lo"], c1["ci_hi"]), CohortAccKCI=f_ci(cK["ci_lo"], cK["ci_hi"]),
             PowerLawB=f_num(fit["b"]), PowerLawRsq=f_num(fit["r2"]))

    # --- Tabela: modele regresji
    wyniki, info, wraz, icc = modele(x, K)
    nazwy = {"log2_proba": "Numer próby (na podwojenie)", "poprzednia": "Poprzednia próba poprawna",
             "log2_odstep": "Dni od poprzedniej próby (na podwojenie)",
             "staz_lata": "Staż pracownika (na rok)"}
    kolejnosc = ["log2_proba", "poprzednia", "log2_odstep", "staz_lata"]
    t4 = []
    for term in kolejnosc:
        row = [nazwy[term]]
        for m in ("M1", "M2", "M3"):
            w = wyniki[m].set_index("term")
            row.append(f"{f_or(w.loc[term, 'OR'])} [{f_or(w.loc[term, 'lo'])}; {f_or(w.loc[term, 'hi'])}]"
                       if term in w.index else "")
        t4.append(row)
    t4.append([SEP, "", "", ""])
    t4.append(["Dane"] + ["Wszystkie próby", "Próby $\\geq$2", "Pierwsze próby"])
    t4.append(["Odpowiedzi"] + [f_int(info[m]["n"]) for m in ("M1", "M2", "M3")])
    t4.append(["Pracownicy / pytania"] + [f"{f_int(info[m]['osoby'])} / {f_int(info[m]['pytania'])}"
                                          for m in ("M1", "M2", "M3")])
    tabela_csv(tdir, "regresja", pd.DataFrame(t4, columns=["Predyktor", "M1 (uczenie)", "M2 (retencja)", "M3 (nowe pytania)"]))
    pd.concat([w.assign(model=m) for m, w in wyniki.items()]).to_csv(ddir / "regresja.csv", index=False)
    for m, pref in (("M1", "MOne"), ("M2", "MTwo"), ("M3", "MThree")):
        for _, r in wyniki[m].iterrows():
            nm = {"log2_proba": "Attempt", "poprzednia": "Prev", "log2_odstep": "Gap", "staz_lata": "Tenure"}[r.term]
            M[f"OR{pref}{nm}"] = f_or(r.OR)
            M[f"OR{pref}{nm}CI"] = f"[{f_or(r.lo)}; {f_or(r.hi)}]"
            M[f"P{pref}{nm}"] = f_p_rel(r.p)
    M.update(MOneDropped=f_int(info["M1"]["wykluczone"]),
             ICCEmployee=f_num(icc["icc_u"]), ICCItem=f_num(icc["icc_q"]),
             SDEmployee=f_num(icc["sd_u"]), SDItem=f_num(icc["sd_q"]),
             RsqMarginal=f_num(icc["r2_m"], 3), RsqConditional=f_num(icc["r2_c"]))

    # --- Tabela i wykres: analizy wrażliwości
    wraz.to_csv(ddir / "wrazliwosc.csv", index=False)
    t5 = pd.DataFrame({"Analiza": wraz["analysis"], "Odpowiedzi": wraz["n"].map(f_int),
                       "OR [95\\% PU]": [f"{f_or(o)} [{f_or(l)}; {f_or(h)}]"
                                         for o, l, h in zip(wraz["OR"], wraz["lo"], wraz["hi"])]})
    tabela_csv(tdir, "wrazliwosc", t5)
    M.update(ORRange=f"{f_or(wraz['OR'].min())}--{f_or(wraz['OR'].max())}")
    for _, r in wraz.iterrows():
        nm = "Sens" + "".join(ch for ch in r.key.title() if ch.isalpha()) + \
             {"len3": "Three", "len5": "Five", "len8": "Eight"}.get(r.key, "")
        M[f"OR{nm}"] = f_or(r.OR)
        M[f"OR{nm}CI"] = f"[{f_or(r.lo)}; {f_or(r.hi)}]"

    # --- Tabela: przejścia między kolejnymi próbami + dystraktory
    tr, dys = przejscia(x, B, rng)
    tr.to_csv(ddir / "przejscia.csv", index=False)
    t6 = []
    for _, r in tr.sort_values("poprzednia", ascending=False).iterrows():
        et = "Poprawna" if r["poprzednia"] == 1 else "Błędna"
        t6.append([et, f_int(r["n"]), f_pct(r["p"]), f_ci(r["ci_lo"], r["ci_hi"]), f_pct(1 - r["p"])])
    tabela_csv(tdir, "przejscia",
               pd.DataFrame(t6, columns=["Poprzednia próba", "$n$", "Kolejna poprawna (\\%)", "95\\% PU",
                                         "Kolejna błędna (\\%)"]))
    r1, r0 = tr.set_index("poprzednia").loc[1], tr.set_index("poprzednia").loc[0]
    M.update(RetainPct=f_pct(r1["p"]), RetainCI=f_ci(r1["ci_lo"], r1["ci_hi"]),
             ForgetPct=f_pct(1 - r1["p"]), RecoverPct=f_pct(r0["p"]),
             RecoverCI=f_ci(r0["ci_lo"], r0["ci_hi"]), PersistPct=f_pct(1 - r0["p"]),
             SameDistractorPct=f_pct(dys["p"]), SameDistractorCI=f_ci(dys["lo"], dys["hi"]),
             SameDistractorN=f_int(dys["n"]), SameDistractorExpected=f_pct(dys["oczekiwane"]),
             SameDistractorExpectedPop=f_pct(dys["oczekiwane_pop"]))

    # --- Tabela i wykres: retencja wg odstępu
    ret = retencja_wg_odstepu(x, B, rng)
    ret.to_csv(ddir / "retencja_wg_odstepu.csv", index=False)
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
    tabela_csv(tdir, "retencja_wg_odstepu",
               pd.DataFrame(t7, columns=["Dni od poprzedniej", "$n$", "Poprawne, \\% [95\\% PU]",
                                         "$n$", "Poprawne, \\% [95\\% PU]"]))

    # --- Tabela i wykres: zmiana na poziomie pracowników
    zo, dvec = zmiana_osob(pairs, users, B, rng)
    t8 = [
        ("Pracownicy z $\\geq$1 sekwencją o $\\geq$3 próbach", f_int(zo["osoby"])),
        ("Poprawa / pogorszenie / bez zmian",
         f"{f_int(zo['poprawa'])} / {f_int(zo['pogorszenie'])} / {f_int(zo['bez_zmian'])}"),
        ("Średnia zmiana, p.p. [95\\% PU]", f"{f_num(zo['sredni_pp'], 1)} {f_ci(zo['sredni_lo'], zo['sredni_hi'], 1, 1)}"),
        ("Mediana zmiany, p.p.", f_num(zo["mediana_pp"], 1)),
        ("Test znaków: odsetek z poprawą [95\\% PU]; $p$",
         f"{f_num(zo['poprawa'] / (zo['poprawa'] + zo['pogorszenie']))} "
         f"{f_ci(zo['znak_lo'], zo['znak_hi'], 2, 1)}; {f_p(zo['znak_p'])}"),
        ("Test Wilcoxona $W$; $p$; korelacja rangowo-dwuseryjna $r$",
         f"{f_int(zo['wilcoxon_W'])}; {f_p(zo['wilcoxon_p'])}; {f_num(zo['r_rb'])}"),
        (SEP, ""),
        ("Sekwencje (pracownik--pytanie) z $\\geq$3 próbami", f_int(zo["pary"])),
        ("Poprawne w próbie 1 / próbie 3 (\\%)", f"{f_pct(zo['p1'])} / {f_pct(zo['p3'])}"),
        ("Błędna$\\to$poprawna / poprawna$\\to$błędna", f"{f_int(zo['mc_c'])} / {f_int(zo['mc_b'])}"),
        ("Test McNemara $\\chi^2$; $p$ (bez uwzględnienia klastrów)", f"{f_num(zo['mc_chi2'], 1)}; {f_p(zo['mc_p'])}"),
    ]
    tabela_csv(tdir, "zmiana_pracownikow", pd.DataFrame(t8, columns=["Miara", "Wartość"]))
    pd.DataFrame([zo]).to_csv(ddir / "zmiana_pracownikow.csv", index=False)
    M.update(EmpN=f_int(zo["osoby"]), EmpImproved=f_int(zo["poprawa"]), EmpWorsened=f_int(zo["pogorszenie"]),
             EmpUnchanged=f_int(zo["bez_zmian"]), EmpMeanChange=f_num(zo["sredni_pp"], 1),
             EmpMeanChangeCI=f_ci(zo["sredni_lo"], zo["sredni_hi"], 1, 1), SignP=f_p_rel(zo["znak_p"]),
             WilcoxonP=f_p_rel(zo["wilcoxon_p"]), RankBiserial=f_num(zo["r_rb"]),
             EmpSharePct=f_pct(zo["osoby"] / x["user_symbol"].nunique()))

    # --- Tabele i wykres: analiza pytań
    poz = analiza_pozycji(x, args.min_pozycja, args.alfa)
    poz.to_csv(ddir / "pytania.csv", index=False)
    dk, pp = poz["dyskryminacja"], poz["p_pierwsza"]
    dom = poz["dominujacy_dystraktor_udzial"]
    alfa = f_num(args.alfa, 2)
    t9 = [
        ("Analizowane pytania", f_int(len(poz))),
        ("Trudność (\\% poprawnych w pierwszej próbie), mediana [IQR]",
         f"{f_pct(pp.median())} {f_ci(pp.quantile(.25), pp.quantile(.75))}"),
        ("Pytania z $<$50\\% / 50--90\\% / $>$90\\% poprawnych",
         f"{(pp < .5).sum()} / {pp.between(.5, .9).sum()} / {(pp > .9).sum()}"),
        (f"Dyskryminacja (korelacja pytanie--reszta $r$), mediana [IQR], pytania z $n\\geq${args.min_pozycja}",
         f"{f_num(dk.median())} {f_ci(dk.quantile(.25), dk.quantile(.75), 2, 1)} ($k$ = {dk.notna().sum()})"),
        ("Pytania z $r<0{,}20$ / $0{,}20$--$0{,}29$ / $\\geq0{,}30$",
         f"{(dk < .2).sum()} / {dk.between(.2, .3, inclusive='left').sum()} / {(dk >= .3).sum()}"),
        ("Udział błędów przypadających na najczęstszy dystraktor (\\%), mediana [IQR]",
         f"{f_pct(dom.median())} {f_ci(dom.quantile(.25), dom.quantile(.75))}"),
        ("Zaobserwowane dystraktory wybierane w $<$5\\% odpowiedzi (niefunkcjonalne)",
         f"{f_int(poz['dystraktory_niefunkcjonalne'].sum())} z {f_int(poz['dystraktory_obserwowane'].sum())} "
         f"({f_pct(poz['dystraktory_niefunkcjonalne'].sum() / poz['dystraktory_obserwowane'].sum())}\\%)"),
        (f"Pytania z poprawą / pogorszeniem przy powtórkach (FDR $q<{alfa}$)",
         f"{poz['istotna_poprawa'].sum()} / {poz['istotne_pogorszenie'].sum()} "
         f"(z {poz['p_trend'].notna().sum()} testowalnych)"),
    ]
    tabela_csv(tdir, "pytania", pd.DataFrame(t9, columns=["Miara", "Wartość"]))
    najtr = poz.sort_values("p_pierwsza").head(args.top_pozycje)
    t10 = pd.DataFrame({"Pytanie": najtr["question_id"], "Moduł": najtr["room_Code"].map(esc),
                        "$n$": najtr["n"].map(f_int), "Pierwsza (\\%)": najtr["p_pierwsza"].map(f_pct),
                        "Kolejne (\\%)": najtr["p_kolejne"].map(lambda v: "--" if pd.isna(v) else f_pct(v)),
                        "Dom.\\ dystr.\\ (\\%)": najtr["dominujacy_dystraktor_udzial"].map(f_pct),
                        "$r_{\\mathrm{it}}$": najtr["dyskryminacja"].map(lambda v: "--" if pd.isna(v) else f_num(v)),
                        "OR trendu": najtr["OR_log2_proba"].map(lambda v: "--" if pd.isna(v) else f_or(v)),
                        "$q$": najtr["q_fdr"].map(f_p)})
    tabela_csv(tdir, "najtrudniejsze_pytania", t10)
    ndys = poz["dystraktory_obserwowane"].sum()
    M.update(ItemDifficultyMedian=f_pct(pp.median()), TopDistractorMedian=f_pct(dom.median()),
             NDistractors=f_int(ndys), NNonFunctional=f_int(poz["dystraktory_niefunkcjonalne"].sum()),
             NonFunctionalPct=f_pct(poz["dystraktory_niefunkcjonalne"].sum() / ndys),
             ItemsModerate=f_int(pp.between(.5, .9).sum()),
             ItemsGoodDisc=f_int((dk >= .3).sum()), ItemsDiscTested=f_int(dk.notna().sum()),
             ItemsImproving=f_int(poz["istotna_poprawa"].sum()), ItemsWorsening=f_int(poz["istotne_pogorszenie"].sum()),
             ItemsTestable=f_int(poz["p_trend"].notna().sum()), ItemDiscMedian=f_num(dk.median()),
             ItemsLowDisc=f_int((dk < .2).sum()), ItemsEasy=f_int((pp > .9).sum()),
             ItemsHard=f_int((pp < .5).sum()), TopItems=f"{args.top_pozycje}")

    # --- Tabela i wykres: demografia pracowników objętych analizą (people.csv)
    if demo is not None:
        d = demo
        t = d["wiek_plec"]
        t11 = [
            ("Pracownicy objęci analizą", f_int(d["osoby"])),
            ("w tym z danymi demograficznymi, $n$ (\\%)", f"{f_int(d['dopasowane'])} ({f_pct(d['dopasowane'] / d['osoby'])})"),
            (SEP, ""),
            ("Kobiety, $n$ (\\%)", f"{f_int(d['kobiety'])} ({f_pct(d['kobiety'] / d['plec_znana'])})"),
            ("Mężczyźni, $n$ (\\%)", f"{f_int(d['mezczyzni'])} ({f_pct(d['mezczyzni'] / d['plec_znana'])})"),
            ("Brak danych o płci, $n$", f_int(d["plec_brak"])),
            (SEP, ""),
            ("Wiek (lata), mediana [IQR]",
             f"{f_num(d['wiek_med'], 0)} {f_ci(d['wiek_q1'], d['wiek_q3'], 0, 1)}"),
            ("Wiek (lata), średnia (SD)", f"{f_num(d['wiek_sr'], 1)} ({f_num(d['wiek_sd'], 1)})"),
            ("Wiek (lata), zakres", f"{f_num(d['wiek_min'], 0)}--{f_num(d['wiek_max'], 0)}"),
        ]
        wiersze_wieku = [(f"{dek}--{dek + 9} lat, $n$ (\\%)", f"{f_int(n)} ({f_pct(n / d['wiek_n'])})")
                         for dek, n in t.sum(axis=1).items()]
        t11 += [(SEP, "")] + wiersze_wieku + [("Brak danych o wieku, $n$", f_int(d["wiek_brak"]))]
        tabela_csv(tdir, "demografia", pd.DataFrame(t11, columns=["Cecha", "Wartość"]))
        t.rename(index=lambda dek: f"{dek}-{dek + 9}").rename_axis("przedzial_wieku").reset_index() \
            .to_csv(ddir / "demografia_wiek_plec.csv", index=False)
        M.update(DemoN=f_int(d["osoby"]), DemoMatched=f_int(d["dopasowane"]),
                 DemoMatchedPct=f_pct(d["dopasowane"] / d["osoby"]), DemoUnmatched=f_int(d["osoby"] - d["dopasowane"]),
                 DemoWomen=f_int(d["kobiety"]), DemoWomenPct=f_pct(d["kobiety"] / d["plec_znana"]),
                 DemoMen=f_int(d["mezczyzni"]), DemoMenPct=f_pct(d["mezczyzni"] / d["plec_znana"]),
                 DemoSexMissing=f_int(d["plec_brak"]), DemoAgeN=f_int(d["wiek_n"]),
                 DemoAgeMissing=f_int(d["wiek_brak"]), AgeMedian=f_num(d["wiek_med"], 0),
                 AgeQOne=f_num(d["wiek_q1"], 0), AgeQThree=f_num(d["wiek_q3"], 0),
                 AgeMin=f_num(d["wiek_min"], 0), AgeMax=f_num(d["wiek_max"], 0),
                 AgeMean=f_num(d["wiek_sr"], 1), AgeSD=f_num(d["wiek_sd"], 1))
        modalna = t.sum(axis=1).idxmax()
        M.update(AgeModalGroup=f"{modalna}--{modalna + 9}",
                 AgeModalGroupPct=f_pct(t.sum(axis=1).max() / d["wiek_n"]))

    # --- wykresy
    plt = styl_wykresow()
    wykres_krzywa(plt, fdir, krzywa, fit, MX, K)
    wykres_odstep(plt, fdir, ret)
    wykres_osoby(plt, fdir, dvec)
    wykres_pozycje(plt, fdir, poz, args.alfa)
    wykres_aktywnosc(plt, fdir, x)
    wykres_wrazliwosc(plt, fdir, wraz)
    if demo is not None:
        wykres_demografia(plt, fdir, demo)
    plt.close("all")

    # --- definicje.tex: stałe liczbowe + polecenia pomocnicze
    import platform, scipy, matplotlib
    M.update(BootReps=f_int(B), Alpha=alfa, MinItemN=f"{args.min_pozycja}", Seed=f"{args.seed}",
             MaxAttemptPooled=f"{MX}", VerPython=platform.python_version(), VerPandas=pd.__version__,
             VerNumpy=np.__version__, VerScipy=scipy.__version__, VerStatsmodels=sm.__version__,
             VerMatplotlib=matplotlib.__version__.split("+")[0])
    makra = [DEFINICJE_NAGLOWEK] + [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in M.items()]
    (katalog / "definicje.tex").write_text("\n".join(makra) + "\n", encoding="utf-8")
    return M, zo, wyniki, wraz, icc


DEFINICJE_NAGLOWEK = r"""% Wygenerowano automatycznie przez analiza_odpowiedzi_naukowa.py -- plik jest NADPISYWANY, nie edytuj ręcznie.
% Wstaw w preambule: \input{definicje.tex}
%
% Liczby w notacji polskiej: przecinek dziesiętny {,} (działa w tekście i w trybie matematycznym),
% odstęp tysięcy \, (od 10 000), minus \ensuremath{-}, przedziały [a; b].
% Makra wartości p (\SignP, \WilcoxonP, \P...) zawierają relację i są do trybu matematycznego: $p \SignP$.
%
% Tabele: \tabelacsv{<kolumny tabular>}{<nazwa pliku bez .csv>} wczytuje \TabDir<nazwa>.csv
% (csvsimple-l3; separator ';'; pierwszy wiersz = nagłówek; komórki w składni LaTeX; komórki ze średnikiem
% są ujęte w klamry; prefiks \midrule w pierwszej komórce = linia oddzielająca grupy wierszy).
% Przypis pod tabelą: \uwagatabeli{...}. Katalogi \TabDir i \FigDir można zdefiniować przed \input.
\RequirePackage{booktabs,csvsimple-l3}
\providecommand{\TabDir}{tabele/}
\providecommand{\FigDir}{rysunki/}
\providecommand{\fillin}[1]{\textbf{[#1]}}
\providecommand{\tabelacsv}[2]{\csvloop{file={\TabDir #2.csv}, separator=semicolon, head,
  column names detection=false, after head=\begin{tabular}{#1}\toprule\csvlinetotablerow\\\midrule,
  command=\csvlinetotablerow, late after line=\\, late after last line=\\\bottomrule\end{tabular}}}
\providecommand{\uwagatabeli}[1]{\par\vspace{2pt}\parbox{\linewidth}{\footnotesize #1}}
%
% Stałe liczbowe"""


# ------------------------------------------------------------ raport tekstowy

def raport(df, rejected, bins, trends, pairs, users, katalog, threshold, art=None, wykluczenie="", demo=None):
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
        lines += [bez_latexu(l) for l in [
                  "", "WYNIKI DO ARTYKUŁU (szczegóły: artykul/tabele, artykul/definicje.tex)",
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
                  f"{M['WilcoxonP']}; r_rb {M['RankBiserial']}.",
                  f"Pytania: poprawa {M['ItemsImproving']} / pogorszenie {M['ItemsWorsening']} z "
                  f"{M['ItemsTestable']} (FDR); niska dyskryminacja (r<0.20): {M['ItemsLowDisc']}."]]
    if demo is not None:
        d = demo
        lines += ["", "DEMOGRAFIA PRACOWNIKÓW OBJĘTYCH ANALIZĄ (people.csv, łączenie przez MD5 imie.nazwisko)",
                  f"Osoby w analizie: {d['osoby']}; z danymi demograficznymi: {d['dopasowane']} "
                  f"({100 * d['dopasowane'] / d['osoby']:.1f}%); bez dopasowania: {d['osoby'] - d['dopasowane']}.",
                  f"Płeć: kobiety {d['kobiety']} ({100 * d['kobiety'] / d['plec_znana']:.1f}%), mężczyźni "
                  f"{d['mezczyzni']} ({100 * d['mezczyzni'] / d['plec_znana']:.1f}%), brak danych {d['plec_brak']}.",
                  f"Wiek: mediana {d['wiek_med']:.0f} [IQR {d['wiek_q1']:.0f}–{d['wiek_q3']:.0f}], średnia "
                  f"{d['wiek_sr']:.1f} (SD {d['wiek_sd']:.1f}), zakres {d['wiek_min']:.0f}–{d['wiek_max']:.0f}; "
                  f"brak danych {d['wiek_brak']}.",
                  "Przedziały wieku (kobiety / mężczyźni" + (" / brak danych o płci" if BRAK in d["wiek_plec"] else "")
                  + " / razem):"]
        for dek, r in d["wiek_plec"].iterrows():
            lines.append(f"  {dek}–{dek + 9} lat: " + " / ".join(str(int(v)) for v in r.values) + f" / {int(r.sum())}")
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
    parser.add_argument("--min-opcje", type=int, default=2,
                        help="Pytania, w których zaobserwowano mniej różnych odpowiedzi, są wykluczane "
                             "(domyślnie 2 = wyklucz pytania z jedną odpowiedzią)")
    parser.add_argument("--bootstrap", type=int, default=2000, help="Liczba replikacji bootstrapu klastrowego")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--kohorta", type=int, default=5, help="Min. liczba prób w kohorcie zbalansowanej")
    parser.add_argument("--max-proba", type=int, default=10, help="Próby od tej wartości łączone w kategorię N+")
    parser.add_argument("--min-pozycja", type=int, default=30, help="Min. pierwszych prób do dyskryminacji pytania")
    parser.add_argument("--top-pozycje", type=int, default=10, help="Liczba najtrudniejszych pytań w tabeli")
    parser.add_argument("--alfa", type=float, default=0.05, help="Próg FDR")
    parser.add_argument("--bez-artykulu", action="store_true", help="Tylko tabele robocze i raport")
    parser.add_argument("--osoby", default="people.csv",
                        help="Plik z wiekiem i płcią (Odpowiadajacy=imie.nazwisko;wiek;Plec), łączony z logiem "
                             "przez MD5 imie.nazwisko; pusty napis = bez analizy demograficznej")
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
    opcje = data.groupby("question_id")["answer_id"].transform("nunique")
    args.wykluczone_pytania = data.loc[opcje < args.min_opcje, "question_id"].nunique()
    args.wykluczone_pytania_n = int((opcje < args.min_opcje).sum())
    data = data.loc[opcje >= args.min_opcje].reset_index(drop=True)
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
    demo = None
    if args.osoby:
        if Path(args.osoby).exists():
            demo = podsumuj_demografie(demografia(data, args.osoby))
        else:
            print(f"UWAGA: brak pliku {args.osoby} -- pomijam analizę demograficzną "
                  "(artykuł odwołuje się do tabeli demografia i rys_demografia)")
    art = None
    if not args.bez_artykulu and not pairs.empty:
        art = materialy_artykulu(data, rejected, pairs, users, out / "artykul", args, demo)
    raport(data, rejected, bins, trends, pairs, users, out, args.minimum, art,
           f"Wykluczone pokoje: {', '.join(args.wyklucz_pokoje) or 'brak'} ({args.wykluczone_n} rekordów); "
           f"wykluczone pytania z jedną odpowiedzią: {args.wykluczone_pytania} ({args.wykluczone_pytania_n} rekordów)", demo)
    print(f"Pliki zapisano w: {out.resolve()}")


if __name__ == "__main__":
    main()
