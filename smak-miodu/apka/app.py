from pathlib import Path

from prepare_data import load_and_merge, save_to_excel
from analiza import run_full_analysis, render_latex
from plots import save_all

data = load_and_merge("badania-1.xlsx")
save_to_excel(data, "gotowe.xlsx")

df = run_full_analysis(data)

save_all(df, out_dir="..")
render_latex(df)
 
# if __name__ == "__main__":
#     df = load_and_prepare()
#     print(f"Shape: {df.shape}")
#     print(df.dtypes)
#     print(df.head())
#     save_to_excel(df, "gotowy.xlsx")

