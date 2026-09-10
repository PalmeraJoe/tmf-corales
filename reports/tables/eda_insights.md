# Hallazgos del análisis exploratorio de datos

## 1. Filtrado de la variable objetivo

Se excluyeron las observaciones sin `Percent_Bleaching` (marcadas como `nd` o nulas), porque no permiten estimar la magnitud del evento de blanqueamiento.

| Indicador | Valor |
|---|---|
| Observaciones originales | 41,361 |
| Observaciones eliminadas (sin `Percent_Bleaching`) | 6,846 (16.55%) |
| **Observaciones retenidas para el EDA** | **34,515** |

## 2. Distribución de `Percent_Bleaching`

`Percent_Bleaching` expresa el porcentaje de colonias o cobertura coralina afectada por blanqueamiento en cada muestreo. Una distribución sesgada hacia valores bajos es coherente con un régimen en el que predominan arrecifes sin evento agudo, interrumpido por picos de mortalidad térmica.

| Estadístico | Valor |
|---|---|
| Media (%) | 9.619 |
| Mediana (%) | 0.250 |
| Desviación estándar (%) | 20.191 |
| Mínimo (%) | 0.000 |
| Percentil 1 (%) | 0.000 |
| Percentil 5 (%) | 0.000 |
| Percentil 10 (%) | 0.000 |
| Percentil 25 (%) | 0.000 |
| Percentil 50 (%) | 0.250 |
| Percentil 75 (%) | 6.000 |
| Percentil 90 (%) | 33.300 |
| Percentil 95 (%) | 69.127 |
| Percentil 99 (%) | 87.500 |
| Máximo (%) | 100.000 |

Figura: `reports/figures/distribucion_percent_bleaching.png`.

## 3. Correlación de Pearson con variables térmicas y de hábitat

Las variables se interpretan con su significado ecológico:

- **SSTA** (*Sea Surface Temperature Anomaly*): desviación de la temperatura superficial respecto a la climatología.
- **TSA** (*Thermal Stress Anomaly*): exposición a temperaturas por encima del umbral de blanqueamiento.
- **`TSA_DHW`** (*Degree Heating Weeks*): integral del estrés térmico en las doce semanas precedentes.
- **`ClimSST`**: temperatura superficial climatológica (kelvin).
- **`Depth_m`**: profundidad del muestreo.
- **`Distance_to_Shore`**: distancia a la costa.

| Variable | Contexto ecológico | r de Pearson con `Percent_Bleaching` |
|---|---|---|
| `TSA_DHW` | TSA_DHW (Degree Heating Weeks, °C·semana) | 0.228 |
| `Depth_m` | Profundidad (m) | 0.165 |
| `TSA` | TSA (anomalía de estrés térmico, °C) | 0.134 |
| `SSTA` | SSTA (anomalía térmica superficial, °C) | 0.092 |
| `ClimSST` | ClimSST (climatología SST, K) | -0.055 |
| `Distance_to_Shore` | Distancia a la costa (m) | 0.006 |

Correlación `SSTA`–`TSA`: 0.543.

Lectura ecológica de los coeficientes:

- `TSA_DHW` y `Percent_Bleaching`: asociación débil positiva (r = 0.228). Es el predictor lineal más asociado a la respuesta y justifica su inclusión en el modelo principal.
- TSA y `Percent_Bleaching`: asociación débil positiva (r = 0.134).
- Profundidad y `Percent_Bleaching`: asociación débil positiva (r = 0.165). El signo positivo no coincide con la expectativa clásica de mayor blanqueamiento en arrecifes someros; el apartado 6.1.3 muestra que recoge estratificación por programa.
- SSTA y `Percent_Bleaching`: asociación muy débil positiva (r = 0.092).
- `ClimSST` y `Percent_Bleaching`: asociación muy débil negativa (r = -0.055).
- Distancia a la costa y `Percent_Bleaching`: asociación muy débil positiva (r = 0.006). A escala global, la distancia a la costa apenas se asocia linealmente con el blanqueamiento.

Figura: `reports/figures/matriz_correlacion.png`.

## 4. Relación SSTA–blanqueamiento

El gráfico `reports/figures/ssta_vs_bleaching.png` muestra la nube de puntos y la tendencia lineal (`regplot`) entre la anomalía térmica superficial y el porcentaje de blanqueamiento. Una pendiente positiva, aunque sea débil a escala global, es coherente con el mecanismo de estrés por calor. La nube es heterocedástica y con bandas en 0%, 30%, 75% y 100%, típicas de protocolos de campo que reportan umbrales discretos.

Para la gestión de Áreas Marinas Protegidas (AMP), el índice lineal más asociado a la respuesta es `TSA_DHW`, no SSTA. La magnitud lineal global de las anomalías puntuales sigue siendo baja; el seguimiento operativo debe apoyarse en el estrés acumulado y en umbrales locales, no en un único gradiente costa–profundidad.
