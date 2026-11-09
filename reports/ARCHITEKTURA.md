# Architektura rozwiązania

> **Status:** dobór narzędzi (Airflow, PostgreSQL + DuckDB, Superset, testy dbt) jest **decyzją grupy**. Model gwiazdy (rozdział 5) i harmonogram (rozdział 6) to nadal **propozycje do omówienia**. Elementy oznaczone ❓ nie zostały jeszcze sprawdzone w praktyce.

**Projekt BI, Grupa 6 – analiza rynku mieszkaniowego: ceny ofertowe vs ceny transakcyjne**
Dokument odpowiada na część 3 wymagań prezentacji: przepływ danych, dobór technologii z uzasadnieniem oraz sposób aktualizacji. To **projekt** architektury: opisuje, jak zbudujemy system, a nie gotową implementację. Opiera się na tym, co ustaliliśmy o źródłach (patrz `RAPORT.md`).

---

## Jak korzystać z tego dokumentu

- **Rozdział 1** – architektura w trzech zdaniach.
- **Rozdział 2** – gotowy plan 4 slajdów (co pokazać, co powiedzieć).
- **Rozdziały 3–7** – szczegóły i uzasadnienia, gdyby ktoś zadał pytanie.

---

## 1. Architektura w trzech zdaniach

1. Dane z czterech źródeł pobieramy skryptami w Pythonie, które już mamy, a uruchamia je i pilnuje harmonogramu **Apache Airflow**.
2. Surowe pliki trafiają do strefy „raw”, potem do **PostgreSQL** (staging), gdzie **dbt** je czyści i testuje, a gotowy model gwiazdy z agregatami ląduje w kolumnowej bazie **DuckDB**.
3. Użytkownicy oglądają wyniki na dashboardach w **Apache Superset**, a system aktualizuje się przyrostowo i co tydzień ponownie pobiera ostatnie 4 miesiące transakcji, bo akty notarialne trafiają do rejestru z opóźnieniem.

---

## 2. Proponowany plan slajdów

### Slajd A – Przepływ danych (całościowy obraz)

**Co pokazać:** schemat z rozdziału 3 (najlepiej przerysowany jako diagram z ikonami).

**Co powiedzieć:**
- Dane płyną od czterech źródeł, przez ekstrakcję, surową kopię i staging, do hurtowni w modelu gwiazdy, a na końcu do dashboardów.
- Nad całością czuwa orkiestrator (Airflow), a na każdym etapie działają testy jakości (dbt).
- Ten układ odpowiada schematowi z wykładu: źródła → integracja → przechowywanie (strefa surowa + hurtownia) → warstwa prezentacji.

### Slajd B – Dobór technologii

**Co pokazać:** tabelę z rozdziału 4 (warstwa → narzędzie → dlaczego).

**Co powiedzieć:**
- Wszystkie narzędzia są darmowe i uruchamiają się lokalnie (Airflow i PostgreSQL w Dockerze).
- Dwie bazy mają różne role: **PostgreSQL** to warstwa pośrednia (staging), a **DuckDB** to kolumnowy magazyn analityczny, z którego czyta Superset.
- Wszystkie narzędzia z minimum narzędziowego z wymagań są pokryte: orkiestracja, transformacje, kontrola jakości, baza pośrednia, baza kolumnowa i wizualizacja.

### Slajd C – Model wielowymiarowy

**Co pokazać:** schemat gwiazdy z rozdziału 5.

**Co powiedzieć:**
- Jeden proces pomiarowy: **obserwacja ceny mieszkania**. Każdy wiersz faktu to albo jedna oferta w danym miesiącu, albo jedna transakcja.
- Dzięki temu oferty i transakcje leżą w jednej tabeli i porównujemy je jednym zapytaniem, np. lukę ofertową w danym miesiącu i miejscu.
- Pięć wymiarów, zgodnie z naszymi wymaganiami informacyjnymi: czas, lokalizacja, nieruchomość, rynek, otoczenie.

### Slajd D – Jak system się aktualizuje

**Co pokazać:** tabelę harmonogramu z rozdziału 6.

