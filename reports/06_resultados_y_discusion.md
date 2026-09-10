# 6. Resultados y Discusión

## 6.1. Análisis exploratorio de datos

### 6.1.1. Calidad del registro y depuración

La depuración inicial descartó las observaciones sin valor en la variable de respuesta, reduciendo
el conjunto de 41 361 a **34 515 observaciones** (16,55 % de registros eliminados). El examen de la
completitud reveló un patrón claramente estructurado: los campos de texto libre presentan entre un
92,85 % y un 94,54 % de valores ausentes, `Bleaching_Level` alcanza el 45,53 % y `Percent_Cover` el
30,11 %. Por el contrario, las variables térmicas derivadas de teledetección (`SSTA`, `TSA`,
`ClimSST` y los estadísticos asociados) muestran proporciones de ausencia inferiores al 0,45 %.

Este contraste resulta coherente con la naturaleza de las fuentes descrita en el apartado 2.6: los
descriptores obtenidos por satélite ofrecen la cobertura sistemática que Liu et al. (2014)
identifican como principal ventaja de los productos de 5 km —capaces de monitorizar directamente el
95 % de los arrecifes—, mientras que las variables que requieren observación directa *in situ*
dependen del protocolo de cada campaña. Dicha asimetría condicionó la selección de predictores
expuesta en el apartado 5.3.2.

### 6.1.2. Distribución de la variable objetivo

La distribución de `Percent_Bleaching` presenta una marcada asimetría positiva, evidenciada por la
divergencia entre sus medidas de tendencia central:

| Estadístico | Valor (%) |
|---|---|
| Media | 9,619 |
| Mediana | 0,250 |
| Desviación típica | 20,191 |
| Percentil 75 | 6,000 |
| Percentil 90 | 33,300 |
| Percentil 95 | 69,127 |
| Percentil 99 | 87,500 |
| Máximo | 100,000 |

*Figura 6.1: `reports/figures/distribucion_percent_bleaching.png`*

La mediana de 0,250 % frente a una media de 9,619 % indica que la mayoría de los muestreos
corresponden a arrecifes sin afectación apreciable, mientras que una minoría de registros alcanza
valores extremos próximos al 100 %. Este perfil es ecológicamente esperable y refleja la dinámica
característica del blanqueamiento coralino descrita por Hoegh-Guldberg (1999): un régimen basal de
estabilidad interrumpido por episodios agudos de estrés térmico asociados a olas de calor marinas.
El percentil 90 se sitúa en 33,300 %, de modo que aproximadamente uno de cada diez muestreos
documenta un evento masivo.

### 6.1.3. Relaciones entre variables térmicas y blanqueamiento

El análisis de correlación de Pearson entre los predictores numéricos oficiales y la variable de
respuesta muestra un gradiente, no un empate en la debilidad:

| Variable | r con `Percent_Bleaching` | Intensidad |
|---|---|---|
| `TSA_DHW` | 0,228 | Débil positiva (la más alta) |
| `Depth_m` | 0,165 | Débil positiva |
| `TSA` | 0,134 | Débil positiva |
| `SSTA` | 0,092 | Muy débil positiva |
| `Distance_to_Shore` | 0,006 | Prácticamente nula |
| `ClimSST` | −0,055 | Muy débil negativa |

*Figura 6.2: `reports/figures/matriz_correlacion.png`*

Los coeficientes de la tabla y de la Figura 6.2 son listwise sobre los seis predictores numéricos
oficiales. En correlación bivariante (solo pares completos) `TSA_DHW`–`Percent_Bleaching`
alcanza r = 0,272, la cifra que reporta la ablación del apartado 5.4.4. En ambos cálculos el
estrés acumulado duplica a `TSA` (0,134) y es el único índice térmico que supera a la
profundidad. Esa es la justificación empírica de meter `TSA_DHW` en el modelo principal, no
un apéndice.

