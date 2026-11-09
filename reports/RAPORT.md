# Raport z rozpoznania źródeł danych (SZKIC – uzupełniany krok po kroku)

Projekt BI, Grupa 6: rynek mieszkaniowy, ceny ofertowe vs transakcyjne.
Zakres: ostatnie ~2 lata (XI 2024 – XI 2026), jedno miasto (*do ustalenia*).

---

## NBP – stopy procentowe

**Dostęp:** dwa pliki XML, bez rejestracji i klucza API:
- `https://static.nbp.pl/dane/stopy/stopy_procentowe.xml`: bieżące stopy
- `https://static.nbp.pl/dane/stopy/stopy_procentowe_archiwum.xml`: pełna historia zmian

Skrypt: `src/nbp_sample.py`. Próbka: `data/sample/nbp_stopy_zdarzenia.csv` (zdarzenia), `data/sample/nbp_stopy_miesieczne.csv` (szereg miesięczny).

**Charakterystyka (pomiar 9.11.2026):**
| | |
|---|---|
| Wolumen | 390 pozycji = 96 zmian stóp, ok. 37 KB |
| Zakres | 1998-02-26 – 2026-03-05 |
| Rodzaje stóp | referencyjna, lombardowa, redyskontowa (od 1998), depozytowa (od 2001-12), dyskontowa (od 2010-01) |
| Częstotliwość zmian | nieregularna, po decyzjach RPP; w zakresie projektu 7 zmian stopy referencyjnej (5,75% → 3,75%) |
| Aktualizacja | pobranie całego pliku (mały) i porównanie atrybutu `data_publikacji` |

**Jakość:**
| Wymiar | Wynik |
|---|---|
| Kompletność | stopa referencyjna bez braków w zakresie projektu (24/24 mies.); braki depozytowej/dyskontowej przed 2001/2010 są **strukturalne** (stopy jeszcze nie istniały), a nie błędem |
| Unikalność | 0 duplikatów (data, stopa) |
| Poprawność formatów | 390/390 wartości w formacie `d,dd`; **przecinek dziesiętny** wymaga konwersji; plik zaczyna się od znacznika BOM UTF-8 |
| Spójność | ostatni wpis archiwum = plik bieżący (5/5 stóp zgodne); plik bieżący ma 3 dodatkowe pozycje (`rozwpw`, `rorepo`, `rowred` – oprocentowanie rezerwy obowiązkowej), których archiwum nie zawiera |
| Aktualność | ⚠️ atrybut `data_publikacji` w archiwum = **2015-03-04**, mimo że dane sięgają 2026-03-05. Metadana jest nieaktualna, więc o świeżości trzeba wnioskować z najnowszej daty `obowiazuje_od` |

**Problemy i postępowanie:**
- przecinek dziesiętny → konwersja przy ładowaniu (czyszczenie)
- format zdarzeniowy („obowiązuje od”) → zamiana na szereg miesięczny, potrzebny do wymiaru czasu (transformacja)
- nieaktualna metadana `data_publikacji` w archiwum → nie opieramy na niej aktualizacji przyrostowej

**Przykład surowego rekordu (archiwum):**
```xml
<pozycje obowiazuje_od="2026-03-05">
    <pozycja id="ref" oprocentowanie="3,75" />
    <pozycja id="lom" oprocentowanie="4,25" />
    ...
</pozycje>
```

**Wykres:** `figures/06_nbp_stopa_referencyjna.png`

**Otwarte (❓):** oprocentowanie kredytów mieszkaniowych (statystyka MIR NBP) i Baza cen nieruchomości NBP nie zostały jeszcze sprawdzone.

---

## RCN – Rejestr Cen Nieruchomości (ceny transakcyjne)

