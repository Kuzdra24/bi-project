# Rozpoznanie źródeł danych – wersja techniczna (pełne liczby i szczegóły)

Projekt BI, Grupa 6 – rynek mieszkaniowy: ceny ofertowe vs transakcyjne.
Pomiar: 9.11.2026. Obszar próbki: **Wrocław (TERYT powiatu 0264)**. Okno czasowe: **VIII 2023 – VI 2024**.
Kod: `src/*.py` (każdy skrypt uruchamia się poleceniem `uv run python src/<nazwa>.py`), próbki: `data/sample/`, wykresy: `reports/figures/`.

---

## 0. Najważniejsze wnioski (na slajdy)

1. **Luka ofertowa da się zmierzyć.** We Wrocławiu mediana ceny ofertowej to 12 414 zł/m², a transakcyjnej 10 912 zł/m², czyli **oferty są o ok. 14% droższe niż ceny faktycznych transakcji**. Luka jest największa dla małych mieszkań (<38 m²: +18%) i występuje w każdym miesiącu okna (wykresy 09, 10, 14).
2. **Cztery źródła łączą się przez wspólne wymiary**: czas (miesiąc), obszar (TERYT + siatka 1 km), przedział powierzchni. NBP pokrywa 100% miesięcy, a 75% ofert leży w komórkach siatki, w których jest też ≥10 transakcji.
3. **Wszystko jest sterowane kodem TERYT i datami** (`config.py`), bez nazw dzielnic, więc ten sam kod działa dla innego powiatu lub całej Polski.
4. **Znaleźliśmy realne problemy, także w samych usługach źródłowych**: dwa błędy w usłudze WFS RCN, przeciążone Overpass API, regulaminy portali zakazujące scrapingu oraz wstępnie oczyszczony zbiór ofert.
5. **Zmiana zakresu względem planu.** Planowany scraping ofert okazał się sprzeczny z regulaminami portali, więc użyliśmy otwartego zbioru Kaggle (Apache 2.0). Jego zakres (VIII 2023 – VI 2024) wyznaczył okno czasowe całego projektu.

---

## R1. Źródła

| Źródło | Co mierzy | Dostęp | Format | Licencja / warunki |
|---|---|---|---|---|
| **RCN** – Rejestr Cen Nieruchomości (GUGiK) | ceny **transakcyjne** (akty notarialne) | usługa WFS 2.0 `mapy.geoportal.gov.pl/wss/service/rcn`, bez rejestracji | **tylko GML** (bez GeoJSON i CSV), EPSG:2180 | nieodpłatnie po nowelizacji Prawa geodezyjnego i kartograficznego; ❓ dokładne warunki ponownego wykorzystania do potwierdzenia |
| **Oferty** – Kaggle „Apartment Prices in Poland” (K. Jamroz) | ceny **ofertowe**, cechy mieszkań | pobranie ZIP przez API Kaggle (bez logowania) | CSV, 1 plik = 1 miesięczna migawka | **Apache 2.0**; ❓ autor nie podaje, z jakich portali pochodzą dane |
| **OSM** – OpenStreetMap | otoczenie: komunikacja, zieleń, usługi | plik `.osm.pbf` z Geofabrik (dolnośląskie, 182 MB); alternatywnie Overpass API | PBF (binarny); Overpass: JSON | **ODbL 1.0**: wymagane „© OpenStreetMap contributors”, share-alike dla bazy pochodnej |
| **NBP** – stopy procentowe | koszt pieniądza | pliki XML `static.nbp.pl/dane/stopy/` (bieżący + archiwum) | XML | dane publiczne; ❓ warunki ponownego wykorzystania nie zostały sprawdzone |

**Odrzucone: scraping portali ogłoszeniowych.** Regulaminy (odczyt 9.11.2026) zakazują automatycznego pobierania danych:

