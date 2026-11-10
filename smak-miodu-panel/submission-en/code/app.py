"""Full recomputation of the analyses for the English manuscript.

Run (from the code/ directory):  python3 app.py
Output: ../out.tex, ../fig_panel_lab.pdf/.png, ../fig_contrast_lab.pdf/.png,
        loaded_data.xlsx (panel data after loading, for checking)
"""
from pathlib import Path

from prepare_data import load_and_merge, save_to_excel
from analysis import to_dataframe, print_summary, render_latex

DATA = Path(__file__).resolve().parent.parent / "data" / "badania-2.xlsx"

data = load_and_merge(DATA)
save_to_excel(data, "loaded_data.xlsx")

df = to_dataframe(data)
print_summary(df)
render_latex(df)