**Co powiedzieć:**
- Na początku robimy jednorazowe **ładowanie inicjalne**, a potem **przyrostowe**, czyli pobieramy tylko to, co nowe.
- Transakcje dzielimy na miesiące. Co tydzień pobieramy ponownie ostatnie 4 miesiące, bo 90% aktów trafia do rejestru w ciągu 118 dni. W ten sposób łapiemy **dane spóźnione**.
- Na dashboardzie ostatnie miesiące mają oznaczenie „dane niepełne”, żeby nikt nie wyciągał z nich pochopnych wniosków.

---

## 3. Przepływ danych

```
   RCN (GML)     Oferty (CSV)     OSM (PBF)     NBP (XML)          1. ŹRÓDŁA
       │              │               │              │
       └──────────────┴───────┬───────┴──────────────┘
                              ▼
               Skrypty Python (src/*.py)                           2. EKSTRAKCJA
                              ▼
               Pliki surowe  data/raw/                             3. STREFA SUROWA
                              ▼
   ┌────────────────── PostgreSQL ────────────────┐
   │  raw / staging – wczytanie, typy, nazwy      │                4. STAGING
   │  intermediate  – czyszczenie, duplikaty,     │                5. TRANSFORMACJE (dbt)
   │                  kwarantanna, siatka 1 km    │
   └───────────────────────┬──────────────────────┘
                           ▼
   ┌─────────────────── DuckDB ───────────────────┐
   │  marts    – model gwiazdy                    │                6. HURTOWNIA
   │  agregaty – mediany, luka ofertowa           │                7. AGREGACJE
   └───────────────────────┬──────────────────────┘
                           ▼
               Apache Superset – dashboardy                        8. PREZENTACJA

   Przez cały czas: Airflow (harmonogram, kolejność, ponawianie) + testy dbt (jakość)
```

**Warstwy krok po kroku:**

| Warstwa | Co się dzieje | Przykład z naszego projektu |
|---|---|---|
| **1. Źródła** | dane w oryginalnych formatach | GML z RCN, CSV z Kaggle, PBF z Geofabrik, XML z NBP |
| **2. Ekstrakcja** | skrypty pobierają dane i zapisują je bez zmian | `src/rcn_sample.py` pobiera lokale miesiąc po miesiącu dla każdego kodu TERYT |
| **3. Strefa surowa** (raw zone) | pliki „jak przyszły”, żeby w razie błędu przeliczyć wszystko bez ponownego pobierania | `data/raw/rcn/lokale_0264_2024-01.xml` |
| **4. Staging** (PostgreSQL) | wczytanie do bazy, ujednolicenie typów i nazw kolumn, konwersje | przecinek dziesiętny NBP → liczba; współrzędne PL-1992 → GPS; usunięcie danych notariusza |
| **5. Intermediate** (PostgreSQL) | logika biznesowa i jakość | odrzucenie transakcji nierynkowych, deduplikacja, kwarantanna, przypisanie kwadratu 1 km, odległość do najbliższego przystanku |
| **6. Marts** (DuckDB) | model gwiazdy: fakty + wymiary | `fakt_obserwacja_ceny`, `dim_czas`, `dim_lokalizacja`… |
| **7. Agregaty** | gotowe podsumowania dla dashboardów | mediana ceny/m² wg miesiąca, kwadratu i rynku; luka ofertowa |
| **8. Prezentacja** | dashboardy dla użytkowników | 6 dashboardów z dokumentu „Użytkownik końcowy” |

---

## 4. Dobór technologii i uzasadnienie

