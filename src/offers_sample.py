"""Krok 4 – Oferty: zbiór Kaggle „Apartment Prices in Poland” (Apache 2.0), profilowanie, wykresy.

Pobranie (bez logowania):
  curl -L -o data/raw/kaggle/apartment-prices-in-poland.zip \
       https://www.kaggle.com/api/v1/datasets/download/krzysztofjamroz/apartment-prices-in-poland
  unzip data/raw/kaggle/apartment-prices-in-poland.zip -d data/raw/kaggle/extracted

Uruchomienie:  uv run python src/offers_sample.py
"""
import json
import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as C  # noqa: E402

SRC_DIR = C.RAW / "kaggle" / "extracted"


def load() -> pd.DataFrame:
    frames = []
    for p in sorted(SRC_DIR.glob("apartments_pl_*.csv")):  # tylko sprzedaż (bez *_rent_*)
        y, m = re.search(r"(\d{4})_(\d{2})", p.name).groups()
        df = pd.read_csv(p)
        df["snapshot"] = pd.Period(f"{y}-{m}", "M")
        df["plik"] = p.name
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def main():
    raw = load()
    st: dict = {"pliki_sprzedaz": int(raw["plik"].nunique()), "wiersze_cala_PL": len(raw),
                "kolumny": list(raw.columns[:-2]), "snapshoty": [str(raw["snapshot"].min()), str(raw["snapshot"].max())],
                "miasta": raw["city"].value_counts().to_dict()}

    # --- profil całego zbioru (wszystkie miasta) – pokazuje, jak zbiór zachowa się przy skali „cała Polska”
    st["braki_pct_cala_PL"] = (raw.isna().mean() * 100).round(1)[lambda s: s > 0].sort_values(ascending=False).to_dict()
    st["id_unikalne_cala_PL"] = int(raw["id"].nunique())
    st["duplikaty_id_w_tym_samym_snapshocie"] = int(raw.duplicated(["snapshot", "id"]).sum())

    # --- zawężenie do obszaru projektu (kody TERYT jak w RCN)
    raw["teryt"] = raw["city"].map(C.KAGGLE_CITY_TO_TERYT)
    df = raw[raw["teryt"].isin(C.TERYT_POWIATY)].copy()
    df["cena_m2"] = df["price"] / df["squareMeters"]
    n = len(df)
    st["obszar"] = {"teryt": C.TERYT_POWIATY, "wiersze": n, "unikalne_id": int(df["id"].nunique()),
                    "oferty_na_snapshot": df.groupby("snapshot").size().astype(int).rename(str).to_dict()}

    # kompletność
    braki = (df.drop(columns=["teryt", "cena_m2", "plik", "snapshot"]).isna().mean() * 100).round(1).sort_values(ascending=False)
    st["obszar"]["braki_pct"] = braki[braki > 0].to_dict()

    # unikalność / trwałość ofert w kolejnych migawkach
    per_id = df.groupby("id").agg(n_snap=("snapshot", "nunique"), p_min=("price", "min"), p_max=("price", "max"))
    st["obszar"]["ile_migawek_na_oferte"] = per_id["n_snap"].value_counts().sort_index().to_dict()
    st["obszar"]["oferty_ze_zmiana_ceny_pct"] = round(100 * (per_id["p_max"] > per_id["p_min"]).mean(), 1)
    chg = per_id[per_id["p_max"] > per_id["p_min"]]
    st["obszar"]["mediana_zmiany_ceny_pct(min->max)"] = round(float(((chg["p_max"] / chg["p_min"] - 1) * 100).median()), 1) if len(chg) else None
    # „te same mieszkania pod różnymi id” – kandydaci na duplikaty (np. kilku pośredników)
    key = ["snapshot", "latitude", "longitude", "squareMeters", "floor", "price"]
    st["obszar"]["podejrzane_duplikaty_inne_id(te_same_wsp_pow_pietro_cena)"] = int(df.duplicated(key).sum())
    key2 = ["snapshot", "latitude", "longitude", "squareMeters", "floor"]
    st["obszar"]["podejrzane_duplikaty_inne_id(bez_ceny)"] = int(df.duplicated(key2).sum())

    # poprawność wartości
    st["obszar"]["pow_poza_[15,250]"] = int((~df["squareMeters"].between(15, 250)).sum())
    st["obszar"]["cena_m2_poza_[3000,50000]"] = int((~df["cena_m2"].between(3000, 50000)).sum())
    st["obszar"]["pietro_wieksze_niz_liczba_pieter"] = int((df["floor"] > df["floorCount"]).sum())
    st["obszar"]["rok_budowy_poza_[1850,2030]"] = int((~df["buildYear"].dropna().between(1850, 2030)).sum())
    st["obszar"]["rok_budowy_po_roku_migawki(rynek_pierwotny?)_pct"] = round(
        100 * (df["buildYear"] >= df["snapshot"].dt.year).mean(), 1)
    st["obszar"]["wspolrzedne_powtarzalne(top5)"] = df.groupby(["latitude", "longitude"]).size().nlargest(5).astype(int).tolist()
    st["obszar"]["cena_m2_kwantyle"] = df["cena_m2"].quantile([0.01, 0.25, 0.5, 0.75, 0.99]).round(0).to_dict()
    st["obszar"]["slowniki"] = {c: df[c].fillna("<brak>").value_counts().to_dict()
                                for c in ["type", "ownership", "buildingMaterial", "condition"]}

    # przykłady problemów
    ex = {
        "zmiana_ceny_tej_samej_oferty": df[df["id"].isin(chg.index[:1])][["id", "snapshot", "price", "squareMeters"]],
        "duplikat_inne_id": df[df.duplicated(key, keep=False)].sort_values(key).head(4)[["id", "snapshot", "latitude", "longitude", "squareMeters", "floor", "price"]],
        "pietro_gt_liczba_pieter": df[df["floor"] > df["floorCount"]].head(3)[["id", "floor", "floorCount", "buildYear"]],
    }
    print(json.dumps(st, indent=1, ensure_ascii=False, default=str))
    for k, v in ex.items():
        print(f"\n-- przykład: {k}\n{v.to_string()}")

    # --- zapis
    out = df.drop(columns=["plik"]).assign(snapshot=lambda d: d["snapshot"].astype(str))
    out.to_parquet(C.SAMPLE / "oferty_kaggle_obszar.parquet", index=False)
    out.head(200).to_csv(C.SAMPLE / "oferty_kaggle_obszar_head200.csv", index=False)
    (C.ROOT / "reports" / "offers_stats.json").write_text(json.dumps(st, indent=1, ensure_ascii=False, default=str))

    # --- wykresy
    src = "Źródło: Kaggle „Apartment Prices in Poland” (K. Jamroz, Apache 2.0)"
    last = df[df["snapshot"] == df["snapshot"].max()]
    ok = last[last["cena_m2"].between(3000, 50000)]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(ok["cena_m2"] / 1000, bins=50, color="#f2b134")
    ax.axvline(ok["cena_m2"].median() / 1000, color="#d1495b", ls="--",
               label=f"mediana {ok['cena_m2'].median():,.0f} zł/m²".replace(",", " "))
    ax.set_title(f"Oferty – cena ofertowa za m² ({C.AREA_NAME}, migawka {df['snapshot'].max()}, n={len(ok)})")
    ax.set_xlabel("tys. zł / m²"); ax.set_ylabel("liczba ofert"); ax.legend(frameon=False)
    ax.text(1, -0.24, src, transform=ax.transAxes, ha="right", fontsize=8, color="gray")
    fig.tight_layout(); fig.savefig(C.FIGURES / "04_oferty_cena_m2_hist.png", dpi=150); plt.close(fig)

    b = braki[braki > 0].sort_values()
    fig, ax = plt.subplots(figsize=(8, 0.32 * len(b) + 1.2))
    ax.barh(b.index, b.values, color=["#d1495b" if x > 50 else "#f2b134" if x > 5 else "#1f5f8b" for x in b.values])
    for i, x in enumerate(b.values):
        ax.text(x + 1, i, f"{x:.0f}%", va="center", fontsize=8)
    ax.set_xlim(0, 100); ax.set_xlabel("% pustych wartości")
    ax.set_title(f"Oferty – kompletność pól ({C.AREA_NAME}, {n} wierszy, {df['snapshot'].nunique()} migawek)")
    fig.tight_layout(); fig.savefig(C.FIGURES / "05_oferty_braki_pol.png", dpi=150); plt.close(fig)

    vc = per_id["n_snap"].value_counts().sort_index()
    fig, ax = plt.subplots(figsize=(8, 3.5))
    ax.bar(vc.index.astype(str), vc.values, color="#f2b134")
    ax.set_title("Oferty – w ilu miesięcznych migawkach pojawia się ta sama oferta (id)")
    ax.set_xlabel("liczba migawek"); ax.set_ylabel("liczba ofert")
    ax.text(1, -0.3, src, transform=ax.transAxes, ha="right", fontsize=8, color="gray")
    fig.tight_layout(); fig.savefig(C.FIGURES / "13_oferty_trwalosc_w_migawkach.png", dpi=150); plt.close(fig)
    print("wykresy zapisane w reports/figures/")


if __name__ == "__main__":
    main()
