"""Validacion externa: Reef Check belt 2021-2026 ajeno a BCO-DMO 773466.

Adapta el export Belt (transecto de 100 m, cuatro segmentos S1-S4) al esquema
del modelo oficial: Percent_Bleaching = media de segmentos no nulos de
'Bleaching (% Of Population)'; blancos distintos de cero. Une SSTA, TSA,
TSA_DHW y ClimSST desde NOAA CRW 5 km (ERDDAP NOAA_DHW, familia Liu/Skirving).
Distance_to_Shore no viaja en Belt (falta la hoja Site): queda NA y la imputa
el pipeline con la mediana del entrenamiento BCO-DMO.

Entrena el RF-8 + DHW, la logistica termica + DHW y la regla CRW solo sobre
las 34 515 observaciones internas. Evalua 2021-2026 y, aparte, los sitios a
mas de 1 km de cualquier registro BCO-DMO.

Genera:
    Validacion_ex/processed/reefcheck_2021_2026_modelo.csv
    data/external/crw_cache.csv
    reports/tables/validacion_externa.md
    reports/figures/validacion_externa.png
    reports/figures/validacion_externa_dhw.png
"""

from __future__ import annotations

import csv
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path
from threading import Lock

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, confusion_matrix
from sklearn.neighbors import BallTree

SRC = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paquete_mejoras import (  # noqa: E402
    ACUMULADO,
    CLASE,
    NUM_BASE,
    TERMICAS,
    ajustar_predecir,
    cargar,
    clasificar,
    coma,
    metricas_binarias,
)

ROOT = Path(__file__).resolve().parents[1]
BELT_PATH = (
    ROOT
    / "Validacion_ex"
    / "Reef Check Data- WW belt 2021- 091026"
    / "Belt.csv"
)
PROCESSED_DIR = ROOT / "Validacion_ex" / "processed"
EXTERNAL_DIR = ROOT / "data" / "external"
TABLES_DIR = ROOT / "reports" / "tables"
FIGURES_DIR = ROOT / "reports" / "figures"
CACHE_PATH = EXTERNAL_DIR / "crw_cache.csv"
OBS_PATH = PROCESSED_DIR / "reefcheck_2021_2026_modelo.csv"

SEG = ["s1 (0-20m)", "s2 (25-45m)", "s3 (50-70m)", "s4 (75-95m)"]
POP = "Bleaching (% Of Population)"
COLONY = "Bleaching (% Of Colony)"
CRW_FILL = -327.68
EARTH_KM = 6371.0
KM_NUEVO = 1.0
ERDDAP = "https://coastwatch.pfeg.noaa.gov/erddap/griddap/NOAA_DHW.csv"
CRW_MAX_DATE = date(2026, 6, 16)
USER_AGENT = "TMF-Corales-academic/1.0 (Reef Check external validation)"
ACCESO_REEFCHECK = date(2026, 9, 10)

MESES = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

INDIAN_COUNTRIES = {
    "Maldives",
    "Mozambique",
    "Madagascar",
    "India",
    "Sri Lanka",
    "Tanzania",
    "United Republic of Tanzania",
    "Kenya",
    "Seychelles",
    "Mauritius",
    "Somalia",
    "Comoros",
    "Mayotte",
    "Reunion",
    "Réunion",
    "Myanmar",
    "Bangladesh",
    "Pakistan",
    "South Africa",
    "British Indian Ocean Territory",
    "Chagos",
}

SABAH_TOKENS = (
    "sabah",
    "kudat",
    "larapan",
    "semporna",
    "tawau",
    "sandakan",
    "kinabalu",
    "pulau penyu",
    "sipadan",
    "mabul",
    "kapalai",
    "selingan",
    "tun sakaran",
)


def ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def parse_fecha(valor) -> date | None:
    if pd.isna(valor):
        return None
    texto = str(valor).strip()
    partes = texto.split("-")
    if len(partes) != 3:
        return None
    try:
        dia = int(partes[0])
        mes = MESES[partes[1].lower()]
        anio = int(partes[2])
        if anio < 100:
            anio += 2000
        return date(anio, mes, dia)
    except (KeyError, ValueError):
        return None


