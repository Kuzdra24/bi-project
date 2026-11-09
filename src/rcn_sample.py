"""Krok 2 – RCN (Rejestr Cen Nieruchomości): próbka lokali przez WFS, profilowanie, wykresy.

Zakres sterowany wyłącznie przez config.TERYT_POWIATY + DATE_FROM/DATE_TO,
więc ten sam kod działa dla dowolnego powiatu lub listy powiatów.

Uruchomienie:  uv run python src/rcn_sample.py
"""
import json
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import requests
from lxml import etree
from pyproj import Transformer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as C  # noqa: E402

WFS = "https://mapy.geoportal.gov.pl/wss/service/rcn"
RAW = C.RAW / "rcn"
FES = "http://www.opengis.net/fes/2.0"
TO_WGS84 = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)
# Pola z danymi osobowymi / zbędne analitycznie – nie trafiają do próbki
DROP = ["DOK_TWORCA", "DOK_OZNACZENIE", "SERWIS_RCN", "TRAN_PRZESTRZEN_NAZW"]


# ---------------------------------------------------------------- WFS helpers
def fes_filter(teryt: str, d_from: str, d_to_incl: str, extra: dict | None = None) -> str:
    # UWAGA: serwer RCN traktuje PropertyIsLessThan na dacie jak <= (sprawdzone 9.11.2026),
    # dlatego zakres podajemy jako [d_from, d_to_incl] – obie granice włącznie.
    conds = [
        f"<fes:PropertyIsEqualTo><fes:ValueReference>TERYT</fes:ValueReference><fes:Literal>{teryt}</fes:Literal></fes:PropertyIsEqualTo>",
        f"<fes:PropertyIsGreaterThanOrEqualTo><fes:ValueReference>DOK_DATA</fes:ValueReference><fes:Literal>{d_from}</fes:Literal></fes:PropertyIsGreaterThanOrEqualTo>",
        f"<fes:PropertyIsLessThanOrEqualTo><fes:ValueReference>DOK_DATA</fes:ValueReference><fes:Literal>{d_to_incl}</fes:Literal></fes:PropertyIsLessThanOrEqualTo>",
    ]
    for k, v in (extra or {}).items():
        conds.append(f"<fes:PropertyIsEqualTo><fes:ValueReference>{k}</fes:ValueReference><fes:Literal>{v}</fes:Literal></fes:PropertyIsEqualTo>")
    return f'<fes:Filter xmlns:fes="{FES}"><fes:And>{"".join(conds)}</fes:And></fes:Filter>'


def wfs_get(**params) -> requests.Response:
    base = dict(SERVICE="WFS", VERSION="2.0.0", REQUEST="GetFeature", TYPENAMES="ms:lokale")
    for attempt in range(3):
        try:
            r = requests.get(WFS, params={**base, **params}, timeout=180,
                             headers={"User-Agent": C.USER_AGENT})
            r.raise_for_status()
            if b"ExceptionReport" in r.content[:2000]:
                raise RuntimeError(r.text[:500])
            return r
        except (requests.RequestException, RuntimeError) as e:
            print(f"  ! próba {attempt + 1}: {e}")
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("WFS nie odpowiada")


def hits(flt: str) -> int:
    r = wfs_get(RESULTTYPE="hits", FILTER=flt)
    return int(etree.fromstring(r.content).get("numberMatched"))


def months() -> list[tuple[str, str]]:
    starts = pd.date_range(pd.Timestamp(C.DATE_FROM).to_period("M").to_timestamp(), pd.Timestamp(C.DATE_TO), freq="MS")
    return [(s.strftime("%Y-%m-%d"), (s + pd.offsets.MonthEnd(0)).strftime("%Y-%m-%d")) for s in starts]


# ---------------------------------------------------------------- parsing
def parse_gml(content: bytes) -> list[dict]:
    root = etree.fromstring(content)
    rows = []
    for feat in root.iter("{http://mapserver.gis.umn.edu/mapserver}lokale"):
        row = {}
        for el in feat:
            name = etree.QName(el).localname
            if name == "boundedBy":
                continue
            if name == "GEOMETRIA":
                pos = el.find(".//{*}pos").text.split()
                row["x_2180"], row["y_2180"] = float(pos[0]), float(pos[1])
            elif len(el):  # gml:timePosition
                row[name] = el[0].text
            else:
                row[name] = el.text if el.text not in (None, "") else None
        rows.append(row)
    return rows


