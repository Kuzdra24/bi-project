# PLAN – etap rozpoznania źródeł danych

Projekt BI, Grupa 6: analiza rynku mieszkaniowego (ceny ofertowe vs transakcyjne).

**Cel etapu:** pobrać z każdego źródła **małą próbkę**, potwierdzić sposób dostępu i format, ocenić jakość danych oraz to, czy źródła da się ze sobą łączyć.
**Produkt końcowy:** **krótki raport (`reports/RAPORT.md`) + ok. 8–10 wykresów PNG**, przekazane osobie, która składa prezentację. Raport ma być gotowy do przeniesienia na slajdy: krótkie akapity, tabele z liczbami, podpisane wykresy.
**Poza zakresem:** pełne pobieranie, staging, hurtownia, dbt, orkiestracja i dashboardy. To robimy na późniejszych etapach.

## Za co odpowiada nasza część

Pokrywamy **stronę danych** z wymagań prezentacji. Część o domenie, użytkownikach i pytaniach analitycznych jest już opisana w dokumentach grupy („Źródła danych”, „Użytkownik końcowy i wymagania OLAP”). Odwołujemy się do niej tylko tam, gdzie trzeba uzasadnić wystarczalność danych.

| Wymaganie z prezentacji | Gdzie w raporcie | Skąd bierzemy treść |
|---|---|---|
| Wykaz źródeł, formaty, sposób pozyskania, licencje | R1. Źródła | sekcje 1–4 planu (dostęp, licencja) |
| Wolumen, zakres czasowy, częstotliwość zmian, możliwości aktualizacji | R2. Charakterystyka | liczby z próbek + „częstotliwość zmian” per źródło |
| Relacje między źródłami i klucze integracyjne | R3. Integracja | sekcja 5 (test łączenia na próbkach) |
| Uzasadnienie, że dane wystarczą do wymagań informacyjnych | R4. Pokrycie wymagań | tabela: pytania A–D → miary/wymiary → pola źródłowe |
| Ocena jakości: kompletność, unikalność, spójność, poprawność formatów, aktualność, integralność referencyjna | R5. Jakość danych | jedna tabela 6 wymiarów × 4 źródła, z liczbami |
| Wyniki profilowania (liczby, wykresy) | R5 + wykresy | `reports/figures/` |
| Problemy + sposób postępowania (czyszczenie / uzupełnianie / odrzucanie / kwarantanna) | R6. Problemy i postępowanie | tabela: problem → przykład → liczba rekordów → akcja |
| Narzędzia kontroli jakości (użyte / planowane) | R6 | asercje pandas teraz; dbt tests / Great Expectations docelowo |
| Przykłady surowych danych, wstępna eksploracja (zapytania, rozkłady) | R7. Dane surowe | 2–3 rekordy z każdego źródła + użyte zapytania (WFS, Overpass, URL) |
| Rzeczywiste problemy na konkretnych przykładach | R6 + R7 | konkretne rekordy (np. transakcja za 1 zł, duplikat ogłoszenia) |

## Ustalony zakres

| Parametr | Decyzja |
|---|---|
| Geografia | **jedno miasto**: ❓ *do wskazania* (najlepiej miasto na prawach powiatu, wtedy w RCN to jeden kod TERYT) |
| Czas | **ostatnie ~2 lata** (ok. XI 2024 – XI 2026) |
| Oferty | **scraping portalu ogłoszeniowego** |
| Środowisko | **Python + uv** |

Legenda: ✅ sprawdzone 9.11.2026 · ❓ niewiadoma do zweryfikowania w kodzie lub w dokumentach

---

## 0. Środowisko (pusty folder → gotowy projekt)

1. `uv init` z Pythonem 3.12, plik `pyproject.toml` i `uv.lock` w repozytorium, żeby cała grupa miała identyczne wersje.
2. Minimalne zależności (bez ciężkich bibliotek GIS na tym etapie):
   - `requests`, `lxml`: pobieranie danych z WFS, XML i HTML
   - `pandas`, `pyarrow`: profilowanie danych, zapis próbek do Parquet/CSV
   - `matplotlib`: proste wykresy na prezentację
   - `beautifulsoup4`: parsowanie stron z ogłoszeniami
   - `jupyter`: notebooki do eksploracji
   - ewentualnie `geopandas`/`shapely`, ale tylko jeśli odległości RCN↔OSM okażą się zbyt uciążliwe do policzenia ręcznie (np. wzorem haversine)
