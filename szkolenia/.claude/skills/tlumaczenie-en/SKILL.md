---
name: tlumaczenie-en
description: Tłumaczy artykuł (main.tex + sekcja-*.tex) na angielski i scala go w jeden plik main-en.tex z angielskimi rysunkami (rysunki/*-en.pdf) i tabelami; tłumaczy przyrostowo tylko pliki zmienione od ostatniego tłumaczenia. Użyj, gdy użytkownik prosi o wersję angielską, tłumaczenie artykułu, aktualizację main-en.tex lub uruchamia /tlumaczenie-en.
---

# Angielska wersja artykułu (main-en.tex)

Argumenty (opcjonalne, można łączyć):
- brak: przyrostowo, tylko pliki NOWY/ZMIENIONY, potem scalenie i kompilacja;
- `suplement`: uwzględnij też `suplement.tex` → `suplement-en.tex` (domyślnie pomijany);
- `od-nowa` lub nazwy plików (np. `sekcja-dyskusja.tex`): przetłumacz wskazane pliki (albo wszystkie) od nowa;
- `buduj`: bez tłumaczenia, tylko scalenie i kompilacja.

Ścieżki: repozytorium `/disk/Work/Artykuly/szkolenia`, artykuł `wyniki_naukowe/artykul` (dalej ART),
skill `.claude/skills/tlumaczenie-en` (dalej SKILL). Skrypt `SKILL/scal_en.py` (python3, tylko biblioteka
standardowa) robi wszystko poza samym tłumaczeniem; przy argumencie `suplement` dodawaj do każdego
wywołania opcję `--suplement` przed poleceniem.

## Jak to działa

- Tłumaczenia są w `ART/en/<plik>.tex` (te same nazwy co polskie źródła). `ART/en/.zrodla/<plik>.tex` to kopia
  polskiego źródła, z którego powstało tłumaczenie; na jej podstawie wykrywa się zmiany i pokazuje diff.
- Liczby, tabele i rysunki po angielsku generuje skrypt analizy w drugim przebiegu (te same obliczenia
  i ziarno): `definicje-en.tex` (te same nazwy makr, kropka dziesiętna), `tabele/*-en.csv`, `rysunki/*-en.pdf`.
- `scal_en.py buduj` tworzy `ART/main-en.tex`: wstawia sekcje z `en/`, treść `definicje-en.tex` i tabele
  (`\tabelacsv` → `tabular` z `*-en.csv`), zamienia `\FigDir rys_x` na `rysunki/rys_x-en`, usuwa komentarze
  całoliniowe, po czym kompiluje (latexmk + bibtex). `main-en.tex` jest nadpisywany: poprawki wprowadza się
  w `en/*.tex`.

## Procedura

1. **Stan.** `python3 SKILL/scal_en.py status --diff` (z katalogu repozytorium). Pokazuje NOWY / ZMIENIONY /
   AKTUALNY dla każdego pliku, diff polskiego źródła od ostatniego tłumaczenia oraz stan materiałów -en.
2. **Materiały -en.** Jeśli status zgłasza „DO ODŚWIEŻENIA”, uruchom skrypt analizy z katalogu repozytorium:
   `/opt/venvs/common/bin/python analiza_odpowiedzi_naukowa.py data.csv --wyniki wyniki_naukowe` (ok. 1 min;
   tylko to środowisko, systemowy python3 zmienia makra `\Ver*`). Skrypt nadpisuje też wersję polską
   (te same liczby). Ostrzeżenia `UWAGA: ... zostanie obcięty` dla rysunków `-en` usuń, skracając angielski
   podpis w funkcji `wykres_*` skryptu (`T("polski", "english")`). Nie uruchamiaj skryptu bez potrzeby.
3. **Przygotowanie.** Wczytaj `SKILL/slownik-en.md` (terminologia i konwencje, wiążące) oraz aktualną
   `ART/terminologia.tex`. Jeśli lista definicji zawiera termin, którego nie ma w słowniku, zgłoś to
   użytkownikowi i zaproponuj odpowiednik.
4. **Tłumaczenie.**
   - NOWY (lub `od-nowa`): przeczytaj cały polski plik i zapisz pełne tłumaczenie do `ART/en/<plik>`.
   - ZMIENIONY: na podstawie diffu zmień w `ART/en/<plik>` tylko odpowiadające fragmenty (Edit). Nie tłumacz
     pliku od nowa: zachowuje to wcześniejsze sformułowania i ręczne poprawki w `en/`.
   - Przy pierwszym tłumaczeniu kilku plików możesz zlecić je równolegle agentom, podając każdemu ścieżki do
     polskiego pliku, `slownik-en.md` i tej sekcji. Po powrocie sprawdź spójność terminów między plikami.
5. **Kontrola i zatwierdzenie.** `python3 SKILL/scal_en.py sprawdz <pliki>` porównuje ze źródłem makra
   liczbowe, cytowania, etykiety, odsyłacze, rysunki, tabele i środowiska. Usuń niezgodności, potem
   `python3 SKILL/scal_en.py zatwierdz <pliki>`.
6. **Scalenie.** `python3 SKILL/scal_en.py buduj`. Przejrzyj zgłoszenia: błędy kompilacji, niezdefiniowane
   polecenia i odsyłacze, linie z polskimi znakami (dozwolone tylko nazwy własne, np. autorów i afiliacji).
7. **Raport dla użytkownika.** Które pliki przetłumaczono lub zaktualizowano, wynik kompilacji (`main-en.pdf`),
   terminy spoza słownika, a także błędy i niespójności zauważone w polskim źródle. Zgłoś je, nie poprawiaj
   ich po cichu w tłumaczeniu.

## Reguły dla plików `en/*.tex`

- Zachowaj bez zmian: nazwy makr liczbowych, klucze `\cite`, `\label`, `\ref`, specyfikacje kolumn
  i nazwy w `\tabelacsv{..}{nazwa}` oraz `\FigDir rys_x` (bez sufiksu -en, dodaje go `buduj`), strukturę
  środowisk i kolejność rycin i tabel.
- `en/main.tex`: `\usepackage[english]{babel}`, `\renewcommand\Authand{ and }\renewcommand\Authands{, and }`,
  `\input{definicje.tex}` i `\input{sekcja-...}` zostają w tej postaci (`buduj` wstawia wersje angielskie).
  Autorów, ORCID i afiliacji (już angielskich) nie zmieniaj.
- Komentarze całoliniowe pomijaj (`buduj` je usuwa), także bloki zakomentowane. Komentarze końcowe po `%`
  przetłumacz albo usuń.
- Treść `\fillin{...}` (uwagi dla współautorów) przetłumacz i zachowaj.
- Konwencje liczb, dat, odsyłaczy, cudzysłowów i styl: `slownik-en.md`, punkty 3 do 5.
