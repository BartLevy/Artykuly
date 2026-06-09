import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import os

OUT_DIR = "figures_png"
os.makedirs(OUT_DIR, exist_ok=True)

def save_fig(fig, filename):
    path = os.path.join(OUT_DIR, filename)
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
                
# ----------------------------
# 1) Dane wejściowe (z tekstu)
# ----------------------------

# Flow próby
sample_flow = pd.DataFrame({
    "stage": ["Initial respondents", "Excluded (non-cochlear)", "Final analyzed"],
    "n": [116, 12, 104]
})

# Demografia: płeć
gender = pd.Series({
    "Women": 44.23,
    "Men": 34.62,
    "Not declared": 21.15
}, name="percent")

# Stan cywilny
marital = pd.Series({
    "Married": 42.31,
    "Single": 24.04,
    "Partnership": 11.54,
    "No answer": 22.12
}, name="percent")

# Gospodarstwo domowe
household = pd.Series({
    "With family": 57.69,
    "Alone": 20.19,
    "No answer": 22.12
}, name="percent")

# Wykształcenie
education = pd.Series({
    "Higher": 41.35,
    "Secondary": 31.73,
    "Primary": 3.85,
    "No data": 23.08
}, name="percent")

# Status zatrudnienia
employment = pd.Series({
    "Professionally active": 46.15,
    "Retired": 19.23,
    "Student": 2.88,
    "Unemployed": 8.65,
    "No answer": 23.08
}, name="percent")

# Wiek, onset HL, wiek implantacji (statystyki opisowe)
stats = pd.DataFrame({
    "variable": ["Age (years)", "Onset hearing loss (years)", "Age at 1st implantation (years)"],
    "min": [19, 0, 1],
    "max": [78, 62, 69],
    "mean": [44.2, 14.78, 32.8],
    "median": [41.2, 6.0, 32.5]
})

# Implantacja
implantation = pd.Series({
    "Unilateral total": 65.38,
    "Bilateral": 12.50,
    "No answer": 22.12
}, name="percent")

unilateral_side = pd.Series({
    "Left only": 20.19,
    "Right only": 45.19
}, name="percent")

# HHIA mean scores
hhia_means = pd.Series({
    "HHIA Total mean (%)": 52.15,
    "HHIA Social mean (%)": 52.98,
    "HHIA Emotional mean (%)": 51.38
}, name="value")

# HHIA distributions (stacked bars)
hhia_dist = pd.DataFrame({
    "No handicap": [6.73, 10.58],
    "Mild/Moderate": [18.27, 18.27],
    "Significant": [52.88, 48.08],
    # Uwaga: suma nie musi dawać 100% (brakujące = brak danych / inne / zaokrąglenia)
}, index=["Social", "Emotional"])

# Skale: mean i SD
scales = pd.DataFrame({
    "mean": [3.30, 2.90, 2.24, 3.07],
    "sd":   [0.47, 0.68, 0.91, 0.61]
}, index=["Empathy (E)", "Spirituality (F)", "Religious struggle (G)", "Well-being (H)"])

# Korelacje między skalami (z tekstu: część dokładna, część w zakresie)
# Uzupełniam macierz przybliżeniem wartości słabych jako np. 0.16 (środek zakresu 0.14–0.19)
# Jeśli wolisz, możesz zostawić NaN i nie kolorować.
r_EF = 0.16
r_EH = 0.16
r_FH = 0.16
r_GH = -0.39  # jedyna istotna
corr_scales = pd.DataFrame(
    [[1.0,   r_EF,  np.nan, r_EH],
     [r_EF,  1.0,   np.nan, r_FH],
     [np.nan,np.nan,1.0,    r_GH],
     [r_EH,  r_FH,  r_GH,   1.0]],
    index=["E", "F", "G", "H"],
    columns=["E", "F", "G", "H"]
)

# Dodatkowe korelacje punktowe z tekstu (przybliżone)
item_corrs = pd.Series({
    "E6 sadness recognition vs H": 0.22,
    "E1 helping as meaning vs H": 0.18,
    "E3 self-sacrifice vs H": -0.19,
    "F16 immortal dimension vs H": 0.22,
    "F4 interconnectedness vs H": 0.21,
    "F14 hope only human action vs H": -0.20,
    "G1 abandonment by God vs H": -0.38,  # zakres -0.34 do -0.42 -> środek
    "G2 divine punishment vs H": -0.38,   # jw.
    "G3 life no deeper meaning vs H": -0.55,
    "E7 relationship change after implant vs H": 0.11
}, name="r")


# ----------------------------
# 2) Helpery do wykresów
# ----------------------------

def bar_percent(series, title):
    s = series.sort_values(ascending=True)
    fig, ax = plt.subplots()
    ax.barh(s.index, s.values)
    ax.set_title(title)
    ax.set_xlabel("Percent")
    for i, v in enumerate(s.values):
        ax.text(v + 0.5, i, f"{v:.2f}%", va="center")
    plt.tight_layout()
    return fig

def stacked_bar(df, title):
    fig, ax = plt.subplots()
    bottom = np.zeros(len(df))
    for col in df.columns:
        ax.bar(df.index, df[col].values, bottom=bottom, label=col)
        bottom += df[col].values
    ax.set_title(title)
    ax.set_ylabel("Percent")
    ax.legend(loc="upper right", frameon=False)
    plt.tight_layout()
    return fig