# ---------------------------------------------------------------- main
def main():
    RAW.mkdir(parents=True, exist_ok=True)
    stats: dict = {"teryt": C.TERYT_POWIATY, "zakres": [str(C.DATE_FROM), str(C.DATE_TO)]}

    # 1) Wolumen per miesiąc – zapytania "hits" (bez pobierania danych)
    vol = []
    for teryt in C.TERYT_POWIATY:
        for d0, d1 in months():
            n_all = hits(fes_filter(teryt, d0, d1))
            n_res = hits(fes_filter(teryt, d0, d1, {"LOK_FUNKCJA": "mieszkalna"}))
            vol.append({"teryt": teryt, "miesiac": d0[:7], "lokale_wszystkie": n_all, "lokale_mieszkalne": n_res})
            print(f"  hits {teryt} {d0[:7]}: {n_all} (mieszkalne {n_res})")
    vol = pd.DataFrame(vol)
    vol.to_csv(C.SAMPLE / "rcn_wolumen_miesieczny.csv", index=False)

    # 2) Próbka: N lokali z każdego miesiąca (surowy GML zapisywany, ponowne uruchomienie korzysta z cache)
    rows = []
    for teryt in C.TERYT_POWIATY:
        for d0, d1 in months():
            p = RAW / f"lokale_{teryt}_{d0[:7]}.xml"
            if not p.exists():
                r = wfs_get(COUNT=C.RCN_SAMPLE_PER_MONTH, FILTER=fes_filter(teryt, d0, d1))
                p.write_bytes(r.content)
                time.sleep(1)
            rows += parse_gml(p.read_bytes())
    df = pd.DataFrame(rows)
    print(f"próbka: {len(df)} rekordów, {df.shape[1]} kolumn")

    # 3) Typy i pola pochodne
    num = ["TRAN_CENA_BRUTTO", "TRAN_VAT", "NIER_POW_GRUNTU", "NIER_CENA_BRUTTO", "NIER_VAT",
           "LOK_LICZBA_IZB", "LOK_NR_KOND", "LOK_POW_UZYT", "LOK_POW_PRZYN", "LOK_CENA_BRUTTO", "LOK_VAT"]
    for c in num:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["DOK_DATA"] = pd.to_datetime(df["DOK_DATA"], errors="coerce")
    df["TRAN_WERSJA_ID"] = pd.to_datetime(df["TRAN_WERSJA_ID"], errors="coerce", utc=True).dt.tz_localize(None)
    df["lon"], df["lat"] = TO_WGS84.transform(df["x_2180"].values, df["y_2180"].values)
    df["lokali_w_transakcji"] = df.groupby("TRAN_OZNACZENIE_TRANS")["gid"].transform("count")
    df["cena_zrodlo"] = df["LOK_CENA_BRUTTO"].notna().map({True: "LOK_CENA_BRUTTO", False: "TRAN_CENA_BRUTTO"})
    df["cena_lokalu"] = df["LOK_CENA_BRUTTO"].fillna(df["TRAN_CENA_BRUTTO"])
    df["cena_m2"] = df["cena_lokalu"] / df["LOK_POW_UZYT"]
    df["opoznienie_dni"] = (df["TRAN_WERSJA_ID"] - df["DOK_DATA"]).dt.days

    # 4) Profilowanie
    n = len(df)
    pct = lambda s: round(100 * s.mean(), 1)  # noqa: E731
    braki = (df.drop(columns=["x_2180", "y_2180", "lon", "lat"]).isna().mean() * 100).round(1).sort_values(ascending=False)
    stats["n_probka"] = n
    stats["n_wszystkie_w_zakresie"] = int(vol["lokale_wszystkie"].sum())
    stats["n_mieszkalne_w_zakresie"] = int(vol["lokale_mieszkalne"].sum())
    stats["braki_pct"] = braki[braki > 0].to_dict()
    for col in ["LOK_FUNKCJA", "TRAN_RODZAJ_TRANS", "TRAN_RODZAJ_RYNKU", "TRAN_SPRZEDAJACY",
                "TRAN_KUPUJACY", "NIER_PRAWO", "NIER_RODZAJ"]:
        stats[f"rozklad_{col}"] = df[col].fillna("<brak>").value_counts().to_dict()

    res = df[df["LOK_FUNKCJA"] == "mieszkalna"].copy()
    stats["mieszkalne_w_probce"] = len(res)
    stats["udzial_nie_1_1_pct"] = pct(res["NIER_UDZIAL"] != "1/1")
    stats["transakcje_wielolokalowe_pct"] = pct(res["lokali_w_transakcji"] > 1)
    stats["cena_z_LOK_CENA_pct"] = pct(res["cena_zrodlo"] == "LOK_CENA_BRUTTO")
    stats["brak_rynku_pct"] = pct(res["TRAN_RODZAJ_RYNKU"].isna())

    # duplikaty: ten sam lokal, data i cena (np. kilka wersji tego samego wpisu)
    dup_key = ["LOK_ID_LOKALU", "DOK_DATA", "TRAN_CENA_BRUTTO"]
    stats["duplikaty_lokal_data_cena"] = int(df.duplicated(dup_key).sum())
    stats["duplikaty_gid"] = int(df["gid"].duplicated().sum())

    # spójność: TERYT vs prefiks identyfikatora lokalu; współrzędne w granicach Polski
    stats["teryt_niezgodny_z_id_lokalu"] = int((df["LOK_ID_LOKALU"].str[:4] != df["TERYT"]).sum())
    in_pl = df["lon"].between(14.0, 24.2) & df["lat"].between(49.0, 55.0)
    stats["wspolrzedne_poza_PL"] = int((~in_pl).sum())
    stats["data_poza_zakresem"] = int((~df["DOK_DATA"].between(pd.Timestamp(C.DATE_FROM), pd.Timestamp(C.DATE_TO))).sum())

    # poprawność wartości (lokale mieszkalne)
    stats["pow_uzyt_podejrzana(<15 lub >250 m2)"] = int((~res["LOK_POW_UZYT"].between(15, 250)).sum())
    stats["cena_m2_podejrzana(<3000 lub >50000)"] = int((~res["cena_m2"].between(3000, 50000)).sum())
    stats["cena_m2_kwantyle"] = res["cena_m2"].quantile([0.01, 0.25, 0.5, 0.75, 0.99]).round(0).to_dict()
    stats["opoznienie_rejestracji_dni_kwantyle"] = df["opoznienie_dni"].quantile([0.1, 0.5, 0.9]).to_dict()

    # zbiór "czysty" do porównań: mieszkalne, wolny rynek, pełna własność 1/1, 1 lokal w transakcji
    clean = res[(res["TRAN_RODZAJ_TRANS"] == "wolnyRynek") & (res["NIER_UDZIAL"] == "1/1")
                & res["LOK_POW_UZYT"].between(15, 250) & res["cena_m2"].between(3000, 50000)]
    stats["czyste_rekordy"] = len(clean)
    stats["czyste_mediana_cena_m2_wg_rynku"] = clean.groupby(clean["TRAN_RODZAJ_RYNKU"].fillna("<brak>"))["cena_m2"].median().round(0).to_dict()

    # przykłady problemów do raportu
    ex = {}
    ex["niska_cena_m2"] = res.nsmallest(3, "cena_m2")[["DOK_DATA", "TRAN_RODZAJ_TRANS", "NIER_UDZIAL", "LOK_POW_UZYT", "TRAN_CENA_BRUTTO", "LOK_CENA_BRUTTO", "cena_m2"]]
    ex["wysoka_cena_m2"] = res.nlargest(3, "cena_m2")[["DOK_DATA", "TRAN_RODZAJ_TRANS", "lokali_w_transakcji", "LOK_POW_UZYT", "TRAN_CENA_BRUTTO", "LOK_CENA_BRUTTO", "cena_m2"]]
    multi = res[res["lokali_w_transakcji"] > 1].sort_values("TRAN_OZNACZENIE_TRANS").head(4)
    ex["transakcja_wielolokalowa"] = multi[["TRAN_OZNACZENIE_TRANS", "LOK_POW_UZYT", "TRAN_CENA_BRUTTO", "LOK_CENA_BRUTTO"]]

    print(json.dumps(stats, indent=1, ensure_ascii=False, default=str))
    for k, v in ex.items():
        print(f"\n-- przykład: {k}\n{v.to_string()}")

    # 5) Zapis próbki (bez danych osobowych)
    out = df.drop(columns=[c for c in DROP if c in df.columns])
    out.to_parquet(C.SAMPLE / "rcn_lokale_probka.parquet", index=False)
    out.head(200).to_csv(C.SAMPLE / "rcn_lokale_probka_head200.csv", index=False)
    (C.ROOT / "reports" / "rcn_stats.json").write_text(json.dumps(stats, indent=1, ensure_ascii=False, default=str))

    # 6) Wykresy
    src = f"Źródło: RCN (GUGiK), WFS, TERYT {','.join(C.TERYT_POWIATY)}"

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(clean["cena_m2"] / 1000, bins=50, color="#1f5f8b")
    ax.axvline(clean["cena_m2"].median() / 1000, color="#d1495b", ls="--",
               label=f"mediana {clean['cena_m2'].median():,.0f} zł/m²".replace(",", " "))
    ax.set_title(f"RCN – cena transakcyjna za m², lokale mieszkalne ({C.AREA_NAME}, próbka n={len(clean)})")
    ax.set_xlabel("tys. zł / m²"); ax.set_ylabel("liczba transakcji"); ax.legend(frameon=False)
    ax.text(1, -0.16, src, transform=ax.transAxes, ha="right", fontsize=8, color="gray")
    fig.tight_layout(); fig.savefig(C.FIGURES / "01_rcn_cena_m2_hist.png", dpi=150); plt.close(fig)

    v = vol.groupby("miesiac")[["lokale_wszystkie", "lokale_mieszkalne"]].sum()
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(v.index, v["lokale_wszystkie"], color="#c9d6e3", label="wszystkie lokale")
    ax.bar(v.index, v["lokale_mieszkalne"], color="#1f5f8b", label="lokale mieszkalne")
    ax.set_title(f"RCN – liczba transakcji lokalami wg miesiąca aktu ({C.AREA_NAME})")
    ax.set_ylabel("liczba lokali"); ax.legend(frameon=False)
    ax.tick_params(axis="x", rotation=60, labelsize=8)
    ax.text(1, -0.28, src + f" (stan na {C.DATE_TO})", transform=ax.transAxes, ha="right", fontsize=8, color="gray")
    fig.tight_layout(); fig.savefig(C.FIGURES / "02_rcn_transakcje_miesiecznie.png", dpi=150); plt.close(fig)

    b = braki[braki > 0].sort_values()
    fig, ax = plt.subplots(figsize=(8, 0.32 * len(b) + 1.2))
    ax.barh(b.index, b.values, color=["#d1495b" if x > 50 else "#f2b134" if x > 5 else "#1f5f8b" for x in b.values])
    ax.set_xlabel("% pustych wartości"); ax.set_xlim(0, 100)
    ax.set_title(f"RCN – kompletność pól (próbka n={n})")
    for i, x in enumerate(b.values):
        ax.text(x + 1, i, f"{x:.0f}%", va="center", fontsize=8)
    fig.tight_layout(); fig.savefig(C.FIGURES / "03_rcn_braki_pol.png", dpi=150); plt.close(fig)

    lag = df["opoznienie_dni"].dropna()
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(lag.clip(upper=365), bins=52, color="#1f5f8b")
    ax.axvline(lag.median(), color="#d1495b", ls="--", label=f"mediana {lag.median():.0f} dni")
    ax.set_title("RCN – opóźnienie wpisu do rejestru (TRAN_WERSJA_ID − DOK_DATA)")
    ax.set_xlabel("dni (obcięte do 365)"); ax.set_ylabel("liczba lokali"); ax.legend(frameon=False)
    ax.text(1, -0.16, src, transform=ax.transAxes, ha="right", fontsize=8, color="gray")
    fig.tight_layout(); fig.savefig(C.FIGURES / "11_rcn_opoznienie_rejestracji.png", dpi=150); plt.close(fig)
    print("wykresy zapisane w reports/figures/")


if __name__ == "__main__":
    main()