| Portal | Zapis |
|---|---|
| Otodom | „Zabrania się […] jakiegokolwiek wykorzystywania tych treści bez pisemnej zgody […]; jakiegokolwiek agregowania i przetwarzania danych […] w celu ich dalszego udostępniania osobom trzecim” |
| Gratka | zakaz „zautomatyzowanych systemów […] do pozyskiwania danych […] do celów komercyjnych (tzw. screen scraping)” |
| Nieruchomości-online (§14a) | zakaz pobierania „przy użyciu programów, skryptów, botów, crawlerów”; wyjątek: „nieistotna część” bazy (art. 7 ustawy o ochronie baz danych) |
| Adresowo | zakaz „parsowania Serwisu przy użyciu botów”; korzystanie „wyłącznie na własny użytek” |
| Domiporta | brak zapisu w regulaminie z 2022 r., ale `robots.txt` blokuje narzędzie `Scrapy` w całym serwisie |
| Morizon | ❓ regulaminu nie udało się odczytać (link w stopce działa tylko w JavaScripcie) |

`robots.txt` Otodom nie blokuje ogłoszeń, ale nie jest to zgoda na wykorzystanie danych. ❓ Otwarte pytanie do prowadzącego: czy mała próbka badawcza (wyjątek z art. 7) jest akceptowalna.

---

## R2. Charakterystyka: wolumen, zakres, częstotliwość zmian, aktualizacja

| | RCN | Oferty (Kaggle) | OSM | NBP |
|---|---|---|---|---|
| Wolumen (Wrocław, okno) | **18 134 lokale**, w tym 14 521 mieszkalnych; ok. 54 MB GML | **20 200 wierszy** = 9 598 unikalnych ofert w 11 migawkach (1 542–2 313 / miesiąc); cała PL: 195 568 wierszy, 15 miast | 8 823 obiekty w 12 kategoriach (z pliku 182 MB dla województwa) | 96 zmian stóp od 1998 r. (37 KB) |
| Zakres czasowy | dowolny (filtr po dacie aktu); dane z 2023 r. i wcześniejsze dostępne | **zamknięty: VIII 2023 – VI 2024** | stan bieżący (plik z 8.11.2026) | 1998-02-26 – 2026-03-05 |
| Częstotliwość zmian | ciągła, z **opóźnieniem**: mediana 57 dni od aktu do wpisu (90% ≤ 118 dni) | brak dalszych aktualizacji | codzienne wydania Geofabrik | nieregularnie, po decyzjach RPP |
| Aktualizacja w systemie | przyrostowo po `DOK_DATA`, ostatnie ~3 miesiące pobierać ponownie (dane spóźnione) | ładowanie jednorazowe; docelowo inne źródło ofert | pełne odświeżenie pliku raz na miesiąc lub kwartał | pobranie całego pliku przy zmianie |

**Aktualność RCN zmierzona na bieżącym oknie (XI 2024 – XI 2026, pierwszy przebieg):** ostatni akt w usłudze pochodzi z 28.09.2026; za X–XI 2026 nie ma ani jednego rekordu, a lipiec–wrzesień 2026 są wyraźnie niepełne (207 lokali we wrześniu wobec ~1 400 średnio). To dowód, że przy aktualizacji trzeba obsłużyć dane spóźnione.

---

## R3. Integracja: relacje i klucze

Oferta i transakcja to **różne zdarzenia bez wspólnego identyfikatora** (RCN jest anonimowy). Łączymy je przez wspólne wymiary.

| Para | Klucz | Wynik testu na próbce |
|---|---|---|
| RCN ↔ Oferty | **TERYT** (oferty: nazwa miasta → TERYT, słownik w `config.py`) + **miesiąc** + **komórka siatki 1 km** (EPSG:2180) + **przedział powierzchni** | 11/11 miesięcy wspólnych; 196 komórek z transakcjami, 206 z ofertami, **86 porównywalnych** (≥10 obserwacji po obu stronach), obejmujących **74,8% ofert** |
| RCN ↔ NBP, Oferty ↔ NBP | miesiąc | **100%** miesięcy ma przypisaną stopę |
| RCN ↔ OSM | współrzędne (EPSG:2180, odległość w metrach) | 4 420 unikalnych lokalizacji RCN; mediana odległości do przystanku 186 m, sklepu 213 m, parku 368 m, szkoły 430 m |
| Oferty ↔ OSM | współrzędne | możliwe (oferty mają lat/lon); zbiór ma też gotowe odległości do POI liczone przez autora |
| Granica obszaru | `teryt:terc` w OSM = `TERYT` w RCN | granica Wrocławia (relacja 451516, `admin_level=6`) znaleziona po samym kodzie |

