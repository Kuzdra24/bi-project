"""Krok 3 – OpenStreetMap: obiekty otoczenia (komunikacja, zieleń, usługi),
profilowanie i test łączenia z punktami transakcji RCN.

Dwa sposoby dostępu do tych samych danych OSM:
  - geofabrik (domyślnie): lokalny plik .osm.pbf z download.geofabrik.de, odczyt pyosmium
  - overpass: zapytania do publicznego Overpass API (9.11.2026 przeciążone – HTTP 502)

Obszar wyznaczany WYŁĄCZNIE kodem TERYT powiatu (granica OSM z tagiem teryt:terc, admin_level=6),
więc kod działa bez zmian dla dowolnego powiatu z config.TERYT_POWIATY.

Uruchomienie:  uv run python src/osm_sample.py [geofabrik|overpass]   (wymaga wcześniej src/rcn_sample.py)
"""
import json
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
from pyproj import Transformer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as C  # noqa: E402

sys.stdout.reconfigure(line_buffering=True)  # widoczny postęp także przy uruchomieniu w tle

ENDPOINTS = ["https://overpass-api.de/api/interpreter",
             "https://overpass.kumi.systems/api/interpreter",
             "https://overpass.private.coffee/api/interpreter"]
RAW = C.RAW / "osm"
TO_2180 = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)

# grupa -> kategoria -> lista (klucz OSM, dopuszczalne wartości)
CATEGORIES = {
    "komunikacja": {
        "przystanek_autobusowy": [("highway", ["bus_stop"])],
        "przystanek_tramwajowy": [("railway", ["tram_stop"])],
        "stacja_kolejowa": [("railway", ["station", "halt"])],
        "peron_PT": [("public_transport", ["platform"])],
        "stop_position_PT": [("public_transport", ["stop_position"])],
    },
    "zielen": {
        "park": [("leisure", ["park"])],
        "las": [("landuse", ["forest"]), ("natural", ["wood"])],
    },
    "uslugi": {
        "sklep_spozywczy": [("shop", ["supermarket", "convenience"])],
        "szkola": [("amenity", ["school"])],
        "przedszkole": [("amenity", ["kindergarten"])],
        "przychodnia_lekarz": [("amenity", ["clinic", "doctors"])],
        "apteka": [("amenity", ["pharmacy"])],
    },
}


def selector(key: str, values: list[str]) -> str:
    return f'nwr["{key}"="{values[0]}"]' if len(values) == 1 else f'nwr["{key}"~"^({"|".join(values)})$"]'


def overpass(query: str) -> dict:
    wait = 10
    for attempt in range(6):
        url = ENDPOINTS[attempt % len(ENDPOINTS)]
        try:
            r = requests.post(url, data={"data": query}, timeout=200,
                              headers={"User-Agent": C.USER_AGENT})
            if r.status_code == 200:
                return r.json()
            print(f"  ! {url} -> HTTP {r.status_code}, czekam {wait}s")
        except requests.RequestException as e:
            print(f"  ! {url} -> {e}, czekam {wait}s")
        time.sleep(wait)
        wait *= 2
    raise RuntimeError("Overpass niedostępny")


def fetch_group(teryt: str, group: str, cats: dict) -> dict:
    p = RAW / f"{teryt}_{group}.json"
    if p.exists():
        return json.loads(p.read_text())
    sel = "".join(f"{selector(k, v)}(area.a);" for rules in cats.values() for k, v in rules)
    q = (f'[out:json][timeout:180];'
         f'rel["boundary"="administrative"]["admin_level"="6"]["teryt:terc"="{teryt}"];map_to_area->.a;'
         f'({sel});out center tags meta;')
    data = overpass(q)
    p.write_text(json.dumps(data))
    time.sleep(5)
    return data


def classify(tags: dict) -> list[str]:
    """Do których kategorii należy obiekt (może do kilku – np. bus_stop + platform)."""
    return [cat for cats in CATEGORIES.values() for cat, rules in cats.items()
            if any(tags.get(k) in v for k, v in rules)]


def to_rows(teryt: str, group: str, data: dict) -> list[dict]:
    rows = []
    for el in data["elements"]:
        tags = el.get("tags", {})
        lat = el.get("lat", el.get("center", {}).get("lat"))
        lon = el.get("lon", el.get("center", {}).get("lon"))
        for cat in classify(tags):
            if cat not in CATEGORIES[group]:
                continue
            rows.append({"teryt": teryt, "grupa": group, "kategoria": cat, "osm_type": el["type"],
                         "osm_id": el["id"], "name": tags.get("name"), "lat": lat, "lon": lon,
                         "last_edit": el.get("timestamp"), "version": el.get("version")})
    return rows  # pola user/uid (dane osobowe edytorów) celowo pomijamy


