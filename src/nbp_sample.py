"""Krok 1 – NBP: pobranie stóp procentowych (XML), profilowanie, wykres.

Uruchomienie:  uv run python src/nbp_sample.py
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import requests
from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as C  # noqa: E402

URLS = {
    "biezace": "https://static.nbp.pl/dane/stopy/stopy_procentowe.xml",
    "archiwum": "https://static.nbp.pl/dane/stopy/stopy_procentowe_archiwum.xml",
}
NAMES = {"ref": "referencyjna", "lom": "lombardowa", "dep": "depozytowa",
         "red": "redyskontowa", "dys": "dyskontowa"}
RAW = C.RAW / "nbp"


def fetch() -> dict[str, Path]:
    RAW.mkdir(parents=True, exist_ok=True)
    paths = {}
    for key, url in URLS.items():
        r = requests.get(url, headers={"User-Agent": C.USER_AGENT}, timeout=30)
        r.raise_for_status()
        p = RAW / Path(url).name
        p.write_bytes(r.content)
        paths[key] = p
    return paths


def pl_float(s: str) -> float:
    return float(s.replace(",", "."))


def parse_archive(path: Path) -> tuple[pd.DataFrame, str]:
    root = etree.parse(str(path)).getroot()
    rows = []
    for grp in root.iter("pozycje"):
        for poz in grp.iter("pozycja"):
            rows.append({"obowiazuje_od": grp.get("obowiazuje_od"), "id": poz.get("id"),
                         "oprocentowanie_raw": poz.get("oprocentowanie")})
    df = pd.DataFrame(rows)
    df["obowiazuje_od"] = pd.to_datetime(df["obowiazuje_od"], format="%Y-%m-%d")
    df["oprocentowanie"] = df["oprocentowanie_raw"].map(pl_float)
    return df, root.get("data_publikacji")


def parse_current(path: Path) -> tuple[pd.DataFrame, str]:
    root = etree.parse(str(path)).getroot()
    rows = [{"id": p.get("id"), "oprocentowanie": pl_float(p.get("oprocentowanie")),
             "obowiazuje_od": pd.to_datetime(p.get("obowiazuje_od"))}
            for p in root.iter("pozycja")]
    return pd.DataFrame(rows), root.get("data_publikacji")


def monthly(events: pd.DataFrame) -> pd.DataFrame:
    """Zdarzenia 'obowiązuje od' -> szereg miesięczny (stan na koniec miesiąca)."""
    wide = events.pivot(index="obowiazuje_od", columns="id", values="oprocentowanie").sort_index()
    idx = pd.date_range(wide.index.min(), pd.Timestamp(C.DATE_TO), freq="ME")
    m = wide.reindex(wide.index.union(idx)).ffill().loc[idx]
    m.index = m.index.to_period("M")
    return m


def main():
    paths = fetch()
    arch, arch_pub = parse_archive(paths["archiwum"])
    cur, cur_pub = parse_current(paths["biezace"])

    # --- profilowanie ---
    print("== NBP – profil ==")
    print(f"archiwum: {len(arch)} pozycji, {arch['obowiazuje_od'].nunique()} zmian, "
          f"{arch['obowiazuje_od'].min().date()} .. {arch['obowiazuje_od'].max().date()}, "
          f"atrybut data_publikacji={arch_pub}")
    print(f"bieżące: {len(cur)} stóp, data_publikacji={cur_pub}")
    print("pozycje per rodzaj stopy (od kiedy występuje):")
    print(arch.groupby("id")["obowiazuje_od"].agg(["count", "min"]).rename(index=NAMES))

    dup = arch.duplicated(["obowiazuje_od", "id"]).sum()
    bad_fmt = (~arch["oprocentowanie_raw"].str.fullmatch(r"\d+,\d{2}")).sum()
    print(f"duplikaty (data, stopa): {dup}; niestandardowy format liczby: {bad_fmt}")

    last = arch[arch["obowiazuje_od"] == arch["obowiazuje_od"].max()].set_index("id")["oprocentowanie"]
    cmp = cur.set_index("id")["oprocentowanie"].to_frame("biezace").join(last.rename("archiwum"))
    cmp["zgodne"] = cmp["biezace"] == cmp["archiwum"]
    print("spójność bieżące vs ostatni wpis archiwum:\n", cmp)

    m = monthly(arch)
    win = m.loc[str(C.DATE_FROM)[:7]:]
    print(f"szereg miesięczny w zakresie projektu: {len(win)} mies., braki ref: {win['ref'].isna().sum()}")
    changes = arch[(arch["id"] == "ref") & (arch["obowiazuje_od"] >= pd.Timestamp(C.DATE_FROM))]
    print("zmiany stopy referencyjnej w zakresie projektu:\n", changes[["obowiazuje_od", "oprocentowanie"]].to_string(index=False))

    # --- zapis próbek ---
    C.SAMPLE.mkdir(parents=True, exist_ok=True)
    arch.drop(columns="oprocentowanie_raw").assign(stopa=lambda d: d["id"].map(NAMES)) \
        .to_csv(C.SAMPLE / "nbp_stopy_zdarzenia.csv", index=False)
    m.rename(columns=NAMES).to_csv(C.SAMPLE / "nbp_stopy_miesieczne.csv")

    # --- wykres ---
    C.FIGURES.mkdir(parents=True, exist_ok=True)
    ref = arch[arch["id"] == "ref"].set_index("obowiazuje_od")["oprocentowanie"]
    ref = pd.concat([ref, pd.Series([ref.iloc[-1]], index=[pd.Timestamp(C.DATE_TO)])])
    start = pd.Timestamp("2019-01-01")
    ref = pd.concat([pd.Series([ref.asof(start)], index=[start]), ref.loc[start:]])
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.step(ref.index, ref.values, where="post", color="#1f5f8b", lw=2)
    ax.axvspan(pd.Timestamp(C.DATE_FROM), pd.Timestamp(C.DATE_TO), color="#f2b134", alpha=0.18,
               label="zakres projektu (~2 lata)")
    ax.set_title("Stopa referencyjna NBP (2019–2026)")
    ax.set_ylabel("%")
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left", frameon=False)
    ax.text(0.99, -0.14, "Źródło: NBP, stopy_procentowe_archiwum.xml", transform=ax.transAxes,
            ha="right", fontsize=8, color="gray")
    fig.tight_layout()
    out = C.FIGURES / "06_nbp_stopa_referencyjna.png"
    fig.savefig(out, dpi=150)
    print("wykres:", out.relative_to(C.ROOT))


if __name__ == "__main__":
    main()