**Dostęp:** usługa WFS 2.0 `https://mapy.geoportal.gov.pl/wss/service/rcn`, bez rejestracji. Warstwy: `ms:lokale`, `ms:budynki`, `ms:dzialki`, `ms:powiaty` (ta ostatnia ma tylko geometrię, bez kodu TERYT). Dane są udostępniane nieodpłatnie po nowelizacji Prawa geodezyjnego i kartograficznego (❓ dokładne warunki ponownego wykorzystania do potwierdzenia).
**Format:** wyłącznie **GML** (3.2 / 3.1.1 / 2.1.2), bez GeoJSON i CSV. Układ współrzędnych domyślnie EPSG:2180 (PL-1992).
**Możliwości serwera (GetCapabilities):** stronicowanie (`COUNT`/`STARTINDEX`), sortowanie, filtry atrybutowe i BBOX, zapytanie `RESULTTYPE=hits` zwracające samą liczbę rekordów.
**Wybór zakresu:** filtr po stronie serwera: `TERYT` (kod powiatu) + `DOK_DATA` (data aktu). Ten sam kod działa dla dowolnej listy powiatów, a więc docelowo dla całej Polski.

Skrypt: `src/rcn_sample.py`. Próbka: `data/sample/rcn_lokale_probka.parquet` (bez pól z danymi osobowymi), wolumen: `data/sample/rcn_wolumen_miesieczny.csv`.

**Charakterystyka (TERYT 0264 – Wrocław, akty XI 2024 – XI 2026, pomiar 9.11.2026):**
| | |
|---|---|
| Wolumen w zakresie | **29 160 lokali**, w tym **24 345 mieszkalnych** (zapytania „hits”, bez pobierania) |
| Próbka | 3 450 lokali (150 z każdego miesiąca), 35 pól |
| Rozmiar | ok. 2,5 KB GML na rekord, czyli pełne dane dla miasta to ok. 70 MB |
| Struktura próbki | 82% mieszkalne, 13% garaże, 5% inne; rynek wtórny 57% / pierwotny 43% |
| Ostatni akt w usłudze | 2026-09-28; ostatnia wersja wpisu 2026-10-16. **Za X i XI 2026 nie ma jeszcze żadnych rekordów** |
| Opóźnienie wpisu | mediana **39 dni** od aktu do wpisu (`TRAN_WERSJA_ID − DOK_DATA`); 90% wpisów w ciągu 82 dni |
| Aktualizacja | przyrostowo po `DOK_DATA`; ostatnie ~3 miesiące trzeba **pobierać ponownie**, bo dane spływają z opóźnieniem |

**Jakość:**
| Wymiar | Wynik |
|---|---|
| Kompletność | pola kluczowe pełne: cena transakcji, powierzchnia, data, rodzaj rynku (0% braków), współrzędne. Braki: `LOK_CENA_BRUTTO` 19%, `LOK_LICZBA_IZB` 18%, `LOK_NR_KOND` 4%, `LOK_ADRES` 1,5%. Pola VAT, `NIER_POW_GRUNTU` i `SERWIS_RCN` są puste w 100% |
| Unikalność | 0 duplikatów `gid` (po obejściu błędu filtra, patrz niżej); 4 pary o tym samym lokalu, dacie i cenie |
| Spójność | TERYT zgodny z prefiksem identyfikatora lokalu w 100%; **5,9%** lokali mieszkalnych należy do transakcji wielolokalowych (mieszkanie + garaż), w których `TRAN_CENA_BRUTTO` obejmuje całość |
| Poprawność formatów | daty ISO, kwoty numeryczne; wartości słownikowe w notacji camelCase (`rynekWtorny`, `wolnyRynek`) |
| Poprawność wartości | 122 z 2 844 lokali mieszkalnych (4,3%) ma cenę < 3 000 zł/m²: głównie **sprzedaż z bonifikatą** (80) i sprzedaż udziałów (np. 1/6, 1/32). 4 rekordy mają `LOK_CENA_BRUTTO` wyraźnie w złej jednostce |
| Aktualność | brak danych za ostatnie ~6 tygodni, a ostatnie 3 miesiące są niepełne (wykres 02) |
| Integralność referencyjna | 100% współrzędnych w granicach Polski; 0 dat poza zakresem filtra |