La asociación de la profundidad no es un efecto ecológico misterioso. La correlación bruta
`Depth_m`–`Percent_Bleaching` es $r = 0{,}166$ en bivariante y $0{,}165$ en la matriz; dentro de
Reef_Check cae a $0{,}011$; residualizando ambas variables respecto a `Data_Source`, $r = 0{,}039`.
Reef_Check muestrea de rutina, en aguas someras (media 6,5 m) y con un 2,11 % de episodios
severos. Donner muestrea eventos, un poco más profundo (9,8 m) y con un 35 % de blanqueamiento
medio. La asociación agregada recoge la diferencia **entre protocolos** —una manifestación de la
paradoja de Simpson— y no un efecto de la profundidad dentro de ellos. En consecuencia, la
contribución SHAP de `Depth_m` documentada en el apartado 6.6 no admite lectura ecológica
directa: la variable opera en gran medida como indicador del programa de procedencia.

Merece destacarse la correlación de **0,543 entre `SSTA` y `TSA`**, previsible a partir de la
identidad algebraica establecida en el apartado 4.1.3: ambos descriptores se derivan del mismo campo
de temperatura superficial mediante los algoritmos de Liu et al. (2014) y difieren únicamente en el
término $ClimSST_{s,d} - MMM_s$, dependiente de la época del año. `TSA_DHW` correlaciona 0,312
con `SSTA` y 0,314 con `TSA`: comparte familia, no es un duplicado de la anomalía puntual. Esta
colinealidad resultará determinante en la interpretación del análisis de interpretabilidad
(apartado 6.6).

El diagrama de dispersión con ajuste lineal entre `SSTA` y `Percent_Bleaching` (Figura 6.3)
confirma una pendiente positiva, coherente con el mecanismo de estrés térmico, si bien de escasa
magnitud. La nube de puntos presenta heterocedasticidad manifiesta y bandas horizontales en los
valores 0 %, 30 %, 75 % y 100 %, atribuibles a protocolos de campo que registran la afectación
mediante umbrales discretos en lugar de mediciones continuas.

*Figura 6.3: `reports/figures/ssta_vs_bleaching.png`*

Las anomalías puntuales (`SSTA`, `TSA`) son linealmente débiles; el estrés acumulado no lo es
en la misma medida. Esa asimetría admite dos lecturas complementarias. Por una parte, el
blanqueamiento responde a la integral del calor, no al instante (apartado 4.1.4). Por otra,
incluso r = 0,228 deja la mayor parte de la varianza fuera de cualquier recta, de modo que
siguen haciendo falta umbrales e interacciones —y, con ellos, algoritmos no lineales— sin
confundir «no lineal» con «ningún predictor lineal útil».

Conviene retener este resultado frente a las métricas de clasificación del apartado 6.3: el
predictor lineal más asociado a la respuesta es `TSA_DHW` ($r = 0{,}228$ listwise; $0{,}272$
bivariante), no `Depth_m`.

### 6.1.4. Autocorrelación espacial de la respuesta y de los predictores

El índice de Moran del apartado 4.5.1, calculado sobre los centroides de 11 068 emplazamientos con
$k = 8$ vecinos más próximos y 999 permutaciones, confirma que la dependencia espacial no es una
hipótesis de trabajo sino una propiedad medida:

| Variable | n emplazamientos | I de Moran | p |
|---|---|---|---|
| Blanqueamiento observado (%) | 11 068 | 0,371 | 0,001 |
| Anomalía de estrés térmico (`TSA`) | 11 047 | 0,330 | 0,001 |
| Anomalía de temperatura (`SSTA`) | 11 047 | 0,279 | 0,001 |
| Estrés térmico acumulado (`TSA_DHW`) | 11 047 | 0,528 | 0,001 |
| Climatología (`ClimSST`) | 11 058 | 0,543 | 0,001 |
| Profundidad (`Depth_m`) | 9 586 | 0,456 | 0,001 |

*Fuente: elaboración propia.*

*Figura 6.4: `reports/figures/moran_autocorrelacion.png`*

El resultado de mayor relevancia metodológica es la **ordenación**. `TSA_DHW` ($I = 0{,}528$) y
`ClimSST` ($I = 0{,}543$) están más agrupados que el propio blanqueamiento ($I = 0{,}371$). Los
índices térmicos portan estructura espacial suficiente para que un algoritmo con capacidad de
memorización identifique la región de procedencia. No existe, en consecuencia, un subconjunto de
predictores espacialmente neutro: esa es la razón por la que la ablación de profundidad, distancia
y climatología no mata la brecha entre validación aleatoria y agrupada.

## 6.2. Preparación de los datos y partición

La discretización de la variable de respuesta en tres niveles de severidad produjo una distribución
marcadamente desbalanceada, que la estratificación preservó con notable fidelidad en ambas
particiones:

| Clase | Conjunto completo | Entrenamiento | Prueba |
|---|---|---|---|
| Bajo | 78,93 % | 78,93 % | 78,94 % |
| Moderado | 8,64 % | 8,64 % | 8,63 % |
| Severo | 12,42 % | 12,42 % | 12,43 % |
| **Total** | **34 515** | **27 612** | **6 903** |

La concordancia entre las tres columnas confirma la correcta aplicación del muestreo estratificado.
El desbalanceo resultante —con la clase mayoritaria concentrando cerca del 79 % de los registros—
determinó la adopción del F1-Score macro como criterio principal de evaluación, conforme al
argumento desarrollado en el apartado 4.4.2.

## 6.3. Comparativa de modelos y la regla de Coral Reef Watch

### 6.3.1. Lo que la validación aleatoria haría creer

Los cuatro algoritmos de una comparativa **histórica** —partición aleatoria estratificada, Random
Forest sin tope de profundidad y **sin** `TSA_DHW`— arrojaron los resultados siguientes. No es el
sistema recomendado: las matrices de confusión de aquel ejercicio no se reproducen en el cuerpo,
porque describirían otro modelo. LightGBM entra solo en esta tabla, con hiperparámetros por
defecto, y no se reentrena bajo validación agrupada.

| Modelo | Accuracy | Precision (Macro) | Recall (Macro) | F1-Score (Macro) | ROC-AUC (OvR ponderado) |
|---|---|---|---|---|---|
| **Random Forest (sin tope, sin DHW)** | **0,8763** | **0,7364** | **0,7588** | **0,7464** | **0,9430** |
| XGBoost (GridSearchCV) | 0,7944 | 0,6224 | 0,7370 | 0,6585 | 0,9001 |
| LightGBM | 0,8250 | 0,6962 | 0,4919 | 0,5364 | 0,8810 |
| Regresión Logística | 0,5456 | 0,4126 | 0,4682 | 0,3893 | 0,6992 |

Random Forest obtuvo el mejor rendimiento en todas las métricas de esta tabla, con un F1-Score
macro de 0,7464. El ROC-AUC de 0,9430 **no se comunica como resultado principal**: Saito y
Rehmsmeier (2015) muestran que, con una prevalencia de 0,124, esa curva transmite una impresión
excesivamente optimista. El desglose por clases confirma la cautela:

| Modelo | Recall «Severo» | Recall «Moderado» | Recall «Bajo» |
|---|---|---|---|
| Random Forest | 0,68 | 0,67 | 0,93 |
| XGBoost | 0,69 | 0,70 | 0,82 |
| LightGBM | 0,34 | 0,16 | 0,97 |
| Regresión Logística | 0,24 | 0,57 | 0,59 |

LightGBM alcanza una exactitud del 82,50 % recuperando únicamente el 34 % de los eventos severos.
Un lector que detuviera aquí la lectura concluiría que el bosque libre constituye el modelo de
elección. Los apartados siguientes muestran que esa conclusión no sobrevive ni a un emplazamiento
nuevo, ni a una cuenca nueva, ni a una temporada futura, ni a la inclusión de `TSA_DHW`.

### 6.3.2. El competidor honesto: Coral Reef Watch

Todo modelo de alerta debe justificarse frente al procedimiento que las agencias ya emplean.
Interpretada como clasificador binario de la clase «Severo», la regla de Coral Reef Watch no
requiere entrenamiento:

| Regla | Alertas emitidas | Sobre el total | Recall | Precisión | F1 de la clase severa |
|---|---|---|---|---|---|
| DHW ≥ 4 °C·semana | 3 401 | 9,85 % | 0,3379 | 0,4261 | 0,3769 |
| DHW ≥ 8 °C·semana | 945 | 2,74 % | 0,1031 | 0,4677 | 0,1689 |

*Fuente: elaboración propia.*

*Figura 6.5: `reports/figures/baseline_crw.png`*

El umbral de 4 °C·semana recupera el **33,8 %** de los episodios severos con una precisión de 0,43,
emitiendo alerta sobre el 9,9 % de las observaciones. Esa es la línea de base operativa. Cualquier
clasificador que no la supere de forma clara, en el escenario de aplicación pertinente, no justifica
su despliegue como sistema de alerta.

## 6.4. Transferibilidad espacial: de Reef_Check al conjunto completo

### 6.4.1. El 2,11 % de severos no es un detalle: `Reef_ID` es Reef_Check

La validación agrupada de la versión anterior de este trabajo se restringía a la submuestra con
`Reef_ID` informado: 22 531 observaciones, 2,11 % de episodios severos frente al 12,42 % del
conjunto completo. Esa asimetría no es un artefacto de muestreo. `Reef_ID` está informado **solo**
en Reef_Check. Donner (51,9 % de severos), McClanahan (77,4 %), FRRP, Kumagai y el resto de
programas —precisamente los que concentran los eventos masivos— quedan íntegramente fuera.

| Programa (`Data_Source`) | n | Severo (%) | Blanqueamiento medio (%) | `Reef_ID` informado (%) |
|---|---|---|---|---|
| Reef_Check | 22 531 | 2,11 | 2,53 | 100,0 |
| Donner | 5 770 | 51,89 | 35,05 | 0,0 |
| AGRRA | 2 848 | 0,74 | 3,31 | 0,0 |
| FRRP | 2 394 | 14,41 | 15,31 | 0,0 |
| Kumagai | 660 | 38,03 | 17,46 | 0,0 |
| McClanahan | 226 | 77,43 | 57,33 | 0,0 |

*Fuente: elaboración propia.*

*Figura 6.6: `reports/figures/procedencia_prevalencia.png`*

La CV por `Reef_ID` mide transferencia **dentro de un programa de monitoreo rutinario**. No estima
transferencia global. La corrección es agrupar por `Site_ID` (11 068 sitios, cobertura 100 %) sobre
las 34 515 observaciones. El apartado 6.7.5 pregunta qué ocurre cuando el programa de prueba es
otro: McClanahan, Donner o el bloque de documentación de eventos.

### 6.4.2. Validación agrupada por `Site_ID` sobre el conjunto completo

`StratifiedGroupKFold` por emplazamiento, cinco pliegues, prevalencia de «Severo» 12,42 %. PR-AUC
con línea base 0,124.

| Modelo | F1 aleatoria | F1 por sitio | Δ relativa | Recall «Severo» | PR-AUC «Severo» |
|---|---|---|---|---|---|
| Logística (base) | 0,393 | 0,392 | −0,4 % | 0,266 | 0,222 |
| Logística + DHW | 0,451 | 0,449 | −0,5 % | 0,386 | 0,345 |
| Logística térmica + DHW | 0,456 | 0,454 | −0,4 % | 0,445 | 0,323 |
| RF `max_depth`=8 + DHW | 0,557 | 0,532 | −4,4 % | 0,559 | 0,514 |
| RF `max_depth`=16 + DHW | 0,724 | 0,603 | −16,7 % | 0,645 | 0,632 |
| RF sin tope + DHW | 0,759 | 0,612 | −19,5 % | 0,644 | 0,656 |

*Fuente: elaboración propia.*

*Figura 6.7: `reports/figures/esquemas_validacion.png`*

Tres lecturas se imponen.

**El estrés acumulado es señal transferible, no un adorno.** En CV por sitio, el recall de
«Severo» de la logística sube de 0,266 a 0,386 al incorporar `TSA_DHW`, y a **0,445** si además se
retiran profundidad, distancia y cuenca. Esa mejora se obtiene añadiendo el índice fisiológico y
quitando descriptores del emplazamiento.

**El RF libre ya no cae un 52 %: cae un 19,5 %.** La caída de F1 con la misma semilla y el mismo
DHW es −4,4 % con profundidad 8, −16,7 % con 16 y −19,5 % sin tope. Una parte grande del «colapso»
documentado al agrupar por `Reef_ID` era hiperparámetro —un bosque de profundidad ilimitada sobre
un programa de monitoreo rutinario—, no destino de los árboles.

**PR-AUC, no ROC-AUC.** Con prevalencia 0,124, la logística + DHW alcanza 0,345 y el RF de
profundidad 8 alcanza 0,514 bajo agrupación por sitio. Ambas cifras superan la línea base; ninguna
se parece al 0,943 de la partición aleatoria.

La logística térmica + DHW (recall 0,445) supera a la regla CRW de 4 °C·semana (0,338) en
detección de episodios severos sobre sitios no observados. Ese es el valor añadido espacial
medible. El apartado 6.7 pregunta si sobrevive a una cuenca nueva y a una temporada futura.

### 6.4.3. Por qué colapsa el bosque libre y por qué resiste la logística

La divergencia no es un accidente empírico. Random Forest sin tope de profundidad particiona el
espacio hasta hojas de pureza máxima (apartado 4.2.2). Acotar `max_depth` a 8 impide construir
esas hojas específicas de emplazamiento y reduce la degradación a un 4,4 %. El bosque libre se
queda, por tanto, como lo que es: una ablación de capacidad.

La regresión logística está estructuralmente impedida de memorizar. Su frontera es lineal en el
espacio de las log-probabilidades relativas. Carente de esa vía, se ve **obligada** a apoyarse en
la señal térmica, por débil que sea. De ahí que su F1 apenas se mueva al cambiar de esquema
(−0,4 %) y que su recall de «Severo» mejore al retirar el contexto del sitio.

El fenómeno sigue siendo la manifestación, en aprendizaje automático, de la pseudorreplicación de
Hurlbert (1984) y de la infraestimación del error que Roberts et al. (2017) y Ploton et al. (2020)
documentan bajo validación aleatoria. La diferencia respecto de Ploton et al. se mantiene: aquí
**sí existe señal ambiental transferible**. Su magnitud, una vez medido el I de Moran y sustituido
`Reef_ID` por `Site_ID`, es más modesta y más honesta que el −52 % de la submuestra Reef_Check.

## 6.5. Lectura crítica: capacidad, autocorrelación y protocolo

La CV por `Reef_ID` que abría este trabajo —F1 de Random Forest de 0,8981 a 0,4297, −52,2 %—
sigue siendo un resultado real. Lo que cambia es su interpretación. Ese experimento se ejecuta
sobre Reef_Check, con un 2,11 % de episodios severos, y con un bosque de profundidad ilimitada.
Sustituir la agrupación por `Site_ID` sobre el conjunto completo y acotar `max_depth` a 8 reduce
la caída a un 4,4 %. El −52 % medía, a la vez, un protocolo, un hiperparámetro y una
autocorrelación térmica que el I de Moran ahora cuantifica ($I = 0{,}528$ en `TSA_DHW` frente a
$I = 0{,}371$ en la respuesta).

La formulación de Legendre (1993) encaja sin forzarla. Hay dependencia espacial *inducida* por
variables de contexto —el tercio de brecha que la ablación suprime en Reef_Check— y autocorrelación
*en los propios campos térmicos*, que es la que sobrevive cuando solo quedan `SSTA`, `TSA` y
`TSA_DHW`. No hay subconjunto espacialmente neutro.

La logística sigue siendo el control metodológico: su F1 no se mueve al agrupar por sitio
(−0,4 %). El bosque acotado es el competidor; el bosque libre, la ablación de capacidad. El
paralelismo con Ploton et al. (2020) se mantiene en el diagnóstico —la validación aleatoria
infraestima el error— y se matiza en la magnitud: aquí queda señal transferible, y su tamaño
honesto es el recall 0,445 de la logística térmica + DHW, no el ROC-AUC 0,943.

## 6.6. Interpretabilidad mediante valores SHAP

### 6.6.1. Importancia global de los predictores

El análisis SHAP (Lundberg y Lee, 2017) se aplica al clasificador que el resto del capítulo
recomienda: Random Forest con `n_estimators` = 200, `max_depth` = 8 y `class_weight='balanced'`,
predictores `SSTA`, `TSA`, `TSA_DHW`, `Depth_m`, `Distance_to_Shore`, `ClimSST` y `Ocean_Name`.
El conjunto de explicación es el pliegue de prueba de un `StratifiedGroupKFold` por `Site_ID`:
6 903 observaciones, 2 238 emplazamientos, **cero** sitios compartidos con el entrenamiento.
TreeSHAP exacto; la profundidad 8 hace innecesario sustituir el bosque por XGBoost.

| Variable | Bajo | Moderado | Severo | Media global |
|---|---|---|---|---|
| `TSA_DHW` | 0,0894 | 0,0197 | 0,0997 | **0,0696** |
| `Ocean_Name_Atlantic` | 0,0849 | 0,0666 | 0,0213 | 0,0576 |
| `Distance_to_Shore` | 0,0420 | 0,0294 | 0,0258 | 0,0324 |
| `Ocean_Name_Pacific` | 0,0421 | 0,0262 | 0,0185 | 0,0289 |
| `Depth_m` | 0,0328 | 0,0146 | 0,0339 | 0,0271 |
| `ClimSST` | 0,0293 | 0,0149 | 0,0262 | 0,0235 |
| `TSA` | 0,0308 | 0,0186 | 0,0163 | 0,0219 |
| `SSTA` | 0,0110 | 0,0073 | 0,0085 | 0,0089 |

*Figura 6.8: `reports/figures/shap_importance_global.png`*

`TSA_DHW` se erige como el predictor de mayor peso global y, de forma más marcada, de la clase
«Severo» (0,0997). El resultado es el que la fisiología y el protocolo operativo hacían esperar:
es el índice de estrés acumulado que Coral Reef Watch emplea como umbral de alerta (Liu et al.,
2014; apartado 4.1.4). `TSA` y `SSTA` conservan signo térmico, pero una fracción sustancial de
la señal puntual queda absorbida por el acumulado. `Ocean_Name_Atlantic` sigue siendo el segundo
predictor global, con peso concentrado en «Bajo» y «Moderado»; sobre «Severo» su contribución es
casi cuatro veces menor.

### 6.6.2. Dirección de los efectos

| Variable | Efecto medio \|SHAP\| | Correlación valor–SHAP | Dirección |
|---|---|---|---|
| `TSA_DHW` | 0,0997 | **0,6671** | Incrementa la probabilidad de clase severa |
| `Depth_m` | 0,0339 | 0,2275 | Incrementa la probabilidad de clase severa |
| `ClimSST` | 0,0262 | −0,4124 | Reduce la probabilidad de clase severa |
| `Distance_to_Shore` | 0,0258 | 0,1427 | No monótona |
| `TSA` | 0,0163 | 0,7934 | Incrementa la probabilidad de clase severa |
| `SSTA` | 0,0085 | 0,7882 | Incrementa la probabilidad de clase severa |

*Figura 6.9: `reports/figures/shap_summary.png`*

`TSA_DHW` presenta una relación positiva consistente (correlación de 0,6671 entre el valor
estandarizado y su contribución SHAP): más semanas de calor por encima del umbral desplazan la
predicción hacia el blanqueamiento severo. `TSA` y `SSTA` apuntan en la misma dirección, con
correlaciones aún más altas (0,7934 y 0,7882) y una magnitud media mucho menor. El bloque
térmico, leído en conjunto, reproduce la cadena de Hoegh-Guldberg (1999) —superación del umbral,
fotoinhibición del fotosistema II, especies reactivas de oxígeno, expulsión de los simbiontes—
sin la inversión de signo que el análisis anterior atribuía a `SSTA` cuando el modelo explicado
era un XGBoost sin DHW.

### 6.6.3. Colinealidad del bloque térmico: SSTA, TSA y DHW

`SSTA`, `TSA` y `TSA_DHW` son transformaciones del mismo campo de temperatura superficial
(Liu et al., 2014). La colinealidad `SSTA`–`TSA` ($r = 0{,}543$, apartado 4.1.3) se extiende al
acumulado, que integra `TSA` a lo largo de doce semanas. Como se advirtió en el apartado 4.3.3,
el reparto SHAP entre predictores correlacionados **no es identificable de forma unívoca**: los
valores de Shapley satisfacen la precisión local sobre la suma, pero distribuyen la contribución
conjunta conforme a los árboles ajustados.

En este bosque, `TSA_DHW` absorbe la mayor parte de esa contribución conjunta: su efecto medio
sobre «Severo» es seis veces el de `TSA` y once veces el de `SSTA`. Las tres correlaciones
valor–SHAP son positivas. No hay, por tanto, un coeficiente que pueda citarse como evidencia de
que el calentamiento reduzca el blanqueamiento. El artefacto de signo que Aas et al. (2021)
asocian a la integración marginal de variables colineales **sí aparecía** cuando se explicaba un
XGBoost sin DHW sobre la partición aleatoria; al explicar el competidor oficial, el bloque
térmico queda alineado con la física del sistema. El reparto interno entre las tres variables
sigue sin ser único; el signo del bloque, no.

### 6.6.4. El efecto protector de ClimSST

`ClimSST` presenta dirección negativa (correlación de −0,4124): los arrecifes situados en aguas
con un régimen térmico basal más cálido reciben menor probabilidad predicha de blanqueamiento
severo. A diferencia del reparto interno del bloque térmico, esta relación admite una
interpretación biológica respaldada por la literatura.

Las comunidades coralinas adaptadas a regímenes históricamente cálidos presentan **umbrales de
blanqueamiento más elevados**, resultado tanto de la selección de genotipos termotolerantes de
zooxantelas como de procesos de aclimatación fisiológica del hospedador. Una misma anomalía
térmica genera, por tanto, un estrés efectivo menor en dichas comunidades.

La convergencia con Sully et al. (2019) se mantiene **en el signo**: aquellos autores, sobre
Reef Check 1998–2017 (no sobre las 34 515 filas de este extracto) y con un modelo jerárquico
bayesiano, documentaron menor frecuencia de blanqueamiento en localidades de elevada varianza
térmica y un desplazamiento al alza del umbral de unos 0,5 °C entre 1998–2006 y 2007–2017
(Weibull de su Figura 4: 28,1 °C a 28,7 °C). El signo negativo de `ClimSST` es la expresión,
en este Random Forest, de un fenómeno de tolerancia compatible con el suyo; el apartado 6.7.7
muestra que la media aritmética de este CSV no recupera esas dos cifras.

Este mecanismo justifica que los índices operativos de alerta se definan como desviaciones
respecto a la climatología local y no en temperatura absoluta (Liu et al., 2014). Sigue siendo
una hipótesis compatible con el modelo, no una relación causal. Una explicación alternativa —no
excluyente— es que `ClimSST` opere en parte como sustituto de la identidad geográfica.

### 6.6.5. Estrés térmico frente a identidad del emplazamiento

La agrupación de los predictores según su naturaleza ecológica, ahora **con** `TSA_DHW` y sobre
el holdout por `Site_ID`, invierte el diagnóstico que se obtenía al explicar un XGBoost sin DHW:

| Grupo de variables | Contribución SHAP acumulada | Peso relativo |
|---|---|---|
| Estrés térmico (`SSTA`, `TSA`, `TSA_DHW`) | 0,1004 | 35,8 % |
| Contexto del emplazamiento (`Depth_m`, `Distance_to_Shore`, `ClimSST`) | 0,0830 | 29,5 % |
| Cuenca (`Ocean_Name`) | 0,0975 | 34,7 % |

El bloque térmico supera al contexto estático (35,8 % frente a 29,5 %; razón contexto/térmicas
de 0,83). Las dummies de cuenca acumulan otro tercio. El modelo recomendado se apoya, por tanto,
tanto en el estrés acumulado como en la identidad biogeográfica; ya no es cierto que el contexto
del sitio pese 1,64 veces más que las térmicas. Esa proporción era un artefacto de explicar otro
clasificador.

**Precisión necesaria sobre la lectura de estas cifras.** Los porcentajes miden la magnitud
agregada de las atribuciones de **este** bosque bajo una agrupación concreta. No son la fracción
del blanqueamiento atribuible a cada factor. Un valor SHAP cuantifica cuánto se apoya un modelo
ya ajustado en una variable, no cuánta varianza del fenómeno biológico depende de ella.

`Depth_m` deja de ser la variable dominante de «Severo» (ahora 0,0339, lejos de `TSA_DHW`).
Su correlación valor–SHAP es positiva (0,2275), pero el apartado 6.1.3 sigue cerrando la
lectura ecológica: $r$ bruta 0,166, $r = 0{,}011$ dentro de Reef_Check, $r$ parcial 0,039
residualizando respecto a `Data_Source`. El bosque usa la profundidad, en buena medida, como
indicador de programa.

`Ocean_Name_Atlantic` conserva el patrón de cuenca: peso alto en «Bajo» (0,0849) y «Moderado»
(0,0666) y bajo en «Severo» (0,0213). En el periodo cubierto el Atlántico concentra menos
eventos masivos que el Pacífico y el Índico (apartado 6.7.1); la dummy opera como sustituto de
un régimen de prevalencia. El *leave-one-ocean-out* no es un conjunto externo: sigue siendo
Sully et al. (2019) con una cuenca retenida.

La objeción de circularidad —explicar el esquema inflado— queda acotada de dos modos. Primero,
el cálculo principal ya se hace sobre emplazamientos disjuntos. Segundo, el mismo bosque
explicado sobre un pliegue aleatorio deja una razón contexto/térmicas de 0,78 frente a 0,83 en
el holdout por `Site_ID` (Figura 6.10). `TSA_DHW` encabeza ambas jerarquías (variación −2,2 %).
La estructura no es un artefacto de la partición aleatoria.

*Figura 6.10: `reports/figures/shap_comparacion_esquemas.png`*

La lectura defendible es, por tanto, más estrecha que la de un XGBoost sin DHW: el competidor
oficial **sí** se apoya en el estrés acumulado, y al mismo tiempo reserva un tercio de la
atribución a la cuenca. Esa segunda parte es coherente con el 0 % de soporte atlántico del
apartado 6.7.6. Ninguna de las dos lecturas sustituye, por sí sola, un conjunto ajeno a
BCO-DMO; ese holdout se presenta en el apartado 6.7.10.


## 6.7. Bloqueo geográfico, temporada futura y la regla de Coral Reef Watch

El apartado 6.4 mide transferencia entre *sitios* del mismo contexto biogeográfico. Un gestor
que lea únicamente esa cifra puede interpretar que el modelo «funciona en arrecifes nuevos». La
salvedad es crucial: son sitios no observados, no cuencas no observadas, y no temporadas que aún
no han ocurrido.

### 6.7.1. Leave-one-ocean-out y validación por ecorregión

El bloqueo geográfico permanece **dentro** de la síntesis de Sully et al. (2019): se retiene una
cuenca o una ecorregión como prueba y se entrena con el resto del mismo corpus. No es un
conjunto independiente, ni una AMP que no figure en BCO-DMO. Sobre ese diseño, Random Forest con
`max_depth` = 8 alcanza, al dejar fuera una cuenca completa, un F1-macro de **0,456** y un recall
de «Severo» de **0,612**. Esa es la cifra de cuenca nueva *dentro de Sully*, no de validación
externa.

| Modelo | Bloqueo | F1 macro | Recall «Severo» | PR-AUC «Severo» |
|---|---|---|---|---|
| Logística térmica + DHW | Leave-one-ocean-out | 0,415 | 0,527 | 0,386 |
| Logística térmica + DHW | Ecorregión (5 pliegues) | 0,446 | 0,469 | 0,351 |
| RF profundidad 8 + DHW | Leave-one-ocean-out | 0,456 | 0,612 | 0,334 |
| RF profundidad 8 + DHW | Ecorregión (5 pliegues) | 0,428 | 0,507 | 0,358 |

*Fuente: elaboración propia. El detalle por cuenca se comenta en el texto.*

El detalle por cuenca del bosque acotado muestra heterogeneidad biogeográfica, no un rendimiento
uniforme: el Atlántico (13 319 observaciones, 18,0 % de severos) rinde un recall de 0,417; el
Índico, 0,662; el Pacífico, 0,573. El Mar Rojo, con un 0,57 % de severos, produce un F1 de 0,300
pese a un recall alto sobre una clase casi vacía. Esa dispersión es exactamente el síntoma que
Meyer y Pebesma (2021) formalizan como **área de aplicabilidad**: el error estimado no es una
cifra única, sino una función de la disimilitud del punto de predicción respecto del soporte de
entrenamiento. Un arrecife del Golfo Pérsico no es intercambiable con uno del Atlántico; comunicar
un único F1 de 0,456 a un gestor oculta esa heterogeneidad. El apartado 6.7.6 sustituye esa cifra
única por el índice de disimilitud de Meyer y Pebesma (2021).

### 6.7.2. Corte temporal: la temporada que aún no ha ocurrido

Se entrena con 1980–2012 (24 109 observaciones, 14,45 % de severos) y se evalúa sobre 2013–2020
(10 406 observaciones, 7,74 % de severos).

| Método | Entrenamiento | Recall | Precisión | F1 severa | Alertas |
|---|---|---|---|---|---|
| Regla CRW: DHW ≥ 4 | No requiere | 0,3975 | 0,4494 | 0,4219 | 6,8 % |
| Regresión logística (térmicas + DHW) | 1980–2012 | 0,5043 | 0,3540 | 0,4160 | 11,0 % |
| Regresión logística (base + DHW) | 1980–2012 | 0,3988 | 0,3078 | 0,3474 | 10,0 % |
| Random Forest `max_depth`=8 (base + DHW) | 1980–2012 | 0,2435 | 0,2988 | 0,2683 | 6,3 % |

*Fuente: elaboración propia.*

Medido sobre el **F1 de la clase severa**, la regla de 4 °C·semana (0,422) y la logística térmica
+ DHW (0,416) son indistinguibles. El bosque, no: recall 0,243. Para «alerta temprana» el
competidor honesto no es Random Forest, es esa regla.

La equivalencia en F1 encubre un intercambio. La logística recupera más episodios (0,504 frente a
0,398) a costa de menos precisión (0,354 frente a 0,449) y del doble de alertas. Si el gestor
prioriza no omitir eventos, el modelo aporta valor; si prioriza no movilizar recursos en falso,
la regla resulta preferible. La estadística no dirime esa elección.

Hughes et al. (2018) documentan que la frecuencia de blanqueamiento masivo se ha incrementado en
el intervalo cubierto por el conjunto; Sully et al. (2019) hallan un desplazamiento al alza del
umbral. El corte temporal no demuestra que el umbral se haya movido —la prevalencia de prueba
cae al 7,74 %, no sube—, pero sí que **el año que aún no ha ocurrido no premia al modelo de
conjunto**. NOAA no pierde frente a estos clasificadores.

### 6.7.3. Sensibilidad a los umbrales de discretización

El contraste con tres alternativas sobre la submuestra Reef_Check —el experimento más adverso—
reproduce el signo del fenómeno: el bosque libre se degrada en torno al 50 % y la logística no.
La magnitud absoluta de las métricas cambia con la prevalencia; el diagnóstico, no. La elección
de 10 % y 30 % no es un supuesto del que dependan las conclusiones.

### 6.7.4. Calibración de P(Severo)

Discriminar no basta. Un gestor que lea «probabilidad 0,70 de episodio severo» necesita saber si
ese 0,70 ocurre cerca del 70 % de las veces. El índice de Brier y el diagrama de fiabilidad se
calcularon sobre P(Severo) en dos escenarios: probabilidades fuera de pliegue de la CV por
`Site_ID` y el corte temporal 2013–2020. La regla CRW entra como clasificador duro (0 o 1).

| Modelo | Brier (sitio) | ECE (sitio) | Brier (2013–2020) | ECE (2013–2020) | Recall argmax (2013–2020) |
|---|---|---|---|---|---|
| Logística térmica + DHW | 0,132 | 0,182 | 0,115 | 0,231 | 0,504 |
| RF profundidad 8 + DHW | 0,099 | 0,130 | 0,084 | 0,126 | 0,243 |
| RF profundidad 8 + isotónica | — | — | 0,068 | 0,024 | 0,037 |
| Regla CRW DHW ≥ 4 | 0,139 | 0,139 | 0,084 | 0,051 | 0,398 |

*Fuente: elaboración propia. La isotónica se ajusta solo sobre el entrenamiento.*

*Figura 6.11: `reports/figures/calibracion_severo.png`*

Tres lecturas. Primera: en CV por sitio el bosque está **mejor calibrado** que la logística (Brier
0,099 frente a 0,132) y que la regla (0,139). La logística, con P media 0,307 frente a una
prevalencia de 0,124, sobrepredice «Severo». Segunda: en el corte temporal el Brier del bosque
(0,084) y el de la regla (0,084) empatan; el ECE de NOAA (0,051) es el más bajo de los
clasificadores no recalibrados. Tercera: la isotónica mejora Brier (0,068) y ECE (0,024) y hunde
el recall a 0,037. Tras calibrar, las probabilidades se contraen hacia la prevalencia de prueba
(7,74 %) y el umbral 0,5 deja de disparar. **Calibrar sin reelegir el umbral operativo no es un
sistema de alerta.** Por eso 7.2.3 sigue siendo una función de coste del gestor, no un 0,5
mágico. La isotónica no sustituye las cifras de F1 del apartado 6.7.2.

### 6.7.5. Leave-one-program-out: el protocolo, no el océano

El experimento retiene un programa (n ≥ 200) como prueba y entrena con el resto. Sigue siendo
Sully et al. (2019). Lo que cambia es el **proceso de etiquetado**.

| Programa | n | Severo (%) | P media (RF-8) | Recall (RF-8) | Brier (RF-8) |
|---|---|---|---|---|---|
| Reef_Check | 22 531 | 2,1 | 0,442 | 0,459 | 0,217 |
| AGRRA | 2 848 | 0,7 | 0,295 | 0,000 | 0,099 |
| FRRP | 2 394 | 14,4 | 0,396 | 0,429 | 0,177 |
| Kumagai | 660 | 38,0 | 0,209 | 0,127 | 0,225 |
| Donner | 5 770 | 51,9 | 0,311 | 0,280 | 0,297 |
| McClanahan | 226 | 77,4 | 0,402 | 0,411 | 0,319 |

*Figura 6.12: `reports/figures/leave_one_program.png`*

McClanahan no es un océano nuevo: es un programa que documenta eventos (77,4 % de severos). El
bosque predice de media 0,402. Donner: 51,9 % observado, 0,311 predicho. A la inversa, sobre
Reef_Check (2,1 % de severos) el mismo bosque predice 0,442. El modelo no «falla en McClanahan»
como si fuera un arrecife atípico; **arrasa la prevalencia del protocolo con la del otro**.

El contraste rutinario → evento lo deja en una sola línea. Se entrena con Reef_Check + AGRRA
(25 379 observaciones, 1,95 % de severos) y se evalúa en Donner + McClanahan + Kumagai (6 656
observaciones, 51,4 % de severos). La logística térmica + DHW predice de media 0,379; el bosque,
0,290. Recall 0,278 y 0,164. Un gestor que desplegara el modelo entrenado en monitoreo rutinario
sobre campañas de evento recibiría una probabilidad anclada al 2 %, no al 50 %. Eso es más
informativo que el ocean-out para la pregunta que el apartado 6.4.1 había dejado abierta.

### 6.7.6. Área de aplicabilidad sobre el ocean-out

El F1 0,456 de cuenca nueva resume cinco océanos **del mismo corpus**. Meyer y Pebesma (2021)
exigen otra pregunta: para **este** arrecife, ¿la predicción cae dentro del soporte de
entrenamiento? El DI se calculó en el espacio de los seis predictores numéricos, estandarizados
y ponderados por la media |SHAP| del Random Forest de profundidad 8 de esa cuenca —TreeSHAP,
no la impureza Gini que el apartado 4.3.2 declara inconsistente—, dejando fuera una cuenca cada
vez.

| Cuenca | n | Dentro del AOA (%) | Recall dentro | Recall fuera | Brier dentro | Brier fuera |
|---|---|---|---|---|---|---|
| Pacífico | 17 446 | 69,3 | 0,194 | 0,544 | 0,075 | 0,148 |
| Atlántico | 13 319 | 0,0 | n/d | 0,302 | n/d | 0,139 |
| Índico | 2 327 | 22,9 | 0,116 | 0,493 | 0,080 | 0,129 |
| Mar Rojo | 1 054 | 14,3 | 0,000 | 0,333 | 0,050 | 0,128 |
| Golfo Pérsico | 369 | 8,1 | 0,000 | 0,531 | 0,022 | 0,091 |

*Fuente: elaboración propia. Umbral: bigote superior del índice de disimilitud de entrenamiento. Pesos: TreeSHAP del bosque de cada cuenca.*

*Figura 6.13: `reports/figures/area_aplicabilidad.png`*

El **37,1 %** de las observaciones de prueba, ponderadas por tamaño de cuenca, cae dentro del AOA.
Cuando el Atlántico es la cuenca nueva, **ningún** punto está dentro: un gestor atlántico no
puede usar el 0,456 como estimación de error. El Pacífico es el único caso con mayoría dentro
(69,3 %). `TSA_DHW` es el predictor con mayor peso SHAP medio entre cuencas (0,073), por delante
de la distancia a la costa (0,049) y de la profundidad (0,040): el espacio de aplicabilidad se
estira sobre todo a lo largo del estrés acumulado, no de la impureza Gini.

El recall es más alto **fuera** del AOA. No es una contradicción. Fuera están los extremos
térmicos, más fáciles de etiquetar como «Severo». El Brier, que es la métrica del AOA, empeora
fuera en todas las cuencas con soporte interno (Pacífico 0,075 frente a 0,148; Índico 0,080
frente a 0,129). Dentro del área la probabilidad está anclada; fuera, el modelo sigue
detectando calor extremo y deja de estar calibrado. Comunicar un único F1 de cuenca nueva oculta
las dos cosas: el Atlántico sin soporte y el error inflado en los puntos disímiles.

### 6.7.7. Contraste empírico con Sully et al. (2019)

Sully et al. (2019) analizaron Reef Check (9 215 puntos, 3 351 emplazamientos, 1998–2017)
con un modelo jerárquico bayesiano y CoRTAD. Dos resultados anclan el capítulo 2: la SST
en episodios de blanqueamiento pasó de 28,1 °C (1998–2006) a 28,7 °C (2007–2017) —medias
de la distribución que su Figura 4 ajusta con Weibull—, y el blanqueamiento fue menos
frecuente donde la varianza térmica es alta. El presente trabajo no reajusta su modelo ni
reproduce ese Weibull. Lo que sí hace es **medir las dos magnitudes como medias
aritméticas** sobre este extracto BCO-DMO (34 515 observaciones; Reef Check 1998–2017 ya
son 20 010 puntos y 3 702 sitios, más del doble que el recorte del artículo).

| Periodo | Definición | n | SST media (°C) |
|---|---|---|---|
| 1998–2006 | Cualquier blanqueamiento | 9 081 | 28,29 |
| 1998–2006 | «Severo» | 2 955 | 28,38 |
| 2007–2017 | Cualquier blanqueamiento | 7 907 | 28,50 |
| 2007–2017 | «Severo» | 1 182 | 29,22 |
| 2018–2020 | Cualquier blanqueamiento | 710 | 28,68 |
| 2018–2020 | «Severo» | 45 | 29,83 |

*Figura 6.14: `reports/figures/contraste_sully.png`*

El signo del desplazamiento se reproduce. La magnitud, no. Sobre todas las fuentes, la media
aritmética sube +0,21 °C en cualquier blanqueamiento (28,29 °C a 28,50 °C) frente a los
+0,6 °C de Sully; +0,84 °C si se restringe a «Severo». El umbral 10 % / 30 % **no entra**
en el cálculo de «cualquier blanqueamiento». Tampoco basta con achacarlo a Donner o
McClanahan: restringida a Reef_Check, la media es 27,82 °C (n = 2 031) y 28,12 °C
(n = 4 870), todavía +0,30 °C y por debajo de 28,1 / 28,7. La discrepancia esperable es
otra: recorte distinto (9 215 frente a 20 010 puntos Reef Check), producto SST distinto
(CoRTAD frente a `Temperature_Kelvin` de CRW) y estadístico distinto (Weibull de su
Figura 4 frente a media aritmética). En 2018–2020 la SST de los 45 episodios severos sigue
alta (29,83 °C), con n demasiado pequeño para leer un nuevo salto de umbral.

La segunda afirmación —menos blanqueamiento donde la SST varía más— se confirma **en signo y
se atenúa en magnitud**, y solo para la desviación de la SST absoluta.
`Temperature_Kelvin_Standard_Deviation` (2 972 sitios con al menos tres censos): ρ = −0,079
con el blanqueamiento medio y ρ = −0,032 con la proporción de «Severo». `ClimSST` frente a
«Severo»: ρ = −0,132. La desviación de la anomalía (`SSTA_Standard_Deviation`) correlaciona
incluso en positivo con P(Severo) (ρ = 0,272): una Spearman incondicional **no** replica el
coeficiente protector de Sully sobre la varianza de anomalías. El SHAP de `ClimSST` del
bosque oficial (apartado 6.6.4) sigue siendo el análogo a nivel de modelo. Lo que Sully
aisló con efectos aleatorios aparece aquí como correlación incondicional débil; no como una
replicación del jerárquico.

### 6.7.8. Entrenar en Caribe y Pacífico Central, evaluar el resto

Un gestor no entrena en cuatro océanos y retiene el quinto. Entrena en las redes que tiene
—el Gran Caribe, Polinesia, Hawái— y pregunta por la Gran Barrera o el Triángulo de Coral.
Ese bloqueo usa 14 628 observaciones (5 598 sitios, 16,9 % de severos) y prueba 19 887
(5 470 sitios, 9,2 % de severos). Sigue siendo Sully et al. (2019). El nombre «Caribe y
Pacífico Central» no describe un diseño equilibrado: **12 914 observaciones (88 %)** son
Tropical Atlantic / Gran Caribe y **1 714 (12 %)** son *Eastern Indo-Pacific*, de las que
1 299 caen en las islas de la Sociedad. Hawái aporta 131. Es, en la práctica, entrenar en
el Caribe con un apéndice polinesio y preguntar por el *Central Indo-Pacific* (14 843
observaciones de prueba, el 75 %). El entrenamiento mezcla Reef_Check (37 %, 3,6 % de
severos), Donner (27 %, 48 % de severos), AGRRA y FRRP; la prueba es un 86 % Reef_Check
(1,6 % de severos), con McClanahan y Kumagai enteros en el lado de prueba. Es más adverso
que el ocean-out, y no solo por geografía: también por protocolo.

| Modelo | Recall | Precisión | F1 severa | PR-AUC | Brier |
|---|---|---|---|---|---|
| Regla CRW DHW ≥ 4 | 0,439 | 0,397 | **0,417** | 0,226 | 0,113 |
| Logística térmica + DHW | 0,169 | 0,472 | 0,248 | 0,335 | 0,125 |
| RF profundidad 8 + DHW | 0,346 | 0,358 | 0,352 | 0,280 | 0,103 |

*Figura 6.15: `reports/figures/transferencia_dominio.png`*

CRW gana el F1 de clase severa en el punto de operación DHW ≥ 4 / umbral 0,5. El bosque no
alcanza a la regla que no se entrena. Medido en **PR-AUC**, el orden se invierte: la
logística térmica (0,335) supera al bosque (0,280) y a CRW (0,226). La regla binaria ordena
peor que un modelo de probabilidad; gana cuando hay que emitir o no una alerta. El 72,6 %
de los puntos de prueba cae dentro del AOA de ese bosque: el soporte térmico de Caribe y
Polinesia **sí cubre** buena parte del Indo-Pacífico central. El fallo no es tanto «fuera
de mapa» como prevalencia y protocolo. Un gestor caribeño que desplegara este bosque en la
Gran Barrera estaría peor que Coral Reef Watch en F1, aun dentro del AOA; no peor en
capacidad de ranking que la logística.

### 6.7.9. 2010–2017 frente a 2018–2020

No hay 2021. El ancla honesta de «entrenar 2010–2021 y evaluar lo que sigue» es 2010–2017
(12 276 observaciones, 7,8 % de severos) contra 2018–2020 (2 521 observaciones, **1,9 %** de
severos, 49 episodios). Toda la prueba es Reef_Check. El año 2020 aporta 90 registros: el
corte es 2018 (1 243) y 2019 (1 188) más un stub. 344 de 567 sitios de prueba ya se
censaron en 2010–2017; **34 de los 49 severos** caen en esos sitios ya vistos.

| Modelo | Recall | F1 severa | PR-AUC | Brier |
|---|---|---|---|---|
| Regla CRW DHW ≥ 4 | 0,000 | 0,000 | 0,019 | 0,050 |
| Logística térmica + DHW | 0,000 | 0,000 | 0,040 | 0,077 |
| RF profundidad 8 + DHW | 0,122 | 0,126 | 0,074 | 0,040 |

CRW no dispara: ninguno de esos 49 «Severo» alcanza DHW ≥ 4 (máximo 3,26; media 1,03; 24 de
los 49 están en la plataforma de Sunda). Son censos rutinarios con el umbral 30 %, no los
eventos masivos que NOAA etiqueta. El bosque recupera 6 de 49 (recall 0,122); la logística,
cero. Sobre los 803 registros de sitios **no** vistos en 2010–2017 el bosque sube a recall
0,400 y F1 0,279 —quince etiquetas positivas: cifra inestable, no un despliegue.

La lectura conjunta con 6.7.2 es nítida. El corte 1980–2012 / 2013–2020 **sigue siendo el
test térmico más informativo**: todavía contenía eventos con DHW alto y CRW empataba a la
logística. El corte 2018–2020 no sustituye a ese experimento ni a 2021–hoy. Es la prueba más
próxima a «los años que el artículo de Sully no vio», y avisa de que el etiquetado rutinario
sin ola de calor (DHW < 4) no es el fenómeno que Donner, McClanahan o la regla de NOAA
describen. No es validación externa. El holdout 2021–2026, ya fuera de BCO-DMO, se presenta
en el apartado 6.7.10.

### 6.7.10. Validación externa: Reef Check 2021–2026

Reef Check Foundation facilitó el export Belt 2021–2026 (acceso el 10 de septiembre de 2026;
CC BY-NC 4.0). Ese fichero no está en BCO-DMO 773466. El RF-8 + DHW, la logística térmica y
la regla CRW se entrenaron **solo** sobre las 34 515 observaciones internas. La etiqueta es
la media de S1–S4 de `Bleaching (% Of Population)`; 83 encuestas con los cuatro segmentos
en blanco se descartaron, no se imputaron a cero. Faltó la hoja Site: `Distance_to_Shore`
queda ausente y el `SimpleImputer` del pipeline oficial la rellena con la mediana del
entrenamiento BCO-DMO. En las 2 555 encuestas evaluadas esa imputación es una **constante**:
el bosque no dispone de variación de distancia a costa en este holdout. `SSTA`, `TSA`,
`TSA_DHW` y `ClimSST` proceden del producto operativo diario de 5 km de Coral Reef Watch
(conjunto `NOAA_DHW` en ERDDAP; Skirving et al., 2020) en el día del censo. Es la misma
familia de productos que Liu et al. (2014), **no** el NetCDF embebido en el extracto
BCO-DMO 773466. 20 encuestas quedaron sin DHW —19 de ellas en 2026, posterior al último día del
producto usado (16 de junio de 2026)—. De las 2 555 restantes, 185 cayeron en un píxel
costero vecino.

Quedan **2 555 encuestas, 834 emplazamientos, 74 episodios severos (2,90 %)**. La media de
`Percent_Bleaching` es 3,20 %. Malasia aporta 1 310 encuestas del Belt bruto; Sabah, 589
(seis severos). El DHW mediano es 0; el máximo, 19,09 °C·semana. 241 censos alcanzan
DHW ≥ 4, y 42 de los 74 severos están entre ellos. 2021 se parece a 2018–2020: un severo,
DHW máximo 3,51, ninguna alerta. 2024 concentra la señal térmica (42 severos, 174 avisos
DHW ≥ 4, máximo 19,09). 2 033 encuestas caen a 1 km o menos de un registro BCO-DMO:
reencuestas temporales, no sitios nuevos. 522 distan más de 1 km (21 severos).

| Subconjunto | Modelo | n | Severo (%) | Recall | F1 | PR-AUC | Brier |
|---|---|---|---|---|---|---|---|
| Completo 2021–2026 | Regla CRW DHW ≥ 4 | 2 555 | 2,90 | 0,568 | 0,267 | 0,111 | 0,090 |
| Completo 2021–2026 | Logística térmica + DHW | 2 555 | 2,90 | 0,405 | 0,278 | 0,266 | 0,106 |
| Completo 2021–2026 | RF profundidad 8 + DHW | 2 555 | 2,90 | 0,243 | 0,220 | 0,165 | 0,060 |
| Sitios > 1 km | Regla CRW DHW ≥ 4 | 522 | 4,02 | 0,571 | 0,245 | 0,106 | 0,142 |
| Sitios > 1 km | Logística térmica + DHW | 522 | 4,02 | 0,571 | 0,329 | 0,367 | 0,113 |
| Sitios > 1 km | RF profundidad 8 + DHW | 522 | 4,02 | 0,429 | 0,353 | 0,233 | 0,069 |
| 2023–2024 | Regla CRW DHW ≥ 4 | 1 116 | 5,38 | 0,700 | 0,308 | 0,154 | 0,169 |
| 2023–2024 | Logística térmica + DHW | 1 116 | 5,38 | 0,500 | 0,316 | 0,317 | 0,129 |
| 2023–2024 | RF profundidad 8 + DHW | 1 116 | 5,38 | 0,283 | 0,279 | 0,221 | 0,082 |

*Figura 6.16: `reports/figures/validacion_externa.png`*

En el conjunto completo CRW recupera 42 de 74 severos (recall 0,568) a costa de 199 falsos
positivos (precisión 0,174). El bosque acotado recupera 18 (TN 2 409, FP 72, FN 56, TP 18):
el mismo recall 0,243 que en el corte interno 2013–2020. La logística se sitúa en medio
(30 verdaderos positivos) y **gana el PR-AUC** (0,266 frente a 0,111 de CRW y 0,165 del
bosque). El Brier más bajo es el del bosque (0,060): vuelve a calibrar mejor de lo que
detecta. En 2023–2024, con DHW alto, CRW sube el recall a 0,700; el bosque se queda en
0,283. Sobre los 522 sitios a más de 1 km el bosque adelanta a CRW en F1 (0,353 frente a
0,245) y la logística adelanta a ambos en PR-AUC (0,367). Sin Malasia el recall del bosque
sube a 0,462: parte de su conservadurismo en el conjunto completo es composición geográfica,
no solo umbral.

*Figura 6.17: `reports/figures/validacion_externa_dhw.png`*

Esto **es** validación externa respecto de Sully et al. (2019) y de BCO-DMO 773466: años
posteriores, fichero distinto, DHW extraído de nuevo. No es otra cosa. El protocolo sigue
siendo Reef Check —el mismo que domina el entrenamiento—. El 79,6 % de los censos
(2 033 de 2 555) revisita un entorno ya visto a 1 km. La tarea sigue siendo concurrente:
DHW del día del censo, no un pronóstico a 1–3 meses. No hay una AMP con umbral de coste
acordado. El agradecimiento a Reef Check Foundation, a Reef Check Malaysia y al Sabah
Biodiversity Centre se consigna en el apartado 7.5.

## 6.8. Síntesis y limitaciones

Los resultados permiten formular nueve conclusiones.

En primer lugar, el ROC-AUC de 0,943 bajo partición aleatoria no es la cifra que debe abrir un
resumen. La métrica operativa es el recall de «Severo» y el PR-AUC (línea base 0,124). En CV por
sitio, la logística + DHW alcanza 0,345 de PR-AUC y el RF de profundidad 8, 0,514.

En segundo lugar, `TSA_DHW` pertenece al modelo principal. Pasa el recall espacial de la logística
de 0,266 a 0,386, y a 0,445 sin contexto del sitio. Completitud 99,65 %; fisiología en el
apartado 4.1.4.

En tercer lugar, la CV por `Reef_ID` mide Reef_Check. La transferencia global se mide por
`Site_ID` y por cuenca. El RF libre cae un 19,5 % por sitio, no un 52 %.

En cuarto lugar, para una temporada futura la regla CRW de 4 °C·semana iguala a la logística en
F1 de clase severa (0,422 frente a 0,416) y deja atrás al bosque (recall 0,243).

En quinto lugar, `Depth_m` no es un efecto de hábitat: es estratificación por programa. El I de
Moran muestra que los índices térmicos están más agrupados que la respuesta; por eso la ablación
de contexto no mata la brecha.

En sexto lugar, el leave-one-program-out no es validación externa. Entrenar en monitoreo
rutinario (1,95 % de severos) y probar en documentación de evento (51,4 %) deja una P media de
0,29–0,38: el modelo arrastra la prevalencia del protocolo. McClanahan (77,4 % observado, 0,40
predicho) es el caso extremo de ese sesgo, no de un océano nuevo.

En séptimo lugar, el F1 0,456 de cuenca nueva no es una cifra de gestor. El 37 % de los puntos
del ocean-out cae dentro del área de aplicabilidad; el Atlántico, el 0 %. Fuera del AOA el
recall sube y el Brier empeora. El DI se pondera con TreeSHAP, no con Gini.

En octavo lugar, el contraste con Sully reproduce el signo del desplazamiento de SST, no la
magnitud ni el Weibull de su Figura 4; Reef Check en este CSV ya duplica su recorte. La
varianza de SST absoluta correlaciona en negativo y débil; la de la anomalía, no. Entrenar
en el Caribe (88 %) más un apéndice polinesio (12 %) deja a CRW por delante del bosque en F1
(0,417 frente a 0,352) y a la logística por delante en PR-AUC, con un AOA del 73 %. El corte
2018–2020 no sustituye 2021–hoy ni al corte 2013–2020: es Reef_Check al 1,9 % de severos, DHW
máximo 3,26, y CRW no dispara. Ese bloqueo sigue siendo interno.

En noveno lugar, el export Belt 2021–2026 **sí es un conjunto fuera de BCO-DMO**. 2 555
encuestas, 74 severos (2,90 %), DHW máximo 19,09. CRW recupera el 56,8 % de los severos
(el 70,0 % en 2023–2024); el bosque, el 24,3 % —el mismo recall que en 2013–2020—; la
logística gana el PR-AUC (0,266). El 79,6 % de los censos está a ≤ 1 km de un registro interno;
sobre los 522 sitios más lejanos el bosque gana el F1 (0,353) y la logística el ranking.
El protocolo sigue siendo Reef Check y la tarea, concurrente. No es una AMP ni una alerta a
1–3 meses.

Entre las limitaciones deben consignarse las siguientes.

**Naturaleza de la variable de respuesta.** El modelo clasifica severidad concurrente con el
muestreo, no un evento futuro. El corte 2013–2020 estima transferencia temporal retrospectiva, no
un pronóstico operativo. El acoplamiento a un pronóstico térmico se esboza en el apartado 7.4.

**Error irreducible biológico.** La variación en la composición simbiótica puede modificar la
tolerancia térmica del holobionte en hasta 1–1,5 °C (Berkelmans y van Oppen, 2006; LaJeunesse
et al., 2018). Dos colonias bajo la misma anomalía pueden responder de forma distinta. Esa
heterogeneidad no está en los predictores satelitales y fija un techo a cualquier modelo de esta
familia. No se cuantifica aquí como fracción de la brecha de transferibilidad —esa descomposición
no se ha calculado—; se consigna como cota cualitativa del error irreducible.

**Heterogeneidad del registro de campo.** Protocolos distintos, momento del censo (Claar y Baum,
2019) y discrepancia satélite–*in situ* (Claar et al., 2019). El apartado 6.7.5 cuantifica el
sesgo de protocolo; no lo elimina.

**Área de aplicabilidad.** El DI de Meyer y Pebesma (2021), ponderado por TreeSHAP, se calculó
sobre el ocean-out. No sustituye el holdout 2021–2026 del apartado 6.7.10, ni un mapa operativo
por arrecife para una AMP concreta.
