"""Wspólne parametry etapu rozpoznania źródeł – jedno miejsce do zmiany zakresu."""
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw"
SAMPLE = ROOT / "data" / "sample"
FIGURES = ROOT / "reports" / "figures"

# Zakres czasowy: ostatnie ~2 lata
DATE_FROM = date(2024, 11, 1)
DATE_TO = date(2026, 11, 9)

# Zakres geograficzny – definiowany WYŁĄCZNIE kodami TERYT powiatów, żeby ten sam kod
# działał dla dowolnego miasta / całej Polski (lista powiatów). Bez nazw dzielnic itp.
AREA_NAME = "Wrocław"
TERYT_POWIATY = ["0264"]   # 0264 = m. Wrocław (miasto na prawach powiatu)

# Próbkowanie RCN: tyle lokali z każdego miesiąca zakresu
RCN_SAMPLE_PER_MONTH = 150

USER_AGENT = "BI-student-project/0.1 (projekt uczelniany, rozpoznanie zrodel)"