---

## R4. Czy dane wystarczą do wymagań informacyjnych

| Grupa pytań (dokument „Użytkownik końcowy…”) | Pokrycie | Luki |
|---|---|---|
| **A. Ceny** – średnia/mediana ofertowa i transakcyjna, zestawienie oferta vs transakcja, dynamika, odchylenie oferty od podobnych | ✅ RCN: cena, powierzchnia, data, rynek, lokalizacja; oferty: cena, powierzchnia, pokoje, rok budowy, lokalizacja | **oferty nie mają rodzaju rynku** (pierwotny/wtórny), więc podział rynku działa tylko dla transakcji; okno ofert to tylko 11 miesięcy |
| **B. Potencjał inwestycyjny** – lokalizacje, oferty niedowartościowane | ✅ pochodne z A i C: luka w komórce siatki / przedziale powierzchni; odchylenie oferty od mediany transakcji „podobnych” | brak danych o czynszach w RCN (Kaggle ma osobne pliki z ofertami wynajmu, niesprawdzone) |
| **C. Lokalizacja i otoczenie** – komunikacja, zieleń, usługi, zależność z ceną | ✅ OSM: 12 kategorii, odległości i liczba obiektów w promieniu dla każdego punktu RCN | OSM to stan **bieżący**, a transakcje są z 2023–24 (infrastruktura mogła się zmienić) |
| **D. Makroekonomia** – stopy vs ceny, okresy kosztu finansowania | ✅ NBP: pełna historia stóp, łączenie po miesiącu | w oknie tylko 2 zmiany stopy (6,75 → 6,00 → 5,75%), czyli mało zmienności; ❓ oprocentowanie kredytów (statystyka MIR NBP) niesprawdzone; dłuższą historię da RCN + NBP, ale nie oferty |
| Wymiar „Nieruchomość” (metraż, pokoje, typ budynku, rok, standard) | metraż i pokoje ✅; typ budynku 82%, rok budowy 87% wypełnienia | standard (`condition`) **pusty w 72%** ofert; RCN ma **izby**, nie pokoje (patrz R6) |

---

## R5. Jakość danych

| Wymiar | RCN | Oferty (Kaggle) | OSM | NBP |
|---|---|---|---|---|
| **Kompletność** | kluczowe pola pełne (cena, powierzchnia, data, rynek 100%); `LOK_LICZBA_IZB` brak 19%, `LOK_CENA_BRUTTO` 17%, `LOK_NR_KOND` 4%, adres 2%; pola VAT 100% puste | cena, metraż, pokoje, współrzędne 100%; `condition` brak 72%, `buildingMaterial` 38%, `type` 18%, `floor` 17%, `buildYear` 13% | współrzędne 100%; nazwy: przystanki <1% braków, parki 69%, lasy 99% | stopa referencyjna 100% w oknie; braki stóp depozytowej i dyskontowej przed 2001/2010 to brak strukturalny (stopy nie istniały) |
| **Unikalność** | 0 duplikatów `gid`; **10 mieszkań** zarejestrowanych podwójnie (ten sam lokal, data i cena, różne ID transakcji); 177 „duplikatów” garaży to sprzedaż udziałów w hali garażowej (poprawne) | 0 duplikatów id w migawce; **264 wiersze** to „to samo mieszkanie pod innym id” (te same współrzędne, metraż, piętro i cena) | jeden przystanek zapisany jako `stop_position` + `platform` + `bus_stop`: 5 996 wierszy → 3 991 obiektów → **~1 582 przystanki** po deduplikacji (nazwa + 100 m) | 0 duplikatów |
| **Spójność** | TERYT zgodny z ID lokalu w 100%; 3,1% mieszkań w transakcjach wielolokalowych (mieszkanie + garaż za jedną cenę) | 14,1% ofert zmienia cenę między migawkami (mediana zmiany 3,9%) | 4 030 wierszy to obiekty należące do kilku kategorii | archiwum = plik bieżący (5/5 stóp) |
| **Poprawność formatów** | GML, daty ISO, słowniki camelCase | CSV, liczby z kropką, słowniki angielskie | PBF; 2 wadliwe multipoligony w całym województwie | **przecinek dziesiętny**, BOM UTF-8 |
| **Poprawność wartości** | 117 mieszkań <3 000 zł/m² i 3 >50 000 zł/m² (0,8%); m.in. **cena 1 zł** za 84 m² | 0 wartości poza zakresem: **zbiór jest wstępnie oczyszczony** przez autora (1. percentyl 8 373 zł/m², ostra dolna krawędź rozkładu) | – | – |
| **Aktualność** | opóźnienie wpisu: mediana 57 dni; ostatnie ~3 miesiące niepełne | zbiór zamrożony na VI 2024 | 26% obiektów nie edytowano od >5 lat; ~1 000 obiektów edytowanych ok. 8 lat temu (masowy import) | ⚠️ metadana `data_publikacji` w archiwum = 2015-03-04, choć dane sięgają 2026 |
| **Integralność referencyjna** | 100% współrzędnych w PL; 0 dat poza filtrem; miejscowość w adresie = „Wrocław” w 14 481/14 521 | wszystkie oferty mają miasto ze słownika → TERYT | granica powiatu znaleziona po TERYT | 100% miesięcy RCN i ofert ma stopę |

