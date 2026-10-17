# Słownik i konwencje tłumaczenia PL → EN

Wiążący przy każdym tłumaczeniu. Wariant języka: **American English** (analyze, behavior, program, modeling).
Gdy tłumaczenie wymaga terminu spoza słownika, użyj go konsekwentnie i zgłoś użytkownikowi jako
kandydata do dopisania (nie dopisuj sam).

## 1. Terminy z `terminologia.tex` (numeracja jak na liście)

| PL | EN | Uwagi |
|---|---|---|
| I. sekwencja | sequence | „sekwencja pracownik–pytanie” → employee–question sequence |
| II. numer próby | attempt number | próba → attempt (nie: trial, try) |
| III. pierwsza próba | first attempt | |
| IV. poprawność | accuracy | zawsze odsetek poprawnych odpowiedzi; „poprawność w próbie k” → accuracy at attempt k |
| V. odstęp | interval | czas w dniach od poprzedniej próby; nie: gap, lag, spacing (makra `\Gap...` mimo nazwy → interval) |
| VI. dystraktor | distractor | |
| VII. informacja zwrotna | feedback | niepoliczalne: „the feedback”, nie „feedbacks” |
| VIII. korekta błędu | error correction | zdarzenie; „odsetek korekt błędów” → error-correction rate |
| IX. zapominanie | forgetting | zdarzenie; „przypadek zapominania” → forgetting event; „odsetek zapominania” → forgetting rate |
| X. powtórzony błąd | repeated error | |
| XI. błędy z rzędu | consecutive errors | „poprawne odpowiedzi z rzędu” → consecutive correct responses |
| XII. kohorta | cohort | nie: balanced cohort |
| XIII. bootstrap | bootstrap | „bootstrap klastrowy (po pracownikach)” → cluster bootstrap (resampling employees) |

## 2. Pozostałe terminy

| PL | EN |
|---|---|
| pracownik | employee |
| pytanie | question; w analizie psychometrycznej: item (item difficulty, item discrimination, item–rest correlation, distractor analysis) |
| odpowiedź (udzielona) / opcja odpowiedzi | response / answer option |
| odpowiedź poprawna / błędna | correct / incorrect response |
| mikrouczenie, program mikrouczenia | microlearning, microlearning program |
| edukacja rozłożona w czasie | spaced education |
| powtórki rozłożone w czasie | spaced repetition |
| efekt rozłożenia w czasie / efekt testowania | spacing effect / testing effect |
| nauka skumulowana | massed learning |
| przypominanie (z pamięci) | retrieval |
| utrwalanie / utrwalenie wiedzy | retention / consolidation (zgodnie z kontekstem) |
| harmonogram (adaptacyjny, stały) | (adaptive, fixed) schedule |
| nawrót błędu | error relapse |
| utrwalone błędne przekonanie | persistent misconception |
| moduł | module |
| szkolenia pracownicze / obowiązkowe | employee training / mandatory training |
| transfer (szkolenia) | transfer of training |
| staż (pracownika) | tenure |
| przedział wieku | age group |
| odsetek | percentage (przy %) / proportion (przy ułamku) |
| punkty procentowe (p.p.) | percentage points (pp) |
| przedział ufności, 95% PU | confidence interval, 95% CI |
| iloraz szans | odds ratio (OR) |
| rozstęp międzykwartylowy | interquartile range (IQR) |
| efekty stałe / losowe, model mieszany | fixed / random effects, mixed model |
| analiza wrażliwości | sensitivity analysis |
| dane anonimizowane / pseudonimizowane | anonymized / pseudonymized data |
| bank spółdzielczy | cooperative bank |
| informacja zwrotna odnosząca się do dystraktora | distractor-specific feedback |

## 3. Elementy dokumentu

| PL | EN |
|---|---|
| Wprowadzenie / Metodologia / Wyniki / Dyskusja / Wnioski | Introduction / Methods / Results / Discussion / Conclusions |
| Ograniczenia i dalsze badania | Limitations and future research |
| Oświadczenia | Declarations |
| Streszczenie: Wprowadzenie / Metody / Wyniki / Wnioski | Background / Methods / Results / Conclusions |
| Słowa kluczowe | Keywords |
| Autor korespondencyjny | Corresponding author (polskie tytuły „dr inż.” pomiń) |
| Etyka / Dostępność danych / Finansowanie / Konflikt interesów / Wykorzystanie narzędzi AI | Ethics / Data availability / Funding / Competing interests / Use of AI tools |
| tab.~\ref{..} / rys.~\ref{..} / podrozdział~\ref{..} / wzór~\eqref{..} | Table~\ref{..} / Figure~\ref{..} / Section~\ref{..} / Eq.~\eqref{..} (na początku zdania także w pełnej formie) |
| Materiał uzupełniający | Supplementary material |

## 4. Konwencje zapisu w tekście

- Liczby wpisane dosłownie: `0{,}20` lub `0,20` → `0.20`; `10 000` lub `10\,000` → `10,000`; przedziały `[a; b]` → `[a, b]`.
  Wartości makr (`\FirstAcc` itd.) są już w notacji angielskiej w `definicje-en.tex`, nie zmieniaj ich nazw.
- Daty: „3 sierpnia 2026” → „3 August 2026”; „od \DateStart{} do \DateEnd” → „from \DateStart{} to \DateEnd”
  (makra dat mają w wersji EN mianownik: „May 2023”).
- Cudzysłowy: `,,tekst''` → ``` ``tekst'' ```.
- Skróty: „np.\ ” → „e.g.,”; „tj.” → „i.e.,”; „tzw.” → pomiń albo „so-called”; „ok.” → „approximately”.
- Myślnik w funkcji wtrącenia: zamień na przecinki lub nawias (jak w wersji polskiej); `--` między liczbami zostaje.
- `\%` po makrze zostaje bez zmian (`\FirstAcc\%`).

## 5. Styl

- Rejestr akademicki, zdania rzeczowe; wierność treści: bez dodawania, pomijania i wzmacniania twierdzeń,
  bez nowych cytowań. Przebudowa zdania dla naturalnego angielskiego jest dopuszczalna.
- Strona bierna lub forma bezosobowa jak w źródle; „we” tylko tam, gdzie konstrukcja bierna byłaby niezręczna.
- Bez przymiotników wartościujących i słownictwa typowego dla LLM: delve, crucial, pivotal, notably,
  underscore, highlight (w znaczeniu „podkreślać”), comprehensive, robust (poza znaczeniem statystycznym),
  landscape, leverage, „it is worth noting”.
- Czasy: wyniki i metody w czasie przeszłym (was, were); stwierdzenia ogólne i odwołania do literatury
  w czasie teraźniejszym.
