# 5. Material y Métodos

## 5.1. Enfoque metodológico: CRISP-DM

El desarrollo del presente Trabajo Fin de Máster se ha estructurado conforme a la metodología
CRISP-DM (*Cross-Industry Standard Process for Data Mining*), formulada por Wirth y Hipp (2000)
como modelo de proceso neutral respecto del sector de aplicación y de la herramienta empleada, y
consolidada desde entonces como estándar de referencia en proyectos de minería de datos y
aprendizaje automático. Los autores conciben el proceso como una secuencia de seis fases con
**retornos explícitos** entre ellas, de modo que los hallazgos de una etapa posterior pueden
motivar la revisión de las decisiones adoptadas en una anterior.

Este carácter iterativo resulta especialmente adecuado en el ámbito de la ecología marina, donde la
validación de los resultados exige un contraste continuo entre el rendimiento estadístico y la
plausibilidad biológica. El presente trabajo ilustra esa realimentación: constatar que `Reef_ID`
identifica un programa, no el conjunto, obligó a rehacer la validación por `Site_ID` y a incorporar
`TSA_DHW` al modelo principal, tal como se describe en los apartados 5.3.2 y 5.4.

La correspondencia entre las fases de la metodología y los artefactos desarrollados se recoge en
la tabla siguiente:

| Fase CRISP-DM | Descripción aplicada al estudio | Artefacto |
|---|---|---|
| Comprensión del negocio | Formulación del problema como clasificación de la severidad del blanqueamiento coralino observado, orientada a la gestión de Áreas Marinas Protegidas (AMP) | Capítulos 2 y 3 |
| Comprensión de los datos | Análisis exploratorio, caracterización de la variable objetivo y evaluación de la calidad del registro | Apartado 6.1; Figuras 6.1–6.4 |
| Preparación de los datos | Filtrado, ingeniería de la variable objetivo categórica, imputación, escalado y codificación | Apartado 5.3 |
| Modelado | Entrenamiento y optimización de cuatro algoritmos de clasificación | Apartados 5.5 y 6.3 |
| Evaluación | Comparativa frente a Coral Reef Watch, CV por `Site_ID`, leave-one-ocean-out y holdout Reef Check 2021–2026 | Apartados 5.4 y 6.3–6.7 |
| Despliegue | Interpretabilidad del modelo y traducción de los resultados a recomendaciones de gestión | Apartados 6.6 y 7.2 |

## 5.2. Origen y estructura del conjunto de datos

Se ha empleado el conjunto de datos *Global Bleaching and Environmental Data*, que compila
observaciones de blanqueamiento coralino a escala mundial acompañadas de las variables
oceanográficas asociadas a cada muestreo. El fichero original contiene **41 361 observaciones y 62
variables**, e integra registros procedentes de diversas fuentes de monitorización de arrecifes.

El conjunto procede de la síntesis global publicada por Sully et al. (2019), que agregó
observaciones de campo de 3 351 emplazamientos en 81 países durante el periodo 1998–2017. El
extracto de trabajo es el dataset *Global Bleaching and Environmental Data* de van Woesik y
Kratochwill (2022), difundido por **BCO-DMO** (registro 773466). Las variables térmicas asociadas
a cada muestreo derivan de los productos operativos de estrés térmico del programa Coral Reef
Watch de la NOAA, cuya formulación algorítmica documentan Liu et al. (2014).

Esta procedencia tiene una consecuencia metodológica que conviene explicitar desde ahora:
`ClimSST`, `SSTA`, `TSA` y `TSA_DHW` no constituyen mediciones independientes entre sí, sino transformaciones
sucesivas de un mismo campo de temperatura superficial. La colinealidad resultante condiciona la
interpretación del análisis de explicabilidad (apartado 6.6.3).

Las variables se agrupan en cinco bloques: identificadores del muestreo y del emplazamiento
(`Site_ID`, `Reef_ID`), descriptores geográficos y biogeográficos (`Latitude_Degrees`,
`Ocean_Name`, `Realm_Name`, `Ecoregion_Name`), características del hábitat (`Depth_m`,
`Distance_to_Shore`, `Turbidity`, `Exposure`), variables térmicas derivadas de teledetección
(`ClimSST`, `SSTA`, `TSA`, `TSA_DHW` y sus estadísticos asociados) y variables de respuesta biológica
(`Percent_Bleaching`, `Bleaching_Level`, `Percent_Cover`).

Debe señalarse que el fichero original codifica los valores ausentes mediante la cadena `nd`. Su
tratamiento explícito como valor nulo durante la lectura resulta imprescindible, dado que su
omisión conduciría a interpretar erróneamente como completas variables con proporciones
sustanciales de datos faltantes.

