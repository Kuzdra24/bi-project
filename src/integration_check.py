"""Krok 5 – Integracja: test łączenia ofert (Kaggle), transakcji (RCN) i stóp NBP na próbkach.

Oferta i transakcja to różne zdarzenia bez wspólnego klucza, więc łączymy je przez wspólne wymiary:
  czas (miesiąc) × obszar (TERYT, siatka 1 km w EPSG:2180 – ogólna, bez nazw dzielnic) × przedział powierzchni.
NBP łączy się z obiema stronami po miesiącu.

Uruchomienie:  uv run python src/integration_check.py
(wymaga: src/nbp_sample.py, src/rcn_sample.py, src/offers_sample.py)
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pyproj import Transformer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as C  # noqa: E402

TO_2180 = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)
AREA_BINS = [0, 38, 50, 65, 80, 1000]
AREA_LABELS = ["<38", "38–50", "50–65", "65–80", "80+"]
GRID_M = 1000
MIN_N = 10  # minimalna liczba obserwacji po każdej stronie, żeby porównywać mediany


def load():
    rcn = pd.read_parquet(C.SAMPLE / "rcn_lokale_probka.parquet")
    rcn = rcn[(rcn["LOK_FUNKCJA"] == "mieszkalna") & (rcn["TRAN_RODZAJ_TRANS"] == "wolnyRynek")
              & (rcn["NIER_UDZIAL"] == "1/1") & rcn["LOK_POW_UZYT"].between(15, 250)
              & rcn["cena_m2"].between(3000, 50000)].copy()
    rcn = rcn.assign(zrodlo="transakcja (RCN)", miesiac=rcn["DOK_DATA"].dt.to_period("M"),
                     pow=rcn["LOK_POW_UZYT"], x=rcn["x_2180"], y=rcn["y_2180"], teryt=rcn["TERYT"])

    off = pd.read_parquet(C.SAMPLE / "oferty_kaggle_obszar.parquet")
    off = off[off["cena_m2"].between(3000, 50000)].copy()
    x, y = TO_2180.transform(off["longitude"].values, off["latitude"].values)
    off = off.assign(zrodlo="oferta (Kaggle)", miesiac=pd.PeriodIndex(off["snapshot"], freq="M"),
                     pow=off["squareMeters"], x=x, y=y)

    nbp = pd.read_csv(C.SAMPLE / "nbp_stopy_miesieczne.csv", index_col=0)
    nbp.index = pd.PeriodIndex(nbp.index, freq="M")
    return rcn, off, nbp


def add_dims(df):
    df = df.copy()
    df["pow_przedzial"] = pd.cut(df["pow"], AREA_BINS, labels=AREA_LABELS, right=False)
    df["komorka_1km"] = (df["x"] // GRID_M).astype(int).astype(str) + "_" + (df["y"] // GRID_M).astype(int).astype(str)
    return df


def gap_table(rcn, off, by):
    a = rcn.groupby(by, observed=True)["cena_m2"].agg(transakcja_mediana="median", n_trans="size")
    b = off.groupby(by, observed=True)["cena_m2"].agg(oferta_mediana="median", n_ofert="size")
    t = a.join(b, how="outer")
    t["luka_pct"] = (t["oferta_mediana"] / t["transakcja_mediana"] - 1) * 100
    return t


def main():
    rcn, off, nbp = load()
    rcn, off = add_dims(rcn), add_dims(off)
    st: dict = {"rcn_rekordy_po_czyszczeniu": len(rcn), "oferty_wiersze": len(off),
                "okno": [str(C.DATE_FROM), str(C.DATE_TO)]}

    # 1) klucz czasu: pokrycie miesięcy po obu stronach + NBP
    m_rcn, m_off = set(rcn["miesiac"]), set(off["miesiac"])
    st["miesiace_rcn"], st["miesiace_ofert"] = len(m_rcn), len(m_off)
    st["miesiace_wspolne"] = len(m_rcn & m_off)
    st["nbp_pokrycie_miesiecy_rcn_pct"] = round(100 * np.mean([m in nbp.index for m in m_rcn]), 1)
    st["nbp_pokrycie_miesiecy_ofert_pct"] = round(100 * np.mean([m in nbp.index for m in m_off]), 1)

    # 2) klucz obszaru: TERYT (oba źródła) + siatka 1 km
    st["teryt_rcn"] = sorted(rcn["teryt"].unique().tolist()); st["teryt_oferty"] = sorted(off["teryt"].unique().tolist())
    g = gap_table(rcn, off, ["komorka_1km"])
    both = g[(g["n_trans"] >= MIN_N) & (g["n_ofert"] >= MIN_N)]
    st["komorki_1km_z_transakcjami"] = int(g["n_trans"].notna().sum())
    st["komorki_1km_z_ofertami"] = int(g["n_ofert"].notna().sum())
    st[f"komorki_1km_porownywalne(>= {MIN_N} po obu stronach)"] = len(both)
    st["oferty_w_porownywalnych_komorkach_pct"] = round(100 * off["komorka_1km"].isin(both.index).mean(), 1)

    # 3) wyniki: luka ofertowa
    city = gap_table(rcn.assign(all="miasto"), off.assign(all="miasto"), ["all"]).iloc[0]
    st["miasto_mediana_transakcja"] = round(city["transakcja_mediana"]); st["miasto_mediana_oferta"] = round(city["oferta_mediana"])
    st["miasto_luka_pct"] = round(city["luka_pct"], 1)
    by_area = gap_table(rcn, off, ["pow_przedzial"])
    by_month = gap_table(rcn, off, ["miesiac"]).join(nbp["referencyjna"])
    st["luka_wg_powierzchni"] = by_area[["transakcja_mediana", "oferta_mediana", "luka_pct", "n_trans", "n_ofert"]].round(1).to_dict("index")
    st["luka_komorki_1km_kwantyle"] = both["luka_pct"].quantile([0.1, 0.5, 0.9]).round(1).to_dict()

    print(json.dumps(st, indent=1, ensure_ascii=False, default=str))
    print(by_month.round(1).to_string())
    by_month.to_csv(C.SAMPLE / "integracja_luka_miesieczna.csv")
    by_area.to_csv(C.SAMPLE / "integracja_luka_wg_powierzchni.csv")
    both.to_csv(C.SAMPLE / "integracja_luka_siatka_1km.csv")
    (C.ROOT / "reports" / "integration_stats.json").write_text(json.dumps(st, indent=1, ensure_ascii=False, default=str))

    src = "Źródła: RCN (GUGiK), Kaggle „Apartment Prices in Poland” (Apache 2.0), NBP"
    COL_T, COL_O = "#1f5f8b", "#f2b134"

    # 09 – główny wykres: oferta vs transakcja wg przedziału powierzchni
    fig, ax = plt.subplots(figsize=(8, 4.2))
    xi = np.arange(len(by_area))
    ax.bar(xi - 0.2, by_area["transakcja_mediana"] / 1000, 0.4, color=COL_T, label="transakcja (RCN)")
    ax.bar(xi + 0.2, by_area["oferta_mediana"] / 1000, 0.4, color=COL_O, label="oferta (Kaggle)")
    for i, (_, r) in enumerate(by_area.iterrows()):
        ax.text(i, max(r["transakcja_mediana"], r["oferta_mediana"]) / 1000 + 0.3, f"{r['luka_pct']:+.0f}%",
                ha="center", fontsize=9, color="#d1495b", fontweight="bold")
    ax.set_xticks(xi, [f"{l} m²" for l in by_area.index])
    ax.set_ylabel("mediana, tys. zł / m²")
    ax.set_title(f"Oferta vs transakcja – mediana ceny za m² wg powierzchni ({C.AREA_NAME}, {C.DATE_FROM:%m.%Y}–{C.DATE_TO:%m.%Y})", fontsize=10)
    ax.set_ylim(0, ax.get_ylim()[1] * 1.22); ax.legend(frameon=False, loc="upper right", ncol=2)
    ax.text(1, -0.16, src + "  |  czerwone: luka ofertowa", transform=ax.transAxes, ha="right", fontsize=7, color="gray")
    fig.tight_layout(); fig.savefig(C.FIGURES / "09_oferta_vs_transakcja_powierzchnia.png", dpi=150); plt.close(fig)

    # 10 – w czasie + stopa NBP
    bm = by_month.dropna(subset=["transakcja_mediana", "oferta_mediana"])
    xs = bm.index.astype(str)
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.plot(xs, bm["transakcja_mediana"] / 1000, "o-", color=COL_T, label="transakcja (RCN)")
    ax.plot(xs, bm["oferta_mediana"] / 1000, "o-", color=COL_O, label="oferta (Kaggle)")
    ax.set_ylabel("mediana, tys. zł / m²"); ax.tick_params(axis="x", rotation=45)
    ax2 = ax.twinx()
    ax2.step(xs, bm["referencyjna"], where="mid", color="gray", ls="--", label="stopa ref. NBP (%)")
    ax2.set_ylabel("stopa referencyjna NBP, %"); ax2.set_ylim(0, max(8, bm["referencyjna"].max() + 1))
    h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, frameon=False, loc="lower left", fontsize=8)
    ax.set_title(f"Oferta vs transakcja w czasie + stopa NBP ({C.AREA_NAME}) – połączenie po miesiącu")
    ax.text(1, -0.27, src, transform=ax.transAxes, ha="right", fontsize=7, color="gray")
    fig.tight_layout(); fig.savefig(C.FIGURES / "10_oferta_vs_transakcja_w_czasie.png", dpi=150); plt.close(fig)

    # 14 – mapa siatki 1 km: luka ofertowa tam, gdzie obie strony mają >= MIN_N obserwacji
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.scatter(rcn["x"], rcn["y"], s=2, color=COL_T, alpha=0.25, label="transakcje (RCN)")
    ax.scatter(off["x"], off["y"], s=2, color=COL_O, alpha=0.15, label="oferty (Kaggle)")
    if len(both):
        cx = both.index.str.split("_").str[0].astype(int) * GRID_M + GRID_M / 2
        cy = both.index.str.split("_").str[1].astype(int) * GRID_M + GRID_M / 2
        lim = max(5, np.nanpercentile(np.abs(both["luka_pct"]), 95))
        sc = ax.scatter(cx, cy, c=both["luka_pct"], cmap="RdBu_r", vmin=-lim, vmax=lim, s=160, marker="s",
                        edgecolor="k", linewidth=0.3)
        fig.colorbar(sc, ax=ax, shrink=0.7, label="luka ofertowa, % (oferta/transakcja − 1)")
    ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
    ax.set_title(f"Siatka 1 km: komórki porównywalne (≥{MIN_N} ofert i ≥{MIN_N} transakcji)", fontsize=10)
    ax.legend(frameon=False, loc="lower left", fontsize=8, markerscale=4)
    ax.text(1, -0.04, "EPSG:2180; " + src, transform=ax.transAxes, ha="right", fontsize=7, color="gray")
    fig.tight_layout(); fig.savefig(C.FIGURES / "14_luka_siatka_1km.png", dpi=150); plt.close(fig)
    print("wykresy zapisane w reports/figures/")


if __name__ == "__main__":
    main()
