# Zgłoszenie do Measurement (Elsevier) – instrukcja

## Jak zbudować paczkę

```bash
cd latex
./make_submission.sh            # wynik: latex/submission_package/
```

Skrypt kopiuje `main-els.tex` (klasa `elsarticle`) jako `manuscript.tex` i dodaje opcję `doubleblind`, bo Measurement stosuje recenzję podwójnie anonimową: nazwiska i afiliacje nie są drukowane w manuskrypcie. Sekcję CRediT (zawiera nazwiska) przenosi z deklaracji na koniec `title_page`. Ryciny zapisuje jako `Figure_1…6` w jednym folderze, bez podfolderów, bo tego wymaga Elsevier. Wstawia `declarations.tex` przed bibliografią i ustawia numerację literatury w kolejności cytowania. Wszystko kompiluje, sprawdza limity z wytycznych i pakuje źródła do `manuscript_source.zip`. Skrypt jest bezpieczny do wielokrotnego uruchamiania, bo za każdym razem buduje folder od nowa. Źródła dokumentów leżą w `latex/submission/`, więc poprawki wprowadzaj tam, a nie w `submission_package/`.

## Co wgrać w Editorial Manager (krok „Attach files”)

| Plik | Typ pozycji (item type) | Uwagi |
|---|---|---|
| `manuscript.tex`, `manuscript.bbl`, `bibliography.bib`, `declarations.tex` | Manuscript WITHOUT Author details (edytowalne źródła LaTeX) | skrypt usuwa blok `\author`/`\affiliation` ze źródła, więc plik jest anonimowy także jako tekst |
| `Figure_1.jpeg` … `Figure_6.png` | Figure | po jednym pliku na rycinę |
| `highlights.txt` | Highlights | nazwa pliku musi zawierać słowo „highlights” |
| `title_page.tex` (lub `.pdf`) | Title Page (with Author details) | jedyne miejsce z nazwiskami, afiliacjami i CRediT |
| `cover_letter.pdf` | Cover Letter | |
| plik Word z narzędzia Elsevier | Declaration of Interest Statement | patrz niżej, wymagany format .doc/.docx |
| `manuscript.pdf` | nie wgrywać jako źródła | tylko do własnej kontroli; system sam zbuduje PDF |

Jeśli system poprosi o jedno archiwum ze źródłami, wgraj `manuscript_source.zip`.

## Do zrobienia przed wysłaniem

Skrypt wypisuje ostrzeżenie dla punktu 1.

1. **Bibliografia:** wpisy `MadhavanWrobel2024MLT` i `Roberts…` mają niepełną listę autorów („and others”). Wytyczne wymagają kompletnych danych, a przy ponad 6 autorach czasopismo samo skróci listę. `Letowski1989SoundQuality` nie ma DOI ani wydawcy.
2. **Oświadczenie o konflikcie interesów:** wypełnij [Elsevier declarations tool](https://declarations.elsevier.com) (opcja „I have nothing to declare”, jeśli dotyczy) i wgraj wygenerowany plik Word. Treść w `declarations.tex` musi się z nim zgadzać.

## Wymagania spełnione (sprawdzone przez skrypt)

- Streszczenie 226 słów (limit 250); 7 słów kluczowych (1–7).
- Highlights: 5 punktów, każdy ≤ 85 znaków.
- Ryciny Figure_1–6 mają co najmniej 2400 px szerokości (minimum 1063 px, 300 dpi); `fft.py` zapisuje je z `dpi=300`.
- Tabele w stylu `booktabs`, bez pionowych linii.
- Źródła edytowalne (.tex), jeden poziom folderu, manuskrypt kompiluje się bez błędów.
- Literatura numerowana w nawiasach kwadratowych w kolejności cytowania.
- Brak znaczników [TODO]; CRediT, adresy afiliacji, dostępność danych (Zenodo) i oświadczenie o AI uzupełnione.
- Oświadczenia (CRediT, konflikt interesów, finansowanie, dane, AI) w osobnych sekcjach przed bibliografią.

## Opcjonalne

- **Graphical abstract** (zalecany, nieobowiązkowy): 531 × 1328 px (wys. × szer.) lub proporcjonalnie więcej, TIFF/EPS/PDF.
- **Preprint na SSRN:** do wyboru przy zgłoszeniu, bez wpływu na decyzję redakcji.
- Manuskrypt jest na klasie `elsarticle` (`main-els.tex`). Poprawki merytoryczne wprowadzaj teraz w `main-els.tex`, nie w `main-en.tex`.
