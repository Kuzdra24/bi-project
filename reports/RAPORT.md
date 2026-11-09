# Rozpoznanie źródeł danych – raport

**Projekt BI, Grupa 6 – analiza rynku mieszkaniowego: ceny ofertowe vs ceny transakcyjne**
Etap: weryfikacja źródeł danych (przed budową hurtowni). Stan na 9.11.2026.

---

## Jak korzystać z tego dokumentu

Raport podsumowuje, co ustaliliśmy o naszych źródłach danych. Jest napisany tak, żeby dało się z niego bezpośrednio złożyć część prezentacji o **domenie i danych**.

- **Rozdział 1** – najważniejsze wnioski w pięciu zdaniach. Jeśli masz minutę, przeczytaj tylko ten rozdział.
- **Rozdział 2** – **gotowy plan slajdów**: przy każdym slajdzie podajemy, co na nim pokazać, co powiedzieć i który wykres wkleić.
- **Rozdziały 3–8** – szczegóły i uzasadnienia, gdyby ktoś zadał pytanie.
- **Słowniczek** na końcu wyjaśnia skróty i pojęcia (RCN, TERYT, mediana itd.).

Część o **architekturze rozwiązania** (przepływ danych, narzędzia, aktualizacja) jest w osobnym pliku `reports/ARCHITEKTURA.md`.

Wszystkie wykresy są w folderze `reports/figures/`, mają numer w nazwie i są gotowe do wklejenia na slajd. Pełne liczby i szczegóły techniczne są w pliku `reports/RAPORT_techniczny.md`.

---

## 1. Najważniejsze w pięciu zdaniach

1. **Oferty mieszkań są średnio o ok. 14% droższe niż ceny, za które mieszkania faktycznie się sprzedają.** We Wrocławiu (VIII 2023 – VI 2024) mediana ceny ofertowej wynosiła 12 414 zł/m², a transakcyjnej 10 912 zł/m². To pokazuje, że temat naszego projektu, czyli różnica między ceną z ogłoszenia a ceną z aktu notarialnego, ma pokrycie w danych.
2. **Wszystkie cztery źródła da się ze sobą połączyć**: według miesiąca, miejsca i metrażu.
3. **Wybór zakresu działa ogólnie.** Obszar wybieramy kodem TERYT, a nie nazwami dzielnic, więc ten sam kod zadziała dla innego miasta albo całej Polski.
4. **W danych są realne problemy**, które opisaliśmy z przykładami, np. transakcja za 1 zł, ta sama sprzedaż zapisana dwa razy i błędy w samej usłudze rządowej.
5. **Musieliśmy zmienić plan:** regulaminy portali ogłoszeniowych zabraniają pobierania danych automatem, więc oferty wzięliśmy z otwartego zbioru na licencji Apache 2.0. To ten zbiór wyznaczył okres analizy.

---

## 2. Proponowany plan slajdów

Kolejność odpowiada wymaganiom z dokumentu „Wymagany zakres prezentacji” (część 1: domena i dane). Przy każdym slajdzie: **co pokazać**, **co powiedzieć** i **skąd wziąć liczby**.

### Slajd 1 – Skąd bierzemy dane

**Co pokazać:** tabelę czterech źródeł (poniżej), bez wykresu. Można dodać logo każdego źródła.

| Pytanie | Źródło | Jak pobieramy | Format |
|---|---|---|---|
| Za ile **naprawdę** sprzedano? | **RCN** – Rejestr Cen Nieruchomości (Geoportal, GUGiK) | usługa internetowa WFS | GML (odmiana XML) |
| Za ile **chcieli** sprzedać? | **Oferty** – zbiór Kaggle „Apartment Prices in Poland” | plik ZIP z CSV | CSV |
| Co jest **w okolicy**? | **OpenStreetMap** (przez serwis Geofabrik) | plik z mapą województwa | PBF |
| Jak **drogi był pieniądz**? | **NBP** – stopy procentowe | plik XML ze strony NBP | XML |

