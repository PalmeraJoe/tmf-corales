# 1. Resumen / Abstract

## 1.1. Resumen

El blanqueamiento coralino constituye una de las manifestaciones más visibles del calentamiento
oceánico y una amenaza directa para la biodiversidad de los arrecifes tropicales
(Hoegh-Guldberg, 1999). El presente Trabajo Fin de Máster desarrolla un flujo de aprendizaje
automático orientado a clasificar la severidad del blanqueamiento coralino observado a escala
global, y a medir con honestidad cuánto de ese rendimiento se transfiere a un emplazamiento
nuevo, a una cuenca nueva y a una temporada que el modelo no ha visto.

Se ha empleado el conjunto *Global Bleaching and Environmental Data*, publicado como dataset
por van Woesik y Kratochwill (2022) en BCO-DMO (registro 773466) y procedente de la síntesis de
Sully, Burkepile, Donovan, Hodgson y van Woesik (2019), que integra observaciones de campo con
productos de estrés térmico de NOAA
Coral Reef Watch (Liu et al., 2014; Skirving et al., 2020). Tras la depuración, el conjunto de
trabajo quedó en **34 515 observaciones** de cinco cuencas. La variable `Percent_Bleaching` se
discretizó en tres niveles —Bajo, Moderado y Severo— y los predictores principales son `SSTA`,
`TSA`, **`TSA_DHW`**, `ClimSST`, `Depth_m`, `Distance_to_Shore` y la cuenca oceánica. El índice de
estrés acumulado entra en el modelo principal (completitud 99,65 %), no en un apéndice.

Bajo partición aleatoria, un Random Forest sin tope de profundidad alcanza un F1-macro de 0,7464
y un ROC-AUC de 0,9430. Esa última cifra **no abre este resumen**. Saito y Rehmsmeier (2015)
muestran que, con una prevalencia de 0,124, la curva ROC es optimista; la métrica operativa es el
recall de «Severo» y el PR-AUC.

La estructura del conjunto —34 515 filas, 11 068 emplazamientos— configura un caso de
pseudorreplicación (Hurlbert, 1984). Una primera validación agrupada por `Reef_ID` hacía caer el
F1 del bosque un 52,2 %. Ese experimento, sin embargo, se ejecuta **solo sobre Reef_Check**:
`Reef_ID` no está informado en Donner, McClanahan, FRRP ni Kumagai, que concentran los eventos
masivos. La submuestra tiene un 2,11 % de episodios severos frente al 12,42 % global. La CV por
`Reef_ID` mide transferencia dentro de un programa de monitoreo rutinario, no transferencia
global.

La corrección es agrupar por `Site_ID` (cobertura 100 %) sobre las 34 515 observaciones, acotar
el bosque a `max_depth` = 8 y poner `TSA_DHW` en el modelo. Entonces la caída de F1 del bosque
libre es del **19,5 %**, no del 52 %; con profundidad 8, del **4,4 %**. El I de Moran
($k = 8$ vecinos) explica por qué la ablación de contexto no mataba la brecha: el blanqueamiento
alcanza $I = 0{,}37$, `TSA` $I = 0{,}33$ y `TSA_DHW` $I = 0{,}53$. Los índices térmicos están
más agrupados que la propia respuesta.

En CV por sitio, el recall de «Severo» de la logística sube de 0,266 a 0,386 al meter DHW, y a
**0,445** si además se retiran profundidad, distancia y cuenca —cifra espacial, sin contexto del
sitio—. El PR-AUC espacial es 0,345 (logística + DHW) y 0,514 (RF profundidad 8), frente a una
línea base de 0,124.

El competidor honesto para alerta temprana no es Random Forest, es la regla de Coral Reef Watch:
Severo si `TSA_DHW` ≥ 4 °C·semana. Esa regla, sin entrenamiento, detecta el 33,8 % de los
episodios severos (precisión 0,43). En un corte temporal distinto (entrena ≤ 2012, test ≥ 2013) la
regla y la logística térmica + DHW empatan en recall (0,398 frente a 0,399); el bosque se queda
en 0,243. Esa 0,398 no es la 0,445 del párrafo anterior. Medido en F1 de clase severa, la regla
(0,422) iguala a la logística térmica + DHW (0,416).

