# MDPI *Foods* submission (English version)

English translation of the manuscript in the parent folder, prepared for submission to
*Foods* (MDPI, `foods` class, article type "Article").

## Build

```bash
./make_submission.sh --rerun   # regenerate out.tex + figures from data/, compile, pack upload/
./make_submission.sh           # compile and pack only
```

## What to upload (folder `upload/`)

| File | Upload as |
|---|---|
| `manuscript.pdf` | Manuscript (PDF) |
| `manuscript_latex.zip` | LaTeX source files (compiles on its own with `pdflatex` + the included `main.bbl`) |
| `cover_letter.pdf` | Cover letter |
| `Figure_1.png/.pdf`, `Figure_2.png/.pdf` | Figures as separate files (PNG at 600 dpi, vector PDF) |

## Before uploading: author-only items

Every `\tbc{...}` (red "[TO BE COMPLETED]" in the PDF) must be filled in and the macro removed:

```bash
grep -n 'tbc{' main.tex cover_letter.tex
```

- **Author contributions** (CRediT roles; the text in the placeholder is only an example).
- **Funding**, including who paid for the laboratory analyses (order ODER 23/2026).
- **Institutional Review Board Statement**: the consumer panel involved human participants.
  *Foods* requires an ethics approval number or a justified waiver.
- **Informed consent** statement.
- **Data availability** statement (on request, or a repository DOI).
- **Acknowledgments** and a **generative AI disclosure**, if AI was used for translation or editing.
- **Conflicts of interest**: the company that ordered the analyses, and the affiliation with the
  Polish Honey Chamber Association.
- Cover letter: journal section, conflict-of-interest sentence, suggested reviewers (optional).
- Check the affiliations and e-mail addresses of all authors.

## Structure

| File | Content | Edit |
|---|---|---|
| `main.tex` | MDPI preamble, title, authors, abstract (200 words), keywords, back matter, appendix | by hand |
| `section-introduction.tex` | 1. Introduction | by hand |
| `section-methods.tex` | 2. Materials and Methods (inputs `out.tex`), closing paragraphs of 3. Results | by hand |
| `out.tex` | 2.4 Statistical Analysis + 3. Results | **generated**; edit `code/template.latex` |
| `section-discussion.tex` | 4. Discussion, 5. Conclusions | by hand |
| `appendix-descriptions.tex` | Appendix A: verbatim laboratory descriptions | by hand |
| `bibliography.bib` | references (English; non-English sources marked "(In Polish/German/Italian)") | by hand |
| `code/` | English version of the analysis pipeline (`app.py`, `analysis.py`, `lab_comparison.py`) | |
| `data/` | `badania-2.xlsx` (panel), `Analiza_porownawcza_ODER_23_2026.xlsx` (laboratories) | do not upload |

## Notes on the translation

- Terminology: "blind consumer panel", "organoleptic" (not "sensory", except in the titles of
  cited works and laboratory method names), "Lab1"–"Lab4", "typicality", "overall acceptance".
  American spelling (odor, flavor, color); quotations from lab reports keep their original spelling.
- Laboratory codes kept as in the Polish version: T (typical), L (slightly or weakly typical),
  N (not typical for honey). Panel verdict "nr" became "inc." (inconclusive).
- Kappa wording follows Landis and Koch (1977): 0.30 = "fair", 0.13 = "slight".
- Appendix A: Lab1–Lab3 wording is taken from the original English (QSI: bilingual DE/EN) test
  reports in `../wyniki/`; Lab4 (Puławy, scanned Polish report) is translated from the workbook.
- `code/` still matches Polish keywords (`nietypow`, `lekko typow`, …) because the source workbook
  is in Polish; all output text, numbers (decimal point) and figure labels are English.
- All numbers in `out.tex` were checked against the Polish `../out.tex` and are identical.
  Numbers typed by hand in the abstract, the end of `section-methods.tex` and in
  `section-discussion.tex` must be re-checked if the data change.