El apartado 5.4.9 describe un segundo corpus, ajeno a este fichero: el export Belt de Reef Check
Foundation (2026) para 2021–2026. No se concatena al conjunto de trabajo de 34 515 observaciones. Se
reserva como holdout de validación externa.

## 5.3. Preparación de los datos

### 5.3.1. Filtrado de la variable objetivo

La variable de respuesta principal es `Percent_Bleaching`, que expresa el porcentaje de cobertura
o de colonias coralinas afectadas por blanqueamiento en cada muestreo. Se descartaron las
observaciones carentes de este valor, al no permitir cuantificar la magnitud del evento. El
filtrado eliminó **6 846 registros (16,55 %)**, quedando un conjunto de trabajo de **34 515
observaciones**.

### 5.3.2. Selección de variables predictoras

Atendiendo tanto al criterio de completitud como a la relevancia ecológica, se seleccionaron seis
predictores cuantitativos y una variable categórica regional. Los cuatro primeros corresponden a
índices operativos del programa Coral Reef Watch, definidos formalmente en el apartado 4.1 conforme
a Liu et al. (2014) y Skirving et al. (2020):

| Variable | Naturaleza | Significado ecológico |
|---|---|---|
| `SSTA` | Continua (°C) | *Sea Surface Temperature Anomaly*: desviación de la temperatura superficial respecto a la climatología del emplazamiento |
| `TSA` | Continua (°C) | *Thermal Stress Anomaly*: exposición a temperaturas por encima del umbral de blanqueamiento |
| `TSA_DHW` | Continua (°C·semana) | *Degree Heating Weeks*: integral del estrés térmico en las doce semanas precedentes |
| `Depth_m` | Continua (m) | Profundidad del muestreo; condiciona la irradiancia recibida y la existencia de refugio térmico |
| `Distance_to_Shore` | Continua (m) | Distancia a la costa; aproxima presiones locales de origen terrestre como escorrentía y turbidez |
| `ClimSST` | Continua (K) | Temperatura superficial climatológica; describe el régimen térmico basal del arrecife |
| `Ocean_Name` | Categórica | Cuenca oceánica; proporciona contexto biogeográfico |

`TSA_DHW` se incorpora al conjunto principal y no a un experimento satélite. Su completitud es del
99,65 % —del mismo orden que `SSTA` y `TSA`— y su fundamento fisiológico está desarrollado en el
apartado 4.1.4: el blanqueamiento responde a la integral del estrés, no a la anomalía puntual.

La inclusión de `ClimSST` merece una justificación específica, pues no describe evento alguno sino
el régimen térmico basal del emplazamiento. Su relevancia predictiva se sustenta en la evidencia de
que la tolerancia térmica de una comunidad coralina depende de su historia climática:
Hoegh-Guldberg (1999) estableció que el blanqueamiento se desencadena al superarse un umbral
específico del holobionte, y Sully et al. (2019) documentaron a escala global que dicho umbral es
más elevado en localidades sometidas históricamente a mayor variabilidad térmica. `ClimSST`
introduce, por tanto, el contexto adaptativo que `SSTA` y `TSA` no capturan por sí solos.

Se excluyeron deliberadamente las variables con porcentajes de ausencia superiores al 30 %
(`Bleaching_Level`, `Substrate_Name`, `Percent_Cover`) y los campos de texto libre
(`Site_Comments`, `Sample_Comments`, `Bleaching_Comments`), cuya cumplimentación supera el 92 % de
valores ausentes y que no constituyen predictores válidos.

En la nomenclatura de las variables transformadas se ha preservado el nombre original del
descriptor oceanográfico, evitando los prefijos genéricos que introduce por defecto la
implementación de `ColumnTransformer`. Esta decisión, de apariencia menor, garantiza que el
contexto marino de cada variable permanezca explícito a lo largo de todo el flujo analítico.

### 5.3.3. Construcción de la variable objetivo categórica

**Naturaleza de la variable de respuesta.** Antes de describir la discretización procede delimitar
con precisión qué predice el modelo, por cuanto de ello depende el alcance legítimo de las
conclusiones. `Percent_Bleaching` registra el porcentaje de colonias blanqueadas **observado en el
momento del muestreo**, y los predictores térmicos describen las condiciones asociadas a ese mismo
registro. La tarea es, en consecuencia, una **clasificación de la severidad del blanqueamiento
observado en función de las condiciones ambientales concurrentes**, y no una predicción de
naturaleza temporal.

