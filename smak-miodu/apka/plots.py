"""Wykresy do artykułu o analizie sensorycznej miodu."""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
from pathlib import Path

AUTH_CLR = "#2874A6"
NOAUTH_CLR = "#CA6F1E"

LOT_ORDER = [
    "1-250906", "2-25c062101", "3-4/02/2020",
    "4-cq23120101-2", "5-cq25111501-1", "6-02/09", "7-4/21/05",
]
LOT_LABELS = {
    "1-250906":        "Lot 1\n(robinia, auth.)",
    "2-25c062101":     "Lot 2\n(robinia, nieauth.)",
    "3-4/02/2020":     "Lot 3\n(wielokwiat., auth.)",
    "4-cq23120101-2":  "Lot 4\n(wielokwiat., auth.)",
    "5-cq25111501-1":  "Lot 5\n(lipowy, auth.)",
    "6-02/09":         "Lot 6\n(wielokwiat., nieauth.)",
    "7-4/21/05":       "Lot 7\n(wielokwiat., nieauth.)",
}


def _style():
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": False,
        "figure.dpi": 150,
    })


def _save(fig, out_dir: str, stem: str) -> None:
    p = Path(out_dir)
    p.mkdir(parents=True, exist_ok=True)
    fig.savefig(p / f"{stem}.pdf", bbox_inches="tight")
    fig.savefig(p / f"{stem}.png", bbox_inches="tight", dpi=150)
    plt.close(fig)
    print(f"  Zapisano {stem}.pdf / .png")


def save_demographics(df: pd.DataFrame, out_dir: str = ".") -> None:
    """Fig 1: Trzy panele — grupy wiekowe, płeć, częstość spożycia."""
    _style()
    resp = df.groupby("id").first().reset_index()
    n = len(resp)

    age_vals  = {1: "<25 lat", 2: "25–45 lat", 3: "46–65 lat", 4: ">65 lat"}
    freq_vals = {1: "Codziennie", 2: "Raz\nw miesiącu", 3: "Okazyjnie"}

    fig, axes = plt.subplots(1, 3, figsize=(13, 4.5))
    fig.suptitle(f"Charakterystyka respondentów (n = {n})", fontsize=12, fontweight="bold", y=1.02)

    # — grupy wiekowe —
    ax = axes[0]
    age_c = resp["age"].value_counts().sort_index()
    xs = [age_vals.get(int(k), str(k)) for k in age_c.index]
    ys = (age_c.values / n * 100)
    bars = ax.bar(xs, ys, color="#5B9BD5", edgecolor="white", width=0.6)
    for bar, cnt in zip(bars, age_c.values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.2,
                str(cnt), ha="center", va="bottom", fontsize=9)
    ax.set_ylabel("Odsetek (%)")
    ax.set_title("Grupy wiekowe")
    ax.set_ylim(0, max(ys) * 1.3)

    # — płeć —
    ax = axes[1]
    gen_c = resp["gender"].value_counts(dropna=True)
    gen_labels = [str(g) for g in gen_c.index]
    gen_pcts = gen_c.values / n * 100
    clrs = ["#E8A0BF", "#5B9BD5", "#A9CCE3"]
    bars = ax.bar(gen_labels, gen_pcts, color=clrs[:len(gen_c)], edgecolor="white", width=0.5)
    for bar, cnt in zip(bars, gen_c.values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.2,
                str(cnt), ha="center", va="bottom", fontsize=9)
    ax.set_ylabel("Odsetek (%)")
    ax.set_title("Płeć")
    ax.set_ylim(0, max(gen_pcts) * 1.3)

    # — częstość spożycia —
    ax = axes[2]
    freq_c = resp["how_often"].value_counts().sort_index()
    xs = [freq_vals.get(int(k), str(k)) for k in freq_c.index]
    ys = freq_c.values / n * 100
    bars = ax.bar(xs, ys, color="#70AD47", edgecolor="white", width=0.6)
    for bar, cnt in zip(bars, freq_c.values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.2,
                str(cnt), ha="center", va="bottom", fontsize=9)
    ax.set_ylabel("Odsetek (%)")
    ax.set_title("Częstotliwość spożycia miodu")
    ax.set_ylim(0, max(ys) * 1.3)

    fig.tight_layout()
    _save(fig, out_dir, "fig_demographics")