**Co powiedzieć:**
- Mamy cztery źródła w czterech różnych formatach, co spełnia wymóg „co najmniej dwóch źródeł”.
- Wszystkie są darmowe i nie wymagają logowania.
- Licencje: oferty – Apache 2.0, OpenStreetMap – ODbL (trzeba podpisać „© OpenStreetMap contributors”), RCN i NBP – dane publiczne.

### Slajd 2 – Dlaczego nie scraping portali (zmiana planu)

**Co pokazać:** cytat z regulaminu Otodom i krótką listę portali.

> „Zabrania się w szczególności: a. jakiegokolwiek wykorzystywania tych treści bez pisemnej zgody uprawnionych; b. jakiegokolwiek agregowania i przetwarzania danych […] w celu ich dalszego udostępniania osobom trzecim […]”
> – Regulamin Otodom (od 17.02.2024)

| Portal | Czy pozwala pobierać dane automatem? |
|---|---|
| Otodom | nie – zakaz wykorzystywania treści bez zgody |
| Gratka | nie – zakaz „screen scrapingu” |
| Nieruchomości-online | nie – zakaz botów i crawlerów (wyjątek: „nieistotna część” bazy) |
| Adresowo | nie – zakaz „parsowania przy użyciu botów” |
| Domiporta | regulamin milczy, ale strona blokuje popularne narzędzie do scrapingu (Scrapy) |

**Co powiedzieć:**
- W pierwotnym planie oferty mieliśmy pobierać z portali. Zanim napisaliśmy jakikolwiek kod, sprawdziliśmy regulaminy, a cztery z pięciu odczytanych wprost tego zabraniają.
- Dlatego użyliśmy gotowego, otwartego zbioru z Kaggle. Ma on jednak zamknięty okres (VIII 2023 – VI 2024) i to on wyznaczył okno czasowe całej analizy.
- To dobry przykład realnego ryzyka projektu: dostępność danych to nie tylko kwestia techniczna, ale też prawna.

### Slajd 3 – Ile mamy danych i jak często się zmieniają

**Co pokazać:** wykres `02_rcn_transakcje_miesiecznie.png` i tabelę poniżej.

| | Transakcje (RCN) | Oferty (Kaggle) | Otoczenie (OSM) | Stopy (NBP) |
|---|---|---|---|---|
| Ile (Wrocław, VIII 2023 – VI 2024) | 18 134 lokale, z czego 14 521 mieszkań | 9 598 ofert (20 200 wierszy w 11 miesięcznych „migawkach”) | 8 823 obiekty (przystanki, parki, sklepy…) | 96 zmian stóp od 1998 r. |
| Jak często się zmienia | na bieżąco, ale z opóźnieniem ok. 2 miesięcy | zbiór zamknięty, nie jest aktualizowany | codziennie | kilka razy w roku |

**Co powiedzieć:**
- Na wykresie widać 1–2 tys. transakcji lokalami miesięcznie, więc danych jest wystarczająco dużo.
- Ważna obserwacja o aktualności: gdy pobraliśmy dane za ostatnie dwa lata, **za październik i listopad 2026 w rejestrze nie było jeszcze ani jednej transakcji**, a wrzesień był prawie pusty. Akty notarialne trafiają do rejestru z opóźnieniem (mediana 57 dni, wykres `11_rcn_opoznienie_rejestracji.png`). Wniosek dla hurtowni: przy każdej aktualizacji trzeba ponownie pobierać ostatnie ~3 miesiące.

### Slajd 4 – Jak łączymy źródła

**Co pokazać:** schemat poniżej (można go przerysować) oraz wykres `08_osm_rcn_odleglosci.png` jako dowód, że połączenie działa.

```
 Oferty (Kaggle) ──┐                         ┌── NBP (stopy)
                   │   wspólne wymiary:      │
                   ├── • miesiąc ────────────┤
                   │   • miasto (kod TERYT)
                   │   • kwadrat siatki 1 km
                   │   • przedział metrażu
 Transakcje (RCN) ─┘            │
                                └── współrzędne ── OpenStreetMap (otoczenie)
```