def parse_coords(valor) -> tuple[float, float]:
    if pd.isna(valor):
        return (np.nan, np.nan)
    partes = str(valor).split(",")
    if len(partes) < 2:
        return (np.nan, np.nan)
    try:
        return float(partes[0].strip()), float(partes[1].strip())
    except ValueError:
        return (np.nan, np.nan)


def ocean_name(region: str, country: str, lon: float) -> str:
    region = (region or "").strip()
    country = (country or "").strip()
    if region == "Atlantic":
        return "Atlantic"
    if region == "Red Sea":
        return "Red Sea"
    if region in {"Arabian Gulf", "Persian Gulf"}:
        return "Arabian Gulf"
    if region in {"Hawaii", "East Pacific"}:
        return "Pacific"
    if country in INDIAN_COUNTRIES:
        return "Indian"
    if country == "France" and pd.notna(lon) and lon < 80:
        return "Indian"
    if country in {"Oman", "Yemen"} and pd.notna(lon):
        return "Arabian Gulf" if lon < 56.5 else "Indian"
    return "Pacific"


def es_sabah(country: str, estado: str, lat: float, lon: float) -> bool:
    if (country or "").strip() != "Malaysia":
        return False
    texto = str(estado or "").lower()
    if any(tok in texto for tok in SABAH_TOKENS):
        return True
    if pd.notna(lat) and pd.notna(lon) and lon >= 115.0 and 4.0 <= lat <= 8.0:
        return True
    return False


def media_segmentos(fila: pd.Series) -> float:
    valores = pd.to_numeric(fila[SEG], errors="coerce")
    if valores.notna().sum() == 0:
        return np.nan
    return float(valores.mean())


def adaptar_belt(ruta: Path | None = None) -> pd.DataFrame:
    ruta = ruta or BELT_PATH
    if not ruta.exists():
        raise FileNotFoundError(f"No se encuentra Belt.csv en {ruta}")

    usecols = [
        "site_id",
        "survey_id",
        "reef_name",
        "coordinates_in_decimal_degree_format",
        "country",
        "state_province_island",
        "region",
        "year",
        "date",
        "depth (m)",
        "organism_code",
        "errors",
        "what_errors",
        *SEG,
    ]
    belt = pd.read_csv(ruta, usecols=usecols, low_memory=False)
    pop = belt.loc[belt["organism_code"] == POP].copy()
    colony = belt.loc[belt["organism_code"] == COLONY, ["survey_id", *SEG]].copy()
    pop["Percent_Bleaching"] = pop.apply(media_segmentos, axis=1)
    colony["Percent_Colony_Bleaching"] = colony.apply(media_segmentos, axis=1)
    pop = pop.merge(
        colony[["survey_id", "Percent_Colony_Bleaching"]],
        on="survey_id",
        how="left",
    )
    n_bruto = len(pop)
    n_na = int(pop["Percent_Bleaching"].isna().sum())
    pop = pop.loc[pop["Percent_Bleaching"].notna()].copy()

    coords = pop["coordinates_in_decimal_degree_format"].map(parse_coords)
    pop["Latitude_Degrees"] = [c[0] for c in coords]
    pop["Longitude_Degrees"] = [c[1] for c in coords]
    pop["fecha"] = pop["date"].map(parse_fecha)
    pop["Date_Year"] = pop["year"].astype("Int64")
    pop["Depth_m"] = pd.to_numeric(pop["depth (m)"], errors="coerce")
    pop["Distance_to_Shore"] = np.nan
    pop["Ocean_Name"] = [
        ocean_name(r, c, lon)
        for r, c, lon in zip(
            pop["region"], pop["country"], pop["Longitude_Degrees"]
        )
    ]
    pop["es_sabah"] = [
        es_sabah(c, e, lat, lon)
        for c, e, lat, lon in zip(
            pop["country"],
            pop["state_province_island"],
            pop["Latitude_Degrees"],
            pop["Longitude_Degrees"],
        )
    ]
    pop["Bleaching_Class"] = pop["Percent_Bleaching"].apply(clasificar)
    pop["y"] = (pop["Bleaching_Class"] == CLASE).astype(int)
    pop["n_segmentos"] = pop[SEG].apply(
        lambda s: pd.to_numeric(s, errors="coerce").notna().sum(), axis=1
    )
    pop["Data_Source"] = "Reef_Check_2021_2026"

    print(
        f"Belt: {n_bruto} encuestas con {POP}; {n_na} sin ningun segmento "
        f"(blancos, no ceros); {len(pop)} utilizables; "
        f"{int(pop['y'].sum())} Severo ({100 * pop['y'].mean():.2f} %); "
        f"Sabah {int(pop['es_sabah'].sum())}.",
        flush=True,
    )
    print("Cuencas mapeadas:\n" + pop["Ocean_Name"].value_counts().to_string())
    print("Paises:\n" + pop["country"].value_counts().head(15).to_string())
    return pop