def save_lots_chart(df: pd.DataFrame, out_dir: str = ".") -> None:
    """Fig 2: Akceptacja smakowa i ogólna ocena per lot — słupki poziome."""
    _style()
    lot = df.groupby("lot").agg(
        auth=("authorized", "first"),
        taste_ok=("is_taste_ok", "mean"),
        overall=("overall_rate", "mean"),
    )
    order = [l for l in LOT_ORDER if l in lot.index]
    lot = lot.loc[order]
    labels = [LOT_LABELS[l] for l in lot.index]
    colors = [AUTH_CLR if lot.loc[l, "auth"] == 1 else NOAUTH_CLR for l in lot.index]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    bars1 = ax1.barh(labels, lot["taste_ok"] * 100, color=colors, edgecolor="white", height=0.6)
    ax1.axvline(50, color="gray", linewidth=0.8, linestyle="--", alpha=0.6)
    for bar, val in zip(bars1, lot["taste_ok"]):
        ax1.text(val * 100 + 1.2, bar.get_y() + bar.get_height() / 2,
                 f"{val:.1%}", va="center", fontsize=8.5)
    ax1.set_xlabel("Odsetek ocen z akceptowalnym smakiem (%)")
    ax1.set_title("Akceptacja smakowa")
    ax1.set_xlim(0, 110)

    bars2 = ax2.barh(labels, lot["overall"], color=colors, edgecolor="white", height=0.6)
    ax2.axvline(3.0, color="gray", linewidth=0.8, linestyle="--", alpha=0.6)
    for bar, val in zip(bars2, lot["overall"]):
        ax2.text(val + 0.07, bar.get_y() + bar.get_height() / 2,
                 f"{val:.2f}", va="center", fontsize=8.5)
    ax2.set_xlabel("Średnia ogólna ocena (1 – 5)")
    ax2.set_title("Ogólna akceptacja")
    ax2.set_xlim(0, 5.8)

    leg = [mpatches.Patch(facecolor=AUTH_CLR, label="Autoryzowane"),
           mpatches.Patch(facecolor=NOAUTH_CLR, label="Nieautoryzowane")]
    ax1.legend(handles=leg, loc="lower right", fontsize=9)

    fig.tight_layout()
    _save(fig, out_dir, "fig_lots")


def save_sensory_distribution(df: pd.DataFrame, out_dir: str = ".") -> None:
    """Fig 3: Rozkład ocen ordinalnych (1/2/3) per atrybut i grupę."""
    _style()
    attrs = [
        ("sweetness",  "Słodycz"),
        ("acidity",    "Kwasowość"),
        ("intensity",  "Intensywność"),
    ]
    level_clrs = ["#F4B942", "#70AD47", "#E05C5C"]
    level_labels = ["za słaba / słaby (1)", "w sam raz (2)", "za silna / silny (3)"]

    fig, axes = plt.subplots(1, 3, figsize=(14, 5))
    fig.suptitle(
        "Rozkład intensywności cech sensorycznych według grupy autoryzacji",
        fontsize=11, fontweight="bold", y=1.02,
    )

    for ax, (attr, title) in zip(axes, attrs):
        pcts = []
        for auth_val in [1, 0]:
            sub = df[df["authorized"] == auth_val][attr].dropna()
            n = len(sub)
            pcts.append([(sub == v).sum() / n * 100 for v in [1, 2, 3]])

        x = np.arange(2)
        bottoms = np.zeros(2)
        for i, (lbl, clr) in enumerate(zip(level_labels, level_clrs)):
            vals = np.array([pcts[g][i] for g in range(2)])
            ax.bar(x, vals, bottom=bottoms, color=clr, label=lbl,
                   edgecolor="white", width=0.55)
            for j in range(2):
                if vals[j] > 7:
                    ax.text(x[j], bottoms[j] + vals[j] / 2,
                            f"{vals[j]:.0f}%", ha="center", va="center",
                            fontsize=8.5, color="white", fontweight="bold")
            bottoms += vals

        ax.set_xticks(x)
        ax.set_xticklabels(["Autoryzowane", "Nieautoryz."], fontsize=9)
        ax.set_ylabel("Odsetek ocen (%)")
        ax.set_title(title)
        ax.set_ylim(0, 115)
        if attr == "intensity":
            ax.legend(loc="upper right", fontsize=8)

    fig.tight_layout()
    _save(fig, out_dir, "fig_sensory")