**Co powiedzieć:**
- Oferta i transakcja to dwa różne zdarzenia. Nie da się powiedzieć, że „ta oferta skończyła się tą transakcją”, bo rejestr jest anonimowy. Porównujemy więc **grupy**: ten sam miesiąc, ten sam kwadrat 1×1 km, podobny metraż.
- Wynik testu: wszystkie 11 miesięcy są wspólne dla obu źródeł, a **75% ofert** leży w kwadratach, w których jest też co najmniej 10 transakcji.
- Stopy NBP dopinamy po miesiącu (100% pokrycia), a OpenStreetMap po współrzędnych. Np. połowa sprzedanych mieszkań ma przystanek bliżej niż 186 m.
- Ważna decyzja projektowa: obszar wybieramy **kodem TERYT** (Wrocław = 0264), a nie listą dzielnic, więc projekt łatwo rozszerzyć na całą Polskę.

### Slajd 5 – Jakość danych: kompletność

**Co pokazać:** dwa wykresy obok siebie: `03_rcn_braki_pol.png` (transakcje) i `05_oferty_braki_pol.png` (oferty).

**Co powiedzieć:**
- **Transakcje (RCN):** najważniejsze pola, czyli cena, metraż, data, rodzaj rynku i lokalizacja, są wypełnione praktycznie w 100%. Braki dotyczą pól pobocznych (np. liczba izb 19%), a pola VAT są puste w całości.
- **Oferty:** cena, metraż, pokoje i lokalizacja są pełne, ale **standard wykończenia brakuje w 72% ofert**, a materiału budynku w 38%.
- Oferty **nie mają w ogóle** informacji, czy to rynek pierwotny czy wtórny, ani daty dodania ogłoszenia.

### Slajd 6 – Problemy w danych na konkretnych przykładach

**Co pokazać:** tabelę 5 problemów (to najciekawszy slajd dla prowadzącego, bo wymaganie mówi wprost o „rzeczywistych problemach na konkretnych przykładach”).

| Problem | Przykład z danych | Co z tym robimy |
|---|---|---|
| Transakcje „nierynkowe” | mieszkania komunalne sprzedawane z bonifikatą po **1 525 zł/m²**; jedna transakcja za **1 zł** (84 m²) | odrzucamy z analizy cen rynkowych |
| Ta sama sprzedaż zapisana dwa razy | ten sam lokal, ten sam dzień i cena 1 366 406 zł, dwa różne numery transakcji | usuwamy duplikaty (10 mieszkań) |
| To samo mieszkanie pod różnymi ogłoszeniami | dwie oferty: ten sam punkt na mapie, 84 m², 7. piętro, 750 000 zł | usuwamy duplikaty (264 wiersze) |
| „Izby” to nie „pokoje” | rejestr liczy też kuchnię (3 izby = ok. 54 m²), a portale podają pokoje | porównujemy po metrażu, nie po liczbie pokoi |
| Błędy w samej usłudze rządowej | filtr „data **mniejsza niż** X” zwracał też dzień X, przez co rekordy się dublowały; prośba o współrzędne GPS była ignorowana | obejście w kodzie + test kontrolny sum |

**Co powiedzieć:**
- Każdy problem znaleźliśmy na prawdziwych rekordach i do każdego mamy plan: czyścimy, odrzucamy albo przenosimy do „kwarantanny”, czyli osobnej tabeli z podejrzanymi rekordami do sprawdzenia.
- Na tym etapie reguły jakości to proste warunki w Pythonie (pandas). W hurtowni przeniesiemy je do **testów dbt** (np. `unique`, `not_null`, dozwolone wartości).

### Slajd 7 – Pierwszy rzut oka na dane (rozkłady cen)

**Co pokazać:** `01_rcn_cena_m2_hist.png` (transakcje) i `04_oferty_cena_m2_hist.png` (oferty).