def snap_lat(lat: float) -> float:
    k = int(round((89.975 - lat) / 0.05))
    k = max(0, min(3599, k))
    return round(89.975 - 0.05 * k, 3)


def snap_lon(lon: float) -> float:
    lon = ((lon + 180.0) % 360.0) - 180.0
    k = int(round((lon - (-179.975)) / 0.05))
    k = max(0, min(7199, k))
    return round(-179.975 + 0.05 * k, 3)


def clave_crw(lat: float, lon: float, fecha: date) -> str:
    return f"{fecha.isoformat()}|{snap_lat(lat):.3f}|{snap_lon(lon):.3f}"


def cargar_cache() -> dict[str, dict]:
    if not CACHE_PATH.exists():
        return {}
    cache: dict[str, dict] = {}
    with CACHE_PATH.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            cache[row["clave"]] = row
    return cache


def guardar_cache(cache: dict[str, dict]) -> None:
    EXTERNAL_DIR.mkdir(parents=True, exist_ok=True)
    campos = [
        "clave",
        "fecha",
        "lat",
        "lon",
        "CRW_SST",
        "CRW_SSTANOMALY",
        "CRW_HOTSPOT",
        "CRW_DHW",
        "estado",
    ]
    tmp = CACHE_PATH.with_name(f"crw_cache.{os.getpid()}.tmp.csv")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        for clave, row in cache.items():
            out = {k: row.get(k, "") for k in campos}
            out["clave"] = clave
            w.writerow(out)
    for intento in range(8):
        try:
            tmp.replace(CACHE_PATH)
            return
        except PermissionError:
            time.sleep(0.3)
    CACHE_PATH.write_bytes(tmp.read_bytes())
    tmp.unlink(missing_ok=True)


def _es_valido(valor: float) -> bool:
    return np.isfinite(valor) and abs(valor - CRW_FILL) > 1e-6


def _parse_erddap(texto: str) -> dict[str, float] | None:
    lineas = [ln for ln in texto.strip().splitlines() if ln.strip()]
    if len(lineas) < 3:
        return None
    cab = [c.strip() for c in lineas[0].split(",")]
    datos = next(
        csv.reader([lineas[-1]]),
        None,
    )
    if not datos or len(datos) != len(cab):
        return None
    fila = dict(zip(cab, datos))
    out = {}
    for campo in ("CRW_SST", "CRW_SSTANOMALY", "CRW_HOTSPOT", "CRW_DHW"):
        try:
            out[campo] = float(fila[campo])
        except (KeyError, ValueError):
            return None
        if not _es_valido(out[campo]):
            return None
    return out