| Warstwa | Narzędzie (wybór grupy) | Dlaczego to | Rozważane alternatywy |
|---|---|---|---|
| **Środowisko** | Python 3.12 + **uv**, Git | już używamy; identyczne wersje bibliotek u wszystkich (`uv.lock`) | conda – cięższa, niepotrzebna |
| **Ekstrakcja** | Python: `requests`, `lxml`, `pyosmium` | skrypty już działają na wszystkich czterech źródłach i obsługują błędy usług, które znaleźliśmy (filtr dat RCN, ignorowane współrzędne) | gotowe konektory (Airbyte, Fivetran) – nie mają konektorów do RCN ani NBP |
| **Orkiestracja** | **Apache Airflow** | standard w branży i przykład wprost wymieniony w wymaganiach; harmonogram, ponawianie po błędzie, **backfill** (nadrobienie zaległych okresów) i podział na przedziały czasu pasują do miesięcznych porcji danych RCN; ma gotową integrację z dbt | Dagster, Prefect – prostsze lokalnie; Airflow jest cięższy (wymaga Dockera, bazy metadanych i schedulera), co uznaliśmy za akceptowalny koszt |
| **Strefa surowa** | pliki na dysku (`data/raw/`), docelowo Parquet | najprostsze „jezioro danych”: tanie, czytelne, łatwo przeliczyć wszystko od nowa | – |
| **Warstwa pośrednia (staging)** | **PostgreSQL** | opcjonalna baza relacyjna z wymagań; dobra do wczytywania i czyszczenia (klucze, indeksy, transakcje); dbt ma dojrzały adapter | – |
| **Magazyn analityczny** | **DuckDB** | **kolumnowa** baza (wymóg „kolumnowy lub MOLAP”); jeden plik bez serwera; szybkie agregacje (mediany, odchylenia); może czytać z PostgreSQL | ClickHouse, Druid – wymagają serwera i są przesadą przy naszym wolumenie (dziesiątki tysięcy wierszy na miasto) |
| **Transformacje** | **dbt** | transformacje w czystym SQL, warstwy staging → intermediate → marts, modele przyrostowe; testy i dokumentacja w jednym miejscu | ręczne skrypty SQL – brak testów, kolejności i dokumentacji |
| **Jakość danych** | **testy dbt** (+ pakiet `dbt-expectations`) | reguły z raportu zapisujemy jako testy (rozdział 7); uruchamiają się automatycznie po każdym ładowaniu; bez dodatkowego narzędzia do nauki | Great Expectations, Soda – bogatsze, ale to kolejne narzędzie |
| **Wizualizacja** | **Apache Superset** | darmowy, ma **mapy cieplne** (heatmapa cen to jedno z wymagań), filtry krzyżowe i dashboardy | Metabase – prostszy, słabsze mapy (plan B); Power BI – tylko Windows; Tableau – płatny |

**Jak współpracują dwie bazy ❓:** dbt buduje warstwy staging i intermediate w PostgreSQL (adapter `dbt-postgres`). Tabele końcowe (model gwiazdy i agregaty) trafiają do DuckDB, który czyta dane z PostgreSQL przez wbudowane rozszerzenie. Dokładny sposób (drugi projekt dbt z adapterem `dbt-duckdb` albo prosty krok w Airflow) wybierzemy po sprawdzeniu, co działa prościej. To **jeszcze niezweryfikowany** element architektury.

**Ryzyka techniczne:**
- **Dwie bazy zamiast jednej** to więcej elementów do utrzymania. Przenoszenie danych z PostgreSQL do DuckDB musi być krokiem w potoku z własnym testem (liczba wierszy po obu stronach).
- DuckDB pozwala na jednego „piszącego” naraz. Superset czyta bazę w trybie tylko do odczytu, a odświeżanie planujemy poza godzinami oglądania dashboardów (np. w nocy).
- ❓ Działanie sterownika DuckDB w Superset sprawdzimy jako pierwszy krok wdrożenia. Jeśli zawiedzie, planem B jest czytanie marts bezpośrednio z PostgreSQL.
- Airflow jest ciężki: do pracy lokalnej potrzebny jest Docker (pamięć i czas startu).

---

## 5. Model wielowymiarowy (schemat gwiazdy)

**Proces pomiarowy:** obserwacja ceny mieszkania na rynku.
**Ziarno faktu (jeden wiersz):** jedna transakcja mieszkaniem z RCN **albo** jedna oferta w danej miesięcznej migawce.

Dlaczego jedna tabela faktów na oferty i transakcje? Wymaganie mówi o analizie **jednego** procesu, a nasz główny wskaźnik, luka ofertowa, to właśnie porównanie obu typów cen. Wymiar `dim_rynek` mówi, czy wiersz to oferta, czy transakcja.