El *leave-one-ocean-out* del bosque acotado da F1 0,456 y recall 0,612: esa es la cifra de
**cuenca nueva dentro de Sully et al. (2019)**. No es una cifra de gestor ni un conjunto
externo. El índice de disimilitud de Meyer y Pebesma (2021), ponderado por TreeSHAP, deja
dentro del área de aplicabilidad el 37 % de los puntos de esa prueba; el Atlántico, el 0 %.
La CV por `Site_ID` evalúa transferibilidad entre arrecifes del mismo contexto biogeográfico; la
generalización a regiones nuevas es el ocean-out **y** ese porcentaje de soporte, no solo el F1.

El leave-one-program-out permanece dentro de Sully et al. (2019). Entrenar en monitoreo rutinario
(1,95 % de severos) y probar en documentación de evento (51,4 %) deja una P(Severo) media de
0,29–0,38. McClanahan (77,4 % observado, 0,40 predicho) mide sesgo de protocolo, no un océano
nuevo. En CV por sitio el Brier de P(Severo) del bosque acotado es 0,099; en el corte temporal
empata con la regla CRW (0,084). Recalibrar con isotónica mejora el ECE y hunde el recall.

El contraste con Sully replica el signo del desplazamiento de SST (28,29 °C a 28,50 °C en
cualquier blanqueamiento; más marcado en «Severo»), no la magnitud ni el Weibull de su
Figura 4. Entrenar en el Caribe (88 %) más Polinesia (12 %) y evaluar el resto deja a CRW
por delante del bosque en F1 (0,417 frente a 0,352) y a la logística por delante en
PR-AUC. El corte 2010–2017 / 2018–2020 —el ancla posible a «entrenar hasta 2021 y testar lo
siguiente», porque el CSV acaba en 2020— es íntegramente Reef_Check, con un 1,9 % de
severos y DHW máximo 3,26; CRW no dispara. Ninguno de esos bloqueos es un conjunto externo.

El export Belt de Reef Check 2021–2026 sí lo es. Entrenado solo en las 34 515 observaciones
internas, el modelo se evalúa sobre 2 555 encuestas ajenas a BCO-DMO (74 severos, 2,90 %;
DHW máximo 19,09). CRW recupera el 56,8 % de los severos —el 70,0 % en 2023–2024—; el bosque
el 24,3 %; la logística gana el PR-AUC (0,266). El protocolo sigue siendo Reef Check y la
tarea, concurrente. El 79,6 % de los censos cae a ≤ 1 km de un registro interno.

Las implicaciones de gestión se articulan en tres escenarios, no en dos. Sitio conocido: bosque
acotado, con potencial utilidad para priorizar campañas. Cuenca nueva: bosque acotado o logística
térmica, solo dentro del área de aplicabilidad. Temporada futura: la regla de NOAA no pierde
frente a estos clasificadores, y convertirlos en alerta a 1–3 meses exige un pronóstico térmico
ajeno, no otro algoritmo. En los tres casos se habla de potencial utilidad operativa, no de
despliegue inmediato.

**Palabras clave:** blanqueamiento coralino, Degree Heating Weeks, Coral Reef Watch, aprendizaje
automático, autocorrelación espacial, índice de Moran, validación cruzada agrupada,
validación externa, Reef Check, pseudorreplicación, Áreas Marinas Protegidas.

## 1.2. Abstract

Coral bleaching is one of the most visible manifestations of ocean warming and a direct threat to
tropical reef biodiversity (Hoegh-Guldberg, 1999). This Master's Thesis develops a machine
learning pipeline to classify observed bleaching severity at global scale, and to measure how
much of that performance transfers to a new site, a new ocean basin and a season the model has
not seen.

The working dataset comprises **34,515 observations** from the *Global Bleaching and
Environmental Data* release of van Woesik and Kratochwill (2022) on BCO-DMO (dataset 773466),
built on the Sully et al. (2019) synthesis
linked to NOAA Coral Reef Watch products (Liu et al., 2014; Skirving et al., 2020). The principal
predictors are `SSTA`, `TSA`, **`TSA_DHW`**, `ClimSST`, depth, distance to shore and ocean basin.
Accumulated heat stress is part of the main model (99.65 % complete), not an appendix.

