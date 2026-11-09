"""Wspólne parametry etapu rozpoznania źródeł – jedno miejsce do zmiany zakresu."""
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw"
SAMPLE = ROOT / "data" / "sample"
FIGURES = ROOT / "reports" / "figures"

# Zakres czasowy: dopasowany do dostępnych danych ofertowych (Kaggle: VIII 2023 – VI 2024).
# Pierwotnie: ostatnie ~2 lata (2024-11-01 – 2026-11-09) – zmienione po analizie regulaminów portali.
DATE_FROM = date(2023, 8, 1)
DATE_TO = date(2024, 6, 30)

# Zakres geograficzny – definiowany WYŁĄCZNIE kodami TERYT powiatów, żeby ten sam kod
# działał dla dowolnego miasta / całej Polski (lista powiatów). Bez nazw dzielnic itp.
AREA_NAME = "Wrocław"
TERYT_POWIATY = ["0264"]   # 0264 = m. Wrocław (miasto na prawach powiatu)

# Zbiór ofert (Kaggle) identyfikuje miasto nazwą, nie kodem – mapowanie na TERYT powiatu,
# żeby oferty i RCN łączyły się tym samym kluczem. Zweryfikowane: 0264 (RCN zwraca rekordy
# z LOK_ADRES "MSC:Wrocław"). Pozostałe miasta dopisać i zweryfikować przy rozszerzaniu zakresu.
KAGGLE_CITY_TO_TERYT = {"wroclaw": "0264"}

# Próbkowanie RCN: tyle lokali z każdego miesiąca zakresu
RCN_SAMPLE_PER_MONTH = 2500   # >= maks. miesięczny wolumen Wrocławia (~2000) → pełne okno dla 1 miasta

USER_AGENT = "BI-student-project/0.1 (projekt uczelniany, rozpoznanie zrodel)"
