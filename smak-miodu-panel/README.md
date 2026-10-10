# Typowość smaku miodu: ślepy panel a ocena laboratoriów

Artykuł (szablon MDPI, czasopismo *Foods*) porównuje dwa źródła danych o tych samych
siedmiu partiach miodu (P1–P7):

1. **Ślepy panel konsumencki**: `apka/badania-2.xlsx` (arkusze `Badania` i `Wyniki`).
2. **Ocena organoleptyczna czterech laboratoriów** (sierpień 2026):
   `wyniki/Analiza_porownawcza_ODER_23_2026.xlsx` (arkusz `Macierz pełna`).

Artykuł nie korzysta z innych danych.

## Szybki start

```bash
cd apka
python3 app.py            # przelicza analizy, generuje out.tex i wykresy
cd ..
latexmk -pdf main.tex     # buduje main.pdf
```

Po każdej zmianie danych w którymkolwiek arkuszu uruchom oba kroki ponownie.

## Wymagania

- Python ≥ 3.10 z pakietami: `pandas`, `numpy`, `scipy`, `openpyxl`, `matplotlib`
  (testowane na Python 3.14, pandas 2.3, numpy 2.3, scipy 1.16, openpyxl 3.1, matplotlib 3.10).
- TeX Live z `latexmk`, `pdflatex` i `bibtex`.

## Co robi `python3 app.py`

| Krok | Plik | Wynik |
|---|---|---|
| Wczytanie panelu | `prepare_data.py` | lista ocen (`DataModel`); braki odpowiedzi zostają brakami |
| Kopia danych | `prepare_data.save_to_excel` | `apka/gotowe.xlsx` (dane po wczytaniu, do kontroli) |
| Charakterystyka panelu | `analiza.py` | liczebności, daty, demografia, braki, statystyki opisowe |
| Panel vs laboratoria | `porownanie_lab.py` | kodowanie opisów laboratoriów, testy, tabele, wykresy |
| Wypełnienie szablonu | `analiza.render_latex` | `out.tex` z `apka/template.latex` |

Wygenerowane pliki (w katalogu głównym): `out.tex`, `fig_panel_lab.pdf/.png`,
`fig_contrast_lab.pdf/.png`.

Samo porównanie z laboratoriami (wydruk wszystkich wartości) uruchomisz poleceniem
`cd apka && python3 porownanie_lab.py`.

## Struktura artykułu

| Plik | Zawartość | Edycja |
|---|---|---|
| `main.tex` | preambuła MDPI, tytuł, autorzy, streszczenie, skróty, załącznik, bibliografia | ręcznie |
| `section-wstep.tex` | 1. Wprowadzenie | ręcznie |
| `section-metody.tex` | 2. Materiał i metody (wczytuje `out.tex`) | ręcznie |
| `out.tex` | 2.4 Analiza statystyczna + 3. Wyniki | **generowany, nie edytować**; zmiany wprowadzaj w `apka/template.latex` |
| `section-dyskusja.tex` | 4. Dyskusja, 5. Wnioski | ręcznie |
| `appendix-opisy.tex` | Załącznik A: dosłowne opisy laboratoriów | ręcznie (zgodny z arkuszem) |
| `bibliografia.bib` | bibliografia (BibTeX) | ręcznie |

W `apka/template.latex` placeholdery `<<nazwa>>` są zastępowane wartościami z
`analiza.compute_results` i `porownanie_lab.compute_lab_comparison`. Jeśli w szablonie
zostanie placeholder bez wartości, `render_latex` zgłasza błąd.

## Zasady analizy

- **Mapowanie próbek** (`porownanie_lab.py`): kody partii w panelu i w arkuszu
  laboratoryjnym są przypisane do symboli P1–P7:

  | Próbka | Kod w panelu | Kod w arkuszu laboratoryjnym |
  |---|---|---|
  | P1 | `1-250906` | `250906` |
  | P2 | `2-25c062101` | `25C062101` |
  | P3 | `3-4/02/2020` | `4/02/2029` |
  | P4 | `4-cq23120101-2` | `CQ23120101-2` |
  | P5 | `5-cq25111501-1` | `CQ25111501-1` |
  | P6 | `6-02/09` | `02/09` |
  | P7 | `7-4/21/05` | `21/05` |

- **Numeracja laboratoriów** w artykule: 1 – QSI, 2 – Eurofins, 3 – Intertek, 4 – Puławy.
- **Kodowanie opisów laboratoriów** (regułowe, z kolumn *Zapach* i *Smak*):
  „nietypowy” → N, „lekko/słabo typowy” → L, „typowy” → T. Wynik laboratorium to
  niższa z ocen zapachu i smaku, a N oznacza zastrzeżenie. Laboratorium 4 (Puławy) nie stosuje
  kwalifikatora typowości, więc jest opisane osobno i nie wchodzi do κ Fleissa.
- **Braki odpowiedzi w panelu** nie są uzupełniane. Statystyki liczone są na dostępnych
  odpowiedziach, a testy dla pomiarów powtarzanych (Cochran Q, Friedman, Wilcoxon) tylko na
  respondentach z kompletem odpowiedzi. Brak płci, wieku lub częstotliwości jest
  raportowany jako „brak danych”.
- **Termin panelu** jest wyliczany z dat w arkuszu `Badania`: miesiące, w których badanie
  odbyło co najmniej 5% respondentów.

## O czym pamiętać

- Część liczb jest wpisana ręcznie w **`main.tex` (streszczenie)** i w
  **`section-dyskusja.tex`** (np. ρ, κ, p, AUC, odsetki błędów). Po zmianie danych porównaj
  je z `out.tex` albo z wydrukiem `python3 porownanie_lab.py`.
- `apka/badania-1.xlsx` to starsza wersja danych panelu i nie jest używana.
- Jeśli `main.pdf` jest uszkodzony albo `latexmk` zgłasza błąd bez komunikatu, zwykle
  kompilacja nałożyła się na automatyczne budowanie w edytorze (LaTeX Workshop).
  Pomaga czysta kompilacja: `latexmk -C main && latexmk -pdf main.tex`.
- `template.tex` i `template.pdf` w katalogu głównym to oryginalny szablon MDPI do wglądu;
  artykuł ich nie używa.
