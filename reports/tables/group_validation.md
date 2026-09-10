# Validación cruzada agrupada por arrecife (GroupKFold sobre `Reef_ID`)

## Objetivo del experimento

La comparativa principal de modelos se construyó mediante muestreo aleatorio estratificado, en el
que un mismo arrecife puede aparecer simultáneamente en entrenamiento y en prueba. Este
experimento evalúa una pregunta distinta y más exigente desde el punto de vista de la gestión
marina: ¿qué rendimiento cabe esperar cuando el modelo se aplica a arrecifes **completamente no
observados** durante el entrenamiento?

Para responderla se emplea `GroupKFold` con `Reef_ID` como variable de agrupación, de modo
que todas las observaciones de un mismo arrecife quedan confinadas en un único pliegue.

## Diseño y submuestra analizada

`Reef_ID` solo está informado en una parte del conjunto de datos, por lo que el experimento
se restringe a esa submuestra. Ambos esquemas de validación se ejecutan sobre **exactamente el
mismo subconjunto**, de manera que la diferencia observada sea atribuible al criterio de
partición y no a un cambio en los datos.

| Característica de la submuestra | Valor |
|---|---|
| Observaciones con `Percent_Bleaching` y `Reef_ID` | 22,531 |
| Arrecifes distintos (`Reef_ID`) | 4,115 |
| Observaciones por arrecife (media) | 5.5 |
| Clase «Bajo» | 93.03 % |
| Clase «Moderado» | 4.86 % |
| Clase «Severo» | 2.11 % |
| Número de pliegues | 5 |

Debe advertirse que esta submuestra presenta un desbalanceo considerablemente mayor que el
conjunto completo: los episodios severos representan aquí un 2.11 %
de los registros, frente al 12,42 % del conjunto empleado en la comparativa principal. Por tanto,
las cifras de este apartado no son directamente comparables con las de
`reports/tables/model_comparison.md`; la lectura pertinente es la **comparación interna** entre
ambos esquemas de validación.

## Resultados

| Modelo | F1 aleatoria (media) | F1 aleatoria (sd) | F1 agrupada (media) | F1 agrupada (sd) | Δ absoluta | Δ relativa (%) |
|---|---|---|---|---|---|---|
| Random Forest | 0.8981 | 0.0138 | 0.4297 | 0.0188 | -0.4684 | -52.1509 |
| XGBoost | 0.7541 | 0.0152 | 0.4296 | 0.0224 | -0.3245 | -43.0349 |
| LightGBM | 0.5908 | 0.0202 | 0.3875 | 0.0275 | -0.2033 | -34.4070 |
| Regresión Logística | 0.3004 | 0.0053 | 0.2949 | 0.0094 | -0.0055 | -1.8362 |

Recall sobre la clase «Severo», métrica crítica para la alerta temprana en Áreas Marinas
Protegidas (AMP):

| Modelo | Recall «Severo» (aleatoria) | Recall «Severo» (agrupada) | Δ absoluta |
|---|---|---|---|
| Regresión Logística | 0.4632 | 0.4253 | -0.0378 |
| XGBoost | 0.8253 | 0.1696 | -0.6557 |
| Random Forest | 0.8295 | 0.1290 | -0.7005 |
| LightGBM | 0.3937 | 0.0647 | -0.3290 |

Figura: `reports/figures/validacion_grupos_reef_id.png`.

## Discusión

Al pasar de la validación aleatoria a la validación agrupada por arrecife, el rendimiento de los
modelos se deteriora de forma sistemática. El caso más acusado es **Random Forest**, con una caída
relativa del F1-Score macro del 52.2 %. Bajo el
esquema agrupado, el mejor F1-Score macro corresponde a **Random Forest**
(0.4297), si bien las diferencias entre los modelos de
árboles prácticamente desaparecen: la ventaja que Random Forest exhibía en la validación aleatoria
se disuelve al exigirle predecir sobre arrecifes no observados.

El hallazgo más relevante es una **inversión en la robustez de los modelos**. La regresión
logística, claramente el peor clasificador bajo validación aleatoria, es a la vez el más estable:
su F1-Score macro apenas varía
(1.8 % de caída relativa). Más aún, en el
escenario agrupado es **Regresión Logística** el modelo que mejor detecta los episodios severos, con un
recall de 0.4253, frente a valores
inferiores a 0,20 en Random Forest y XGBoost. Estos últimos ven desplomarse su recall de la clase
«Severo» desde valores próximos a 0,83 hasta el entorno de 0,13–0,17.

La lectura es inequívoca: los modelos de árboles no estaban aprendiendo principalmente la relación
entre estrés térmico y blanqueamiento, sino la identidad de cada arrecife y su historial. Un
modelo lineal, incapaz de memorizar emplazamientos concretos, conserva la escasa señal ambiental
genuina y se comporta mejor al extrapolar. Este resultado desaconseja seleccionar el modelo final
únicamente por su rendimiento en la validación aleatoria.

Esta degradación admite una interpretación ecológica precisa. Las variables `Depth_m`,
`Distance_to_Shore` y `ClimSST` son prácticamente constantes dentro de un mismo arrecife, de modo
que actúan como una firma del emplazamiento. Cuando ese arrecife aparece en ambos lados de la
partición, los modelos basados en árboles pueden reconocerlo y reproducir su comportamiento
histórico de blanqueamiento, sin necesidad de haber aprendido el mecanismo de estrés térmico
subyacente. La validación agrupada elimina esa vía y obliga al modelo a apoyarse en la señal
ambiental genuina, que el análisis exploratorio ya mostraba débil en las anomalías puntuales
(r ≤ 0,134 para SSTA y TSA) y encabezada por `TSA_DHW` (r = 0,228 listwise; 0,272 bivariante).

La mayor dispersión entre pliegues del esquema agrupado refuerza esta lectura: el rendimiento
depende del conjunto concreto de arrecifes que quedan fuera del entrenamiento, lo que evidencia
una **heterogeneidad biogeográfica** que las cinco variables predictoras no capturan. Arrecifes
de distintas ecorregiones difieren en composición de especies, historia térmica y capacidad de
aclimatación de sus comunidades de zooxantelas, factores ausentes del conjunto de predictores.

## Conclusiones para la gestión

Los resultados de la validación aleatoria describen la capacidad del modelo para **interpolar
dentro de una red de arrecifes ya monitorizada**, escenario realista cuando una AMP dispone de
series históricas de seguimiento. Los resultados de la validación agrupada, más conservadores,
describen la capacidad de **extrapolar a arrecifes sin histórico**, que es el escenario habitual
al extender la vigilancia a nuevas áreas.

En consecuencia, se recomienda reportar ambas cifras en la memoria: la primera como límite
superior optimista y la segunda como estimación prudente para la planificación. Para desplegar el
modelo en emplazamientos no monitorizados convendría incorporar descriptores ecorregionales y
métricas acumuladas de estrés térmico (por ejemplo, *Degree Heating Weeks*), en lugar de asumir
que el rendimiento observado en la validación aleatoria se mantendrá.

La elección del modelo debe subordinarse al escenario de aplicación. Para una AMP con red de
seguimiento consolidada, Random Forest sigue siendo la opción preferente. Para extender la alerta
temprana a arrecifes sin histórico, un modelo más simple y estable resulta preferible pese a su
menor rendimiento aparente, ya que la prioridad es no dejar sin detectar episodios severos.

Como refinamiento metodológico, `StratifiedGroupKFold` permitiría preservar la proporción de
clases entre pliegues manteniendo la separación por arrecife, lo que reduciría la varianza
observada en la estimación.
