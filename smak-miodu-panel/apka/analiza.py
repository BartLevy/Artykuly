"""
Analiza ślepego panelu konsumenckiego — charakterystyka panelu, statystyki
opisowe i wypełnienie szablonu LaTeX (template.latex -> ../out.tex).

Porównanie panelu z laboratoriami: porownanie_lab.py.
"""
from __future__ import annotations

import re
from dataclasses import asdict
from pathlib import Path
from typing import Any, List

import numpy as np
import pandas as pd
from scipy import stats

_SCALES = ["overall_rate", "sweetness", "acidity", "intensity", "is_typical"]


def to_dataframe(data: List[Any]) -> pd.DataFrame:
    """Lista DataModel -> DataFrame z kolumnami liczbowymi (braki = NaN)."""
    df = pd.DataFrame([asdict(d) for d in data])
    for c in ["age", "how_often"] + _SCALES:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def auc(score: np.ndarray, target: np.ndarray) -> float:
    """AUC z testu Manna-Whitneya."""
    pos, neg = score[target == 1], score[target == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    u, _ = stats.mannwhitneyu(pos, neg, alternative="two-sided")
    return u / (len(pos) * len(neg))


# --------------------------------------------------------------------------- #
#  Wartości do szablonu
# --------------------------------------------------------------------------- #

_MONTHS = {1: "styczniu", 2: "lutym", 3: "marcu", 4: "kwietniu", 5: "maju",
           6: "czerwcu", 7: "lipcu", 8: "sierpniu", 9: "wrześniu",
           10: "październiku", 11: "listopadzie", 12: "grudniu"}


def _compute_general(df: pd.DataFrame) -> dict:
    resp = df.groupby("id").first()
    n, n_resp = len(df), len(resp)
    period = pd.to_datetime(resp["date"], errors="coerce").dt.to_period("M")
    by_month = period.value_counts().sort_index()
    main = by_month[by_month >= 0.05 * n_resp].index   # miesiące z ≥5% respondentów
    in_main = period.isin(set(main))
    return {
        "n_ocen": n,
        "n_respondentow": n_resp,
        "n_lotow": df["lot"].nunique(),
        "panel_months": " i~".join(_MONTHS[p.month] for p in main) + f" {main[-1].year}",
        "n_date_main": int(in_main.sum()),
        "n_date_other": int((period.notna() & ~in_main).sum()),
        "n_date_missing": int(period.isna().sum()),
        "n_missing_typical": int(df["is_typical"].isna().sum()),
        "n_missing_overall": int(df["overall_rate"].isna().sum()),
        "n_missing_sweet": int(df["sweetness"].isna().sum()),
        "n_missing_acid": int(df["acidity"].isna().sum()),
        "n_missing_intens": int(df["intensity"].isna().sum()),
        "n_comments": int(df["comment"].notna().sum()),
    }


def _compute_basic(df: pd.DataFrame) -> dict:
    short = {"overall_rate": "overall", "sweetness": "sweetness",
             "acidity": "acidity", "intensity": "intensity", "is_typical": "typical"}
    r = {}
    for col, name in short.items():
        r[f"mean_{name}"] = round(float(df[col].mean()), 3)
        r[f"std_{name}"] = round(float(df[col].std()), 3)
    return r


def _compute_demographics(df: pd.DataFrame) -> dict:
    resp = df.groupby("id").first()
    n = len(resp)
    r: dict = {}

    def add(prefix: str, series: pd.Series, mapping: dict) -> None:
        counts = series.value_counts()
        for k, slug in mapping.items():
            cnt = int(counts.get(k, 0))
            r[f"{prefix}_{slug}_n"] = cnt
            r[f"{prefix}_{slug}_pct"] = round(cnt / n * 100, 1)
        r[f"{prefix}_na_n"] = int(series.isna().sum())

    add("age", resp["age"], {1: "lt25", 2: "25_45", 3: "46_65", 4: "gt65"})
    add("gender", resp["gender"], {"k": "k", "m": "m"})
    add("freq", resp["how_often"], {1: "daily", 2: "monthly", 3: "occasional"})
    return r


def compute_results(df: pd.DataFrame) -> dict:
    r: dict = {}
    r.update(_compute_general(df))
    r.update(_compute_basic(df))
    r.update(_compute_demographics(df))
    return r


def print_summary(df: pd.DataFrame) -> None:
    v = compute_results(df)
    print(f"Respondenci: {v['n_respondentow']} | oceny: {v['n_ocen']} | próbki: {v['n_lotow']}")
    print(f"Termin panelu: {v['panel_months']} "
          f"(inne daty: {v['n_date_other']}, brak daty: {v['n_date_missing']})")
    print("Braki odpowiedzi:", {k: v[k] for k in v if k.startswith("n_missing")})
    print(df.groupby("lot")[_SCALES].mean().round(3))


# --------------------------------------------------------------------------- #
#  Renderowanie LaTeX
# --------------------------------------------------------------------------- #

def _pl_number(key: str, val) -> str:
    """Polski zapis liczb (przecinek dziesiętny); p-wartości z relacją ('= …' / '< …')."""
    is_p = key.startswith("p_") or key.endswith("_p")
    if is_p and isinstance(val, float) and val < 0.001:
        val = "<0.001"
    if isinstance(val, float):
        val = f"{val:g}"
    val = re.sub(r"(\d)\.(\d)", r"\1{,}\2", str(val))
    if is_p:
        val = val.replace("<", "< ") if val.startswith("<") else "= " + val
    return val


def render_latex(
    df: pd.DataFrame,
    template_path: str | Path = "template.latex",
    output_path: str | Path = "../out.tex",
) -> None:
    """Wypełnia placeholdery <<var>> w szablonie LaTeX i zapisuje wynik."""
    from porownanie_lab import compute_lab_comparison

    values = {k: _pl_number(k, v) for k, v in compute_results(df).items()}
    values.update(compute_lab_comparison(df))

    text = Path(template_path).read_text(encoding="utf-8")
    for key, val in values.items():
        text = text.replace(f"<<{key}>>", str(val))
    missing = sorted(set(re.findall(r"<<(\w+)>>", text)))
    if missing:
        raise KeyError(f"Niewypełnione placeholdery: {missing}")
    Path(output_path).write_text(text, encoding="utf-8")
    print(f"Zapisano {output_path}")