3. `git init` i `.gitignore` (ignorujemy `data/raw/`, `.venv/`, checkpointy notebooków).
4. Struktura katalogów:
   ```
   projekt/
   ├── PLAN.md
   ├── pyproject.toml
   ├── config.py              # miasto, TERYT, bbox, zakres dat – jedno miejsce
   ├── src/                   # skrypty pobierające próbki (po jednym na źródło)
   ├── notebooks/             # 01_nbp, 02_rcn, 03_osm, 04_oferty, 05_integracja
   ├── data/raw/<źródło>/     # surowe odpowiedzi (nie commitujemy)
   ├── data/sample/           # oczyszczone próbki (CSV/Parquet)
   └── reports/
       ├── figures/           # PNG na slajdy
       └── RAPORT.md          # krótki raport dla osoby składającej prezentację
   ```

Kolejność prac (od najprostszego do najbardziej ryzykownego): **NBP → RCN → OSM → oferty → integracja → podsumowanie**.

---

## 1. NBP: stopy procentowe i wskaźniki

**Dostęp i format**
- ✅ Bieżące stopy NBP to plik XML `https://static.nbp.pl/dane/stopy/stopy_procentowe.xml`. Zawiera stopę referencyjną, lombardową, depozytową, redyskontową i dyskontową oraz atrybuty `oprocentowanie` (przecinek dziesiętny!) i `obowiazuje_od`. Ostatnia publikacja: 2026-03-05, stopa referencyjna 3,75%.
- ✅ Historia zmian to plik XML `https://static.nbp.pl/dane/stopy/stopy_procentowe_archiwum.xml` (ok. 37 KB, HTTP 200).
- ❓ Oprocentowanie kredytów mieszkaniowych: NBP publikuje statystykę stóp procentowych banków (MIR), prawdopodobnie jako XLSX. Adresu i struktury pliku jeszcze nie sprawdziliśmy.
- ❓ „Baza cen nieruchomości mieszkaniowych” NBP: dane kwartalne, **zagregowane**. Nie nadaje się na fakt, ale może posłużyć jako punkt odniesienia do kontroli naszych median. Do sprawdzenia: link, format i zakres miast.
- `api.nbp.pl` obsługuje kursy walut i ceny złota, **nie** stopy procentowe, więc w tym etapie z niego nie korzystamy.
- Licencja: ❓ dane są publicznie dostępne na stronie NBP. Warunki ponownego wykorzystania sprawdzimy w stopce/regulaminie strony nbp.pl.

**Częstotliwość zmian:** stopy zmieniają się nieregularnie, po decyzjach RPP (posiedzenia mniej więcej raz w miesiącu), a zmiany są rzadkie. Aktualizacja jest więc tania: wystarczy sprawdzać `data_publikacji` w pliku.

**Próbka:** całe archiwum stóp (jest małe), przycięte do ostatnich ~2 lat + kontekst wcześniejszy. Do tego jeden plik MIR, jeśli go znajdziemy.

**Co sprawdzamy**
- parsowanie formatu: przecinek dziesiętny, daty, kodowanie (plik ma BOM UTF-8)
- ciągłość: przejście ze zdarzeń „stopa obowiązuje od” na szereg miesięczny, potrzebny wymiar czasu
- zgodność wartości z archiwum vs pliku bieżącego (spójność)

**Wykres na prezentację:** linia schodkowa stopy referencyjnej w czasie.

**Ryzyka:** niewielkie. Przy wymaganiu D2 („okresy różnych kosztów finansowania”) ryzykiem jest brak łatwo dostępnych danych o oprocentowaniu kredytów.

---

## 2. RCN: Rejestr Cen Nieruchomości (ceny transakcyjne)

