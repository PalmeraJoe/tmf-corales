# 3. Objetivos

## 3.1. Objetivo general

Desarrollar y evaluar críticamente un sistema de clasificación de la severidad del blanqueamiento
coralino observado a escala global, construido sobre variables oceanográficas derivadas de teledetección
satelital (Liu et al., 2014) y observaciones de campo compiladas por Sully et al. (2019),
determinando de forma explícita en qué medida el rendimiento predictivo obtenido es transferible a
arrecifes no observados durante el entrenamiento.

La formulación del objetivo general incorpora deliberadamente la exigencia de transferibilidad
espacial. No se persigue únicamente maximizar una métrica de clasificación, sino establecer qué
fracción del rendimiento medido corresponde a conocimiento ecológico generalizable y cuál procede
del reconocimiento de emplazamientos previamente observados, en línea con las advertencias
metodológicas de Roberts et al. (2017) y Ploton et al. (2020).

## 3.2. Objetivos específicos

### OE1. Ingesta y consolidación del conjunto de datos

Incorporar al repositorio el conjunto *Global Bleaching and Environmental Data*, distribuido a
través de la infraestructura BCO-DMO, estableciendo una estructura de directorios que separe los
datos originales de los derivados y garantice la trazabilidad de las transformaciones aplicadas.
Comprende la identificación y normalización de los códigos de valor ausente presentes en el
fichero de origen, así como la caracterización de la completitud de cada campo.

*Fase CRISP-DM: Comprensión de los datos.*

### OE2. Análisis exploratorio y caracterización ecológica de las variables

Realizar un análisis exploratorio que documente la distribución de la variable de respuesta
`Percent_Bleaching`, cuantifique las asociaciones lineales entre los predictores ambientales y
dicha variable, y evalúe la estructura de correlación entre los propios índices térmicos. El
análisis debe interpretarse a la luz del mecanismo fisiológico descrito por Hoegh-Guldberg (1999),
identificando qué patrones resultan ecológicamente esperables y cuáles requieren explicación
adicional.

*Fase CRISP-DM: Comprensión de los datos.*

### OE3. Construcción de un flujo de preprocesado libre de fuga de información

Implementar un pipeline reproducible de imputación, escalado y codificación categórica cuyos
estadísticos se estimen **exclusivamente** sobre la partición de entrenamiento, y verificar
empíricamente la ausencia de contaminación del conjunto de prueba. Incluye la discretización
razonada de la variable de respuesta en tres niveles ordinales de severidad y la partición
estratificada que preserve la prevalencia de los episodios severos en ambos subconjuntos.

*Fase CRISP-DM: Preparación de los datos.*

### OE4. Modelado comparativo con compensación del desbalanceo de clases

Entrenar y comparar los competidores oficiales —regresión logística multinomial y Random Forest
(Breiman, 2001) con `max_depth` = 8— frente a la regla de Coral Reef Watch, incorporando
ponderación que compense la acusada asimetría de clases. XGBoost (Chen y Guestrin, 2016) y
LightGBM (Ke et al., 2017) se retienen únicamente en la comparativa aleatoria histórica del
apartado 6.3.1; LightGBM se ejecutó con parámetros por defecto y no entra en la validación
agrupada. La comparación oficial se apoya en métricas robustas al desbalanceo, con el F1-Score
macro y, sobre todo, el recall y el PR-AUC de la clase «Severo».

*Fase CRISP-DM: Modelado.*

### OE5. Evaluación de la transferibilidad espacial mediante validación agrupada

Diseñar y ejecutar un experimento de validación cruzada agrupada por emplazamiento
(`StratifiedGroupKFold` sobre `Site_ID`) que cubra el 100 % de las observaciones, y contrastarlo
con una validación aleatoria estratificada, con un *leave-one-ocean-out* y con un corte temporal.
La diferencia entre estimaciones proporciona una medida directa del grado de memorización espacial
de cada algoritmo, conforme al procedimiento recomendado por Roberts et al. (2017) y aplicado por
Ploton et al. (2020). El término de comparación operativo es la regla de Coral Reef Watch
(`TSA_DHW` ≥ 4 °C·semana), no un clasificador trivial. El mismo objetivo incluye un
*leave-one-program-out* —transferencia entre protocolos de monitoreo, todavía interna a la
síntesis— y el índice de disimilitud de Meyer y Pebesma (2021) sobre el ocean-out, de modo que
el F1 de cuenca nueva no se comunique como cifra única. Incluye asimismo el bloqueo Caribe +
apéndice polinesio (*Eastern Indo-Pacific*), el corte 2010–2017 / 2018–2020 —complemento del
corte térmico 2013–2020, no su sustituto— y la comparación empírica, en signo, de las dos
afirmaciones de Sully et al. (2019); ninguno de esos ejercicios es un conjunto externo. El
holdout Reef Check 2021–2026 del apartado 5.4.9 sí lo es: no se concatena al CSV interno y
no forma parte de BCO-DMO 773466.

