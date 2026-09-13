"""API de Caleta: gestión local de AMP o resort, no alerta macro NOAA."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .config import DATA_CSV, FRONTEND_DIST
from .engine import build_desk, properties_catalog, station_history

app = FastAPI(
    title="Caleta",
    description="Mesa de gestión local para una AMP o un resort: qué arrecifes inspeccionar.",
    version=__version__,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5174",
        "http://localhost:5174",
        "http://127.0.0.1:8010",
        "http://localhost:8010",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "product": "Caleta",
        "version": __version__,
        "role": "gestión local AMP/resort",
        "not": "termómetro de alerta macro NOAA",
        "data_csv": str(DATA_CSV),
        "data_found": DATA_CSV.exists(),
        "tfm_untouched": True,
    }


@app.get("/api/properties")
def properties() -> dict:
    return properties_catalog()


@app.get("/api/desk")
def desk(
    property_id: str = Query("florida_keys"),
    season: int | None = Query(None),
    dives: int = Query(12, ge=1, le=200),
    base: str = Query(""),
) -> dict:
    try:
        return build_desk(
            property_id,
            season,
            dives,
            base_id=None if base in ("", "all", "auto") else base,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/station")
def station(
    property_id: str = Query("florida_keys"),
    site_id: str = Query(...),
) -> dict:
    try:
        return station_history(property_id, site_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
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
        "product": "Caleta",
        "message": "Compila la interfaz con npm run build en caleta/frontend.",
    }