La distinción no es terminológica. Un sistema de alerta temprana en sentido estricto requeriría
estimar $P(\text{blanqueamiento en } t + \Delta \mid \text{condiciones en } t)$, lo que exige un
diseño longitudinal con desfase explícito entre predictores y respuesta. El presente diseño es
transversal y estima $P(\text{clase de severidad} \mid \text{condiciones concurrentes})$. Por ello
se emplea a lo largo de la memoria la expresión «severidad de blanqueamiento observada» en lugar de
«riesgo», reservándose este último término para el ámbito de la priorización de recursos de gestión,
donde su uso sí resulta apropiado. Las implicaciones prácticas de esta delimitación se retoman en
el apartado 7.2.

**Umbrales de discretización.** Se derivó la variable ordinal `Bleaching_Class` a partir de
`Percent_Bleaching` con tres niveles de severidad:

| Clase | Criterio | Interpretación para la gestión |
|---|---|---|
| Bajo | `Percent_Bleaching` < 10 % | Arrecife sin evento agudo detectable |
| Moderado | 10 % ≤ `Percent_Bleaching` ≤ 30 % | Episodio incipiente que requiere seguimiento |
| Severo | `Percent_Bleaching` > 30 % | Evento de blanqueamiento masivo con riesgo de mortalidad |

Los cortes responden a un criterio operativo. El umbral inferior separa el fondo de blanqueamiento
crónico de baja intensidad —presente de forma casi permanente en cualquier arrecife y carente de
significado como evento— de una afectación apreciable en la inspección visual. El superior delimita los episodios de carácter
masivo, que son los que comprometen la supervivencia de la colonia si el estrés persiste
(Hoegh-Guldberg, 1999) y los que motivan la intervención de gestión.

Debe reconocerse, no obstante, que cualquier discretización de una variable continua conlleva
pérdida de información y que la elección concreta de los cortes admite discusión. Por ello el
apartado 6.7.3 somete esta decisión a un análisis de sensibilidad, contrastando la configuración
adoptada con otras tres alternativas razonables para verificar que las conclusiones del trabajo no
dependen de ella.

### 5.3.4. Pipeline de transformación y prevención del Data Leakage

El preprocesado se implementó mediante un `ColumnTransformer` que encadena tres operaciones: la
imputación de valores ausentes de las variables numéricas por la mediana, su estandarización con
`StandardScaler` y la codificación *one-hot* de `Ocean_Name`.

El aspecto metodológicamente crítico reside en que **todos los estadísticos de transformación se
estiman exclusivamente sobre el conjunto de entrenamiento** y se aplican posteriormente al
conjunto de prueba. Si las medianas de imputación o los parámetros de escalado se calculasen sobre
la totalidad de los datos, la información del conjunto de prueba se filtraría en el proceso de
entrenamiento (*Data Leakage*), produciendo estimaciones de rendimiento optimistas y no
reproducibles en un despliegue real.

Las medianas empleadas en la imputación, estimadas únicamente sobre el conjunto de entrenamiento,
fueron: `SSTA` = 0,2700 °C; `TSA` = −0,7100 °C; `TSA_DHW` = 0,0000 °C·semana;
`Depth_m` = 6,0000 m; `Distance_to_Shore` = 475,9200 m; y `ClimSST` = 300,8000 K.

La verificación empírica de la ausencia de fuga de información se obtiene al comprobar que las
variables estandarizadas presentan media nula y desviación típica unitaria exactas en el conjunto
de entrenamiento, mientras que en el conjunto de prueba se desvían ligeramente de dichos valores
(por ejemplo, `SSTA` presenta una media de −0,0051 y una desviación de 1,0140), comportamiento
esperable cuando los parámetros proceden únicamente de la partición de entrenamiento.

## 5.4. Estrategia de validación

### 5.4.1. Partición estratificada

La partición principal reserva el **80 % de las observaciones para entrenamiento (27 612
registros) y el 20 % para prueba (6 903 registros)**, aplicando estratificación sobre
`Bleaching_Class`. La estratificación resulta indispensable ante el marcado desbalanceo del
conjunto, y garantiza que la proporción de episodios severos se mantenga en ambas particiones.

### 5.4.2. Validación cruzada agrupada por emplazamiento

**Precisión sobre la unidad experimental.** El conjunto de datos define dos niveles de agregación
espacial que conviene no confundir, pues la elección entre ellos determina la interpretación de
todo el diseño de validación:

| Identificador | Nivel | Recuento | Cobertura |
|---|---|---|---|
| Observación (fila) | Registro individual de muestreo | 34 515 | 100 % |
| `Site_ID` | Emplazamiento o punto de muestreo concreto | 11 068 | 100 % |
| `Reef_ID` | Arrecife, que agrupa varios emplazamientos próximos | 4 115 | 65,3 % |

