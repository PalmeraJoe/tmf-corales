# Comprobaciones de robustez metodológica

Este informe recoge dos análisis complementarios orientados a contrastar decisiones que la
comparativa principal adopta sin justificación empírica: la elección de los umbrales de
discretización y el esquema de validación sobre el que se calcula la explicabilidad.

Submuestra empleada: 22,531 observaciones con `Reef_ID` informado
(4,115 arrecifes).

## A. Sensibilidad a los umbrales de discretización

La conversión de `Percent_Bleaching` en tres niveles ordinales exige fijar dos cortes. La
memoria adopta 10 % y 30 %, valores de uso extendido en la literatura de seguimiento
arrecifal, pero la elección debe someterse a contraste: si las conclusiones dependieran del
corte, carecerían de solidez.

### Random Forest

| Umbrales | Prevalencia «Severo» (%) | F1 macro (aleatoria) | F1 macro (agrupada) | Δ relativa (%) | Recall «Severo» (agrupada) |
|---|---|---|---|---|---|
| 5 % / 25 % | 2,8006 | 0,9027 | 0,4681 | -48,1395 | 0,1997 |
| 10 % / 30 % (adoptado) | 2,2236 | 0,8997 | 0,4242 | -52,8494 | 0,1316 |
| 10 % / 50 % | 1,1540 | 0,9051 | 0,4304 | -52,4513 | 0,1000 |
| 20 % / 40 % | 1,5800 | 0,9088 | 0,4283 | -52,8731 | 0,1294 |

### Regresión logística

| Umbrales | Prevalencia «Severo» (%) | F1 macro (aleatoria) | F1 macro (agrupada) | Δ relativa (%) | Recall «Severo» (agrupada) |
|---|---|---|---|---|---|
| 5 % / 25 % | 2,8006 | 0,3143 | 0,3095 | -1,5204 | 0,4470 |
| 10 % / 30 % (adoptado) | 2,2236 | 0,2976 | 0,2977 | 0,0288 | 0,4552 |
| 10 % / 50 % | 1,1540 | 0,2967 | 0,2940 | -0,9130 | 0,4538 |
| 20 % / 40 % | 1,5800 | 0,2726 | 0,2712 | -0,4892 | 0,4376 |

### Lectura

El resultado central de la memoria —la degradación severa de Random Forest frente a la
estabilidad de la regresión logística al pasar a validación agrupada— se reproduce en las
cuatro configuraciones ensayadas. La magnitud absoluta de las métricas varía con la
prevalencia resultante, como cabe esperar, pero **el signo y el orden de magnitud del
fenómeno son invariantes** respecto al umbral escogido.

La elección de 10 % y 30 % no es, por tanto, un supuesto del que dependan las conclusiones.
Su justificación es operativa: el corte inferior separa los arrecifes sin afectación
apreciable y el superior delimita los episodios masivos, que constituyen el objeto de
interés para la gestión.

## B. Explicabilidad SHAP bajo partición espacial

El análisis SHAP del capítulo 6 explica el Random Forest oficial (`max_depth` = 8, con
`TSA_DHW`) sobre un pliegue de `StratifiedGroupKFold` por `Site_ID` (6 903 observaciones,
2 238 emplazamientos, solapamiento nulo). Para acotar el riesgo de que esa jerarquía sea un
artefacto del esquema de validación se repite el cálculo sobre un pliegue aleatorio del mismo
tamaño. Lo genera `src/explainability.py`; ya no se explica un XGBoost sin DHW sobre Reef_Check.

| Variable | SHAP (partición aleatoria) | SHAP (partición agrupada) | Variación (%) |
|---|---|---|---|
| TSA_DHW | 0,0712 | 0,0696 | −2,2 |
| Ocean_Name_Atlantic | 0,0566 | 0,0576 | 1,7 |
| Distance_to_Shore | 0,0325 | 0,0324 | −0,4 |
| Ocean_Name_Pacific | 0,0275 | 0,0289 | 5,2 |
| Depth_m | 0,0254 | 0,0271 | 6,8 |
| ClimSST | 0,0246 | 0,0235 | −4,5 |
| TSA | 0,0228 | 0,0219 | −3,8 |
| SSTA | 0,0113 | 0,0089 | −21,0 |

*Figura: `reports/figures/shap_comparacion_esquemas.png`*

### Reparto entre contexto del emplazamiento y estrés térmico

| Grupo de variables | Partición aleatoria | Partición agrupada |
|---|---|---|
| Contexto del sitio (`Depth_m`, `Distance_to_Shore`, `ClimSST`) | 0,0825 | 0,0830 |
| Estrés térmico (`SSTA`, `TSA`, `TSA_DHW`) | 0,1053 | 0,1004 |
| Razón contexto / térmicas | 0,78 | 0,83 |

Con DHW en el modelo, el bloque térmico supera al contexto bajo ambos esquemas. `TSA_DHW`
encabeza las dos jerarquías.

### Precisión terminológica

Debe subrayarse que estas magnitudes expresan la **proporción de la atribución agregada del
modelo** bajo una agrupación concreta de variables, y no la fracción del blanqueamiento
explicada por cada grupo de factores. Un valor de contribución SHAP cuantifica cuánto se
apoya el modelo ajustado en una variable, no cuánta varianza del fenómeno biológico depende
de ella. La confusión entre ambas lecturas constituye un error de interpretación frecuente
en la aplicación de estas técnicas.

## Reproducibilidad

Script de umbrales: `src/robustness_checks.py`. Script SHAP: `src/explainability.py`.
Semilla fija (`random_state=42`). El preprocesado se ajusta de forma independiente dentro de
cada partición de entrenamiento.