GEOFABRIK_PBF = C.RAW / "geofabrik" / "dolnoslaskie-latest.osm.pbf"
GEOFABRIK_URL = "https://download.geofabrik.de/europe/poland/dolnoslaskie-latest.osm.pbf"


def read_geofabrik(pbf: Path) -> tuple[list[dict], str]:
    """Jedno przejście po pliku PBF (pyosmium): granice powiatów po teryt:terc + obiekty kategorii.
    Obiekty powierzchniowe reprezentuje środek (średnia współrzędnych węzłów / centroid multipoligonu)."""
    import osmium
    import shapely

    teryts = set(C.TERYT_POWIATY)
    wkb = osmium.geom.WKBFactory()
    keys = {k for cats in CATEGORIES.values() for rules in cats.values() for k, _ in rules}

    class H(osmium.SimpleHandler):
        def __init__(self):
            super().__init__()
            self.objs, self.bounds, self.invalid = [], {}, []

        def _keep(self, o, otype, lat, lon, osm_id=None):
            if not any(k in o.tags for k in keys):
                return
            tags = {k: o.tags.get(k) for k in keys | {"name"} if k in o.tags}
            cats = classify(tags)
            if cats:
                self.objs.append({"osm_type": otype, "osm_id": osm_id or o.id, "name": tags.get("name"), "lat": lat,
                                  "lon": lon, "last_edit": o.timestamp.isoformat(), "version": o.version, "cats": cats})

        def node(self, n):
            if n.tags:
                self._keep(n, "node", n.location.lat, n.location.lon)

        def way(self, w):
            if w.tags and any(k in w.tags for k in keys):
                pts = [(nd.location.lat, nd.location.lon) for nd in w.nodes if nd.location.valid()]
                if pts:
                    self._keep(w, "way", float(np.mean([p[0] for p in pts])), float(np.mean([p[1] for p in pts])))

        def area(self, a):
            if a.from_way():
                return  # zamknięte linie obsłużone w way()
            t = a.tags
            is_bound = t.get("boundary") == "administrative" and t.get("admin_level") == "6" and t.get("teryt:terc") in teryts
            if not (is_bound or any(k in t for k in keys)):
                return
            try:
                geom = shapely.from_wkb(bytes.fromhex(wkb.create_multipolygon(a)))
            except RuntimeError:  # wadliwy multipoligon w danych OSM (np. niedomknięty pierścień)
                self.invalid.append(a.orig_id())
                return
            if is_bound:
                self.bounds[t.get("teryt:terc")] = geom
            else:
                c = geom.centroid
                self._keep(a, "relation", c.y, c.x, osm_id=a.orig_id())

    h = H()
    h.apply_file(str(pbf), locations=True)
    missing = teryts - set(h.bounds)
    if missing:
        raise RuntimeError(f"Brak granicy powiatu w pliku PBF dla TERYT: {missing}")
    print(f"  PBF: {len(h.objs)} obiektów kategorii w całym pliku; granice: {list(h.bounds)}; "
          f"wadliwe multipoligony (pominięte, cały plik): {len(h.invalid)}, np. relacje {h.invalid[:5]}")

    rows = []
    lat = np.array([o["lat"] for o in h.objs]); lon = np.array([o["lon"] for o in h.objs])
    for teryt, poly in h.bounds.items():
        inside = shapely.contains_xy(poly, lon, lat)
        for o, ok in zip(h.objs, inside):
            if not ok:
                continue
            for cat in o["cats"]:
                grp = next(g for g, cs in CATEGORIES.items() if cat in cs)
                rows.append({"teryt": teryt, "grupa": grp, "kategoria": cat, **{k: v for k, v in o.items() if k != "cats"}})
    stamp = osmium.io.Reader(str(pbf), osmium.osm.osm_entity_bits.NOTHING).header().get("osmosis_replication_timestamp")
    return rows, stamp


def nearest_and_count(px, py, ox, oy, radius=500.0, chunk=500):
    """Brute force w metrach (EPSG:2180): odległość do najbliższego obiektu i liczba w promieniu."""
    dmin = np.empty(len(px)); cnt = np.empty(len(px), dtype=int)
    for i in range(0, len(px), chunk):
        dx = px[i:i + chunk, None] - ox[None, :]
        dy = py[i:i + chunk, None] - oy[None, :]
        d = np.sqrt(dx * dx + dy * dy)
        dmin[i:i + chunk] = d.min(axis=1)
        cnt[i:i + chunk] = (d <= radius).sum(axis=1)
    return dmin, cnt