La unidad de observación es la fila. La unidad **experimental** que este trabajo considera
pertinente para la transferencia entre sitios es el emplazamiento (`Site_ID`): está informado en el
100 % de los registros y no selecciona un programa de monitoreo concreto. Un mismo emplazamiento
agrupa en promedio 3,1 observaciones.

`Reef_ID` solo está informado en 22 531 registros, y esos registros pertenecen **íntegramente** al
programa Reef_Check. Donner, McClanahan, FRRP, Kumagai y el resto de fuentes —precisamente las que
concentran los eventos masivos— quedan fuera de cualquier experimento agrupado por `Reef_ID`. La
validación por arrecife no estima, por tanto, la transferencia global: estima la transferencia
dentro de un protocolo de monitoreo rutinario. El diagnóstico de esta asimetría y sus consecuencias
se desarrollan en el apartado 6.4.1. La corrección adoptada es agrupar por `Site_ID` sobre las
34 515 observaciones.

Esta circunstancia plantea dos problemas metodológicos bien documentados en la literatura
ecológica. El primero es la **pseudorreplicación**, definida por Hurlbert (1984) como el empleo de
estadística inferencial sobre datos en los que las réplicas no son estadísticamente independientes:
las observaciones de un mismo emplazamiento no constituyen unidades muestrales independientes,
supuesto sobre el que descansa la estimación convencional del error de generalización. Resulta
pertinente señalar que aquel autor identificó los estudios de bentos marino entre los de mayor
incidencia de esta práctica. El segundo es la **autocorrelación espacial** de los propios índices
térmicos, cuantificada en el apartado 4.5.1: `TSA_DHW` alcanza $I = 0{,}528$, por encima del
blanqueamiento observado. Un algoritmo con capacidad de memorización suficiente puede reconocer la
región de procedencia a través del régimen térmico, sin haber aprendido el mecanismo ecológico
subyacente.

Roberts et al. (2017) demostraron que, ante estructuras de dependencia de esta naturaleza, la
validación cruzada aleatoria infraestima gravemente el error de predicción, y recomiendan la
validación por bloques (*block cross-validation*) siempre que el objetivo sea predecir sobre datos
nuevos o seleccionar predictores causales.

Para cuantificar la magnitud de este efecto se diseñó un experimento basado en
`StratifiedGroupKFold` con `Site_ID` como variable de agrupación, de manera que la totalidad de las
observaciones de un emplazamiento se confina en un único pliegue. Ambos esquemas de validación
—aleatorio estratificado y agrupado— se ejecutaron con cinco pliegues sobre **exactamente el mismo
conjunto completo**, a fin de que las diferencias observadas sean atribuibles al criterio de
partición y no a una variación en los datos analizados. Este diseño pareado reproduce el
procedimiento empleado por Ploton et al. (2020).

### 5.4.3. Bloqueo geográfico: ecorregión y cuenca oceánica

La agrupación por `Site_ID` garantiza que ningún emplazamiento aparezca en dos pliegues, pero no
impone separación geográfica entre sitios distintos. En la tipología de Valavi et al. (2019),
corresponde al extremo de grano más fino del espectro. Por ello se añadieron dos esquemas de grano
más grueso:

- **Validación cruzada por ecorregión** (113 ecorregiones, cinco pliegues agrupados): estima la
  transferencia entre regiones biogeográficas del mismo océano.
- ***Leave-one-ocean-out*** (cinco cuencas): el modelo se entrena en cuatro cuencas y se evalúa en
  la quinta. `Ocean_Name` se excluye de los predictores por ser constante en cada conjunto de
  prueba. La cifra resultante es la de «cuenca nueva».

La agrupación por `Reef_ID` se retiene únicamente como diagnóstico del sesgo de protocolo, no como
estimación de transferibilidad.

### 5.4.4. Ablación de predictores y de capacidad

La comparación entre esquemas de validación cuantifica la magnitud de la degradación, pero no
identifica su origen. Se contrastaron tres conjuntos de predictores —base, base con `TSA_DHW`, y
únicamente índices térmicos más `TSA_DHW`, sin profundidad, distancia ni cuenca— bajo ambos
esquemas sobre datos idénticos. Si la señal que se pierde al separar los emplazamientos procediera
de los descriptores del sitio, un modelo privado de ellos debería degradarse menos.

En paralelo se contrastó la **capacidad** del Random Forest: profundidad máxima 8, profundidad
máxima 16 y sin tope, con la misma semilla y el mismo conjunto de predictores. El bosque sin
restricción de profundidad se interpreta como ablación de capacidad, no como competidor oficial.

### 5.4.5. Corte temporal y regla de Coral Reef Watch