**Co powiedzieć:**
- Transakcje: większość mieszkań we Wrocławiu sprzedawała się za 9–13 tys. zł/m².
- Oferty: rozkład jest przesunięty w prawo, czyli oferty są droższe.
- **Uwaga:** rozkład ofert jest „ucięty” od dołu (brak ofert poniżej ok. 8–9 tys. zł/m²). To znak, że autor zbioru wcześniej usunął część rekordów, a my nie znamy jego reguł. To ograniczenie, które trzeba uczciwie podać.

### Slajd 8 – Pierwszy wynik: luka między ofertą a transakcją

**Co pokazać:** **`09_oferta_vs_transakcja_powierzchnia.png`** (najważniejszy wykres), opcjonalnie `10_oferta_vs_transakcja_w_czasie.png` lub mapę `14_luka_siatka_1km.png`.

**Co powiedzieć:**
- W każdej grupie metrażu oferta jest droższa od transakcji, o 13–18%. Najwięcej przy kawalerkach (<38 m²: +18%).
- Na wykresie w czasie widać, że luka utrzymuje się przez cały okres. Ceny ofertowe rosły równomiernie, a transakcyjne skokami.
- Na mapie siatki widać, że luka różni się między częściami miasta: w niektórych kwadratach oferty są nawet tańsze niż transakcje, w innych droższe o ponad 30%.
- Ten wynik to dowód, że dane pozwalają odpowiedzieć na nasze główne pytanie analityczne.

### Slajd 9 – Otoczenie i stopy procentowe

**Co pokazać:** `07_osm_obiekty_kategorie.png` i `06_nbp_stopa_referencyjna.png`.

**Co powiedzieć:**
- Z OpenStreetMap mamy 12 kategorii obiektów: przystanki, parki, lasy, sklepy, szkoły, przedszkola, przychodnie, apteki.
- Ciekawostka jakościowa: ten sam przystanek bywa zapisany w OSM nawet trzy razy (inny typ punktu), więc ~6 tys. zapisów to w rzeczywistości ok. **1,6 tys. przystanków**.
- Stopy NBP: w naszym okresie stopa referencyjna spadła z 6,75% do 5,75%, a potem stała w miejscu. To mało zmian, więc wnioski o wpływie stóp na ceny będą ostrożne.

### Slajd 10 – Ograniczenia i co dalej

**Co powiedzieć:**
- Oferty są z lat 2023–2024, nie są aktualne. Pytamy prowadzącego, czy wolno nam pobrać małą próbkę z portalu do celów badawczych.
- Oferty nie mają podziału na rynek pierwotny i wtórny, więc ten podział pokażemy tylko dla transakcji.
- OpenStreetMap pokazuje dzisiejszą mapę, a transakcje są sprzed 2 lat (np. przystanek mógł powstać później).
- Do sprawdzenia: dane NBP o oprocentowaniu kredytów oraz dokładne warunki licencyjne RCN i NBP.

---

## 3. Źródła danych – szczegóły

### 3.1 RCN – Rejestr Cen Nieruchomości (ceny transakcyjne)

**Co to jest:** publiczny rejestr prowadzony przez starostwa. Trafia do niego każda sprzedaż nieruchomości na podstawie aktu notarialnego: cena, metraż, data, rodzaj rynku i położenie. Od niedawna dane są udostępniane bezpłatnie.

**Jak pobraliśmy dane:** przez usługę internetową WFS na Geoportalu. Wysyłamy zapytanie typu „daj mi lokale z powiatu 0264 sprzedane w styczniu 2024”, a serwer zwraca plik GML (odmiana XML). Usługa umie też zwrócić **samą liczbę** pasujących rekordów, bez danych, co przydało się do szybkiego policzenia wolumenu.

**Co jest w środku (najważniejsze pola):** cena transakcji i cena lokalu, metraż, liczba izb, piętro, data aktu, rodzaj rynku (pierwotny/wtórny), rodzaj transakcji (np. wolny rynek, bonifikata), kto sprzedaje i kto kupuje (np. osoba fizyczna, deweloper), adres, współrzędne.