def bar_with_error(df, title, ylim=(1,5)):
    fig, ax = plt.subplots()
    ax.bar(df.index, df["mean"].values, yerr=df["sd"].values, capsize=5)
    ax.set_title(title)
    ax.set_ylabel("Mean (± SD)")
    ax.set_ylim(*ylim)
    plt.xticks(rotation=20, ha="right")
    plt.tight_layout()
    return fig

def radar_plot(values_dict, title, rmin=0, rmax=100):
    labels = list(values_dict.keys())
    values = np.array(list(values_dict.values()), dtype=float)

    # zamknięcie wielokąta
    angles = np.linspace(0, 2*np.pi, len(labels), endpoint=False)
    values_closed = np.concatenate([values, [values[0]]])
    angles_closed = np.concatenate([angles, [angles[0]]])

    fig = plt.figure()
    ax = plt.subplot(111, polar=True)
    ax.plot(angles_closed, values_closed)
    ax.fill(angles_closed, values_closed, alpha=0.15)
    ax.set_title(title)
    ax.set_thetagrids(angles * 180/np.pi, labels)
    ax.set_ylim(rmin, rmax)
    plt.tight_layout()
    return fig

def heatmap_corr(corr, title):
    fig, ax = plt.subplots()
    data = corr.values.astype(float)
    im = ax.imshow(data, aspect="auto")

    ax.set_title(title)
    ax.set_xticks(range(corr.shape[1]))
    ax.set_yticks(range(corr.shape[0]))
    ax.set_xticklabels(corr.columns)
    ax.set_yticklabels(corr.index)

    # wartości w komórkach
    for i in range(corr.shape[0]):
        for j in range(corr.shape[1]):
            val = corr.iat[i, j]
            if np.isnan(val):
                text = "NA"
            else:
                text = f"{val:.2f}"
            ax.text(j, i, text, ha="center", va="center")

    fig.colorbar(im, ax=ax)
    plt.tight_layout()
    return fig


# ----------------------------
# 3) Wykresy
# ----------------------------

# 3.1 Flow próby
fig, ax = plt.subplots()
ax.bar(sample_flow["stage"], sample_flow["n"])
ax.set_title("Sample flow")
ax.set_ylabel("N")
plt.xticks(rotation=15, ha="right")
for i, v in enumerate(sample_flow["n"].values):
    ax.text(i, v + 1, str(v), ha="center")
plt.tight_layout()
save_fig(fig, "fig_01_sample_flow.png")

# 3.2 Demografia (percent)
save_fig(bar_percent(gender, "Gender distribution (%)"),
         "fig_02_gender.png")

save_fig(bar_percent(marital, "Marital status (%)"),
         "fig_03_marital_status.png")

save_fig(bar_percent(household, "Household composition (%)"),
         "fig_04_household.png")

save_fig(bar_percent(education, "Education (%)"),
         "fig_05_education.png")

save_fig(bar_percent(employment, "Employment status (%)"),
         "fig_06_employment.png")



# 3.3 Implantacja
save_fig(bar_percent(implantation, "Implantation type (%)"),
         "fig_07_implantation_type.png")

save_fig(bar_percent(unilateral_side, "Unilateral implantation side (%)"),
         "fig_08_implantation_side.png")

# 3.4 HHIA: średnie + rozkład
fig, ax = plt.subplots()
ax.bar(hhia_means.index, hhia_means.values)
ax.set_title("HHIA mean scores (%)")
ax.set_ylabel("Percent")
plt.xticks(rotation=20, ha="right")
for i, v in enumerate(hhia_means.values):
    ax.text(i, v + 0.6, f"{v:.2f}", ha="center")
plt.tight_layout()
save_fig(fig, "fig_09_hhia_means.png")

save_fig(stacked_bar(hhia_dist,
         "HHIA handicap distribution (%)"),
         "fig_10_hhia_distribution.png")


#stacked_bar(hhia_dist, "HHIA handicap distribution (%) (note: may not sum to 100%)")

# 3.5 Skale: mean ± SD
# bar_with_error(scales, "Scale means ± SD (1–5)", ylim=(1,5))
save_fig(bar_with_error(scales,
         "Scale means ± SD (1–5)", ylim=(1,5)),
         "fig_11_scales_mean_sd.png")


# 3.6 Radar (np. HHIA domeny + total)
# radar_plot({
#     "Total": 52.15,
#     "Social": 52.98,
#     "Emotional": 51.38
# }, "HHIA (radar) (%)", rmin=0, rmax=100)

save_fig(
    radar_plot(
        {"Total": 52.15, "Social": 52.98, "Emotional": 51.38},
        "HHIA profile (radar)", rmin=0, rmax=100
    ),
    "fig_12_hhia_radar.png"
)

# 3.7 Heatmapa korelacji skal
# heatmap_corr(corr_scales, "Correlation heatmap (scales)")
save_fig(
    heatmap_corr(corr_scales, "Correlation heatmap (scales)"),
    "fig_13_corr_scales_heatmap.png"
)

# 3.8 Korelacje itemów vs well-being (bar)
fig, ax = plt.subplots()
s = item_corrs.sort_values()
ax.barh(s.index, s.values)
ax.set_title("Selected item correlations with Well-being (H)")
ax.set_xlabel("r")
ax.axvline(0, linewidth=1)
for i, v in enumerate(s.values):
    ax.text(v + (0.01 if v >= 0 else -0.01), i, f"{v:.2f}", va="center",
            ha="left" if v >= 0 else "right")
plt.tight_layout()
save_fig(fig, "fig_14_item_correlations.png")

# plt.show()