def save_overall_boxplot(df: pd.DataFrame, out_dir: str = ".") -> None:
    """Fig 4: Box ploty ogólnej akceptacji dla każdego lotu."""
    _style()
    order = [l for l in LOT_ORDER if l in df["lot"].unique()]
    data_by_lot = [df[df["lot"] == l]["overall_rate"].dropna().values for l in order]
    labels = [LOT_LABELS[l] for l in order]
    colors = [AUTH_CLR if df[df["lot"] == l]["authorized"].iloc[0] == 1 else NOAUTH_CLR for l in order]

    fig, ax = plt.subplots(figsize=(13, 5))
    bp = ax.boxplot(
        data_by_lot, patch_artist=True,
        medianprops={"color": "black", "linewidth": 2},
        flierprops={"marker": "o", "markersize": 3.5, "alpha": 0.45},
        whiskerprops={"linewidth": 1.2},
        capprops={"linewidth": 1.2},
    )
    for patch, clr in zip(bp["boxes"], colors):
        patch.set_facecolor(clr)
        patch.set_alpha(0.72)

    ax.set_xticks(range(1, len(labels) + 1))
    ax.set_xticklabels(labels, fontsize=8.5)
    ax.set_ylabel("Ogólna akceptacja (1 – 5)")
    ax.set_title("Rozkład ogólnej akceptacji sensorycznej według próbki")
    ax.set_ylim(0.3, 5.7)
    ax.axhline(3, color="gray", linewidth=0.8, linestyle="--", alpha=0.6)

    leg = [mpatches.Patch(facecolor=AUTH_CLR, alpha=0.72, label="Autoryzowane"),
           mpatches.Patch(facecolor=NOAUTH_CLR, alpha=0.72, label="Nieautoryzowane")]
    ax.legend(handles=leg, fontsize=9)

    fig.tight_layout()
    _save(fig, out_dir, "fig_overall_boxplot")


def save_paired_scatter(df: pd.DataFrame, out_dir: str = ".") -> None:
    """Fig 5: Scatter sparowanych ocen per respondent (auth vs nieauth)."""
    _style()
    g = (
        df.groupby(["id", "authorized"])["is_taste_ok"].mean()
        .unstack().dropna()
    )
    g.columns = ["nieauth", "auth"]

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(g["nieauth"], g["auth"], alpha=0.45, color=AUTH_CLR, s=40, edgecolors="none")

    mn = g["nieauth"].mean()
    ma = g["auth"].mean()
    ax.axvline(mn, color=NOAUTH_CLR, linewidth=1.6, linestyle=":", label=f"śr. nieauth = {mn:.3f}")
    ax.axhline(ma, color=AUTH_CLR, linewidth=1.6, linestyle=":", label=f"śr. auth = {ma:.3f}")
    ax.plot([0, 1], [0, 1], "k--", linewidth=0.8, alpha=0.4)

    ax.set_xlabel("Śr. akceptacja smakowa — miody nieautoryzowane")
    ax.set_ylabel("Śr. akceptacja smakowa — miody autoryzowane")
    ax.set_title("Sparowane oceny per respondent: auth vs nieauth\n(każdy punkt = jeden respondent)")
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, 1.05)
    ax.legend(fontsize=9)

    fig.tight_layout()
    _save(fig, out_dir, "fig_paired")