def main():
    source = sys.argv[1] if len(sys.argv) > 1 else "geofabrik"
    RAW.mkdir(parents=True, exist_ok=True)
    rows, osm_base = [], None
    if source == "overpass":
        for teryt in C.TERYT_POWIATY:
            for group, cats in CATEGORIES.items():
                data = fetch_group(teryt, group, cats)
                osm_base = data.get("osm3s", {}).get("timestamp_osm_base")
                rows += to_rows(teryt, group, data)
                print(f"  {teryt} {group}: {len(data['elements'])} elementów")
        source = "Overpass API"
    else:
        if not GEOFABRIK_PBF.exists():
            raise SystemExit(f"Brak {GEOFABRIK_PBF}. Pobierz: curl -L -o {GEOFABRIK_PBF} {GEOFABRIK_URL}")
        t0 = time.time()
        rows, osm_base = read_geofabrik(GEOFABRIK_PBF)
        source = "Geofabrik (.osm.pbf)"
        print(f"  odczyt PBF: {time.time() - t0:.0f} s")
    df = pd.DataFrame(rows)
    df["last_edit"] = pd.to_datetime(df["last_edit"], utc=True)
    df["x"], df["y"] = TO_2180.transform(df["lon"].values, df["lat"].values)

    # --- profilowanie ---
    st: dict = {"teryt": C.TERYT_POWIATY, "zrodlo": source, "stan_danych_osm": osm_base, "obiekty_wiersze": len(df),
                "obiekty_unikalne_osm": int(df[["osm_type", "osm_id"]].drop_duplicates().shape[0])}
    st["brak_wspolrzednych"] = int(df["lat"].isna().sum())
    st["obiekty_w_kilku_kategoriach"] = int(df.duplicated(["osm_type", "osm_id"], keep=False).sum())
    per = df.groupby("kategoria").agg(liczba=("osm_id", "size"),
                                      node=("osm_type", lambda s: (s == "node").sum()),
                                      way_rel=("osm_type", lambda s: (s != "node").sum()),
                                      brak_nazwy_pct=("name", lambda s: round(100 * s.isna().mean(), 1)))

    # Duplikaty "fizyczne": ten sam obiekt rzeczywisty zmapowany kilka razy.
    # Uproszczona deduplikacja (ogólna, niezależna od miasta): ta sama kategoria + nazwa + komórka siatki 100 m.
    named = df[df["name"].notna()].copy()
    named["cell"] = (named["x"] // 100).astype(int).astype(str) + "_" + (named["y"] // 100).astype(int).astype(str)
    dd = named.groupby(["kategoria", "name", "cell"]).size()
    per["duplikaty_nazwa_100m"] = (dd[dd > 1] - 1).groupby(level=0).sum()
    per = per.fillna({"duplikaty_nazwa_100m": 0}).astype({"duplikaty_nazwa_100m": int})

    # Przystanki – ten sam przystanek bywa zapisany jako bus_stop, platform i stop_position.
    tr = df[df["grupa"] == "komunikacja"].copy()
    tr["cell"] = (tr["x"] // 100).astype(int).astype(str) + "_" + (tr["y"] // 100).astype(int).astype(str)
    st["komunikacja_wiersze"] = len(tr)
    st["komunikacja_unikalne_obiekty_osm"] = int(tr[["osm_type", "osm_id"]].drop_duplicates().shape[0])
    st["komunikacja_przystanki_po_dedup(nazwa+100m)"] = int(tr[tr["name"].notna()].groupby(["name", "cell"]).ngroups)
    st["komunikacja_bez_nazwy"] = int(tr["name"].isna().sum())

    age = (pd.Timestamp(osm_base) - df.drop_duplicates(["osm_type", "osm_id"])["last_edit"]).dt.days / 365.25
    st["ostatnia_edycja_lata_kwantyle"] = age.quantile([0.25, 0.5, 0.75, 0.9]).round(1).to_dict()
    st["edycja_starsza_niz_5_lat_pct"] = round(100 * (age > 5).mean(), 1)

    # --- test łączenia z RCN ---
    rcn_path = C.SAMPLE / "rcn_lokale_probka.parquet"
    join = {}
    if rcn_path.exists():
        rcn = pd.read_parquet(rcn_path)
        rcn = rcn[rcn["LOK_FUNKCJA"] == "mieszkalna"].drop_duplicates(["x_2180", "y_2180"])
        px, py = rcn["x_2180"].values, rcn["y_2180"].values
        dist = {}
        for grp, cats in [("komunikacja", None), ("zielen", ["park"]), ("uslugi", ["sklep_spozywczy"]),
                          ("uslugi", ["szkola"])]:
            sub = df[(df["grupa"] == grp) & (df["kategoria"].isin(cats) if cats else True)]
            sub = sub.drop_duplicates(["osm_type", "osm_id"])
            label = cats[0] if cats else "przystanek (dowolny)"
            d, c = nearest_and_count(px, py, sub["x"].values, sub["y"].values)
            dist[label] = d
            join[label] = {"mediana_odl_m": round(float(np.median(d))), "p90_odl_m": round(float(np.percentile(d, 90))),
                           "pct_w_500m": round(100 * float((d <= 500).mean()), 1),
                           "mediana_liczby_w_500m": float(np.median(c))}
        st["test_laczenia_rcn"] = {"punkty_rcn(unikalne budynki)": len(rcn), **join}

    print(json.dumps(st, indent=1, ensure_ascii=False, default=str))
    print(per.to_string())

    # --- zapis ---
    df.drop(columns=["x", "y"]).to_parquet(C.SAMPLE / "osm_obiekty.parquet", index=False)
    per.to_csv(C.SAMPLE / "osm_profil_kategorii.csv")
    (C.ROOT / "reports" / "osm_stats.json").write_text(json.dumps(st, indent=1, ensure_ascii=False, default=str))

    # --- wykresy ---
    src = f"Źródło: © OpenStreetMap contributors (ODbL), {source}, stan {str(osm_base)[:10]}, TERYT {','.join(C.TERYT_POWIATY)}"
    colors = {"komunikacja": "#1f5f8b", "zielen": "#3a9d5d", "uslugi": "#f2b134"}
    g = df.groupby(["grupa", "kategoria"]).size().reset_index(name="n").sort_values(["grupa", "n"])
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(g["kategoria"], g["n"], color=[colors[x] for x in g["grupa"]])
    for i, n in enumerate(g["n"]):
        ax.text(n, i, f" {n}", va="center", fontsize=8)
    ax.set_title(f"OSM – liczba obiektów w kategoriach otoczenia ({C.AREA_NAME})")
    ax.set_xlabel("liczba obiektów (przed deduplikacją)")
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=c, label=g) for g, c in colors.items()], frameon=False, loc="lower right")
    ax.text(1, -0.16, src, transform=ax.transAxes, ha="right", fontsize=7, color="gray")
    fig.tight_layout(); fig.savefig(C.FIGURES / "07_osm_obiekty_kategorie.png", dpi=150); plt.close(fig)

    if join:
        fig, ax = plt.subplots(figsize=(8, 4))
        for label, col in zip(dist, ["#1f5f8b", "#3a9d5d", "#f2b134", "#d1495b"]):
            ax.hist(np.clip(dist[label], 0, 2000), bins=40, histtype="step", lw=2, color=col,
                    label=f"{label} (mediana {np.median(dist[label]):.0f} m)")
        ax.set_title("Odległość od mieszkania (RCN) do najbliższego obiektu (OSM)")
        ax.set_xlabel("metry (ostatni słupek = 2000 m i więcej)"); ax.set_ylabel("liczba lokalizacji RCN")
        ax.legend(frameon=False, fontsize=8)
        ax.text(1, -0.24, "Źródła: RCN (GUGiK) + © OpenStreetMap contributors (ODbL)", transform=ax.transAxes,
                ha="right", fontsize=8, color="gray")
        fig.tight_layout(); fig.savefig(C.FIGURES / "08_osm_rcn_odleglosci.png", dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 3.5))
    ax.hist(age, bins=40, color="#1f5f8b")
    ax.axvline(age.median(), color="#d1495b", ls="--", label=f"mediana {age.median():.1f} roku")
    ax.set_title("OSM – czas od ostatniej edycji obiektu (aktualność)")
    ax.set_xlabel("lata"); ax.set_ylabel("liczba obiektów"); ax.legend(frameon=False)
    ax.text(1, -0.3, src, transform=ax.transAxes, ha="right", fontsize=7, color="gray")
    fig.tight_layout(); fig.savefig(C.FIGURES / "12_osm_aktualnosc_edycji.png", dpi=150); plt.close(fig)
    print("wykresy zapisane w reports/figures/")


if __name__ == "__main__":
    main()
