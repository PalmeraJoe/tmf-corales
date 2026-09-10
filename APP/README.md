# Baliza

Plataforma de **priorización de inspecciones** para gestores de arrecifes. Vive entera en `APP/` y no modifica el código, los datos ni los informes del TFM.

No es un predictor global de blanqueamiento. Es una mesa de campaña:

> Con el presupuesto disponible, te indicamos qué arrecifes inspeccionar primero, con qué nivel de confianza y por qué.

## Qué hace

Para una **red territorial** (Florida Keys, Bahamas, Jamaica, Gran Barrera norte, Belice) y una temporada histórica:

- calibra el Random Forest oficial del TFM (`max_depth = 8`, con `TSA_DHW`) **solo con el histórico local anterior a esa temporada**;
- puntúa cada estación con P(Bajo / Moderado / Severo);
- muestra DHW, nivel Coral Reef Watch, área de aplicabilidad (Meyer y Pebesma, 2021), incertidumbre y factores;
- recorta la lista al presupuesto de inmersiones;
- ajusta el umbral con el coste de una falsa alarma frente al de omitir un evento;
- contrasta cuántos episodios severos observados habría capturado ese ranking frente a ordenar por DHW / CRW.

La temporada es un simulacro operativo sobre el registro de Sully et al. (vía BCO-DMO). El modelo **no estima la severidad a 1–3 meses**. Para eso haría falta alimentar el mismo clasificador con DHW de un pronóstico térmico y validar el acoplamiento.

## Cómo arrancar

Opción rápida, un solo servidor (recomendada):

```powershell
cd APP
.\start.ps1
```

Abre [http://127.0.0.1:8000](http://127.0.0.1:8000). El script crea el entorno, instala dependencias, compila la interfaz y lanza la API, que también sirve la mesa de campaña.

Desarrollo con recarga en caliente, dos terminales:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:PYTHONPATH = "$PWD\backend"
.\.venv\Scripts\python.exe -m uvicorn baliza.main:app --reload --host 127.0.0.1 --port 8000
```

```powershell
cd frontend
npm install
npm run dev
```

En ese modo la interfaz queda en [http://127.0.0.1:5173](http://127.0.0.1:5173) y proxya `/api` al puerto 8000.

El CSV se lee en modo consulta desde `../data/raw/global_bleaching_environmental.csv`. Los modelos locales se guardan en `APP/artifacts/`.

## Lectura comercial (y científica)

| Esto | No esto |
| --- | --- |
| Priorización operativa en una AMP o red ya conocida | SaaS global de alerta autónoma |
| Evaluación de severidad probable bajo condiciones térmicas de la temporada | Predicción a tres meses |
| Capa sobre NOAA: umbral, ranking, AOA, explicación | Sustituto de Coral Reef Watch |

El competidor real es el producto gratuito de NOAA más la hoja de cálculo del gestor. Baliza solo merece cobrarse si reduce visitas de baja prioridad o aumenta la detección de episodios severos con el mismo número de inmersiones.

Antes de comercializar hay que revisar licencias de BCO-DMO, productos NOAA, marcas y código.