**Dostęp i format**
- ✅ Usługa WFS: `https://mapy.geoportal.gov.pl/wss/service/rcn`. GetCapabilities zwraca warstwy `ms:lokale`, `ms:budynki`, `ms:dzialki`, `ms:powiaty`.
- ✅ Warstwa `ms:lokale` (DescribeFeatureType) zawiera m.in.: `GEOMETRIA` (punkt), `TERYT`, `TRAN_RODZAJ_TRANS`, `TRAN_RODZAJ_RYNKU` (*opcjonalne*), `TRAN_SPRZEDAJACY`, `TRAN_KUPUJACY`, `TRAN_CENA_BRUTTO`, `DOK_DATA` (data aktu), `NIER_PRAWO`, `NIER_UDZIAL`, `LOK_FUNKCJA`, `LOK_LICZBA_IZB` (*opcj.*), `LOK_NR_KOND` (piętro, *opcj.*), `LOK_POW_UZYT`, `LOK_CENA_BRUTTO` (*opcj.*), `LOK_ADRES` (*opcj.*).
- Alternatywa: pobieranie masowe w Geoportalu („Dane do pobrania → Dane powiatowe → Transakcje”, wg komunikatu GUGiK). Format z interfejsu ❓.
- Licencja: według komunikatów GUGiK dane RCN są udostępniane **nieodpłatnie** po nowelizacji Prawa geodezyjnego i kartograficznego. ❓ Do sprawdzenia: dokładne warunki ponownego wykorzystania oraz to, czy pełny zakres danych jest już dostępny dla naszego powiatu (źródła różnie podają liczbę zasilonych powiatów: ok. 320, potem 362).
- ❓ Limity WFS: maksymalna liczba obiektów na żądanie, stronicowanie (`count`/`startIndex`), dostępne `outputFormat` (domyślnie GML; czy jest GeoJSON?), filtrowanie po dacie po stronie serwera.

**Częstotliwość zmian:** rejestr jest zasilany na bieżąco przez starostwa, ale z opóźnieniem względem daty aktu (❓ ile miesięcy; zmierzymy to na próbce). Do aktualizacji potrzebne będą ładowanie przyrostowe po `DOK_DATA` / `TRAN_WERSJA_ID` i obsługa danych spóźnionych, czyli ponowne pobieranie ostatnich miesięcy.

**Próbka:** `GetFeature` dla `ms:lokale` w obrębie bbox wybranego miasta (lub filtrowane po TERYT). Bierzemy kilkaset–kilka tysięcy rekordów z ostatnich ~2 lat. Do tego mały wycinek `ms:budynki`, żeby sprawdzić, czy jest tam rok budowy lub liczba kondygnacji (atrybuty „nieruchomości” z wymagań).

**Co sprawdzamy**
- **kompletność:** % braków w polach opcjonalnych, zwłaszcza `TRAN_RODZAJ_RYNKU` (kluczowe dla podziału pierwotny/wtórny), `LOK_LICZBA_IZB`, `LOK_CENA_BRUTTO`, `LOK_ADRES`
- **poprawność:** `LOK_FUNKCJA` ograniczona do lokali mieszkalnych. Rozkład ceny za m² i wartości odstające (cena 1 zł, darowizny, transakcje rodzinne). Powierzchnie 0 lub nierealne.
- **unikalność:** jedna transakcja obejmująca kilka lokali (ta sama `TRAN_OZNACZENIE_TRANS`), co rodzi pytanie, którą cenę dzielimy przez powierzchnię: `TRAN_CENA_BRUTTO` czy `LOK_CENA_BRUTTO`
- **spójność:** sprzedaż udziałów (`NIER_UDZIAL` ≠ 1/1), rodzaje praw (własność vs spółdzielcze)
- **aktualność:** liczba transakcji per miesiąc. Spodziewamy się „ogona” w ostatnich miesiącach, bo starostwo wprowadza akty z opóźnieniem.
- **dane osobowe:** jakie wartości mają `TRAN_SPRZEDAJACY`/`KUPUJACY` (oczekujemy kategorii typu „osoba fizyczna”, ❓)

