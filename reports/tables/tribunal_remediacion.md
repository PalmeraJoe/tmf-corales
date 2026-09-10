# Remedición de las objeciones del tribunal

Experimentos diseñados para cerrar las lagunas identificadas en la evaluación de la memoria. Script: `src/tribunal_remediacion.py`. Semilla fija (`random_state=42`). El preprocesado se ajusta dentro de cada partición de entrenamiento.

## 1. El sesgo de `Reef_ID` no es de prevalencia: es de protocolo

`Reef_ID` está informado **solo** en Reef_Check. Donner, AGRRA, FRRP y el resto de programas —precisamente los que concentran los eventos masivos— quedan fuera de la validación agrupada de la memoria. La solución no es discutir el 2,11 % frente al 12,42 %: es repetir la validación agrupando por `Site_ID` (cobertura 100 %) o por bloque geográfico.

| Fuente | n | Severo | Bleach medio (%) | Con Reef_ID | Profundidad media (m) |
|---|---|---|---|---|---|
| Reef_Check | 22531 | 2,11 % | 2,53 | 100,0 % | 6,51 |
| Donner | 5770 | 51,89 % | 35,05 | 0,0 % | 9,82 |
| AGRRA | 2848 | 0,74 % | 3,31 | 0,0 % | 7,01 |
| FRRP | 2394 | 14,41 % | 15,31 | 0,0 % | 8,13 |
| Kumagai | 660 | 38,03 % | 17,46 | 0,0 % | 5,13 |
| McClanahan | 226 | 77,43 % | 57,33 | 0,0 % | 5,96 |
| Safaie | 77 | 25,97 % | 24,35 | 0,0 % | 5,01 |
| Nuryana | 5 | 60,00 % | 30,90 | 0,0 % | n/d |
| Setiawan | 4 | 100,00 % | 66,00 | 0,0 % | n/d |

## 2. La correlación positiva con la profundidad es un confusor de fuente

Correlación bruta `Depth_m`–`Percent_Bleaching`: r = 0,166. Dentro de Reef_Check: r = 0,011. En el resto de fuentes: r = 0,134. Tras residualizar ambas variables respecto a `Data_Source`: r parcial = 0,039. Agregando al sitio: r = 0,085. La asociación aparente se desinfla cuando se controla el protocolo. Reef_Check muestrea rutinariamente aguas someras con poco blanqueamiento; Donner y McClanahan concentran campañas de evento, algo más profundas y con mucha más severidad.

## 3. I de Moran sobre centroides de sitio (k = 8 vecinos)

| Variable | I de Moran | p (99 permutaciones) | Sitios |
|---|---|---|---|
| Percent_Bleaching (media de sitio) | 0,352 | 0,010 | 11047 |
| TSA | 0,310 | 0,010 | 11047 |
| TSA_DHW | 0,516 | 0,010 | 11047 |

La autocorrelación de los índices térmicos justifica el bloqueo geográfico: no basta con separar réplicas del mismo `Reef_ID`.

## 4. Baseline operativo NOAA Coral Reef Watch

Reglas sin entrenamiento, evaluadas sobre las 34 515 observaciones con respuesta. Mapeo de tres clases: DHW < 4 Bajo, 4–8 Moderado, ≥ 8 Severo. Las reglas binarias etiquetan positivo como Severo y el resto como Bajo.

| Regla | Recall Severo | Precisión Severo | F1 macro | Recall en Reef_Check | Recall en resto |
|---|---|---|---|---|---|
| CRW 3 clases (DHW 4/8) | 0,103 | 0,468 | 0,380 | 0,076 | 0,106 |
| Alerta si DHW >= 4 | 0,338 | 0,426 | 0,418 | 0,236 | 0,351 |
| Alerta si DHW >= 8 | 0,103 | 0,468 | 0,350 | 0,076 | 0,106 |
| HotSpot TSA >= 1 | 0,148 | 0,260 | 0,352 | 0,131 | 0,150 |

## 5. DHW en el modelo principal y RF con profundidad acotada

Conjunto completo (n = 34 515), validación aleatoria estratificada frente a `StratifiedGroupKFold` por `Site_ID` (11 068 sitios, cobertura 100 %). Media ± desviación de 5 pliegues.

| Modelo | F1 aleatoria | F1 por Site_ID | Δ relativa | Recall Severo (Site_ID) | PR-AUC Severo (Site_ID) |
|---|---|---|---|---|---|
| Logistica base | 0,393 | 0,392 | -0,4 % | 0,266 | 0,222 |
| Logistica + DHW | 0,451 | 0,449 | -0,5 % | 0,386 | 0,345 |
| Logistica termica + DHW | 0,456 | 0,454 | -0,4 % | 0,445 | 0,323 |
| RF profundidad 8 + DHW | 0,557 | 0,532 | -4,4 % | 0,559 | 0,514 |
| RF profundidad 16 + DHW | 0,724 | 0,603 | -16,7 % | 0,645 | 0,632 |
| RF libre + DHW | 0,759 | 0,612 | -19,5 % | 0,644 | 0,656 |

## 6. Transferencia entre cuencas y ecorregiones

| Modelo | Bloqueo | F1 macro | Recall Severo | PR-AUC Severo |
|---|---|---|---|---|
| Logistica termica + DHW | Leave-one-ocean-out | 0,415 | 0,527 | 0,386 |
| Logistica termica + DHW | Ecorregion (5 pliegues) | 0,446 | 0,469 | 0,351 |
| RF profundidad 8 + DHW | Leave-one-ocean-out | 0,456 | 0,612 | 0,334 |
| RF profundidad 8 + DHW | Ecorregion (5 pliegues) | 0,428 | 0,507 | 0,358 |

## 7. Validación temporal

| Corte | Modelo | n train | n test | F1 macro | Recall Severo | PR-AUC Severo |
|---|---|---|---|---|---|---|
| Entrena <=2012 / test >=2013 | Logistica + DHW | 24109 | 10406 | 0,480 | 0,399 | 0,298 |
| Entrena <=2012 / test >=2013 | RF profundidad 8 + DHW | 24109 | 10406 | 0,451 | 0,243 | 0,217 |
| Entrena <=2012 / test >=2013 | CRW DHW>=4 | 24109 | 10406 | 0,447 | 0,398 | n/d |
| Entrena <=2013 / test >=2014 | Logistica + DHW | 25632 | 8883 | 0,489 | 0,428 | 0,319 |
| Entrena <=2013 / test >=2014 | RF profundidad 8 + DHW | 25632 | 8883 | 0,481 | 0,319 | 0,284 |
| Entrena <=2013 / test >=2014 | CRW DHW>=4 | 25632 | 8883 | 0,447 | 0,402 | n/d |

## Lectura para la defensa

- Si la logística con DHW no supera de forma clara a `DHW >= 4` en recall, el valor del TFM no es el clasificador, sino haber cuantificado cuándo el ML no transfiere.
- Si acotar `max_depth` reduce la brecha aleatoria/espacial, parte del «colapso» de Random Forest era hiperparámetro, no destino de la familia.
- El leave-one-ocean-out es la cifra que hay que dar cuando un gestor pregunta por un arrecife en una cuenca nueva.

Figuras: `tribunal_fuentes_severidad.png`, `tribunal_profundidad_fuente.png`, `tribunal_baseline_crw.png`.