def consultar_erddap(lat: float, lon: float, fecha: date, ctx: ssl.SSLContext) -> dict[str, float] | None:
    if fecha > CRW_MAX_DATE:
        return None
    dim = f"[({fecha.isoformat()}T12:00:00Z)][({lat:.3f})][({lon:.3f})]"
    url = (
        f"{ERDDAP}?CRW_SST{dim},CRW_SSTANOMALY{dim},CRW_HOTSPOT{dim},CRW_DHW{dim}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    ultimo: Exception | None = None
    for intento in range(4):
        try:
            with urllib.request.urlopen(req, timeout=90, context=ctx) as resp:
                cuerpo = resp.read().decode("utf-8", errors="replace")
            return _parse_erddap(cuerpo)
        except urllib.error.HTTPError as exc:
            if exc.code in {404, 400}:
                return None
            ultimo = exc
            time.sleep(0.8 * (intento + 1))
        except Exception as exc:
            ultimo = exc
            time.sleep(0.8 * (intento + 1))
    if ultimo:
        raise ultimo
    return None


def extraer_punto(lat: float, lon: float, fecha: date, ctx: ssl.SSLContext) -> dict:
    lat = snap_lat(lat)
    lon = snap_lon(lon)
    offsets = [
        (0.0, 0.0),
        (0.05, 0.0),
        (-0.05, 0.0),
        (0.0, 0.05),
        (0.0, -0.05),
        (0.05, 0.05),
        (0.05, -0.05),
        (-0.05, 0.05),
        (-0.05, -0.05),
        (0.10, 0.0),
        (-0.10, 0.0),
        (0.0, 0.10),
        (0.0, -0.10),
    ]
    ultimo_error = ""
    for dlat, dlon in offsets:
        try:
            got = consultar_erddap(lat + dlat, lon + dlon, fecha, ctx)
        except Exception as exc:
            ultimo_error = str(exc)
            time.sleep(0.4)
            continue
        if got:
            got["estado"] = "ok" if (dlat, dlon) == (0.0, 0.0) else "vecino"
            return got
    return {
        "CRW_SST": "",
        "CRW_SSTANOMALY": "",
        "CRW_HOTSPOT": "",
        "CRW_DHW": "",
        "estado": f"fallo:{ultimo_error[:80]}" if ultimo_error else "sin_dato",
    }


def extraer_crw(obs: pd.DataFrame, max_puntos: int | None = None) -> pd.DataFrame:
    EXTERNAL_DIR.mkdir(parents=True, exist_ok=True)
    cache = cargar_cache()
    ctx = ssl_context()
    pendientes: list[tuple[str, float, float, date]] = []
    vistos: set[str] = set()
    for lat, lon, fecha in zip(
        obs["Latitude_Degrees"], obs["Longitude_Degrees"], obs["fecha"]
    ):
        if pd.isna(lat) or pd.isna(lon) or fecha is None:
            continue
        clave = clave_crw(float(lat), float(lon), fecha)
        if clave in vistos:
            continue
        vistos.add(clave)
        if clave in cache and cache[clave].get("estado", "").startswith(("ok", "vecino", "sin_dato")):
            continue
        pendientes.append((clave, float(lat), float(lon), fecha))

    if max_puntos is not None:
        pendientes = pendientes[:max_puntos]

    print(
        f"CRW: cache {len(cache)} claves; pendientes {len(pendientes)}.",
        flush=True,
    )
    if pendientes:
        lock = Lock()
        hechos = 0

        def _trabajo(item: tuple[str, float, float, date]) -> None:
            clave, lat, lon, fecha = item
            got = extraer_punto(lat, lon, fecha, ctx)
            row = {
                "clave": clave,
                "fecha": fecha.isoformat(),
                "lat": f"{lat:.6f}",
                "lon": f"{lon:.6f}",
                **got,
            }
            with lock:
                cache[clave] = row

        with ThreadPoolExecutor(max_workers=4) as pool:
            futuros = [pool.submit(_trabajo, item) for item in pendientes]
            hechos = 0
            for fut in as_completed(futuros):
                fut.result()
                hechos += 1
                if hechos % 40 == 0:
                    guardar_cache(cache)
                    print(f"  CRW {hechos}/{len(pendientes)}", flush=True)
        guardar_cache(cache)
        print(f"CRW: cache final {len(cache)}.")

    ssta, tsa, dhw, clim, estado = [], [], [], [], []
    for lat, lon, fecha in zip(
        obs["Latitude_Degrees"], obs["Longitude_Degrees"], obs["fecha"]
    ):
        if pd.isna(lat) or pd.isna(lon) or fecha is None:
            ssta.append(np.nan)
            tsa.append(np.nan)
            dhw.append(np.nan)
            clim.append(np.nan)
            estado.append("sin_coord")
            continue
        row = cache.get(clave_crw(float(lat), float(lon), fecha), {})
        sst = pd.to_numeric(row.get("CRW_SST"), errors="coerce")
        anom = pd.to_numeric(row.get("CRW_SSTANOMALY"), errors="coerce")
        hot = pd.to_numeric(row.get("CRW_HOTSPOT"), errors="coerce")
        deg = pd.to_numeric(row.get("CRW_DHW"), errors="coerce")
        ssta.append(float(anom) if pd.notna(anom) else np.nan)
        tsa.append(float(hot) if pd.notna(hot) else np.nan)
        dhw.append(float(deg) if pd.notna(deg) else np.nan)
        if pd.notna(sst) and pd.notna(anom):
            clim.append(float(sst) - float(anom) + 273.15)
        else:
            clim.append(np.nan)
        estado.append(row.get("estado", "ausente"))

    out = obs.copy()
    out["SSTA"] = ssta
    out["TSA"] = tsa
    out["TSA_DHW"] = dhw
    out["ClimSST"] = clim
    out["crw_estado"] = estado
    n_ok = int(out["TSA_DHW"].notna().sum())
    print(f"CRW unido: {n_ok}/{len(out)} con TSA_DHW.")
    return out


def marcar_solape(obs: pd.DataFrame, intern: pd.DataFrame) -> pd.DataFrame:
    intern = intern.dropna(subset=["Latitude_Degrees", "Longitude_Degrees"]).copy()
    tree = BallTree(
        np.radians(intern[["Latitude_Degrees", "Longitude_Degrees"]].to_numpy()),
        metric="haversine",
    )
    reef = intern.loc[intern["Data_Source"].fillna("") == "Reef_Check"]
    tree_rc = BallTree(
        np.radians(reef[["Latitude_Degrees", "Longitude_Degrees"]].to_numpy()),
        metric="haversine",
    )
    coords = np.radians(obs[["Latitude_Degrees", "Longitude_Degrees"]].to_numpy())
    dist_all = tree.query(coords, k=1)[0][:, 0] * EARTH_KM
    dist_rc = tree_rc.query(coords, k=1)[0][:, 0] * EARTH_KM
    out = obs.copy()
    out["dist_km_bco"] = dist_all
    out["dist_km_reefcheck"] = dist_rc
    out["sitio_nuevo_1km"] = dist_all > KM_NUEVO
    out["sitio_nuevo_vs_reefcheck"] = dist_rc > KM_NUEVO
    print(
        f"Solape 1 km: {int((~out['sitio_nuevo_1km']).sum())} reencuestas "
        f"cerca de BCO-DMO; {int(out['sitio_nuevo_1km'].sum())} sitios nuevos."
    )
    return out


def _fila_metricas(
    nombre: str, y: np.ndarray, p: np.ndarray, pred: np.ndarray | None
) -> dict:
    m = metricas_binarias(y, p, pred)
    m["pr_auc"] = float(average_precision_score(y, p)) if y.any() else float("nan")
    m["Modelo"] = nombre
    return m


def evaluar_subset(
    nombre: str, tr: pd.DataFrame, te: pd.DataFrame
) -> tuple[list[dict], dict]:
    y = te["y"].to_numpy()
    p_lr, pred_lr = ajustar_predecir("lr", tr, te, TERMICAS + ACUMULADO, [])
    p_rf, pred_rf = ajustar_predecir("rf", tr, te, NUM_BASE, ["Ocean_Name"])
    p_crw = (te["TSA_DHW"].fillna(0) >= 4.0).astype(float).to_numpy()
    pred_crw = np.where(p_crw >= 0.5, CLASE, "Bajo")
    filas = [
        _fila_metricas("Regla CRW DHW >= 4", y, p_crw, pred_crw),
        _fila_metricas("Logistica termica + DHW", y, p_lr, pred_lr),
        _fila_metricas("RF profundidad 8 + DHW", y, p_rf, pred_rf),
    ]
    for m in filas:
        m["Subset"] = nombre
        print(
            f"  {nombre:<28} {m['Modelo']:<28} "
            f"n={m['n']} prev={100 * m['prevalencia']:.2f}% "
            f"rec={m['recall']:.3f} F1={m['f1_severo']:.3f} "
            f"PR={m['pr_auc']:.3f} Brier={m['brier']:.3f}"
        )
    extras = {
        "y": y,
        "p_lr": p_lr,
        "p_rf": p_rf,
        "p_crw": p_crw,
        "pred_lr": pred_lr,
        "pred_rf": pred_rf,
        "pred_crw": pred_crw,
        "te": te,
    }
    return filas, extras


def figura_barras(filas: list[dict]) -> None:
    orden_sub = []
    for f in filas:
        if f["Subset"] not in orden_sub:
            orden_sub.append(f["Subset"])
    modelos = [
        "Regla CRW DHW >= 4",
        "Logistica termica + DHW",
        "RF profundidad 8 + DHW",
    ]
    colores = ["#c45911", "#1f4e79", "#2e7d32"]
    metricas = [("recall", "Recall Severo"), ("f1_severo", "F1 Severo"), ("pr_auc", "PR-AUC")]
    fig, axes = plt.subplots(1, 3, figsize=(12.6, 4.6), sharey=False)
    x = np.arange(len(orden_sub))
    ancho = 0.24
    lookup = {(f["Subset"], f["Modelo"]): f for f in filas}
    for ax, (clave, titulo) in zip(axes, metricas):
        for i, (modelo, color) in enumerate(zip(modelos, colores)):
            vals = [lookup[(s, modelo)].get(clave, np.nan) for s in orden_sub]
            ax.bar(x + (i - 1) * ancho, vals, ancho, label=modelo, color=color)
        ax.set_title(titulo)
        ax.set_xticks(x)
        ax.set_xticklabels(orden_sub, rotation=18, ha="right", fontsize=8)
        ax.set_ylim(0, 1.05)
        ax.grid(axis="y", alpha=0.3)
    axes[0].legend(fontsize=7, loc="upper left")
    fig.suptitle(
        "Validacion externa Reef Check 2021-2026 (entrenamiento solo BCO-DMO)",
        fontsize=11,
    )
    fig.tight_layout()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES_DIR / "validacion_externa.png", dpi=300)
    plt.close(fig)