**Problemy i postępowanie:**
| Problem | Przykład z próbki | Skala | Postępowanie |
|---|---|---|---|
| **Błąd serwera:** `PropertyIsLessThan` na dacie działa jak `<=` | filtr `< 2025-04-01` zwracał też akty z 1.04 → 54 zdublowane rekordy, suma miesięcy 29 680 zamiast 29 160 | każdy filtr zakresu dat | zakres podajemy jako [pierwszy, ostatni dzień] włącznie; test kontrolny: suma miesięcy = wynik dla całego okresu |
| **Błąd serwera:** `SRSNAME=EPSG:4326` jest ignorowany | nagłówek deklaruje WGS84, a współrzędne są w PL-1992 (`367505.19 353312.20`) | wszystkie rekordy | przeliczamy sami (`pyproj`, EPSG:2180 → 4326) |
| Transakcje niewolnorynkowe | `sprzedazZBonifikata` (mieszkania komunalne): mediana **1 595 zł/m²** | 6,4% mieszkalnych (bonifikata 3,5%, bezprzetargowa 2,5%, inne 0,4%) | **odrzucenie** z analiz cen rynkowych (filtr `TRAN_RODZAJ_TRANS = wolnyRynek`) |
| Sprzedaż udziałów | udział 1/6, 90 000 zł za 48,6 m² | 2,4% mieszkalnych | **odrzucenie** (tylko `NIER_UDZIAL = 1/1`) |
| Cena transakcji obejmuje kilka lokali | 600 000 zł za transakcję, w tym 570 000 zł za mieszkanie | 5,9% mieszkalnych | cena z `LOK_CENA_BRUTTO`, a tylko gdy jej brak, z `TRAN_CENA_BRUTTO` |
| Cena lokalu w złej jednostce | `TRAN_CENA_BRUTTO=410000`, `LOK_CENA_BRUTTO=410` | 4 rekordy (0,1%) | **kwarantanna**: reguła „cena/m² poza [3 000; 50 000]” |
| Izby ≠ pokoje | `LOK_LICZBA_IZB` liczy także kuchnię (mediana pow.: 1 izba = 31 m², 3 izby = 54 m²) | semantyka pola | nie porównujemy wprost z „liczbą pokoi” z ofert; do porównań bierzemy przedziały powierzchni |
| Dane osobowe | `DOK_TWORCA` = imię, nazwisko i adres notariusza | 100% | pole usuwane już przy ładowaniu (minimalizacja danych) |

**Wyniki eksploracji:** po odfiltrowaniu (mieszkalne, wolny rynek, udział 1/1, cena 3–50 tys. zł/m²) zostaje 2 586 z 2 844 lokali (91%). **Mediana: 12 696 zł/m²** (pierwotny 12 811, wtórny 12 618); kwartyle 10,4–14,3 tys. zł/m².

**Przykład surowego rekordu (GML, skrócony):**
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

**Przykładowe zapytanie (liczba lokali mieszkalnych z jednego miesiąca):**
```
GET .../wss/service/rcn?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&TYPENAMES=ms:lokale&RESULTTYPE=hits
    &FILTER=<fes:Filter><fes:And>
        TERYT = '0264'  AND  DOK_DATA >= '2025-04-01'  AND  DOK_DATA <= '2025-04-30'  AND  LOK_FUNKCJA = 'mieszkalna'
    </fes:And></fes:Filter>
```

**Wykresy:** `figures/01_rcn_cena_m2_hist.png`, `figures/02_rcn_transakcje_miesiecznie.png`, `figures/03_rcn_braki_pol.png`, `figures/11_rcn_opoznienie_rejestracji.png`

**Ograniczenia próbki:** w każdym miesiącu bierzemy pierwsze 150 rekordów w kolejności zwracanej przez serwer, więc nie jest to losowanie. Rozkłady są orientacyjne. `TRAN_WERSJA_ID` może oznaczać ostatnią modyfikację wpisu, a nie pierwsze dodanie, więc opóźnienie to szacunek.
**Otwarte (❓):** warstwa `ms:budynki` (rok budowy?) nie została jeszcze sprawdzona; nie znamy też harmonogramu odświeżania samej usługi WFS.
