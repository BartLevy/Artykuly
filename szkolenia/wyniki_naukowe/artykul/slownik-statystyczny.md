# Słownik pojęć statystycznych

Słownik obejmuje metody i miary statystyczne użyte w artykule. Przy każdym haśle podano definicję, wzór (o ile jest prosty), sposób odczytania wyniku na przykładzie danych z artykułu oraz funkcję skryptu `analiza_odpowiedzi_naukowa.py`, która daną wielkość oblicza. Przykładowe liczby pochodzą z bieżącego pliku `definicje.tex` i zmienią się po ponownym uruchomieniu skryptu na innych danych.

Plik nie jest wstawiany do artykułu ani nadpisywany przez skrypt.

---

## 1. Statystyki opisowe

### Mediana
Wartość dzieląca uporządkowane obserwacje na dwie równe części: połowa obserwacji jest od niej mniejsza, połowa większa. W odróżnieniu od średniej nie zależy od wartości skrajnych, dlatego stosuje się ją do zmiennych o rozkładzie skośnym, takich jak liczba odpowiedzi na pracownika lub odstęp między próbami.
*Przykład:* mediana odstępu między kolejnymi próbami tego samego pytania wynosi 36 dni.
*Skrypt:* `materialy_artykulu` (tabela `zbior_danych`).

### Rozstęp międzykwartylowy (IQR, ang. *interquartile range*)
Przedział od pierwszego kwartyla $Q_1$ (25. percentyl) do trzeciego kwartyla $Q_3$ (75. percentyl), w którym mieści się środkowa połowa obserwacji. W artykule podawany w nawiasie kwadratowym po medianie.
*Przykład:* odstęp między próbami, mediana 36 dni [18; 90], czyli u połowy powtórek odstęp mieścił się między 18 a 90 dniami.

### Średnia i odchylenie standardowe (SD, ang. *standard deviation*)
Średnia arytmetyczna $\bar{x} = \frac{1}{n}\sum x_i$ opisuje położenie rozkładu, a odchylenie standardowe $s = \sqrt{\frac{1}{n-1}\sum (x_i-\bar{x})^2}$ jego rozproszenie. W artykule użyte dla wieku pracowników oraz dla odchyleń standardowych efektów losowych w modelu mieszanym.

### Odsetek i punkt procentowy (p.p.)
Odsetek to udział obserwacji spełniających warunek, wyrażony w procentach (np. odsetek poprawnych odpowiedzi). Różnicę dwóch odsetków podaje się w punktach procentowych: wzrost z 82,6% do 87,3% to zmiana o 4,7 p.p., a nie o 4,7%.

---

## 2. Wnioskowanie i niepewność oszacowań

### Przedział ufności (PU, ang. *confidence interval*, CI)
Przedział wartości, który przy wielokrotnym powtarzaniu badania obejmowałby prawdziwą wartość parametru w określonym odsetku powtórzeń (tu 95%). Szerokość przedziału odzwierciedla precyzję oszacowania. W artykule zapisywany jako [dolna granica; górna granica].
*Przykład:* odsetek poprawnych odpowiedzi w pierwszej próbie 82,5% [81,0; 83,9].

### Bootstrap
Metoda szacowania niepewności przez wielokrotne losowanie ze zwracaniem próby o tej samej liczebności z danych pierwotnych i ponowne obliczanie statystyki w każdej replikacji. Rozkład otrzymanych wartości zastępuje nieznany rozkład teoretyczny. Przedział percentylowy 95% wyznacza się z 2,5. i 97,5. percentyla replikacji.

### Bootstrap klastrowy
Odmiana bootstrapu, w której losuje się całe klastry (tu pracowników wraz ze wszystkimi ich odpowiedziami), a nie pojedyncze obserwacje. Uwzględnia to fakt, że odpowiedzi jednej osoby są ze sobą skorelowane; zwykły bootstrap traktowałby je jako niezależne i zawężałby przedziały ufności. W każdej z 2000 replikacji odsetek liczono jako iloraz sumy poprawnych odpowiedzi do sumy wszystkich odpowiedzi wylosowanych pracowników.
*Skrypt:* `bootstrap_srednie` (losowanie wag z rozkładu wielomianowego), `udzialy_z_ci`.

