"""API de Baliza: priorización de inspecciones, no un predictor aislado."""

from __future__ import annotations

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__
from .config import DATA_CSV, FRONTEND_DIST
from .engine import (
    build_campaign,
    campaign_brief,
    list_networks,
    score_custom_sites,
    station_detail,
)
from .live import parse_station_csv, probe_live_crw, save_census, store_client_stations
from .ops import CAPABILITIES

app = FastAPI(
    title="Baliza",
    description=(
        "Servicio de apoyo a decisiones para gestores de arrecifes: "
        "ranking de inspecciones, umbral según coste y área de aplicabilidad."
    ),
    version=__version__,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://127.0.0.1:8004",
        "http://localhost:8004",
        "http://127.0.0.1:8006",
        "http://localhost:8006",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CensusBody(BaseModel):
    network: str = "florida_keys"
    site_id: str
    percent_bleaching: float = Field(ge=0, le=100)
    note: str = ""


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "product": "Baliza",
        "version": __version__,
        "data_csv": str(DATA_CSV),
        "data_found": DATA_CSV.exists(),
    }


@app.get("/api/capabilities")
def capabilities() -> dict:
    live = probe_live_crw()
    items = [dict(item) for item in CAPABILITIES]
    for item in items:
        if item["id"] == "live_crw":
            if live.get("ok"):
                item["status"] = "listo"
                item["note"] = (
                    f"ERDDAP respondió. DHW de prueba (Florida) = {live.get('dhw')} "
                    f"({live.get('time')}). El modo histórico de la mesa no se sustituye."
                )
            else:
                item["status"] = "no ahora"
                item["note"] = (
                    "El conector existe, pero NOAA/ERDDAP no respondió: "
                    f"{live.get('error')}"
                )
    return {"live": live, "capabilities": items}


@app.get("/api/networks")
def networks() -> dict:
    return {"networks": list_networks()}


@app.get("/api/campaign")
def campaign(
    network: str = Query("florida_keys"),
    season: int | None = Query(None),
    dives: int = Query(24, ge=1, le=400),
    cost_false_alarm: float = Query(1.0, gt=0, le=100),
    cost_miss: float = Query(6.0, gt=0, le=200),
    boat_days: int = Query(3, ge=1, le=14),
    cost_dive_eur: float = Query(400.0, gt=0, le=20000),
    hours_per_dive: float = Query(3.0, gt=0, le=24),
    aoa_quota: float = Query(0.25, ge=0, le=1),
    origin: str = Query("auto"),
) -> dict:
    try:
        return build_campaign(
            network,
            season,
            dives,
            cost_false_alarm,
            cost_miss,
            boat_days=boat_days,
            cost_dive_eur=cost_dive_eur,
            hours_per_dive=hours_per_dive,
            aoa_quota=aoa_quota,
            origin_id=None if origin in ("", "auto") else origin,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/station")
def station(
    site_id: str,
    network: str = Query("florida_keys"),
    season: int | None = Query(None),
    cost_false_alarm: float = Query(1.0, gt=0, le=100),
    cost_miss: float = Query(6.0, gt=0, le=200),
) -> dict:
    if season is None:
        raise HTTPException(status_code=422, detail="Indica la temporada.")
    try:
        return station_detail(network, season, site_id, cost_false_alarm, cost_miss)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/report", response_class=PlainTextResponse)
def report(
    network: str = Query("florida_keys"),
    season: int | None = Query(None),
    dives: int = Query(24, ge=1, le=400),
    cost_false_alarm: float = Query(1.0, gt=0, le=100),
    cost_miss: float = Query(6.0, gt=0, le=200),
    boat_days: int = Query(3, ge=1, le=14),
    cost_dive_eur: float = Query(400.0, gt=0, le=20000),
    hours_per_dive: float = Query(3.0, gt=0, le=24),
    origin: str = Query("auto"),
) -> str:
    try:
        data = build_campaign(
            network,
            season,
            dives,
            cost_false_alarm,
            cost_miss,
            boat_days=boat_days,
            cost_dive_eur=cost_dive_eur,
            hours_per_dive=hours_per_dive,
            origin_id=None if origin in ("", "auto") else origin,
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return campaign_brief(data)


@app.post("/api/census")
def census(body: CensusBody) -> dict:
    return save_census(body.network, body.site_id, body.percent_bleaching, body.note)


@app.post("/api/network/upload")
async def upload_network(
    network: str = Query("florida_keys"),
    use_live: bool = Query(False),
    file: UploadFile = File(...),
) -> dict:
    raw = (await file.read()).decode("utf-8-sig")
    try:
        rows = parse_station_csv(raw)
        stored = store_client_stations(network, file.filename or "estaciones.csv", rows)
        scored = score_custom_sites(network, rows, use_live=use_live)
        scored["stored"] = stored
        return scored
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


INDEX_FILE = FRONTEND_DIST / "index.html"
ASSETS_DIR = FRONTEND_DIST / "assets"
if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")


@app.get("/")
def frontend_index():
    if INDEX_FILE.exists():
        return FileResponse(INDEX_FILE)
    return {
        "product": "Baliza",
        "message": "Compila la interfaz con npm run build en APP/frontend.",
    }