**Co zauważyliśmy:**
- We Wrocławiu w okresie VIII 2023 – VI 2024 było 18 134 sprzedanych lokali: 80% to mieszkania, reszta to głównie garaże.
- Sprzedaży na rynku pierwotnym było więcej niż na wtórnym (ok. 57% do 43% mieszkań).
- Po odrzuceniu transakcji nierynkowych, sprzedaży udziałów i błędnych wartości zostaje **13 552 mieszkań** do analizy cen.
- Jedno pole zawiera imię, nazwisko i adres notariusza. Usuwamy je od razu, bo nie jest nam potrzebne, a to dane osobowe.

### 3.2 Oferty – zbiór Kaggle (ceny ofertowe)

**Co to jest:** zbiór udostępniony na Kaggle przez Krzysztofa Jamroza, na licencji Apache 2.0. Zawiera oferty sprzedaży (i osobno wynajmu) mieszkań z 15 największych miast Polski, zbierane raz w miesiącu od sierpnia 2023 do czerwca 2024.

**Jak pobraliśmy dane:** jednym poleceniem przez API Kaggle, bez logowania. Dostajemy ZIP z 19 plikami CSV (11 plików ze sprzedażą, 8 z wynajmem).

**Co jest w środku:** cena, metraż, liczba pokoi, piętro i liczba pięter, rok budowy, typ budynku, materiał, standard, udogodnienia (balkon, winda, parking…), współrzędne oraz gotowe odległości do szkół, przychodni, aptek itd.

**Co zauważyliśmy:**
- Każdy plik to „migawka”, czyli stan ofert w danym miesiącu. Ta sama oferta może się pojawić w kilku migawkach: **połowa ofert występuje tylko raz**, a pojedyncze wiszą przez wszystkie 11 miesięcy (wykres `13_oferty_trwalosc_w_migawkach.png`).
- **14% ofert zmienia cenę** między migawkami, zwykle o kilka procent (mediana 3,9%).
- Autor nie podaje, z jakich portali zebrał dane. To ważna niewiadoma.
- W jednym punkcie na mapie potrafi być nawet 168 ofert, więc lokalizacja jest często przybliżona (np. środek osiedla).

### 3.3 OpenStreetMap (otoczenie)

**Co to jest:** otwarta mapa świata tworzona przez społeczność, coś jak Wikipedia map. Każdy obiekt (przystanek, park, sklep) ma opis w formie tagów, np. `highway=bus_stop`.

**Jak pobraliśmy dane:** najpierw próbowaliśmy usługi Overpass, która pozwala zapytać „daj mi wszystkie przystanki we Wrocławiu”. Okazała się **przeciążona**: odrzucała nawet najprostsze zapytania, a serwer sam pisze, że jest przeznaczony do użytku ręcznego. Przeszliśmy więc na **Geofabrik**, czyli gotowy plik z całą mapą województwa dolnośląskiego (182 MB). Nasz skrypt czyta go w niecałą minutę i wycina obszar Wrocławia po kodzie TERYT.

**Co zauważyliśmy:**
- Przystanki są opisane bardzo dokładnie (prawie wszystkie mają nazwy), parki i lasy znacznie słabiej (69% parków bez nazwy).
- Jedna czwarta obiektów nie była edytowana od ponad 5 lat. Około tysiąca obiektów zmieniono jednocześnie mniej więcej 8 lat temu, co wygląda na jednorazowy import (wykres `12_osm_aktualnosc_edycji.png`).
- W całym województwie tylko 2 obiekty miały uszkodzoną geometrię.

### 3.4 NBP (stopy procentowe)

**Co to jest:** oficjalne stopy procentowe NBP. Najważniejsza jest stopa referencyjna, od której zależy m.in. oprocentowanie kredytów hipotecznych.

**Jak pobraliśmy dane:** dwa małe pliki XML ze strony NBP: aktualne stopy i pełna historia zmian od 1998 r.