A depth-unconstrained Random Forest reaches a macro F1 of 0.7464 and a ROC-AUC of 0.9430 under
random splits. That AUC is **not** the headline figure. With a 0.124 prevalence, PR-AUC and
severe-class recall are the operational metrics (Saito and Rehmsmeier, 2015).

A first grouped validation on `Reef_ID` cut Random Forest F1 by 52.2 %. That experiment runs
**only on Reef_Check**: `Reef_ID` is missing from Donner, McClanahan, FRRP and Kumagai, the
programmes that record mass events. Grouping by `Site_ID` on the full set, capping forest depth
at 8 and including `TSA_DHW` changes the picture. Unconstrained Random Forest F1 then drops by
**19.5 %**; with `max_depth` = 8, by **4.4 %**. Moran's *I* (*k* = 8) shows why context ablation
did not close the gap: bleaching *I* = 0.37, TSA *I* = 0.33, DHW *I* = 0.53. The thermal indices
are more spatially clustered than the response.

On site-grouped CV, logistic severe-class recall rises from 0.266 to 0.386 with DHW, and to
**0.445** without depth, distance and basin (a spatial figure, not a seasonal one). Spatial PR-AUC
is 0.345 (logistic + DHW) and 0.514 (depth-8 forest), against a 0.124 baseline.

The honest early-warning baseline is not Random Forest. It is Coral Reef Watch: Severe if
`TSA_DHW` ≥ 4 °C-weeks. That untrained rule recovers 33.8 % of severe episodes (precision 0.43).
On a separate temporal split (train ≤ 2012, test ≥ 2013) the rule and logistic + DHW tie on recall
(0.398 vs 0.399); the forest falls to 0.243. That 0.398 is not the 0.445 above. On severe-class F1
they remain indistinguishable (0.422 vs 0.416). Leave-one-ocean-out with a depth-8 forest yields F1 0.456 and recall 0.612 —
the figure for a **new basin inside Sully et al. (2019)**, not an independent corpus. Only 37 %
of those test points fall inside the Meyer and Pebesma (2021) area of applicability, weighted by
TreeSHAP rather than Gini impurity; none of the Atlantic does. Leave-one-program-out stays inside the
Sully et al. (2019) synthesis: training on routine monitoring (1.95 % severe) and testing on
event documentation (51.4 %) yields a mean P(Severe) of 0.29–0.38. Site-grouped Brier for the
capped forest is 0.099; on the temporal split it ties NOAA's rule (0.084). Training only on
the Greater Caribbean (88 % of that training set) plus a Polynesian appendix (Eastern
Indo-Pacific, 12 %) and testing the rest leaves Coral Reef Watch ahead of the forest on
severe F1 (0.417 vs 0.352); logistic leads on PR-AUC. The 2010–2017 /
2018–2020 split —the honest stand-in for “train to 2021 and test later”, because the file
ends in 2020— is entirely Reef_Check at 1.9 % severe and maximum DHW 3.26; CRW never fires.
None of these blocks is an independent corpus.

The Reef Check Belt export for 2021–2026 is. Trained only on the 34,515 internal records, the
official models are evaluated on 2,555 surveys outside BCO-DMO (74 severe, 2.90 %; maximum
DHW 19.09). CRW recovers 56.8 % of severe cases —70.0 % in 2023–2024—; the forest, 24.3 %;
logistic leads on PR-AUC (0.266). The protocol is still Reef Check and the task is still
concurrent. 79.6 % of surveys lie within 1 km of an internal record.

Management implications are stated as three scenarios: a known site, a new basin (only inside
the area of applicability), and a future season. Turning the classifier into a 1–3-month warning
requires an external SST forecast, not a different algorithm. For the year that has not yet
happened, NOAA's rule does not lose to these classifiers.

**Keywords:** coral bleaching, Degree Heating Weeks, Coral Reef Watch, machine learning, spatial
autocorrelation, Moran's I, grouped cross-validation, external validation, Reef Check,
pseudoreplication, Marine Protected Areas.