**Wykresy:** histogram ceny/m², transakcje per miesiąc, % braków per pole, punkty transakcji na tle bbox miasta.

**Ryzyka:** opóźnienie zasilania rejestru; luki w danych z konkretnego powiatu; brak rodzaju rynku w części rekordów; GML trudniejszy w parsowaniu niż JSON.

---

## 3. OpenStreetMap: otoczenie (komunikacja, zieleń, usługi)

**Dostęp i format**
- **Overpass API** (`overpass-api.de`): zapytania per kategoria w bbox miasta, wynik w JSON. Wiki OSM sugeruje dla publicznej instancji orientacyjnie <10 000 zapytań i <1 GB dziennie. Przy jednym mieście wystarczy kilka zapytań, więc limit nas nie dotyczy. Po odpowiedzi 429 robimy przerwę.
- Na później (pełny zakres): ekstrakty Geofabrik `.osm.pbf` (Polska / województwa). W tym etapie ich nie pobieramy.
- Licencja: **ODbL 1.0**. Wymagane jest uznanie autorstwa („© OpenStreetMap contributors”), a baza pochodna podlega share-alike. Trzeba o tym wspomnieć na slajdzie.

**Częstotliwość zmian:** dane są edytowane w sposób ciągły, ale infrastruktura miasta zmienia się wolno. Odświeżanie raz na miesiąc lub kwartał w zupełności wystarczy.

**Próbka:** obiekty w bbox wybranego miasta, osobne zapytanie dla każdej kategorii:
- komunikacja: `public_transport=platform|stop_position`, `highway=bus_stop`, `railway=tram_stop|station|halt`
- zieleń: `leisure=park`, `landuse=forest|grass`
- usługi: `shop=supermarket|convenience`, `amenity=school|kindergarten|clinic|doctors|pharmacy`
- (opcjonalnie) czynniki negatywne, np. `landuse=industrial`, główne drogi

**Co sprawdzamy**
- liczba obiektów per kategoria (czy pokrycie miasta jest sensowne)
- **duplikaty:** ten sam przystanek jako `stop_position` + `platform` + `bus_stop`; park jako `way` i jako `relation`
- **kompletność tagów:** np. % przystanków bez `name`
- geometria: dla obiektów powierzchniowych bierzemy centroid
- test łączenia: dla 100 punktów z RCN liczymy odległość do najbliższego przystanku/parku i liczbę obiektów w promieniu 500 m

**Wykresy:** liczba obiektów per kategoria; rozkład odległości „transakcja → najbliższy przystanek”.

**Ryzyka:** niejednolite tagowanie, duplikaty, a także to, że OSM to stan *bieżący*, nie historyczny (transakcje sprzed 2 lat oceniamy według dzisiejszej infrastruktury). To ograniczenie opiszemy na prezentacji.

---

## 4. Oferty: scraping portalu ogłoszeniowego

**Dostęp i format**
- Kandydat główny: **Otodom** (największy wolumen). Alternatywy: Morizon, Gratka, OLX nieruchomości.
- ✅ `otodom.pl/robots.txt` nie blokuje stron wyników (`/pl/wyniki/...`) ani ogłoszeń; blokuje m.in. `/api/query` (z wyjątkiem `?crawl=true`), `/oferta/kontakt/`, widok mapy `?map=1`. Strona wyników dla Krakowa zwraca HTTP 200.
- ❓ **Regulamin serwisu:** nie udało się go odczytać automatycznie (strona pomocy przekierowuje do logowania). **Zanim napiszemy scraper, ktoś z grupy musi przeczytać aktualny regulamin** i sprawdzić zapisy o automatycznym pobieraniu danych i o prawie do bazy danych. Jeśli scraping jest zakazany, przechodzimy na inny portal albo na gotowy zbiór (np. Kaggle).
- ❓ Format: hipoteza do sprawdzenia jest taka, że strony Otodom (Next.js) zawierają dane ogłoszeń w osadzonym JSON (`__NEXT_DATA__`). Wtedy parsujemy JSON, a nie HTML. Nie zweryfikowaliśmy tego.
- Zasady pobierania: niewielka liczba żądań, przerwa 2–3 s, identyfikujący User-Agent, bez logowania i bez danych kontaktowych ogłoszeniodawców (RODO). Zapisujemy surowe odpowiedzi, żeby nie odpytywać portalu ponownie.