La validación agrupada mide transferencia en el espacio. La pregunta operativa añade la dimensión
temporal: se entrena con las campañas hasta 2012 y se evalúa sobre 2013–2020, temporada que el
modelo no ha visto. El término de comparación no es un clasificador trivial, sino la **regla
operativa de Coral Reef Watch**: alerta de nivel 1 si `TSA_DHW` ≥ 4 °C·semana y de nivel 2 si
`TSA_DHW` ≥ 8 (Liu et al., 2014; Skirving et al., 2020). Esa regla no requiere entrenamiento, ajuste
de hiperparámetros ni histórico del emplazamiento.

Complementariamente se ejecutó un corte **restringido a la década reciente**: entrenamiento
2010–2017 y prueba 2018–2020. El conjunto interno no contiene 2021 ni años posteriores (máximo 2020,
n = 90). Esa prueba cae **después** de la ventana 1998–2017 de Sully et al. (2019). No es un
corpus externo: el 100 % de 2018–2020 es Reef_Check, y ninguno de sus 49 «Severo» alcanza
DHW ≥ 4. El corte 1980–2012 / 2013–2020 permanece como el test térmico de referencia
**dentro** de BCO-DMO. El holdout 2021–2026, ya ajeno a ese fichero, se describe en 5.4.9.

### 5.4.6. Leave-one-program-out y contraste de protocolo

`Data_Source` identifica el programa de origen, no un conjunto externo. Se retuvo como prueba,
uno a uno, cada programa con al menos 200 observaciones y se entrenó con el resto. El experimento
permanece dentro de la síntesis de Sully et al. (2019): estima transferencia **entre protocolos**,
no validación externa. Complementariamente se contrastó el monitoreo rutinario (Reef_Check y
AGRRA) frente a la documentación de eventos (Donner, McClanahan y Kumagai). La métrica de lectura
principal no es el F1, sino la distancia entre la prevalencia observada y la P(Severo) media: un
desfase sistemático delata un cambio del proceso de etiquetado, no solo una pérdida de
discriminación.

### 5.4.7. Calibración de P(Severo) y área de aplicabilidad

Sobre las probabilidades de la clase «Severo» se calcularon el índice de Brier y el error
esperado de calibración (ECE) en diez bins de cuantiles, bajo CV por `Site_ID` (probabilidades
fuera de pliegue) y bajo el corte temporal. El diagrama de fiabilidad compara esas curvas con
la diagonal. Una regresión isotónica, ajustada únicamente sobre el entrenamiento, se retiene
como diagnóstico: si mejora el Brier a costa del recall a umbral 0,5, no sustituye al
clasificador oficial.

El área de aplicabilidad se calculó sobre el *leave-one-ocean-out* del Random Forest de
profundidad 8, siguiendo a Meyer y Pebesma (2021). Los seis predictores numéricos se
estandarizan en el entrenamiento y se ponderan por la media del valor absoluto SHAP del propio
bosque de esa cuenca —TreeSHAP exacto, no la reducción de impureza Gini, que Lundberg et al.
(2020) demuestran inconsistente (apartado 4.3.2)—. El índice de disimilitud (DI) de cada punto
de prueba es la distancia euclídea ponderada al vecino de entrenamiento más próximo. El umbral
del AOA es el bigote superior (Q3 + 1,5 IQR) del DI de cada punto de entrenamiento a su vecino.
Dentro de ese umbral la estimación de error se considera anclada al soporte; fuera, no.

### 5.4.8. Contraste con Sully y transferencias de dominio

Tres experimentos cierran el contraste con Sully et al. (2019) y las transferencias que un
gestor reconocería como «entrenar aquí, aplicar allá». Ninguno usa un conjunto ajeno a
BCO-DMO.

**Replicación empírica.** Sully et al. (2019) estimaron 28,1 °C y 28,7 °C sobre Reef Check
(9 215 puntos, 3 351 sitios), CoRTAD y un ajuste Weibull de la SST en episodios de
blanqueamiento (su Figura 4), no sobre este extracto BCO-DMO. Aquí se calcula la media
aritmética de `Temperature_Kelvin` − 273,15 en observaciones con `Percent_Bleaching` > 0,
en 1998–2006, 2007–2017 y 2018–2020, sobre todas las fuentes y, como análogo más cercano,
solo sobre Reef_Check. En paralelo, Spearman a nivel de emplazamiento entre
`Temperature_Kelvin_Standard_Deviation` y la proporción de episodios severos. No se
reajusta el modelo jerárquico ni se reproduce el Weibull de su Figura 4.