*Fase CRISP-DM: Evaluación.*

### OE6. Análisis de interpretabilidad mediante valores SHAP

Descomponer las predicciones del **Random Forest recomendado** (`max_depth` = 8, con `TSA_DHW`)
mediante el marco de atribución aditiva de Lundberg y Lee (2017), sobre un holdout agrupado por
`Site_ID` de modo que ningún emplazamiento entre a la vez en el ajuste y en la explicación. El
análisis debe establecer no solo la jerarquía de importancia global, sino también la dirección del
efecto de cada variable, y confrontar dichas direcciones con el conocimiento ecológico disponible,
identificando aquellas atribuciones que constituyen artefactos de la colinealidad entre predictores
y no relaciones biológicas interpretables.

*Fase CRISP-DM: Evaluación.*

### OE7. Transferencia de los resultados a la gestión de Áreas Marinas Protegidas

Traducir los hallazgos técnicos en recomendaciones operativas diferenciadas para la gestión de
Áreas Marinas Protegidas, distinguiendo tres escenarios: sitio conocido, cuenca nueva y temporada
futura. El término de comparación en los dos últimos es la regla de Coral Reef Watch, no un
clasificador trivial.

*Fase CRISP-DM: Despliegue.*

## 3.3. Correspondencia entre objetivos, fases metodológicas y productos

| Objetivo | Fase CRISP-DM | Artefacto generado |
|---|---|---|
| OE1 | Comprensión de los datos | Conjunto de datos original de blanqueamiento y variables ambientales |
| OE2 | Comprensión de los datos | Análisis exploratorio; Figuras 6.1–6.4 |
| OE3 | Preparación de los datos | Flujo de preprocesado y conjuntos de modelado |
| OE4 | Modelado | Comparativa de algoritmos (apartado 6.3) |
| OE5 | Evaluación | Validación espacial, temporal, de protocolo y externa Reef Check 2021–2026; Figuras 6.5–6.7 y 6.11–6.17 |
| OE6 | Evaluación | Análisis SHAP del RF-8 + DHW; Figuras 6.8–6.10 |
| OE7 | Despliegue | Capítulo 7 de la presente memoria |

## 3.4. Delimitación del alcance

Conviene precisar los límites del trabajo para evitar expectativas no atendidas por el diseño
adoptado.

El estudio clasifica la **severidad del blanqueamiento observado de forma concurrente con el
muestreo**, y no la probabilidad de un evento futuro. No constituye, por tanto, un sistema de
predicción temporal, distinción que se desarrolla en el apartado 5.3.3 y que delimita el alcance de
las conclusiones sobre alerta temprana. El corte 1980–2012 / 2013–2020 del apartado 6.7 estima transferencia a una temporada no
observada, no un pronóstico operativo. El corte 2010–2017 / 2018–2020 acota esa pregunta a
los años posteriores a Sully et al. (2019); el fichero interno no contiene 2021. Esa laguna se
cierra en el apartado 5.4.9 con el export Belt de Reef Check 2021–2026, que no se concatena al
conjunto de 34 515 observaciones: se reserva como holdout externo. El experimento sigue siendo
una clasificación concurrente, no un sistema de alerta.

El diseño es de **naturaleza transversal**: cada observación se trata como un registro independiente
en el tiempo. La acumulación de estrés en la ventana previa —formalizada en el índice *Degree
Heating Weeks*— forma parte del conjunto principal de predictores (`TSA_DHW`).

El conjunto de predictores de la comparativa principal comprende **seis variables cuantitativas y
una categórica regional**, omitiendo descriptores de composición de la comunidad coralina,
cobertura bentónica, turbidez y presiones antrópicas locales.

Finalmente, el trabajo no persigue la **inferencia causal**. Las relaciones identificadas mediante
el análisis de interpretabilidad describen el comportamiento del modelo ajustado y admiten
interpretación ecológica como hipótesis compatibles con los datos, pero no constituyen evidencia
de causalidad.