```
                         dim_czas
                  (data, miesiąc, kwartał, rok,
                   stopa ref. NBP, zmiana stopy)
                              │
  dim_nieruchomosc ───── FAKT_OBSERWACJA_CENY ───── dim_lokalizacja
  (przedział metrażu,     • cena całkowita           (TERYT, miasto, województwo,
   pokoje/izby, piętro,   • cena za m²                kwadrat 1 km, środek kwadratu)
   rok budowy, typ        • powierzchnia                      │
   budynku, standard)     • odległość do przystanku     dim_otoczenie
                          • odległość do parku          (na kwadrat 1 km: liczba przystanków,
                          • liczba obserwacji = 1        parków, sklepów, szkół; odległości
                              │                          średnie; dostęp do komunikacji)
                         dim_rynek
                  (typ ceny: oferta/transakcja,
                   rynek pierwotny/wtórny/nieznany,
                   rodzaj transakcji, typ sprzedającego,
                   typ kupującego, źródło danych)
```

| Wymiar | Przykładowe atrybuty (min. 5) | Skąd dane |
|---|---|---|
| **dim_czas** | data, miesiąc, kwartał, rok, nazwa miesiąca, stopa referencyjna, stopa lombardowa, czy w tym miesiącu zmieniono stopę, czy okres jest kompletny w RCN | kalendarz + NBP + metryka opóźnienia RCN |
| **dim_lokalizacja** | TERYT powiatu, miasto, województwo, identyfikator kwadratu 1 km, współrzędne środka kwadratu | RCN, oferty (miasto → TERYT), siatka |
| **dim_otoczenie** | liczba przystanków / parków / sklepów / szkół w kwadracie, średnia odległość do przystanku, klasa dostępności komunikacji | OpenStreetMap |
| **dim_nieruchomosc** | przedział metrażu, liczba pokoi (oferty) / izb (RCN), piętro, przedział roku budowy, typ budynku, standard | oferty + RCN |
| **dim_rynek** | typ ceny, rynek pierwotny/wtórny, rodzaj transakcji, typ sprzedającego, typ kupującego, źródło | RCN + oferty |

**Agregaty** (warstwa „agregacje” z wymagań): mediany nie da się zsumować z mniejszych grup, więc liczymy je z góry i zapisujemy jako gotowe tabele:
- `agg_ceny_miesiac_lokalizacja` – mediana, średnia, odchylenie standardowe i liczba obserwacji wg miesiąca × kwadratu × rynku × typu ceny;
- `agg_luka_ofertowa` – luka % wg miesiąca × kwadratu × przedziału metrażu (tylko tam, gdzie jest ≥10 ofert i ≥10 transakcji);
- `agg_otoczenie_vs_cena` – cena/m² wg klasy dostępności komunikacji i zieleni.

Dashboardy czytają agregaty, więc działają szybko. Do szczegółów, np. pojedynczej oferty, sięgamy przez fakt.

---

## 6. Aktualizacja danych

### 6.1 Ładowanie inicjalne i przyrostowe

| Źródło | Ładowanie inicjalne | Ładowanie przyrostowe | Klucz, po którym rozpoznajemy rekord |
|---|---|---|---|
| **RCN** | wszystkie miesiące z wybranego okresu, osobno dla każdego kodu TERYT | nowe miesiące + **ponowne pobranie ostatnich 4 miesięcy** (dane spóźnione) | identyfikator transakcji i lokalu + znacznik wersji wpisu; nowsza wersja zastępuje starszą |
| **Oferty** | jednorazowo cały zbiór Kaggle (11 migawek) | zbiór nie jest aktualizowany; przy nowym źródle: dopisywanie co tydzień nowej migawki z datą pobrania | id oferty + data migawki |
| **OSM** | plik województwa (docelowo całej Polski) | pełne odświeżenie pliku; przeliczenie odległości i `dim_otoczenie` | typ i id obiektu OSM; zapamiętujemy datę stanu mapy |
| **NBP** | całe archiwum od 1998 r. | pobranie pliku i dopisanie tylko nowych zmian stóp | data „obowiązuje od” + rodzaj stopy |

Modele faktów w dbt są **przyrostowe**: przeliczamy tylko zmienione miesiące, a nie całą historię. Ponowne uruchomienie dla tego samego miesiąca daje ten sam wynik (operacja idempotentna), więc ponawianie po błędzie jest bezpieczne.

### 6.2 Harmonogram odświeżania