---

## R6. Problemy i postępowanie

| # | Problem | Konkretny przykład | Skala | Postępowanie |
|---|---|---|---|---|
| 1 | **Błąd usługi RCN:** filtr `PropertyIsLessThan` na dacie działa jak `<=` | filtr „< 2025-04-01” zwracał też akty z 1.04 → 54 zdublowane rekordy, suma miesięcy 29 680 zamiast 29 160 | każdy filtr zakresu dat | zakres jako [pierwszy, ostatni dzień] włącznie + **test kontrolny**: suma miesięcy = wynik dla całego okresu |
| 2 | **Błąd usługi RCN:** parametr `SRSNAME=EPSG:4326` ignorowany | nagłówek deklaruje WGS84, współrzędne w PL-1992: `367505.19 353312.20` | wszystkie rekordy | przeliczenie we własnym zakresie (`pyproj`, EPSG:2180 → 4326) |
| 3 | Transakcje niewolnorynkowe | sprzedaż z bonifikatą (mieszkania komunalne): mediana **1 525 zł/m²**; sprzedaż bezprzetargowa: 8 312 zł/m² | 5,1% mieszkań | **odrzucenie** z analiz cen rynkowych (`TRAN_RODZAJ_TRANS = wolnyRynek`) |
| 4 | Sprzedaż udziałów | udział 71/1 000 000 za 7 600 zł | 1,4% mieszkań | **odrzucenie** (`NIER_UDZIAL = 1/1`) |
| 5 | Cena transakcji obejmuje kilka lokali | mieszkanie + garaż: 600 000 zł za całość, 570 000 zł za mieszkanie | 3,1% mieszkań | cena z `LOK_CENA_BRUTTO`, a tylko gdy jej brak, z `TRAN_CENA_BRUTTO` |
| 6 | Wartości błędne | `TRAN_CENA_BRUTTO = 1` zł za 84 m²; `LOK_CENA_BRUTTO = 903,29` przy cenie transakcji 903 290 zł (zła jednostka) | 120 mieszkań (0,8%) | **kwarantanna**: reguła cena/m² ∉ [3 000; 50 000] |
| 7 | Podwójna rejestracja transakcji | ten sam lokal, 2023-10-17, 1 366 406 zł, dwa różne ID transakcji, wpisy z 27 i 28.11 | 10 mieszkań | **deduplikacja** po (lokal, data, cena) |
| 8 | Izby ≠ pokoje | RCN liczy izby z kuchnią: mediana 1 izba = 32 m², 3 izby = 54 m² | semantyka pola | nie porównujemy z „pokojami” z ofert; do porównań używamy przedziałów powierzchni |
| 9 | Dane osobowe w RCN | `DOK_TWORCA` = imię, nazwisko i adres notariusza | 100% | pole **usuwane przy ładowaniu** |
| 10 | Oferty: to samo mieszkanie pod różnymi id | 2 oferty, ta sama pozycja (51.07905, 17.04037), 84 m², 7. piętro, 750 000 zł | 264 wiersze (1,3%) | **deduplikacja** po (migawka, współrzędne, metraż, piętro, cena) |
| 11 | Oferty: przybliżona geolokalizacja | do **168 ofert** w jednym punkcie (prawdopodobnie środek ulicy lub osiedla) | część ofert | analizy przestrzenne na siatce 1 km, nie na poziomie budynku |
| 12 | Oferty: zbiór wstępnie oczyszczony | 0 ofert poza zakresami; ucięta dolna część rozkładu (<~8–9 tys. zł/m²) | cały zbiór | opisać jako ograniczenie: luka może być **zaniżona lub zawyżona**, bo nie znamy reguł autora |
| 13 | Oferty: brak rodzaju rynku i daty publikacji | rok budowy ≥ rok migawki tylko w 2,5% (słaby zamiennik rynku pierwotnego) | 100% | podział pierwotny/wtórny tylko po stronie RCN; czas oferty = miesiąc migawki |
| 14 | OSM: wielokrotne zapisy przystanków | `stop_position` + `platform` + `bus_stop` dla tego samego przystanku | 5 996 → ~1 582 | deduplikacja (nazwa + 100 m); do liczenia odległości wystarczą surowe punkty |
| 15 | OSM: wadliwe geometrie | relacje 21293193, 21570009 – multipoligon nie do złożenia | 2 w województwie | **odrzucenie** z logowaniem ID |
| 16 | Overpass API przeciążone | HTTP 502 „at capacity, request queue is full” nawet dla zapytania `out count`; instancje zapasowe bez odpowiedzi | 9.11.2026 | przejście na pliki Geofabrik (ten sam OSM, ODbL); Overpass zostaje jako opcja do eksploracji |
| 17 | NBP: nieaktualna metadana | `data_publikacji="2015-03-04"` w archiwum z danymi do 2026 | 1 atrybut | aktualizacja oparta na najnowszym `obowiazuje_od` |