def figura_dhw(te: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(7.4, 5.2))
    ax.scatter(
        te.loc[te["y"] == 0, "TSA_DHW"],
        te.loc[te["y"] == 0, "Percent_Bleaching"],
        s=18,
        alpha=0.45,
        c="#4f81bd",
        label="No severo",
    )
    ax.scatter(
        te.loc[te["y"] == 1, "TSA_DHW"],
        te.loc[te["y"] == 1, "Percent_Bleaching"],
        s=36,
        alpha=0.85,
        c="#c45911",
        label="Severo (>30 %)",
    )
    ax.axhline(30, color="#666666", ls="--", lw=1, label="Umbral Severo 30 %")
    ax.axvline(4, color="#c45911", ls=":", lw=1.2, label="CRW DHW = 4")
    ax.set_xlabel("TSA_DHW (CRW 5 km, dia del censo)")
    ax.set_ylabel("Percent_Bleaching (media S1-S4, % poblacion)")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "validacion_externa_dhw.png", dpi=300)
    plt.close(fig)


def matriz_texto(y: np.ndarray, pred_bin: np.ndarray) -> str:
    tn, fp, fn, tp = confusion_matrix(y, pred_bin, labels=[0, 1]).ravel()
    return f"TN {tn}, FP {fp}, FN {fn}, TP {tp}"


