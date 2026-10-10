"""Pełne przeliczenie analiz do artykułu.

Uruchomienie (z katalogu apka/):  python3 app.py
Wynik: ../out.tex, ../fig_panel_lab.pdf, ../fig_contrast_lab.pdf, gotowe.xlsx
"""
from prepare_data import load_and_merge, save_to_excel
from analiza import to_dataframe, print_summary, render_latex

data = load_and_merge("badania-2.xlsx")
save_to_excel(data, "gotowe.xlsx")

df = to_dataframe(data)
print_summary(df)
render_latex(df)