**Narzędzia kontroli jakości:** na tym etapie reguły w pandas (powyższe filtry, testy kontrolne liczności, deduplikacje, zakresy). Docelowo przenosimy je do **testów dbt** (`unique`, `not_null`, `accepted_values` dla słowników RCN, `relationships` dla kluczy TERYT/miesiąc) i/lub Great Expectations / Soda (zakresy cen, odsetek braków, test „suma miesięcy = total”). Rekordy z reguł kwarantanny trafiają do osobnej tabeli zamiast znikać.

---

## R7. Dane surowe i przykładowe zapytania

**RCN – rekord GML (skrócony):**
```xml
<ms:lokale gml:id="lokale.13689671">
  <gml:Point srsName="urn:ogc:def:crs:EPSG::2180"><gml:pos>361084.63 361411.46</gml:pos></gml:Point>
  <ms:TERYT>0264</ms:TERYT>
  <ms:TRAN_RODZAJ_TRANS>wolnyRynek</ms:TRAN_RODZAJ_TRANS>
  <ms:TRAN_RODZAJ_RYNKU>rynekWtorny</ms:TRAN_RODZAJ_RYNKU>
  <ms:TRAN_CENA_BRUTTO>400000</ms:TRAN_CENA_BRUTTO>
  <ms:DOK_DATA><gml:timePosition>2023-09-22</gml:timePosition></ms:DOK_DATA>
  <ms:LOK_FUNKCJA>mieszkalna</ms:LOK_FUNKCJA>
  <ms:LOK_LICZBA_IZB>3</ms:LOK_LICZBA_IZB>
  <ms:LOK_NR_KOND>10</ms:LOK_NR_KOND>
  <ms:LOK_POW_UZYT>37</ms:LOK_POW_UZYT>
  <ms:LOK_ADRES>MSC:Wrocław;UL:Wincentego Stysia;NR_PORZ:20a</ms:LOK_ADRES>
</ms:lokale>
```
Zapytanie o liczbę rekordów (bez pobierania danych):
```
GET mapy.geoportal.gov.pl/wss/service/rcn?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature
    &TYPENAMES=ms:lokale&RESULTTYPE=hits
    &FILTER=  TERYT = '0264' AND DOK_DATA >= '2024-01-01' AND DOK_DATA <= '2024-01-31' AND LOK_FUNKCJA = 'mieszkalna'
→ numberMatched="1624"
```

