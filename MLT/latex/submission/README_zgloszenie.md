# Zgłoszenie do Applied Acoustics – instrukcja

## Jak zbudować paczkę

```bash
cd latex
./make_submission.sh            # wynik: latex/submission_package/
```

Skrypt kopiuje `main-en.tex` jako `manuscript.tex`. Ryciny zapisuje jako `Figure_1…6` w jednym folderze, bez podfolderów, bo tego wymaga Elsevier. Wstawia `declarations.tex` przed bibliografią i ustawia numerację literatury w kolejności cytowania. Wszystko kompiluje, sprawdza limity z wytycznych i pakuje źródła do `manuscript_source.zip`. Skrypt jest bezpieczny do wielokrotnego uruchamiania, bo za każdym razem buduje folder od nowa. Źródła dokumentów leżą w `latex/submission/`, więc poprawki wprowadzaj tam, a nie w `submission_package/`.

## Co wgrać w Editorial Manager (krok „Attach files”)

| Plik | Typ pozycji (item type) | Uwagi |
|---|---|---|
| `manuscript.tex`, `manuscript.bbl`, `bibliography.bib`, `declarations.tex` | Manuscript (LaTeX source) | wszystkie źródła, ten sam poziom folderu |
| `Figure_1.jpeg` … `Figure_6.png` | Figure | po jednym pliku na rycinę |
| `highlights.txt` | Highlights | nazwa pliku musi zawierać słowo „highlights” |
| `title_page.pdf` (lub `.tex`) | Title Page | |
| `cover_letter.pdf` | Cover Letter | |
| plik Word z narzędzia Elsevier | Declaration of Interest Statement | patrz niżej, wymagany format .doc/.docx |
| `manuscript.pdf` | nie wgrywać jako źródła | tylko do własnej kontroli; system sam zbuduje PDF |

Jeśli system poprosi o jedno archiwum ze źródłami, wgraj `manuscript_source.zip`.

## Do zrobienia przed wysłaniem

Skrypt wypisuje ostrzeżenia dla punktów 1–5.

1. **Znaczniki [TODO]** w `submission/declarations.tex`, `title_page.tex` i `cover_letter.tex`:
   - role CRediT każdego autora (lista dozwolonych ról jest w komentarzu w pliku);
   - pełne adresy pocztowe obu afiliacji (ulica, kod); wytyczne wymagają adresu z nazwą kraju;
   - potwierdzenie przez wszystkich autorów: brak konfliktu interesów, brak finansowania, zgoda na publikację;
   - **dostępność danych:** czasopismo stosuje „Option C”, czyli trzeba zdeponować dane w repozytorium (np. Zenodo: `tmp.json` z cechami i `fft.py`), podać DOI albo wyjaśnić, czemu nie można ich udostępnić. Warunki licencji BBC Sound Effects sprawdź przed wysłaniem;
   - **oświadczenie o AI:** opisuje użycie Claude do tłumaczenia i sprawdzania spójności liczb. Popraw zakres, jeśli był inny. Oświadczenie jest obowiązkowe, jeśli AI było używane.
2. **Rozdzielczość rycin:** minimum 1063 px szerokości (300 dpi). Za małe są `chart-centroid`, `chart-f0`, `chart-par` (1000 px) i `correl-matrix` (800 px). W `MLT/fft.py` dodaj `dpi=300` w dwóch wywołaniach `plt.savefig` (wykresy słupkowe w `draw_2` i mapa korelacji). Potem uruchom skrypt ponownie i skopiuj ryciny do `latex/images/`.
3. **Pionowe linie w tabeli** (dodatek, `|c|`): wytyczne każą ich unikać. Warto przerobić tabelę na styl `booktabs`, jak pozostałe tabele.
4. **Bibliografia:** wpisy `MadhavanWrobel2024MLT` i `Roberts…` mają niepełną listę autorów („and others”). Wytyczne wymagają kompletnych danych, a przy ponad 6 autorach czasopismo samo skróci listę. `Letowski1989SoundQuality` nie ma DOI ani wydawcy.
5. **Oświadczenie o konflikcie interesów:** wypełnij [Elsevier declarations tool](https://declarations.elsevier.com) (opcja „I have nothing to declare”, jeśli dotyczy) i wgraj wygenerowany plik Word. Treść w `declarations.tex` musi się z nim zgadzać.

## Wymagania spełnione (sprawdzone przez skrypt)

- Streszczenie 226 słów (limit 250); 7 słów kluczowych (1–7).
- Highlights: 5 punktów, każdy ≤ 85 znaków.
- Źródła edytowalne (.tex), jeden poziom folderu, manuskrypt kompiluje się bez błędów.
- Literatura numerowana w nawiasach kwadratowych w kolejności cytowania.
- Oświadczenia (CRediT, konflikt interesów, finansowanie, dane, AI) w osobnych sekcjach przed bibliografią.

## Opcjonalne

- **Graphical abstract** (zalecany, nieobowiązkowy): 531 × 1328 px (wys. × szer.) lub proporcjonalnie więcej, TIFF/EPS/PDF.
- **Preprint na SSRN:** do wyboru przy zgłoszeniu, bez wpływu na decyzję redakcji.
- Szablon `elsarticle` jest zalecany, ale nie wymagany; obecna klasa `article` jest dopuszczalna.