**Co zauważyliśmy:**
- Dane są czyste: bez duplikatów i braków w naszym okresie.
- Liczby zapisane są z **przecinkiem** (np. „5,75”), co trzeba przekonwertować.
- Plik z historią ma w nagłówku datę publikacji z 2015 r., choć zawiera dane do 2026 r. Nie można więc na tej dacie polegać.

---

## 4. Czy te dane wystarczą do naszych pytań analitycznych?

Odnosimy się do czterech grup pytań z dokumentu „Użytkownik końcowy i wymagania informacyjne”.

| Grupa pytań | Czy damy radę? | Na czym się opieramy | Czego brakuje |
|---|---|---|---|
| **A. Ceny** (średnie, mediany, oferta vs transakcja, zmiany w czasie) | **tak** | RCN + oferty | podział na rynek pierwotny/wtórny tylko dla transakcji; okres ofert to tylko 11 miesięcy |
| **B. Potencjał inwestycyjny** (gdzie inwestować, oferty niedowartościowane) | **tak** | porównanie oferty z medianą podobnych transakcji w tym samym kwadracie i metrażu | dane o czynszach są w paczce Kaggle, ale jeszcze ich nie sprawdziliśmy |
| **C. Lokalizacja i otoczenie** (przystanki, zieleń, usługi) | **tak** | OpenStreetMap + współrzędne transakcji i ofert | mapa jest „dzisiejsza”, transakcje sprzed 2 lat |
| **D. Czynniki makro** (stopy vs ceny) | **częściowo** | NBP, połączenie po miesiącu | w naszym okresie stopy prawie się nie zmieniały; brak danych o oprocentowaniu kredytów |

---

## 5. Jakość danych – podsumowanie

Ocenialiśmy sześć wymiarów jakości wymaganych w zadaniu. ✓ = dobrze, ~ = są problemy, ale do opanowania.

| Wymiar | Co to znaczy | Transakcje (RCN) | Oferty | OSM | NBP |
|---|---|---|---|---|---|
| Kompletność | czy pola są wypełnione | ✓ kluczowe pola pełne | ~ standard brakuje w 72% | ~ parki bez nazw | ✓ |
| Unikalność | czy nie ma duplikatów | ~ 10 zdublowanych sprzedaży | ~ 264 duplikaty ofert | ~ przystanki zapisane kilka razy | ✓ |
| Spójność | czy dane nie przeczą sobie | ~ cena dla kilku lokali naraz (3%) | ✓ | ✓ | ✓ historia = stan bieżący |
| Poprawność formatów | czy da się je wczytać | ~ tylko GML, błąd z układem współrzędnych | ✓ | ✓ | ~ przecinek dziesiętny |
| Poprawność wartości | czy liczby mają sens | ~ 0,8% cen nierealnych (np. 1 zł) | ~ zbiór wstępnie „oczyszczony” przez autora | ✓ | ✓ |
| Aktualność | czy dane są świeże | ~ opóźnienie ok. 2 miesięcy | ~ tylko do VI 2024 | ~ 26% obiektów nieedytowanych od 5 lat | ~ błędna data w nagłówku |

---

## 6. Pełna lista problemów i co z nimi robimy