def save_age_analysis(df: pd.DataFrame, out_dir: str = ".") -> None:
    """Fig 6: Akceptacja smakowa i ogólna ocena wg grupy wiekowej."""
    _style()
    resp_mean = df.groupby(["id", "age"]).agg(
        taste_ok=("is_taste_ok", "mean"),
        overall=("overall_rate", "mean"),
    ).reset_index()

    age_vals = {1: "<25 lat", 2: "25–45 lat", 3: "46–65 lat", 4: ">65 lat"}
    age_clrs = ["#5B9BD5", "#70AD47", "#E8A0BF", "#F4B942"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("Oceny sensoryczne według grupy wiekowej respondentów",
                 fontsize=11, fontweight="bold", y=1.02)

    # akceptacja smakowa per wiek
    age_groups = sorted(resp_mean["age"].dropna().unique())
    labels = [age_vals.get(int(a), str(a)) for a in age_groups]
    clrs = [age_clrs[i % len(age_clrs)] for i in range(len(age_groups))]

    means_taste = [resp_mean[resp_mean["age"] == a]["taste_ok"].mean() * 100
                   for a in age_groups]
    bars = ax1.bar(labels, means_taste, color=clrs, edgecolor="white", width=0.6)
    for bar, val in zip(bars, means_taste):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.5,
                 f"{val:.1f}%", ha="center", va="bottom", fontsize=9)
    ax1.set_ylabel("Odsetek akceptacji smaku (%)")
    ax1.set_title("Akceptacja smakowa (is_taste_ok)")
    ax1.set_ylim(0, 115)

    # ogólna ocena per wiek — box plot
    data_by_age = [resp_mean[resp_mean["age"] == a]["overall"].dropna().values
                   for a in age_groups]
    bp = ax2.boxplot(data_by_age, patch_artist=True,
                     medianprops={"color": "black", "linewidth": 2},
                     flierprops={"marker": "o", "markersize": 3.5, "alpha": 0.5})
    for patch, clr in zip(bp["boxes"], clrs):
        patch.set_facecolor(clr)
        patch.set_alpha(0.75)
    ax2.set_xticklabels(labels, fontsize=9)
    ax2.set_ylabel("Ogólna ocena (1 – 5)")
    ax2.set_title("Ogólna ocena wg grupy wiekowej")
    ax2.axhline(3, color="gray", linewidth=0.8, linestyle="--", alpha=0.6)
    ax2.set_ylim(0.3, 5.7)

    fig.tight_layout()
    _save(fig, out_dir, "fig_age_analysis")


def save_freq_analysis(df: pd.DataFrame, out_dir: str = ".") -> None:
    """Fig 7: Akceptacja i ogólna ocena wg częstotliwości spożycia miodu."""
    _style()
    freq_vals = {1: "Codziennie", 2: "Raz\nw miesiącu", 3: "Okazyjnie"}
    freq_clrs = ["#2874A6", "#70AD47", "#CA6F1E"]

    resp_mean = df.groupby(["id", "how_often"]).agg(
        taste_ok=("is_taste_ok", "mean"),
        overall=("overall_rate", "mean"),
    ).reset_index()

    freq_groups = sorted(resp_mean["how_often"].dropna().unique())
    labels = [freq_vals.get(int(f), str(f)) for f in freq_groups]
    clrs = [freq_clrs[i % len(freq_clrs)] for i in range(len(freq_groups))]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5))
    fig.suptitle("Oceny sensoryczne według częstotliwości spożycia miodu",
                 fontsize=11, fontweight="bold", y=1.02)

    means_taste = [resp_mean[resp_mean["how_often"] == f]["taste_ok"].mean() * 100
                   for f in freq_groups]
    bars = ax1.bar(labels, means_taste, color=clrs, edgecolor="white", width=0.5)
    for bar, val in zip(bars, means_taste):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.5,
                 f"{val:.1f}%", ha="center", va="bottom", fontsize=9)
    ax1.set_ylabel("Odsetek akceptacji smaku (%)")
    ax1.set_title("Akceptacja smakowa (is_taste_ok)")
    ax1.set_ylim(0, 115)

    data_by_freq = [resp_mean[resp_mean["how_often"] == f]["overall"].dropna().values
                    for f in freq_groups]
    bp = ax2.boxplot(data_by_freq, patch_artist=True,
                     medianprops={"color": "black", "linewidth": 2},
                     flierprops={"marker": "o", "markersize": 3.5, "alpha": 0.5})
    for patch, clr in zip(bp["boxes"], clrs):
        patch.set_facecolor(clr)
        patch.set_alpha(0.75)
    ax2.set_xticklabels(labels, fontsize=9)
    ax2.set_ylabel("Ogólna ocena (1 – 5)")
    ax2.set_title("Ogólna ocena wg częstotliwości spożycia")
    ax2.axhline(3, color="gray", linewidth=0.8, linestyle="--", alpha=0.6)
    ax2.set_ylim(0.3, 5.7)

    fig.tight_layout()
    _save(fig, out_dir, "fig_freq_analysis")