def escribir_informe(
    filas: list[dict],
    obs: pd.DataFrame,
    extras: dict,
    n_train: int,
) -> None:
    te = extras["completo"]["te"]
    y = extras["completo"]["y"]
    n_sabah = int(obs["es_sabah"].sum())
    n_nuevo = int(obs["sitio_nuevo_1km"].sum())
    n_reenc = int((~obs["sitio_nuevo_1km"]).sum())
    dhw_max = float(te["TSA_DHW"].max())
    dhw_med = float(te["TSA_DHW"].median())
    n_dhw4 = int((te["TSA_DHW"] >= 4).sum())
    n_sev_dhw4 = int(((te["TSA_DHW"] >= 4) & (te["y"] == 1)).sum())
    acceso = ACCESO_REEFCHECK.strftime("%d de %B de %Y")
    meses_es = {
        "January": "enero",
        "February": "febrero",
        "March": "marzo",
        "April": "abril",
        "May": "mayo",
        "June": "junio",
        "July": "julio",
        "August": "agosto",
        "September": "septiembre",
        "October": "octubre",
        "November": "noviembre",
        "December": "diciembre",
    }
    acceso_en = ACCESO_REEFCHECK.strftime("%d %B %Y")
    acceso_es = ACCESO_REEFCHECK.strftime("%d de ") + meses_es[
        ACCESO_REEFCHECK.strftime("%B")
    ] + " de " + str(ACCESO_REEFCHECK.year)

    lineas = [
        "# Validacion externa: Reef Check 2021-2026",
        "",
        "Corpus ajeno a BCO-DMO 773466 / Sully et al. (2019). El modelo oficial",
        f"(RF profundidad 8 + DHW) se entrena solo sobre las {coma(n_train, 0)}",
        "observaciones internas. La etiqueta es `Bleaching (% Of Population)`,",
        "media de los segmentos S1-S4 con dato; los blancos no se imputan a cero.",
        "`Bleaching (% Of Colony)` se retiene como auxiliar y no es el target.",
        "`Distance_to_Shore` no consta en Belt (no se recibio Site.csv) y la",
        "imputa el pipeline con la mediana del entrenamiento.",
        "",
        f"Acceso a los datos: {acceso_es}. Licencia CC BY-NC 4.0.",
        "Cita: Reef Check Foundation. Reef Check Global Reef Dataset.",
        f"data.reefcheck.org. Date Accessed ({acceso_en}).",
        "",
        "## Inventario",
        "",
        f"- Encuestas con al menos un segmento de poblacion: {coma(len(obs), 0)}",
        f"- Emplazamientos (`site_id`): {coma(obs['site_id'].nunique(), 0)}",
        f"- Episodios Severo (Percent_Bleaching > 30): {coma(int(obs['y'].sum()), 0)} "
        f"({coma(100 * obs['y'].mean(), 2)} %)",
        f"- Media de Percent_Bleaching: {coma(float(obs['Percent_Bleaching'].mean()), 2)} %",
        f"- Reencuestas a <= 1 km de BCO-DMO: {coma(n_reenc, 0)}",
        f"- Sitios a > 1 km de cualquier registro BCO-DMO: {coma(n_nuevo, 0)}",
        f"- Censos en Sabah (Malasia): {coma(n_sabah, 0)}",
        f"- TSA_DHW mediano / maximo: {coma(dhw_med, 2)} / {coma(dhw_max, 2)}",
        f"- Censos con DHW >= 4: {coma(n_dhw4, 0)} (de ellos Severo: {coma(n_sev_dhw4, 0)})",
        "",
        "Anos: "
        + ", ".join(
            f"{int(a)} n={int(n)}"
            for a, n in obs["Date_Year"].value_counts().sort_index().items()
        )
        + ".",
        "",
        "## Metricas (umbral 0,5 sobre P(Severo); CRW = DHW >= 4)",
        "",
        "| Subconjunto | Modelo | n | Severo (%) | Recall | Precision | F1 | PR-AUC | Brier |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for m in filas:
        lineas.append(
            f"| {m['Subset']} | {m['Modelo']} | {coma(m['n'], 0)} | "
            f"{coma(100 * m['prevalencia'], 2)} | {coma(m['recall'])} | "
            f"{coma(m['precision'])} | {coma(m['f1_severo'])} | "
            f"{coma(m['pr_auc'])} | {coma(m['brier'])} |"
        )

    cm_rf = matriz_texto(y, (extras["completo"]["p_rf"] >= 0.5).astype(int))
    cm_lr = matriz_texto(y, (extras["completo"]["p_lr"] >= 0.5).astype(int))
    cm_crw = matriz_texto(y, extras["completo"]["p_crw"].astype(int))
    lineas.extend(
        [
            "",
            "## Matrices binarias (conjunto completo, umbral 0,5)",
            "",
            f"- RF-8: {cm_rf}",
            f"- Logistica: {cm_lr}",
            f"- CRW: {cm_crw}",
            "",
            "## Condiciones de uso (extracto)",
            "",
            "Agradecimiento a Reef Check Foundation, sus capitulos y voluntarios.",
            "Los censos de Sabah requieren ademas reconocer al Sabah Biodiversity",
            "Centre (SaBC) como autoridad de licencia y a Reef Check Malaysia (RCM)",
            "como titular de la licencia de acceso. Los informes deben compartirse",
            "con Reef Check Foundation y, por los datos de Sabah, con SaBC.",
            "",
            "Script: `src/validacion_externa_reefcheck.py`.",
        ]
    )
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    (TABLES_DIR / "validacion_externa.md").write_text(
        "\n".join(lineas) + "\n", encoding="utf-8"
    )
    print("Tabla:", TABLES_DIR / "validacion_externa.md")


def guardar_obs(obs: pd.DataFrame) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    cols = [
        "site_id",
        "survey_id",
        "reef_name",
        "country",
        "state_province_island",
        "region",
        "Ocean_Name",
        "Date_Year",
        "fecha",
        "Latitude_Degrees",
        "Longitude_Degrees",
        "Depth_m",
        "Distance_to_Shore",
        "SSTA",
        "TSA",
        "TSA_DHW",
        "ClimSST",
        "Percent_Bleaching",
        "Percent_Colony_Bleaching",
        "Bleaching_Class",
        "y",
        "n_segmentos",
        "es_sabah",
        "dist_km_bco",
        "dist_km_reefcheck",
        "sitio_nuevo_1km",
        "sitio_nuevo_vs_reefcheck",
        "crw_estado",
        "Data_Source",
    ]
    out = obs.copy()
    out["fecha"] = out["fecha"].map(lambda d: d.isoformat() if isinstance(d, date) else d)
    out[cols].to_csv(OBS_PATH, index=False)
    print("Observaciones:", OBS_PATH)


def main() -> None:
    t0 = time.time()
    intern = cargar()
    intern["Date_Year"] = pd.to_numeric(intern["Date_Year"], errors="coerce")
    obs = adaptar_belt()
    obs = extraer_crw(obs)
    obs = marcar_solape(obs, intern)
    guardar_obs(obs)

    te = obs.loc[obs["TSA_DHW"].notna()].copy()
    if te.empty:
        raise RuntimeError(
            "Ninguna encuesta tiene TSA_DHW. Revisar cache CRW / red a ERDDAP."
        )
    te["Bleaching_Class"] = te["Percent_Bleaching"].apply(clasificar)

    subsets = {
        "completo 2021-2026": te,
        "sitios >1 km": te.loc[te["sitio_nuevo_1km"]],
        "2023-2024": te.loc[te["Date_Year"].isin([2023, 2024])],
        "sin Malasia": te.loc[te["country"] != "Malaysia"],
    }
    filas: list[dict] = []
    extras: dict = {}
    for nombre, sub in subsets.items():
        if len(sub) < 30 or int(sub["y"].sum()) < 3:
            print(f"  omitido {nombre}: n={len(sub)} severos={int(sub['y'].sum())}")
            continue
        f, ex = evaluar_subset(nombre, intern, sub)
        filas.extend(f)
        extras[nombre.split()[0]] = ex
    extras["completo"] = extras.get("completo", extras[next(iter(extras))])

    figura_barras(filas)
    figura_dhw(extras["completo"]["te"])
    escribir_informe(filas, te, extras, n_train=len(intern))
    print(f"Listo en {time.time() - t0:.1f} s.")


if __name__ == "__main__":
    # prueba puntual de ERDDAP: python -c no; usar --max via env
    import os

    if os.environ.get("CRW_SMOKE") == "1":
        ctx = ssl_context()
        got = extraer_punto(2.548556, 103.960028, date(2022, 8, 23), ctx)
        print(got)
    else:
        main()