| # | Problem | Ile rekordów | Co robimy |
|---|---|---|---|
| 1 | Usługa RCN: filtr „mniejsze niż” na dacie działa jak „mniejsze lub równe” | dotyczy każdego zapytania o okres | obejście w kodzie + test: suma miesięcy musi się równać wynikowi dla całego okresu |
| 2 | Usługa RCN ignoruje prośbę o współrzędne GPS | wszystkie rekordy | przeliczamy współrzędne sami |
| 3 | Transakcje nierynkowe (bonifikata, sprzedaż bez przetargu) | 5,1% mieszkań | odrzucamy z analizy cen |
| 4 | Sprzedaż części mieszkania (udziały, np. 1/6) | 1,4% mieszkań | odrzucamy |
| 5 | Jedna cena za mieszkanie + garaż | 3,1% mieszkań | bierzemy cenę samego lokalu, jeśli jest podana |
| 6 | Nierealne ceny (1 zł; cena wpisana w tysiącach) | 0,8% mieszkań | kwarantanna |
| 7 | Ta sama sprzedaż zapisana dwa razy | 10 mieszkań | usuwamy duplikaty |
| 8 | „Izby” w rejestrze ≠ „pokoje” w ofertach | całe pole | porównujemy po metrażu |
| 9 | Dane osobowe notariusza w rejestrze | całe pole | usuwamy przy wczytaniu |
| 10 | To samo mieszkanie w kilku ogłoszeniach | 264 wiersze ofert | usuwamy duplikaty |
| 11 | Przybliżona lokalizacja ofert | część ofert | analizy na kwadratach 1 km, nie na budynkach |
| 12 | Zbiór ofert wstępnie przefiltrowany przez autora | cały zbiór | opisujemy jako ograniczenie |
| 13 | Brak rynku pierwotny/wtórny i daty ogłoszenia w ofertach | wszystkie oferty | podział rynku tylko dla transakcji |
| 14 | Przystanki zapisane w OSM po kilka razy | ~6 000 zapisów → ~1 600 przystanków | łączymy po nazwie i odległości |
| 15 | Uszkodzone geometrie w OSM | 2 obiekty | pomijamy i zapisujemy ich numery |
| 16 | Przeciążona usługa Overpass | – | używamy pliku z Geofabrik |
| 17 | Błędna data publikacji w pliku NBP | 1 pole | ignorujemy, bierzemy datę ostatniej zmiany stopy |

**Narzędzia kontroli jakości:** teraz proste reguły w Pythonie (biblioteka pandas). W docelowym systemie te same reguły zapiszemy jako testy w **dbt** (np. „identyfikator musi być unikalny”, „cena nie może być pusta”, „rodzaj rynku musi mieć jedną z dozwolonych wartości”), ewentualnie w Great Expectations albo Soda. Podejrzane rekordy nie będą usuwane po cichu, tylko trafią do osobnej tabeli „kwarantanny”.

---

## 7. Przykłady surowych danych (do slajdu „techniczna prezentacja danych”)

**Transakcja z RCN** (fragment pliku GML, czyli tak dane wyglądają „prosto z serwera”):
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
  <ms:LOK_POW_UZYT>37</ms:LOK_POW_UZYT>
  <ms:LOK_ADRES>MSC:Wrocław;UL:Wincentego Stysia;NR_PORZ:20a</ms:LOK_ADRES>
</ms:lokale>
```
Jak to czytać: mieszkanie 37 m², 3 izby, rynek wtórny, sprzedane 22.09.2023 za 400 000 zł (ok. 10 800 zł/m²).

**Oferta z Kaggle** (jeden wiersz CSV, skrócony; przykład z innego miasta, ale format jest taki sam):
```
city,type,squareMeters,rooms,floor,buildYear,latitude,longitude,...,price
szczecin,blockOfFlats,47.0,2.0,6.0,1981.0,53.4285438,14.5528116,...,449000
```

**Ta sama oferta w kolejnych miesiącach** (widać obniżkę ceny):
```
luty 2024: 695 000 zł → marzec: 695 000 → kwiecień: 695 000 → maj: 685 000 → czerwiec: 685 000   (53 m²)
```

**Stopy NBP** (fragment XML; zwróć uwagę na przecinek w liczbach):
```xml
<pozycje obowiazuje_od="2026-03-05">
    <pozycja id="ref" oprocentowanie="3,75" />