**Bloqueo Caribe + Pacífico Central.** El entrenamiento se restringe a las ecorregiones del
Gran Caribe (Bahamas–Florida, Belize, Antillas, Jamaica, Cuba, Caribe sur y Campeche) y al
reino *Eastern Indo-Pacific* (campo `Realm_Name`: Polinesia, Hawái, Line, Phoenix,
Marshall). Ese reino **no** es el *Central Indo-Pacific* de Spalding —ese es, precisamente,
el grueso de la prueba (Gran Barrera, Triángulo de Coral)—. `Ocean_Name` se excluye para
que la dummy «Pacífico» no filtre identidad de Polinesia hacia la Gran Barrera. El
competidor es de nuevo CRW. Sobre ese bosque se calcula el AOA ponderado por TreeSHAP.

**Corte 2010–2017 / 2018–2020.** Se reportan dos lecturas: todas las observaciones de
prueba, y solo los `Site_ID` ausentes del entrenamiento. El año 2020 aporta 90 registros:
el corte es, en la práctica, 2018–2019 más un stub. La segunda lectura aísla sitios nuevos
en años posteriores a Sully; no aísla un fenómeno térmico nuevo.

### 5.4.9. Validación externa: Reef Check 2021–2026

El CSV interno termina en 2020. Reef Check Foundation (2026) facilitó, bajo licencia CC BY-NC 4.0,
el export Belt del programa tropical para 2021–2026 (acceso el 10 de septiembre de 2026). Ese
fichero **no** forma parte de BCO-DMO 773466 (van Woesik y Kratochwill, 2022) ni del recorte
1998–2017 de Sully et al. (2019). No se recibió la hoja Site ni la de Substrate; el Belt ya informa
coordenadas, fecha, profundidad, país y región.

La unidad es la encuesta (`survey_id`), ligada al emplazamiento por `site_id`. El transecto de
100 m se divide en cuatro segmentos de 20 m (S1–S4). La etiqueta homóloga de `Percent_Bleaching`
es `Bleaching (% Of Population)`: porcentaje de colonias blanqueadas sobre el conjunto de corales
del segmento. Si el blanqueamiento está presente, el protocolo estima además el porcentaje medio
de cada colonia afectada (`Bleaching (% Of Colony)`); ese segundo campo se retiene como auxiliar
y **no** entra en el umbral del 30 %. Los blancos no se imputan a cero: significan que el dato no
se registró (Reef Check Foundation, comunicación de los metadatos). Se toma la media de los
segmentos con valor; 83 encuestas con los cuatro segmentos vacíos se descartan. Las cinco
categorías de basura y daño coralino, medidas en escala 0–3, no se usan.

`Ocean_Name` no coincide con la `region` de Reef Check (`Indo-Pacific` no es una cuenca del
modelo). Se mapea por región (Atlantic, Red Sea, Arabian Gulf, Hawaii, East Pacific) y, en el
Indo-Pacífico, por país y longitud (Maldivas, Mozambique y Madagascar al Índico; Malasia,
Indonesia, Australia y Polinesia al Pacífico). `Distance_to_Shore` no viaja en Belt: queda
ausente y el `SimpleImputer` del pipeline oficial la rellena con la mediana del entrenamiento
BCO-DMO. En las 2 555 encuestas evaluadas esa imputación es una **constante**: el bosque no
dispone de variación de distancia a costa en este holdout. No se inventa un valor por sitio.

`SSTA`, `TSA`, `TSA_DHW` y `ClimSST` se extraen del producto operativo diario de 5 km de Coral
Reef Watch (conjunto `NOAA_DHW` en ERDDAP; Skirving et al., 2020) en el día del censo: anomalía
respecto a la climatología diaria, HotSpot con signo —homólogo de `TSA`—, DHW y climatología
`SST − SSTA` convertida a kelvin. Es la misma familia de productos que Liu et al. (2014) y
Skirving et al. (2020), **no** el NetCDF embebido en el extracto BCO-DMO 773466. El modelo
oficial, la logística térmica y la regla `TSA_DHW` ≥ 4 se **entrenan solo** sobre las 34 515
observaciones internas y se evalúan sobre este holdout.
Se reportan dos lecturas: todas las encuestas con DHW informado, y las que distan más de 1 km
de cualquier registro BCO-DMO (haversine). La primera admite reencuestas del mismo sitio; la
segunda es la prueba espacial más estricta. El experimento sigue siendo concurrente —DHW del día
del censo, no un pronóstico— y el protocolo sigue siendo Reef Check. No es una prueba de alerta
en una AMP.

Los censos de Sabah (Malasia) permanecen en el conjunto. Su uso exige reconocer al Sabah
Biodiversity Centre (SaBC) y a Reef Check Malaysia, conforme a las condiciones de acceso
comunicadas con el export (apartado 7.5).

## 5.5. Algoritmos evaluados

Se seleccionaron algoritmos que cubren un espectro creciente de complejidad, desde un modelo lineal
de referencia y una regla operativa sin entrenamiento hasta implementaciones de conjunto con
capacidad acotada:

| Algoritmo | Configuración | Tratamiento del desbalanceo |
|---|---|---|
| Regla Coral Reef Watch | `TSA_DHW` ≥ 4 o ≥ 8 °C·semana; sin entrenamiento | No aplica |
| Regresión logística | `max_iter` = 1000 | `class_weight='balanced'` |
| Random Forest (competidor) | `n_estimators` = 200, `max_depth` = 8 | `class_weight='balanced'` |
| Random Forest (ablación de capacidad) | `n_estimators` = 200, `max_depth` ∈ {16, None} | `class_weight='balanced'` |

La regresión logística cumple la función de modelo de referencia interpretable y de **control
metodológico**: su restricción estructural —imposibilidad de aislar combinaciones específicas de
valores de los predictores— impide memorizar emplazamientos, de modo que su comportamiento bajo
ambos esquemas de validación acota la magnitud de la señal ambiental transferible.

Random Forest (Breiman, 2001) se presenta en dos papeles distintos. El competidor oficial lleva
`max_depth` = 8: profundidad suficiente para capturar interacciones térmicas no lineales, insuficiente
para construir hojas específicas de emplazamiento. El bosque sin tope de profundidad se retiene
como ablación de capacidad, que es lo que realmente era el modelo de la comparativa inicial. El
apartado 6.4.3 muestra que una parte sustancial del «colapso» documentado al agrupar por `Reef_ID`
era hiperparámetro, no destino de la familia de árboles.

XGBoost (Chen y Guestrin, 2016) y LightGBM (Ke et al., 2017) **no forman parte de la comparativa
oficial**. Aparecen únicamente en la tabla histórica del apartado 6.3.1 (partición aleatoria, sin
`TSA_DHW`, bosque libre). LightGBM se ejecutó con hiperparámetros por defecto; no se reentrena
bajo validación agrupada ni entra en el análisis SHAP. La formulación matemática de ambos se
conserva en el apartado 4.2 como trasfondo de aquella comparativa.

El tratamiento del desbalanceo constituye un requisito ineludible: la clase «Bajo» concentra cerca
del 79 % de las observaciones, por lo que un clasificador trivial que predijese siempre dicha
categoría alcanzaría una exactitud aparentemente elevada sin ninguna utilidad para la gestión.
En la comparativa histórica, XGBoost —cuya implementación multiclase no admite `class_weight`—
compensó el desbalanceo mediante pesos por muestra calculados exclusivamente sobre el conjunto
de entrenamiento.

Se optó de forma deliberada por la **reponderación** de las observaciones y no por técnicas de
remuestreo sintético. La alternativa canónica, SMOTE (Chawla, Bowyer, Hall y Kegelmeyer, 2002), genera observaciones
minoritarias artificiales interpolando entre cada registro y sus vecinos más próximos en el espacio
de predictores. Este procedimiento resulta desaconsejable en el presente diseño por dos razones
concretas. En primer lugar, la interpolación entre observaciones vecinas en un conjunto con fuerte
estructura espacial tiende a generar registros intermedios entre arrecifes próximos, lo que
introduciría una forma adicional de fuga de información precisamente en la dimensión que este
trabajo pretende aislar. En segundo lugar, las observaciones sintéticas carecen de identificador de
arrecife, por lo que no podrían asignarse de manera coherente a los pliegues de la validación
agrupada. La reponderación, al modificar únicamente la función de pérdida sin alterar el soporte
muestral, preserva íntegra la correspondencia entre observación y unidad espacial.

La búsqueda en rejilla de XGBoost que documenta el apartado 6.3.1 se ejecutó con validación
cruzada de tres particiones sobre el conjunto de entrenamiento aleatorio, empleando el F1-Score
macro como criterio. No se reutiliza como competidor bajo `Site_ID`.

## 5.6. Métricas de evaluación

Dada la naturaleza desbalanceada del problema, la exactitud global resulta insuficiente como
criterio único. Se adoptó por tanto el conjunto de métricas siguiente:

- **Accuracy**: proporción global de aciertos; se reporta por convención, con las reservas
  indicadas.
- **Precision, Recall y F1-Score macro**: promedian el rendimiento de las tres clases con igual
  peso, con independencia de su frecuencia.
- **Recall de la clase «Severo»**: métrica operativa principal. Un falso negativo equivale a no
  activar el protocolo de vigilancia en un arrecife que está sufriendo un evento masivo.
- **PR-AUC de la clase «Severo»** (`average_precision_score`): área bajo la curva de
  precisión-exhaustividad. Saito y Rehmsmeier (2015) muestran que, ante desbalanceo, esta curva es
  más informativa que la ROC. La línea base es la prevalencia, 0,124. El ROC-AUC se retiene como
  métrica complementaria y **no abre** la comunicación de resultados.