### Wartość p
Prawdopodobieństwo uzyskania wyniku co najmniej tak odległego od hipotezy zerowej jak zaobserwowany, przy założeniu, że hipoteza zerowa jest prawdziwa. Mała wartość p świadczy przeciw hipotezie zerowej, lecz nie mierzy wielkości efektu ani prawdopodobieństwa, że hipoteza jest prawdziwa.
*Przykład:* dla stażu w modelu 3 p = 0,061, a przedział ufności OR [0,76; 1,01] obejmuje 1, zatem brak podstaw do odrzucenia hipotezy o braku związku.

### Poziom istotności (α)
Z góry przyjęty próg wartości p (lub q), poniżej którego wynik uznaje się za istotny statystycznie. W artykule α = 0,05.

### Odsetek fałszywych odkryć (FDR, ang. *false discovery rate*)
Oczekiwany udział wyników fałszywie dodatnich wśród wszystkich wyników uznanych za istotne. Kontrolę FDR stosuje się, gdy wykonuje się wiele testów jednocześnie (tu osobny test trendu dla każdego ze 164 pytań); bez korekty część istotnych wyników pojawiałaby się przypadkowo.

### Procedura Benjaminiego–Hochberga i wartość q
Metoda kontroli FDR. Wartości p z $m$ testów porządkuje się rosnąco ($p_{(1)} \le \dots \le p_{(m)}$) i przekształca w wartości q: $q_{(i)} = \min_{j \ge i} \frac{m\,p_{(j)}}{j}$. Pytanie uznaje się za istotne, gdy $q < \alpha$.
*Przykład:* poprawność istotnie rosła z powtórkami w 44 ze 164 pytań przy $q < 0,05$.
*Skrypt:* `analiza_pozycji` (`multipletests(..., method="fdr_bh")`).

---

## 3. Modele regresji

### Regresja logistyczna
Model dla zmiennej binarnej (odpowiedź poprawna = 1, błędna = 0), w którym logit prawdopodobieństwa sukcesu jest liniową funkcją predyktorów: $\operatorname{logit}(p) = \ln\frac{p}{1-p} = \beta_0 + \beta_1 x_1 + \dots$. Współczynniki $\beta$ są wyrażone na skali logitowej, a po przekształceniu $e^{\beta}$ dają ilorazy szans.

### Modele M1–M3
Trzy modele regresji logistycznej z efektami stałymi pracownika ($\alpha_i$) i pytania ($\gamma_j$), opisane w podrozdziale „Modele statystyczne” artykułu. $Y_{ijt}$ to poprawność odpowiedzi pracownika $i$ na pytanie $j$ w próbie $t$.
- **M1, model uczenia** (wszystkie odpowiedzi): $\operatorname{logit} P(Y_{ijt}=1) = \alpha_i + \gamma_j + \beta_1\log_2 t$. OR 1,38 [1,32; 1,45] na podwojenie numeru próby.
- **M2, model retencji** (próby $t\ge2$): $\alpha_i + \gamma_j + \beta_1\log_2 t + \beta_2 Y_{ij,t-1} + \beta_3\log_2\Delta_{ijt} + \beta_4 S_{it}$, gdzie $\Delta$ to odstęp w dniach, a $S$ staż w latach. OR 3,85 dla poprawnej poprzedniej odpowiedzi, 0,88 na podwojenie odstępu.
- **M3, model nowych pytań** (tylko $t=1$): $\alpha_i + \gamma_j + \beta_4 S_{it}$. OR 0,88 [0,76; 1,01] na rok stażu; efekt identyfikowany z pierwszych kontaktów tej samej osoby z kolejnymi pytaniami.

*Skrypt:* `modele` (wywołania `logit_fe` dla `M1`, `M2`, `M3`).

### Logit i skala logitowa
Logit to logarytm naturalny szans, $\ln\frac{p}{1-p}$. Skala logitowa jest nieograniczona, co pozwala modelować prawdopodobieństwa addytywnie. Na tej skali raportowano również odchylenia standardowe efektów losowych (pracownik SD = 0,69, pytanie SD = 1,10).

### Szanse i iloraz szans (OR, ang. *odds ratio*)
Szanse to stosunek prawdopodobieństwa zdarzenia do prawdopodobieństwa jego braku, $\frac{p}{1-p}$ (dla $p = 0,8$ szanse wynoszą 4). Iloraz szans to stosunek szans w dwóch warunkach; OR = 1 oznacza brak związku, OR > 1 wzrost, OR < 1 spadek szans. OR nie jest równoważny ilorazowi prawdopodobieństw, zwłaszcza przy wysokich odsetkach poprawnych odpowiedzi.
*Przykład:* poprawna poprzednia odpowiedź, OR = 3,85: szanse poprawnej odpowiedzi są prawie czterokrotnie większe niż po odpowiedzi błędnej.