| Co | Kiedy | Dlaczego tak |
|---|---|---|
| NBP | codziennie rano | plik jest mały; zmiana stopy jest rzadka, ale ważna |
| RCN | raz w tygodniu (np. w poniedziałek w nocy) | rejestr zasila się na bieżąco, ale z opóźnieniem; częściej nie ma sensu |
| OSM | raz w miesiącu | infrastruktura miasta zmienia się wolno; Geofabrik publikuje plik codziennie |
| Oferty | jednorazowo (Kaggle); przy nowym źródle co tydzień | – |
| dbt build (transformacje + testy) + agregaty | automatycznie po każdym ładowaniu | Airflow uruchamia dbt dopiero, gdy dane wejściowe są gotowe |

### 6.3 Obsługa danych spóźnionych

Zmierzyliśmy, że akt notarialny trafia do RCN średnio po 57 dniach, a w 90% przypadków w ciągu 118 dni. Dlatego:

1. **Okno ponownego pobrania = 4 miesiące.** Każde cotygodniowe uruchomienie pobiera na nowo 4 ostatnie miesiące i nadpisuje je w hurtowni.
2. **Test kontrolny liczności.** Dla każdego miesiąca porównujemy liczbę rekordów w hurtowni z liczbą, którą zwraca usługa RCN (zapytanie o samą liczbę). Różnica oznacza błąd ładowania.
3. **Oznaczenie kompletności.** W `dim_czas` miesiące młodsze niż 4 miesiące mają flagę „dane niepełne”, którą dashboard pokazuje użytkownikowi.
4. **Starsze korekty.** Raz na kwartał robimy pełne przeładowanie całego okresu, żeby wyłapać rzadkie późne poprawki starszych wpisów.

---

## 7. Kontrola jakości w potoku

Reguły z raportu źródłowym (`RAPORT.md`, rozdział 6) zapisujemy jako testy dbt:

| Test | Przykład reguły | Co się dzieje, gdy nie przejdzie |
|---|---|---|
| `unique`, `not_null` | identyfikator obserwacji jest unikalny; cena i data nie są puste | potok się zatrzymuje, dashboard nie dostaje złych danych |
| `accepted_values` | rodzaj rynku ∈ {rynekPierwotny, rynekWtorny}; typ ceny ∈ {oferta, transakcja} | ostrzeżenie, nowa wartość do przejrzenia |
| `relationships` | każdy wiersz faktu ma pasujący miesiąc w `dim_czas` i kwadrat w `dim_lokalizacja` | potok się zatrzymuje |
| test zakresu | cena/m² w przedziale 3 000–50 000 zł | rekord trafia do **kwarantanny** |
| test własny | suma rekordów RCN w miesiącu = liczba ze źródła | potok się zatrzymuje |
| test świeżości (`source freshness`) | ostatnia zmiana stóp NBP lub ostatnia migawka nie starsza niż X dni | ostrzeżenie |

---

## Słowniczek (pojęcia z tego dokumentu)

| Pojęcie | Wyjaśnienie |
|---|---|
| **DAG** | schemat zadań w Airflow: co ma się wykonać i w jakiej kolejności |
| **Orkiestracja** | automatyczne uruchamianie kroków potoku we właściwej kolejności i o właściwej porze |
| **Backfill** | nadrabianie zaległych okresów, u nas np. ponowne przetworzenie kilku miesięcy transakcji |
| **Strefa surowa (raw)** | kopia danych dokładnie w takiej postaci, w jakiej przyszły ze źródła |
| **Staging** | warstwa, w której dane są wczytane i ujednolicone, ale jeszcze bez logiki biznesowej |
| **Marts** | końcowe tabele hurtowni przygotowane pod analizy (model gwiazdy) |
| **Baza kolumnowa** | baza zapisująca dane kolumnami, a nie wierszami; bardzo szybka przy sumach i medianach |
| **Model gwiazdy** | tabela faktów (pomiary) w środku i tabele wymiarów (kontekst: kiedy, gdzie, co) dookoła |
| **Ziarno** | co dokładnie oznacza jeden wiersz tabeli faktów |
| **Ładowanie przyrostowe** | pobieranie tylko nowych lub zmienionych danych zamiast wszystkiego od nowa |
| **Idempotentność** | wielokrotne uruchomienie tego samego kroku daje ten sam wynik |
| **Dane spóźnione** | dane o zdarzeniach z przeszłości, które pojawiają się w źródle z opóźnieniem |