- **Índice de Brier y ECE de P(Severo)**: calibración de la probabilidad, no solo discriminación.
  Un 0,70 predicho debe ocurrir cerca del 70 % de las veces si la salida se usa como alerta.

## 5.7. Análisis de interpretabilidad

La interpretabilidad se abordó mediante valores SHAP (*SHapley Additive exPlanations*), marco
propuesto por Lundberg y Lee (2017) y fundamentado en la teoría de juegos cooperativos, que
atribuye a cada variable su contribución marginal a la predicción. Su justificación teórica reside
en que los valores de Shapley constituyen la única asignación dentro de la clase de métodos de
atribución aditiva que satisface simultáneamente las propiedades de precisión local, ausencia y
consistencia, según se detalla en el apartado 4.3.

Se empleó el algoritmo `TreeExplainer`, implementación de la variante TreeSHAP que proporciona una
solución exacta para modelos basados en árboles con complejidad polinómica en lugar de la
exponencial que exigiría el cálculo directo sobre todas las coaliciones de variables.

El análisis se aplicó al **Random Forest oficial** (`n_estimators` = 200, `max_depth` = 8,
`class_weight='balanced'`), con `TSA_DHW` en el conjunto de predictores. El conjunto de
explicación es el pliegue de prueba de un `StratifiedGroupKFold` por `Site_ID` (6 903
observaciones; 2 238 emplazamientos; solapamiento nulo de sitios entre ajuste y explicación).
La profundidad máxima de 8 hace el cálculo exacto tratable: no hay que sustituir el competidor
por XGBoost ni submuestrear. El mismo cálculo se repitió bajo partición aleatoria para comprobar
que la jerarquía de atribución no es un artefacto del esquema inflado.

Debe tenerse presente que los predictores numéricos llegan al modelo estandarizados, por lo que
los valores representados en los diagramas SHAP corresponden a desviaciones respecto a la media
del conjunto de entrenamiento y no a magnitudes absolutas en grados Celsius o metros.

Se advierte finalmente de una salvedad interpretativa relevante dada la naturaleza de los datos.
La propiedad de precisión local garantiza que las atribuciones sumen exactamente la salida del
modelo, pero cuando dos predictores están correlacionados el reparto de la contribución conjunta
entre ambos no queda unívocamente determinado: depende de la estructura concreta de los árboles
ajustados. `SSTA`, `TSA` y `TSA_DHW` derivan del mismo campo térmico (Liu et al., 2014); las
direcciones individuales deben leerse como bloque, cuestión que se retoma en el apartado 6.6.3.

## 5.8. Entorno de desarrollo y reproducibilidad

El análisis se implementó íntegramente en Python 3.13.7 sobre un entorno virtual aislado. El
armazón del flujo de trabajo lo proporciona scikit-learn (Pedregosa et al., 2011), del que se
emplean las abstracciones de `ColumnTransformer` y `Pipeline` para encapsular el preprocesado, los
generadores de particiones `StratifiedKFold` y `StratifiedGroupKFold` para los dos esquemas de
validación contrastados, y la implementación de la regresión logística multinomial y de Random
Forest. Las versiones de las bibliotecas empleadas son las siguientes:

| Biblioteca | Versión | Función |
|---|---|---|
| pandas | 3.0.5 | Manipulación de datos tabulares |
| NumPy | 2.5.2 | Cálculo numérico |
| scikit-learn | 1.9.0 | Preprocesado, modelado y validación |
| SHAP | 0.52.0 | Interpretabilidad del modelo |
| Matplotlib | 3.11.1 | Generación de figuras |
| seaborn | 0.13.2 | Visualización estadística |
| PyArrow | 25.0.1 | Serialización en formato Parquet |
| XGBoost | 3.4.1 | Solo comparativa aleatoria histórica (apartado 6.3.1); no es competidor oficial |
| LightGBM | 4.7.0 | Solo comparativa aleatoria histórica (apartado 6.3.1); no es competidor oficial |

La reproducibilidad se garantiza mediante la fijación de la semilla aleatoria (`random_state` = 42)
en todos los procesos estocásticos —partición de datos, inicialización de los modelos de conjunto
y validación cruzada—, así como mediante la persistencia de los conjuntos procesados en formato
Parquet. Las figuras se exportan a 300 puntos por pulgada, resolución adecuada para su
reproducción impresa. Los experimentos de *leave-one-program-out*, calibración y área de
aplicabilidad se documentan en los apartados 5.4.6, 5.4.7 y 6.7. El holdout Reef Check 2021–2026
se documenta en los apartados 5.4.9 y 6.7.10.
