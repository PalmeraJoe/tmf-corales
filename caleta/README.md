# Caleta

Mesa de **gestión local** para una AMP o un resort: qué estaciones inspeccionar esta temporada según el historial del `Site_ID`.

No toca el TFM ni Baliza. No es un termómetro de alerta macro de NOAA. Lee el CSV del TFM en modo consulta.

El predictor es el XGBoost local del laboratorio DSS (memoria del arrecife + condiciones de la temporada). El DHW de NOAA solo empuja un evento de calor nuevo para no pegarse al pasado.

## Arranque

```bash
cd caleta
python3 -m pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
PYTHONPATH=backend python3 -m uvicorn caleta.main:app --host 127.0.0.1 --port 8010
```

Abre [http://127.0.0.1:8010](http://127.0.0.1:8010).

Desarrollo con recarga:

```bash
PYTHONPATH=backend python3 -m uvicorn caleta.main:app --reload --host 127.0.0.1 --port 8010
```

```bash
cd caleta/frontend && npm install && npm run dev
```

La interfaz de desarrollo queda en [http://127.0.0.1:5174](http://127.0.0.1:5174).

## Qué hace

Eliges AMP/región, opcionalmente una base (santuario o resort) y el cupo de inmersiones. Caleta:

1. se queda solo con estaciones que ya tienen historial (`Site_ID` con más de una visita);
2. predice la **última visita** de cada sitio con un XGBoost que ve el censo previo (última clase, tasa de Severo, DHW medio) más SSTA/TSA/DHW/profundidad;
3. ordena las inmersiones de *tu* red;
4. te dice si el sitio es crónico, un evento nuevo de calor, o puede esperar;
5. contrasta cuántos severos observados habría pillado el cupo frente a ordenar por DHW.

En Florida Keys, con 20 inmersiones, el ranking local recuperó 12 de 23 severos frente a 5 si se ordena por el termómetro NOAA.

Baliza sigue siendo la mesa de campaña TFM (RF-8 + 45 % DHW). Caleta es la mesa del gestor de una red concreta con memoria de sitio.