### Transformacja log₂ i OR „na podwojenie”
Numer próby i odstęp w dniach wprowadzono do modeli jako $\log_2(x)$. Wzrost $\log_2(x)$ o 1 odpowiada podwojeniu $x$, więc OR odnosi się do podwojenia wartości (próba 1→2, 2→4, 4→8). Przekształcenie odzwierciedla malejący przyrost efektu z każdą kolejną próbą. Odstęp przed logarytmowaniem ograniczono od dołu do 1 dnia.
*Przykład:* OR = 1,38 [1,32; 1,45] na podwojenie numeru próby; OR = 0,88 na podwojenie odstępu oznacza spadek szans o 12% przy każdym podwojeniu czasu od poprzedniej próby.
*Skrypt:* `przygotuj` (kolumny `log2_proba`, `log2_odstep`).

### Efekty stałe (ang. *fixed effects*)
Osobny wyraz wolny dla każdego pracownika i każdego pytania, wprowadzony jako zmienne zero-jedynkowe. Pochłania on stałe różnice poziomu wiedzy między osobami i trudności między pytaniami, dzięki czemu efekt numeru próby jest szacowany wyłącznie z porównań w obrębie tej samej osoby i tego samego pytania.
*Skrypt:* `logit_fe` (`C(user_symbol) + C(question_id)`).

### Pomijanie pracowników i pytań bez zmienności
Gdy pracownik (lub pytanie) ma wyłącznie odpowiedzi poprawne albo wyłącznie błędne, jego efekt stały dąży do nieskończoności i nie może zostać oszacowany. Skrypt iteracyjnie usuwa takie jednostki przed dopasowaniem modelu (w modelu 1 pominięto 282 odpowiedzi). Model szacuje się następnie zwykłą metodą największej wiarygodności ze zmiennymi zero-jedynkowymi.
*Skrypt:* `logit_fe` (pętla `while True`).

### Błędy standardowe klastrowane (ang. *cluster-robust standard errors*)
Odporny estymator wariancji współczynników (typu „sandwich”), który dopuszcza dowolną korelację reszt w obrębie klastra (pracownika). Bez tej korekty powtarzane odpowiedzi tej samej osoby byłyby traktowane jako niezależne, a przedziały ufności byłyby zbyt wąskie.
*Skrypt:* `logit_fe`, `analiza_pozycji` (`cov_type="cluster"`).

### Uogólnione równania estymujące (GEE, ang. *generalized estimating equations*)
Metoda szacowania modelu regresji dla danych skorelowanych, w której zakłada się roboczą strukturę korelacji w obrębie klastra, a błędy standardowe wyznacza się odpornie. Daje efekt **uśredniony populacyjnie** (ang. *population-averaged*), czyli przeciętną zmianę w populacji, w odróżnieniu od efektu **warunkowego** w obrębie osoby, uzyskiwanego z efektów stałych lub losowych. Efekty uśrednione populacyjnie są zwykle bliższe 1 niż warunkowe, co wyjaśnia niższy OR w GEE (1,29).
*Skrypt:* `modele` (`smf.gee`).

### Korelacja wymienna (ang. *exchangeable correlation*)
Robocza struktura korelacji w GEE zakładająca jednakową korelację między dowolnymi dwiema odpowiedziami tego samego pracownika, niezależnie od ich kolejności i odstępu w czasie.

### Model mieszany (ang. *mixed model*)
Model regresji łączący efekty stałe (wspólne dla wszystkich, tu efekt numeru próby) z efektami losowymi (odchylenia poszczególnych jednostek traktowane jako próba z rozkładu normalnego). Pozwala oszacować, jak duża część zmienności przypada na różnice między pracownikami, a jak duża na różnice między pytaniami.

### Losowy wyraz wolny i skrzyżowane efekty losowe
Losowy wyraz wolny to indywidualne przesunięcie poziomu logitu dla jednostki, $u_j \sim N(0, \sigma_u^2)$. Efekty są **skrzyżowane**, gdy każda odpowiedź należy jednocześnie do dwóch niezależnych grupowań (pracownika i pytania), z których żadne nie jest zagnieżdżone w drugim. Model nie zawierał losowych nachyleń, czyli nie dopuszczał różnego tempa uczenia się u poszczególnych pracowników.
*Skrypt:* `modele` (`BinomialBayesMixedGLM`, składniki `u` i `q`).