**Częstotliwość zmian:** bardzo wysoka. Oferty pojawiają się, znikają i zmieniają cenę codziennie. Historię da się budować tylko przez cykliczne migawki (np. raz w tygodniu) z datą pobrania. To argument za podejściem przyrostowym w dalszym etapie.

**Próbka:** ~200–500 ofert sprzedaży mieszkań z wybranego miasta (kilka–kilkanaście stron wyników), opcjonalnie szczegóły ~50 ogłoszeń.

**Co sprawdzamy**
- jakie pola są dostępne: cena, cena/m², powierzchnia, pokoje, piętro, rok budowy, rynek (pierwotny/wtórny), stan wykończenia, typ budynku, lokalizacja (dzielnica? współrzędne? czy dokładne, czy przybliżone?), data publikacji
- **kompletność** per pole, **poprawność** (cena/m² = cena / powierzchnia?), wartości odstające
- **duplikaty:** to samo mieszkanie wystawione przez kilku pośredników, ogłoszenia „podbijane”
- oferty deweloperskie z ceną „od” lub bez ceny („zapytaj o cenę”)

**Wykresy:** histogram ceny/m², liczba ofert per dzielnica, % braków per pole.

**Ryzyka (najwyższe ze wszystkich źródeł)**
- regulamin lub prawo do bazy danych mogą zabraniać scrapingu (decyzja prawna, nie techniczna)
- **brak historii:** scraping daje tylko *bieżący* stan ofert. Zakresu „ostatnie 2 lata” nie odtworzymy dla ofert, a jedynie dla transakcji (RCN) i stóp (NBP). Historię ofert zbudujemy dopiero przez cykliczne pobieranie (podejście przyrostowe w dalszym etapie). Do decyzji: czy uzupełniamy ją gotowym zbiorem historycznym.
- zabezpieczenia antybotowe, zmiany struktury strony
- lokalizacja może być przybliżona lub ukryta

---

## 5. Integracja źródeł: test łączenia na próbkach

Między ofertami a transakcjami **nie ma wspólnego klucza**: to różne zdarzenia, a anonimowy RCN nie wskaże konkretnego ogłoszenia. Łączymy je więc przez wymiary wspólne.

| Para źródeł | Klucz łączenia | Co sprawdzamy |
|---|---|---|
| RCN ↔ NBP | data (`DOK_DATA` → miesiąc) | czy każdy miesiąc ma przypisaną stopę |
| Oferty ↔ NBP | data pobrania / publikacji → miesiąc | j.w. |
| RCN ↔ OSM | współrzędne punktu | odległości, liczba obiektów w promieniu |
| Oferty ↔ OSM | współrzędne (jeśli są) | j.w.; dokładność lokalizacji ofert |
| Oferty ↔ RCN | **lokalizacja (dzielnica / siatka) + przedział metrażu + liczba pokoi + okres** | czy w tych samych „koszykach” jest dość rekordów z obu stron, by porównać mediany ceny/m² |

Kluczowy test pod temat projektu: dla 2–3 dzielnic porównujemy **medianę ceny/m² z ofert** (stan dziś) z **medianą z transakcji** (ostatnie miesiące). Trzeba też ustalić, jak przypisać dzielnicę do punktu RCN. ❓ Opcje: granice dzielnic z OSM (`admin_level`) albo pole adresu.

**Wykres na prezentację:** słupki „oferta vs transakcja” ceny/m² per dzielnica. To pierwszy dowód, że luka ofertowa da się zmierzyć.

---

## 6. Wynik etapu: raport + wykresy dla osoby składającej prezentację

