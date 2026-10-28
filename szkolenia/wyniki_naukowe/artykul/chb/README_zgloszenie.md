# Zgłoszenie do Computers in Human Behavior (Elsevier)

Źródłem wersji CHB jest **tylko `manuscript.tex`** (klasa elsarticle, utworzony 2026-10-23 z `main-en.tex`,
liczby wpisane na stałe). Zmiany w polskim tekście ani `/tlumaczenie-en` go nie aktualizują.

Budowa i kontrola pakietu: `./make_submission.sh` → katalog `pakiet/` (płaski, jak wymaga Elsevier).

## Pliki do wgrania w Editorial Manager

| Plik | Typ w systemie |
|---|---|
| `title_page.pdf` (lub .tex) | Title page (with author details) |
| `manuscript.pdf` + `manuscript_source.zip` | Manuscript (anonymized) / LaTeX source |
| `Figure_1.pdf` … `Figure_3.pdf` | Figure |
| `Highlights.docx` | Highlights |
| `cover_letter.pdf` | Cover letter |

## Do uzupełnienia przed wysłaniem (skrypt zgłasza je jako TODO)

1. **CRediT** (`title_page.tex`): role każdego z pięciu autorów.
2. **Proponowani recenzenci**: autorzy nie mają kandydatów; jeśli Editorial Manager wymaga tego pola,
   trzeba będzie kogoś wskazać przy wysyłce.

## Do sprawdzenia

- Afiliacja M. J. Wróbla: w `main.tex` jest „Collegium Medicum NCU, Toruń”, na stronie tytułowej przyjęto
  pełną nazwę i adres z projektu MLT (Collegium Medicum w Bydgoszczy).
- Oświadczenie o AI wymienia Claude Sonnet 5.5 (redakcja językowa) i Claude Opus 5.5 (tłumaczenie).
- Oświadczenie etyczne (`declarations.tex`): badanie na zanonimizowanych danych banku, bez zgody komisji
  etycznej i bez zgody pracowników; potwierdź, że jest to zgodne z zasadami uczelni.
- Highlights (`highlights.txt`): 3–5 punktów, do 85 znaków każdy.

## Wymagania CHB uwzględnione w pakiecie

Recenzja podwójnie anonimowa (autorzy, afiliacje, konflikt interesów i CRediT tylko na stronie
tytułowej; nazwa wydziału banku usunięta z tekstu), streszczenie do 250 słów bez nagłówków
i z rozwiniętym „pp”, maks. 6 słów kluczowych, highlights w osobnym pliku, cytowania autor–rok (APA,
`elsarticle-harv`), tabele jako tekst bez pionowych linii, numeracja wierszy, oświadczenie o AI w sekcji
o tytule wymaganym przez Elsevier przed bibliografią, standardowe zdanie o finansowaniu, oświadczenie
o dostępności danych, zdanie o nieanalizowanej płci w ograniczeniach (SGBA).