### Estymacja MAP i aproksymacja Laplace'a
Model mieszany dopasowano metodą maksimum a posteriori (MAP, `fit_map`) z biblioteki statsmodels, czyli przez znalezienie modu rozkładu a posteriori parametrów. Niepewność współczynnika wyznaczono z krzywizny rozkładu w modzie (aproksymacja Laplace'a), a przedział 95% jako $\hat\beta \pm 1,96 \cdot SE$. Rozwiązanie zastosowano, ponieważ w środowisku nie był dostępny pakiet lme4 (R).

### Współczynnik korelacji wewnątrzklasowej (ICC, ang. *intraclass correlation coefficient*)
Udział wariancji przypadającej na dane grupowanie w całkowitej wariancji. W regresji logistycznej wariancję reszt na skali latentnej przyjmuje się jako wariancję rozkładu logistycznego, $\pi^2/3 \approx 3,29$:
$$\mathrm{ICC}_{\text{pytanie}} = \frac{\sigma_q^2}{\sigma_u^2 + \sigma_q^2 + \pi^2/3}.$$
*Przykład:* ICC pytania 0,24, ICC pracownika 0,09: różnice trudności między pytaniami odpowiadają za większą część zmienności poprawności niż różnice między pracownikami.
*Skrypt:* `modele` (słownik `icc`).

### R² brzegowy i warunkowy Nakagawy
Miary dopasowania modelu mieszanego na skali latentnej. R² **brzegowy** to udział wariancji wyjaśnionej przez efekty stałe ($\sigma_f^2$, wariancja predykcji z numeru próby), R² **warunkowy** to udział wyjaśniony łącznie przez efekty stałe i losowe:
$$R^2_m = \frac{\sigma_f^2}{\sigma_f^2+\sigma_u^2+\sigma_q^2+\pi^2/3}, \qquad R^2_c = \frac{\sigma_f^2+\sigma_u^2+\sigma_q^2}{\sigma_f^2+\sigma_u^2+\sigma_q^2+\pi^2/3}.$$
*Przykład:* $R^2_m = 0,021$, $R^2_c = 0,35$: sam numer próby wyjaśnia niewielką część zmienności poprawności, mimo że jego efekt jest istotny i stabilny; większość wyjaśnionej zmienności wynika z różnic między pytaniami i osobami.

### Funkcja potęgowa i potęgowe prawo praktyki
Zależność odsetka błędów od numeru próby opisano funkcją $\text{błąd} = a \cdot \text{próba}^{-b}$. Po zlogarytmowaniu obu stron zależność jest liniowa, $\ln(\text{błąd}) = \ln a - b \ln(\text{próba})$, i dopasowano ją metodą najmniejszych kwadratów z wagami $\sqrt{n}$, bez łącznej kategorii prób 10+. Wykładnik $b$ określa tempo spadku błędów, a R² dopasowania mierzy zgodność punktów z prostą na skali logarytmicznej.
*Przykład:* $b = 0,29$, R² = 0,98.
*Skrypt:* `krzywa_uczenia`.

### Performance factors analysis (PFA) i half-life regression (HLR)
Modele ucznia znane z literatury systemów tutorskich i aplikacji do nauki słownictwa. PFA przewiduje poprawność z liczby wcześniejszych sukcesów i porażek, HLR modeluje zanik pamięci w funkcji czasu od ostatniej powtórki. Model 2 w artykule jest do nich analogiczny (poprzedni wynik, odstęp), lecz nie jest ich implementacją.

---

## 4. Testy statystyczne

### Test znaków
Test nieparametryczny dla danych sparowanych, w którym liczy się tylko kierunek zmiany (poprawa albo pogorszenie), z pominięciem remisów. Przy hipotezie zerowej poprawa i pogorszenie są jednakowo prawdopodobne, więc liczba poprawiających się ma rozkład dwumianowy z $p = 0,5$. Przedział ufności dla odsetka poprawiających się wyznaczono metodą dokładną (Cloppera–Pearsona).
*Przykład:* 102 pracowników poprawiło wynik, 20 pogorszyło, 27 bez zmian; 102/122 = 0,84.
*Skrypt:* `zmiana_osob` (`binomtest`).

### Test rangowanych znaków Wilcoxona
Test nieparametryczny dla danych sparowanych, który oprócz kierunku uwzględnia wielkość zmian. Bezwzględne różnice rangowane są od najmniejszej do największej, a statystyka $W$ porównuje sumy rang różnic dodatnich i ujemnych. Remisy (różnica 0) pominięto.
*Skrypt:* `zmiana_osob` (`wilcoxon`).

### Korelacja rangowo-dwuseryjna (ang. *rank-biserial correlation*)
Miara wielkości efektu dla testu Wilcoxona: $r = \frac{R_+ - R_-}{R_+ + R_-}$, gdzie $R_+$ i $R_-$ to sumy rang różnic dodatnich i ujemnych. Przyjmuje wartości od −1 do 1; 0 oznacza brak przewagi kierunku.
*Przykład:* $r = 0,72$, czyli zmiany dodatnie wyraźnie przeważały pod względem liczby i wielkości.

### Test McNemara
Test dla sparowanych danych binarnych, oparty wyłącznie na parach niezgodnych: $b$ (poprawna → błędna) i $c$ (błędna → poprawna). Statystyka z poprawką na ciągłość: $\chi^2 = \frac{(|b-c|-1)^2}{b+c}$. W artykule test traktuje sekwencje jako niezależne i nie uwzględnia ich zgrupowania w pracownikach, dlatego podano go pomocniczo.
*Skrypt:* `zmiana_osob` (`mcnemar(..., exact=False, correction=True)`).

### Korelacja Pearsona
Miara siły liniowego związku dwóch zmiennych, $r = \frac{\operatorname{cov}(x,y)}{s_x s_y}$, w zakresie od −1 do 1. W artykule użyta jako korelacja pytanie–reszta (zob. dyskryminacja); dla zmiennej binarnej i ciągłej jest równoważna korelacji punktowo-dwuseryjnej.

---

## 5. Obciążenia i analizy wrażliwości

### Ubywanie obserwacji (ang. *attrition*)
Zmniejszanie się liczby sekwencji w kolejnych próbach, ponieważ część pracowników przestaje odpowiadać lub nie otrzymuje kolejnych powtórek. Jeżeli kontynuacja zależy od wyników, krzywa uczenia z wszystkich dostępnych sekwencji może być zniekształcona.

### Obciążenie przeżywalności (ang. *survivorship bias*)
Szczególny przypadek obciążenia wynikającego z ubywania obserwacji: w późniejszych próbach pozostają głównie osoby lepsze lub bardziej zaangażowane, co może dawać pozorny wzrost poprawności bez rzeczywistego uczenia się.

### Obciążenie typu pattern-mixture
Obciążenie powstające, gdy sekwencje o różnej długości różnią się poziomem lub tempem zmian, a krzywa łączy je w jedną. Kontrolowano je, szacując efekt osobno w warstwach długości sekwencji (3–4, 5–7, ≥8 prób); zbliżone OR (1,30; 1,35; 1,40) wskazują, że efekt nie wynika z mieszania sekwencji o różnej długości.

### Kohorta zbalansowana
Stały zbiór sekwencji, które osiągnęły co najmniej 5 prób, obserwowany wyłącznie w próbach 1–5. Każdy punkt krzywej opiera się na tych samych 5187 sekwencjach, co eliminuje wpływ ubywania obserwacji na kształt krzywej.
*Skrypt:* `krzywa_uczenia` (argument `kohorta`).

### Analiza wrażliwości
Powtórzenie głównej analizy przy zmienionych założeniach (inny podzbiór danych, inna metoda estymacji) w celu sprawdzenia, czy wniosek od nich zależy. W artykule wykonano dziesięć specyfikacji efektu numeru próby; OR mieściły się w zakresie 1,29–1,50.
*Skrypt:* `modele` (tabela `wrazliwosc`).

### Efekt sufitowy
Ograniczenie możliwego wzrostu wyniku, gdy jego wartość początkowa jest bliska maksimum. Przy 82,5% poprawnych odpowiedzi w pierwszych próbach zakres poprawy jest niewielki, co zaniża bezwzględne przyrosty i utrudnia wykrycie poprawy w łatwych pytaniach.

---

## 6. Psychometria (klasyczna teoria testu)

### Klasyczna teoria testu (KTT, ang. *classical test theory*)
Podejście do oceny pytań testowych oparte na prostych wskaźnikach obliczanych z odpowiedzi: trudności, dyskryminacji i funkcjonowaniu dystraktorów. Trudność i dyskryminację liczono wyłącznie na pierwszych próbach, aby nie zawyżały ich wcześniejsze powtórki; wskaźniki dystraktorów (udział najczęstszego dystraktora, dystraktory niefunkcjonalne) obliczono na wszystkich odpowiedziach na pytanie.
*Skrypt:* `analiza_pozycji`.

### Trudność pytania
Odsetek poprawnych odpowiedzi na pytanie w pierwszej próbie. Wbrew nazwie wyższa wartość oznacza pytanie łatwiejsze. Pytania z ponad 90% poprawnych odpowiedzi słabo różnicują osoby i pozostawiają mało miejsca na uczenie się.

### Dyskryminacja i korelacja pytanie–reszta (ang. *item–rest correlation*)
Dyskryminacja opisuje, w jakim stopniu pytanie odróżnia osoby o wyższym i niższym poziomie wiedzy. Mierzono ją korelacją Pearsona między poprawnością odpowiedzi na dane pytanie a odsetkiem poprawnych odpowiedzi tej samej osoby na **pozostałe** pytania (wyłączenie bieżącego pytania zapobiega sztucznemu zawyżeniu korelacji). Uwzględniono pracowników z co najmniej 10 pierwszymi próbami i pytania z co najmniej 30 takimi odpowiedziami. Przyjęto progi: $r < 0,20$ dyskryminacja niska, $r \ge 0,30$ dobra.
*Przykład:* mediana korelacji pytanie–reszta wynosi 0,22.

### Dystraktor
Błędna opcja odpowiedzi w pytaniu wielokrotnego wyboru. Znane są tylko dystraktory wybrane co najmniej raz; opcje nigdy niewybrane nie występują w logu.

### Dystraktor niefunkcjonalny
Dystraktor wybierany rzadko, w skrypcie w mniej niż 5% wszystkich odpowiedzi na dane pytanie. Nie przyciąga osób o niepełnej wiedzy, więc w praktyce zmniejsza liczbę realnych opcji i ułatwia zgadnięcie.
*Przykład:* 55,3% zaobserwowanych dystraktorów było niefunkcjonalnych.

### Udział najczęstszego dystraktora
Odsetek błędnych odpowiedzi na pytanie, które przypadają na najczęściej wybierany dystraktor. Wysoka wartość wskazuje, że błędy koncentrują się na jednej opcji, co może oznaczać typowe błędne przekonanie.

### Oczekiwany odsetek ponownego wyboru tego samego dystraktora
Wartość odniesienia dla odsetka przypadków, w których po dwóch kolejnych błędach pracownik wybrał ten sam dystraktor. Policzono dwa warianty:
- **wybór losowy** spośród $k$ zaobserwowanych dystraktorów pytania: $1/k$, uśrednione po przypadkach (47,1%);
- **wybór ważony popularnością**: prawdopodobieństwo, że dwa niezależne błędne wybory trafią w tę samą opcję, $\sum_j p_j^2$, gdzie $p_j$ to udział dystraktora $j$ wśród wszystkich błędów w pytaniu (59,6%).

Zaobserwowane 71,6% przekracza oba warianty, co oznacza powtarzanie konkretnej odpowiedzi ponad to, co wynika z samej popularności dystraktorów.
*Skrypt:* `przejscia`.

---

## Indeks skrótów

| Skrót | Rozwinięcie |
|---|---|
| CI / PU | przedział ufności (ang. *confidence interval*) |
| FDR | odsetek fałszywych odkryć (ang. *false discovery rate*) |
| GEE | uogólnione równania estymujące (ang. *generalized estimating equations*) |
| HLR | half-life regression |
| ICC | współczynnik korelacji wewnątrzklasowej (ang. *intraclass correlation coefficient*) |
| IQR | rozstęp międzykwartylowy (ang. *interquartile range*) |
| KTT | klasyczna teoria testu (ang. *classical test theory*) |
| MAP | maksimum a posteriori |
| OR | iloraz szans (ang. *odds ratio*) |
| PFA | performance factors analysis |
| p.p. | punkt procentowy |
| SD | odchylenie standardowe (ang. *standard deviation*) |
| SE | błąd standardowy (ang. *standard error*) |