**`reports/RAPORT.md`**, docelowo 3–5 stron, sekcje R1–R7 z tabeli „Za co odpowiada nasza część”:
- R1 Źródła: jedna tabela (źródło, co mierzy, dostęp, format, licencja)
- R2 Charakterystyka: wolumen próbki, zakres dat, częstotliwość zmian, możliwość aktualizacji
- R3 Integracja: schemat powiązań + tabela kluczy + wynik testu łączenia (ile rekordów udało się połączyć)
- R4 Pokrycie wymagań: grupy pytań A–D (ceny, potencjał, otoczenie, makro) → które pola z których źródeł je obsługują, z uczciwym wskazaniem luk (np. brak historii ofert, brak rodzaju rynku w części RCN)
- R5 Jakość danych: tabela 6 wymiarów jakości × 4 źródła z konkretnymi liczbami
- R6 Problemy i postępowanie: problem → konkretny przykład → skala → akcja (czyszczenie / uzupełnianie / odrzucenie / kwarantanna); narzędzia: asercje pandas teraz, dbt tests / Great Expectations docelowo
- R7 Dane surowe: po 2–3 rekordy z każdego źródła + zapytania, którymi je pobraliśmy
- na końcu krótka lista otwartych kwestii (❓ nierozstrzygnięte)

**`reports/figures/`**: proste i czytelne wykresy PNG z podpisami, gotowe do wklejenia na slajd:
1. RCN – histogram ceny/m²
2. RCN – liczba transakcji per miesiąc (widać opóźnienie zasilania)
3. RCN – % braków per pole
4. Oferty – histogram ceny/m²
5. Oferty – % braków per pole
6. NBP – stopa referencyjna w czasie (wykres schodkowy)
7. OSM – liczba obiektów per kategoria
8. OSM↔RCN – rozkład odległości do najbliższego przystanku
9. **Oferta vs transakcja – mediana ceny/m² per dzielnica** (główny wykres pod temat projektu)
10. (opcjonalnie) mapa punktów transakcji i ofert w mieście

Kod (skrypty + notebooki) zostaje w repozytorium jako dowód, że liczby są powtarzalne, ale odbiorca raportu nie musi go uruchamiać.

---

## Decyzje potrzebne przed startem

1. **Które miasto?** Kryteria: miasto na prawach powiatu (jeden TERYT w RCN), duży wolumen ofert. Kandydaci: Warszawa, Kraków, Wrocław, Poznań, Gdańsk, Łódź.
2. **Regulamin portalu:** kto z grupy go sprawdza i co robimy, jeśli scraping jest zabroniony (inny portal czy gotowy zbiór)?
3. **Historia ofert:** akceptujemy, że oferty to tylko bieżący stan (porównanie z ostatnimi miesiącami RCN), czy szukamy dodatkowo zbioru historycznego?

---

## Zmiany względem planu (9.11.2026)

| Plan | Realizacja | Powód |
|---|---|---|
| Jedno miasto – do wskazania | **Wrocław (TERYT 0264)**; zakres sterowany tylko kodami TERYT w `config.py` | decyzja grupy; kod ma działać dla całej Polski |
| Okno: ostatnie ~2 lata (XI 2024 – XI 2026) | **VIII 2023 – VI 2024** | jedyne legalnie dostępne dane ofertowe (Kaggle) obejmują ten okres |
| Oferty: scraping portalu | **Kaggle „Apartment Prices in Poland” (Apache 2.0)** | regulaminy Otodom, Gratki, Nieruchomości-online i Adresowo zakazują automatycznego pobierania (szczegóły: `reports/RAPORT.md`, R1) |
| OSM: Overpass API | **plik `.osm.pbf` z Geofabrik** (Overpass zostaje jako opcja w skrypcie) | Overpass przeciążony (HTTP 502), serwer zaleca własną instancję do automatycznego użycia |
| RCN: próbka kilkaset–kilka tysięcy rekordów | **pełne okno dla Wrocławia** (18 134 lokale, ok. 54 MB) | mała, nielosowa próbka (150 / miesiąc) dawała tylko 25 porównywalnych komórek siatki; pełne okno daje 86 |
| Wynik: `reports/RAPORT.md` + wykresy | zgodnie z planem: raport R1–R7 + 14 wykresów | – |