def save_age_sensory(df: pd.DataFrame, out_dir: str = ".") -> None:
    """Fig 8: Rozkład intensywności cech sensorycznych (1/2/3) per grupa wiekowa."""
    _style()
    attrs = [
        ("sweetness",  "Słodycz"),
        ("acidity",    "Kwasowość"),
        ("intensity",  "Intensywność"),
    ]
    age_vals = {1: "<25", 2: "25–45", 3: "46–65", 4: ">65"}
    level_clrs = ["#F4B942", "#70AD47", "#E05C5C"]
    level_labels = ["za słaba (1)", "w sam raz (2)", "za silna (3)"]

    age_groups = sorted(df["age"].dropna().unique())
    x = np.arange(len(age_groups))
    xlabels = [age_vals.get(int(a), str(a)) for a in age_groups]

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle("Rozkład ocen sensorycznych według grupy wiekowej",
                 fontsize=11, fontweight="bold", y=1.02)

    for ax, (attr, title) in zip(axes, attrs):
        pcts = []
        for a in age_groups:
            sub = df[df["age"] == a][attr].dropna()
            n = len(sub)
            pcts.append([(sub == v).sum() / n * 100 for v in [1, 2, 3]])

        bottoms = np.zeros(len(age_groups))
        for i, (lbl, clr) in enumerate(zip(level_labels, level_clrs)):
            vals = np.array([pcts[g][i] for g in range(len(age_groups))])
            ax.bar(x, vals, bottom=bottoms, color=clr, label=lbl,
                   edgecolor="white", width=0.6)
            for j in range(len(age_groups)):
                if vals[j] > 8:
                    ax.text(x[j], bottoms[j] + vals[j] / 2,
                            f"{vals[j]:.0f}%", ha="center", va="center",
                            fontsize=8.5, color="white", fontweight="bold")
            bottoms += vals

        ax.set_xticks(x)
        ax.set_xticklabels(xlabels, fontsize=9)
        ax.set_ylabel("Odsetek ocen (%)")
        ax.set_title(title)
        ax.set_ylim(0, 120)
        if attr == "intensity":
            ax.legend(loc="upper right", fontsize=8)

    fig.tight_layout()
    _save(fig, out_dir, "fig_age_sensory")


def save_age_auth_interaction(df: pd.DataFrame, out_dir: str = ".") -> None:
    """Fig 9: Interakcja: akceptacja smaku (auth vs nieauth) × wiek respondenta."""
    _style()
    age_vals = {1: "<25 lat", 2: "25–45 lat", 3: "46–65 lat", 4: ">65 lat"}
    age_groups = sorted(df["age"].dropna().unique())
    labels = [age_vals.get(int(a), str(a)) for a in age_groups]

    auth_means, nonauth_means = [], []
    for a in age_groups:
        sub = df[df["age"] == a]
        auth_means.append(sub[sub["authorized"] == 1]["is_taste_ok"].mean() * 100)
        nonauth_means.append(sub[sub["authorized"] == 0]["is_taste_ok"].mean() * 100)

    x = np.arange(len(age_groups))
    w = 0.35

    fig, ax = plt.subplots(figsize=(9, 5))
    bars1 = ax.bar(x - w / 2, auth_means, width=w, color=AUTH_CLR,
                   edgecolor="white", label="Autoryzowane")
    bars2 = ax.bar(x + w / 2, nonauth_means, width=w, color=NOAUTH_CLR,
                   edgecolor="white", label="Nieautoryzowane")

    for bar, val in zip(bars1, auth_means):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.5,
                f"{val:.1f}%", ha="center", va="bottom", fontsize=8.5)
    for bar, val in zip(bars2, nonauth_means):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.5,
                f"{val:.1f}%", ha="center", va="bottom", fontsize=8.5)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("Odsetek akceptacji smaku (%)")
    ax.set_title("Akceptacja smaku miodów autoryzowanych vs nieautoryzowanych\nwedług grupy wiekowej respondentów")
    ax.set_ylim(0, 120)
    ax.legend(fontsize=9)

    fig.tight_layout()
    _save(fig, out_dir, "fig_age_auth_interaction")


def save_all(df: pd.DataFrame, out_dir: str = ".") -> None:
    print("Generowanie wykresów...")
    save_demographics(df, out_dir)
    save_lots_chart(df, out_dir)
    save_sensory_distribution(df, out_dir)
    save_overall_boxplot(df, out_dir)
    save_paired_scatter(df, out_dir)
    save_age_analysis(df, out_dir)
    save_freq_analysis(df, out_dir)
    save_age_sensory(df, out_dir)
    save_age_auth_interaction(df, out_dir)
    print("Wszystkie wykresy zapisane.")
