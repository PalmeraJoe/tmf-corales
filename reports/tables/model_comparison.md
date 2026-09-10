# Comparativa de modelos de clasificación

Los cuatro clasificadores se entrenaron sobre el conjunto de entrenamiento (80 %) y se evaluaron
sobre el conjunto de prueba (20 %), estratificado por nivel de riesgo de blanqueamiento.
Todos los modelos incorporan tratamiento del desbalanceo de clases, dado que la clase «Bajo»
representa cerca del 79 % de las observaciones.

## Tabla comparativa de métricas (conjunto de prueba)

| Modelo | Accuracy | Precision (Macro) | Recall (Macro) | F1-Score (Macro) | ROC-AUC (OvR ponderado) |
|---|---|---|---|---|---|
| Regresión Logística | 0.5456 | 0.4126 | 0.4682 | 0.3893 | 0.6992 |
| Random Forest | 0.8763 | 0.7364 | 0.7588 | 0.7464 | 0.9430 |
| LightGBM | 0.8250 | 0.6962 | 0.4919 | 0.5364 | 0.8810 |
| XGBoost (GridSearchCV) | 0.7944 | 0.6224 | 0.7370 | 0.6585 | 0.9001 |

## Interpretación

El modelo con mejor F1-Score macro es **Random Forest**. Dado el fuerte desbalanceo de clases, la
métrica macro resulta más informativa que la exactitud global, ya que pondera por igual los
episodios de blanqueamiento severo y los arrecifes sin afectación aparente.

Los hiperparámetros óptimos de XGBoost, seleccionados mediante `GridSearchCV`
(validación cruzada de 3 particiones sobre el conjunto de entrenamiento y `f1_macro`
como criterio), fueron: `learning_rate` = 0.2, `max_depth` = 7.

Desde la perspectiva de la gestión de Áreas Marinas Protegidas (AMP), interesa especialmente la
capacidad de recuperación (*recall*) sobre la clase «Severo»: un falso negativo implica no activar
el protocolo de vigilancia en un arrecife que sí está sufriendo un evento de blanqueamiento.

## Limitaciones metodológicas

La partición se realizó mediante muestreo aleatorio estratificado sobre `Bleaching_Class`, criterio
que garantiza la representación proporcional de los eventos severos en ambos conjuntos.
No obstante, conviene explicitar una limitación en la interpretación de los resultados.
El conjunto analizado contiene 34,515 observaciones procedentes de únicamente 11,068 arrecifes distintos (`Site_ID`), es decir, una media de 3.1 muestreos por emplazamiento.
Al operar la partición a nivel de observación y no de emplazamiento, un mismo arrecife puede estar
representado simultáneamente en entrenamiento y en prueba. Dado que `Depth_m`,
`Distance_to_Shore` y `ClimSST` presentan valores casi constantes dentro de cada emplazamiento,
los modelos basados en árboles pueden reconocer arrecifes ya observados durante el entrenamiento.

En consecuencia, las métricas de esta tabla deben interpretarse como una estimación del rendimiento
en arrecifes ya monitorizados, y no como la capacidad de generalización a emplazamientos nuevos.
Esta lectura es coherente con el análisis exploratorio: las anomalías puntuales correlacionan
débilmente con el blanqueamiento (r ≤ 0,134), mientras que `TSA_DHW` alcanza r = 0,228
(listwise) y 0,272 (bivariante). La validación agrupada por `Site_ID` se presenta en el
apartado 6.4.

## Figuras asociadas

Las matrices de confusión de cada modelo se encuentran en `reports/figures/` con el prefijo
`confusion_matrix_`.