**Oferty – wiersz CSV (`apartments_pl_2024_06.csv`, inne miasto, nagłówek skrócony):**
```
id,city,type,squareMeters,rooms,floor,floorCount,buildYear,latitude,longitude,centreDistance,poiCount,...,ownership,buildingMaterial,condition,...,price
811891f98a870dfd6e414374a0a85560,szczecin,blockOfFlats,47.0,2.0,6.0,12.0,1981.0,53.4285438,14.5528116,0.79,67.0,...,condominium,concreteSlab,,...,449000
```
Ta sama oferta w kolejnych migawkach, ze zmianą ceny:
```
id 000967d7…  2024-02: 695 000 | 2024-03: 695 000 | 2024-04: 695 000 | 2024-05: 685 000 | 2024-06: 685 000  (53 m²)
```

**OSM – wybór obszaru po TERYT (Overpass QL; ta sama logika w odczycie PBF):**
```
rel["boundary"="administrative"]["admin_level"="6"]["teryt:terc"="0264"]; map_to_area->.a;
nwr["highway"="bus_stop"](area.a);
```

**NBP – fragment archiwum XML:**
```xml
<pozycje obowiazuje_od="2026-03-05">
    <pozycja id="ref" oprocentowanie="3,75" />
    <pozycja id="lom" oprocentowanie="4,25" />
</pozycje>
```

---

## Wykresy (`reports/figures/`)

| Plik | Co pokazuje | Do slajdu |
|---|---|---|
| `09_oferta_vs_transakcja_powierzchnia.png` | **główny wynik**: mediana ceny/m² oferta vs transakcja w 5 przedziałach powierzchni, luka +13…+18% | domena / sens projektu |
| `10_oferta_vs_transakcja_w_czasie.png` | obie mediany miesięcznie + stopa NBP (łączenie po miesiącu) | integracja, makro |
| `14_luka_siatka_1km.png` | mapa siatki 1 km: luka w 86 komórkach porównywalnych | integracja przestrzenna |
| `01_rcn_cena_m2_hist.png` | rozkład ceny transakcyjnej/m² (RCN, po czyszczeniu) | eksploracja |
| `02_rcn_transakcje_miesiecznie.png` | liczba transakcji miesięcznie (wszystkie vs mieszkalne) | wolumen |
| `03_rcn_braki_pol.png` | kompletność pól RCN | jakość |
| `11_rcn_opoznienie_rejestracji.png` | opóźnienie wpisu do RCN (mediana 57 dni) | aktualność |
| `04_oferty_cena_m2_hist.png` | rozkład ceny ofertowej/m² (migawka VI 2024), widoczna ucięta dolna krawędź | eksploracja / problem 12 |
| `05_oferty_braki_pol.png` | kompletność pól ofert (`condition` 72% braków) | jakość |
| `13_oferty_trwalosc_w_migawkach.png` | w ilu migawkach pojawia się ta sama oferta | unikalność / snapshoty |
| `06_nbp_stopa_referencyjna.png` | stopa referencyjna 2019–2026 z zaznaczonym oknem | makro |
| `07_osm_obiekty_kategorie.png` | liczba obiektów OSM w 12 kategoriach | otoczenie |
| `08_osm_rcn_odleglosci.png` | odległość mieszkanie → najbliższy przystanek/park/sklep/szkoła | integracja RCN ↔ OSM |
| `12_osm_aktualnosc_edycji.png` | czas od ostatniej edycji obiektów OSM | aktualność OSM |

---

## Otwarte kwestie (❓)

- Prowadzący: czy mała próbka scrapingu (wyjątek z art. 7 ustawy o ochronie baz danych) jest akceptowalna. Od tego zależy źródło **aktualnych** ofert.
- Warunki ponownego wykorzystania danych RCN i NBP (licencja formalna).
- Statystyka oprocentowania kredytów mieszkaniowych NBP (MIR): niesprawdzona.
- RCN `ms:budynki` (rok budowy?) i `ms:dzialki`: niesprawdzone.
- Morizon: regulamin nieodczytany.
- Kaggle: pliki z ofertami **wynajmu** (XI 2023 – VI 2024) są w paczce, ale nie zostały przeanalizowane.
- Overpass API: ponowna próba w innym terminie (skrypt: `uv run python src/osm_sample.py overpass`).