</pozycje>
```

**Przykładowe zapytanie do RCN** (zwraca samą liczbę rekordów):
„Ile mieszkań sprzedano we Wrocławiu (TERYT 0264) w styczniu 2024?” → **1 624**

---

## 8. Spis wykresów

Wszystkie pliki są w `reports/figures/`. ★ = polecamy na slajd.

| Plik | Co pokazuje | Slajd |
|---|---|---|
| ★ `09_oferta_vs_transakcja_powierzchnia.png` | oferta vs transakcja według metrażu – **główny wynik** | 8 |
| `10_oferta_vs_transakcja_w_czasie.png` | oferta vs transakcja miesiąc po miesiącu + stopa NBP | 8 |
| `14_luka_siatka_1km.png` | mapa: gdzie oferty są droższe od transakcji, a gdzie tańsze | 8 |
| ★ `02_rcn_transakcje_miesiecznie.png` | liczba transakcji w kolejnych miesiącach | 3 |
| `11_rcn_opoznienie_rejestracji.png` | ile dni mija od aktu notarialnego do wpisu w rejestrze | 3 |
| ★ `08_osm_rcn_odleglosci.png` | odległość od sprzedanego mieszkania do przystanku, parku, sklepu, szkoły | 4 |
| ★ `03_rcn_braki_pol.png` | które pola w rejestrze są puste | 5 |
| ★ `05_oferty_braki_pol.png` | które pola w ofertach są puste | 5 |
| ★ `01_rcn_cena_m2_hist.png` | rozkład cen transakcyjnych za m² | 7 |
| ★ `04_oferty_cena_m2_hist.png` | rozkład cen ofertowych za m² | 7 |
| `13_oferty_trwalosc_w_migawkach.png` | jak długo oferty „wiszą” na rynku | (dodatkowy) |
| ★ `07_osm_obiekty_kategorie.png` | ile jest przystanków, parków, sklepów itd. | 9 |
| ★ `06_nbp_stopa_referencyjna.png` | stopa referencyjna NBP 2019–2026 | 9 |
| `12_osm_aktualnosc_edycji.png` | jak dawno edytowano obiekty na mapie | (dodatkowy) |

---

## Słowniczek

| Pojęcie | Wyjaśnienie |
|---|---|
| **RCN** | Rejestr Cen Nieruchomości – państwowa baza cen z aktów notarialnych |
| **Geoportal / GUGiK** | rządowy portal map / Główny Urząd Geodezji i Kartografii, który go prowadzi |
| **WFS** | standard usługi internetowej do pobierania danych mapowych (wysyłasz zapytanie, dostajesz dane) |
| **GML** | format plików z danymi przestrzennymi, odmiana XML |
| **TERYT** | urzędowy kod jednostki terytorialnej, np. **0264 = Wrocław** (jako powiat) |
| **Kaggle** | serwis z darmowymi zbiorami danych |
| **Migawka** | stan ofert z jednego miesiąca (jeden plik CSV = jedna migawka) |
| **OSM / OpenStreetMap** | otwarta mapa świata tworzona przez społeczność |
| **Geofabrik** | serwis udostępniający gotowe pliki z danymi OSM dla krajów i regionów |
| **Overpass** | usługa do zadawania zapytań do OSM (u nas przeciążona) |
| **PBF** | skompresowany format pliku z danymi OSM |
| **Mediana** | wartość środkowa: połowa obserwacji jest niższa, połowa wyższa. Lepsza od średniej, bo nie psują jej skrajne ceny |
| **Luka ofertowa** | o ile procent cena z ogłoszenia jest wyższa od ceny transakcyjnej |
| **Siatka 1 km** | podział mapy na kwadraty 1×1 km. Pozwala porównywać miejsca bez używania nazw dzielnic |
| **Kwarantanna** | osobna tabela na podejrzane rekordy: nie usuwamy ich, tylko odkładamy do sprawdzenia |
| **dbt** | narzędzie do przekształcania danych w hurtowni i testowania ich jakości |
| **Stopa referencyjna** | główna stopa procentowa NBP, wpływa na koszt kredytów |

---

*Kod źródłowy: folder `src/` (każdy skrypt uruchamia się poleceniem `uv run python src/<nazwa>.py`). Próbki danych: `data/sample/`. Szczegóły techniczne i pełne liczby: `reports/RAPORT_techniczny.md`.*
