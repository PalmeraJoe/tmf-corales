# Ablación de predictores y transferibilidad espacial

Experimento complementario a la comparativa principal, diseñado para contrastar de forma
directa la hipótesis de memorización espacial y para cuantificar la aportación del estrés
térmico acumulado.

## Diseño

- **Submuestra**: 22,531 observaciones con `Reef_ID` informado, correspondientes a
  4,115 arrecifes.
- **Esquemas de validación**: `StratifiedKFold` frente a `StratifiedGroupKFold`
  (agrupación por `Reef_ID`), ambos con 5 pliegues sobre idénticos datos.
- **Prevalencia de clases**: Bajo 93.03 %,
  Moderado 4.86 %, Severo 2.11 %.
- **Modelos**: Random Forest (`n_estimators=200`, `class_weight='balanced'`) y regresión
  logística (`class_weight='balanced'`), que actúan respectivamente como algoritmo con y sin
  capacidad de memorización.

El uso de `StratifiedGroupKFold` en lugar de `GroupKFold` corrige una limitación de la
comparativa principal: preserva de forma aproximada la proporción de clases entre pliegues
sin permitir que un mismo arrecife aparezca en entrenamiento y evaluación.

## Resultados: Random Forest

| Conjunto de predictores | F1 macro (aleatoria) | F1 macro (agrupada) | Δ absoluta | Δ relativa (%) | Recall «Severo» (agrupada) |
|---|---|---|---|---|---|
| Base (comparativa principal) | 0,8981 | 0,4407 | -0,4574 | -50,9255 | 0,1555 |
| Base + DHW | 0,8960 | 0,4597 | -0,4363 | -48,6935 | 0,1890 |
| Solo termicas | 0,7295 | 0,4237 | -0,3058 | -41,9162 | 0,1807 |
| Solo termicas + DHW | 0,7446 | 0,4462 | -0,2985 | -40,0816 | 0,2312 |
| Solo contexto del sitio | 0,8208 | 0,3967 | -0,4242 | -51,6745 | 0,1011 |
| Base sin Depth_m | 0,8531 | 0,4412 | -0,4119 | -48,2833 | 0,1682 |
| Base sin Distance_to_Shore | 0,8589 | 0,4464 | -0,4124 | -48,0200 | 0,1722 |
| Base sin ClimSST | 0,8979 | 0,4064 | -0,4916 | -54,7442 | 0,1049 |

## Resultados: regresión logística

| Conjunto de predictores | F1 macro (aleatoria) | F1 macro (agrupada) | Δ absoluta | Δ relativa (%) | Recall «Severo» (agrupada) |
|---|---|---|---|---|---|
| Base (comparativa principal) | 0,3004 | 0,2961 | -0,0043 | -1,4291 | 0,4218 |
| Base + DHW | 0,3398 | 0,3364 | -0,0034 | -0,9964 | 0,4886 |
| Solo termicas | 0,3042 | 0,2971 | -0,0072 | -2,3511 | 0,4300 |
| Solo termicas + DHW | 0,3424 | 0,3394 | -0,0030 | -0,8768 | 0,4886 |
| Solo contexto del sitio | 0,3176 | 0,3222 | 0,0046 | 1,4440 | 0,3669 |
| Base sin Depth_m | 0,3019 | 0,2958 | -0,0061 | -2,0336 | 0,4048 |
| Base sin Distance_to_Shore | 0,2985 | 0,2986 | 0,0001 | 0,0434 | 0,4302 |
| Base sin ClimSST | 0,3041 | 0,2944 | -0,0097 | -3,1738 | 0,4385 |

## Lectura de los resultados

### Contraste de la hipótesis de memorización espacial

La predicción falsable es explícita: si la degradación bajo validación agrupada procediera
de las variables que identifican el emplazamiento, un modelo privado de ellas debería
degradarse sensiblemente menos.

| Conjunto | F1 aleatoria | F1 agrupada | Brecha absoluta | Δ relativa |
|---|---|---|---|---|
| Base (incluye contexto del sitio) | 0.8981 | 0.4407 | 0.4574 | -50.9 % |
| Solo variables térmicas | 0.7295 | 0.4237 | 0.3058 | -41.9 % |
| Solo contexto del sitio | 0.8208 | 0.3967 | 0.4242 | -51.7 % |

El resultado **matiza sustancialmente la interpretación inicial**. Privar al modelo de las
tres variables de contexto reduce la brecha absoluta de
0.4574 a
0.3058 puntos de F1 macro, esto es, en un
33 %.
La reducción es apreciable y confirma que dichas variables contribuyen al fenómeno, pero
**dos tercios de la brecha persisten** en un modelo que solo dispone de `SSTA` y `TSA`.

La conclusión correcta no es, por tanto, que Random Forest memorice la identidad del arrecife
a través de una firma compuesta por profundidad, distancia a costa y climatología. Es que el
sobreajuste a la estructura espacial es un fenómeno más general: los propios índices térmicos
están espacialmente autocorrelacionados, de modo que un algoritmo con capacidad suficiente
puede explotar esa estructura aun careciendo de descriptores estáticos del emplazamiento.

### El caso de ClimSST

La ablación individual arroja un resultado contrario a la hipótesis de que `ClimSST` opere
como sustituto encubierto de la localización. Su eliminación **empeora** la transferencia
espacial: el F1 macro agrupado desciende de 0.4407 a
0.4064
y la degradación relativa se agrava hasta el
-54.7 %.
Si la variable actuase principalmente como identificador geográfico, su retirada habría
mejorado la generalización a arrecifes nuevos. El comportamiento observado es el opuesto, lo
que respalda la lectura biológica de tolerancia térmica adquirida frente a la interpretación
puramente espacial.

### Aportación del estrés térmico acumulado

`TSA_DHW` presenta una correlación marginal con `Percent_Bleaching` de r = 0,272, que duplica
la de `TSA` (r = 0,142) y supera a la de cualquier otro predictor disponible. Su incorporación
mejora el rendimiento precisamente en el escenario relevante, el de arrecifes no observados:

| Métrica (validación agrupada) | Base | Base + DHW | Variación |
|---|---|---|---|
| F1 macro, Random Forest | 0.4407 | 0.4597 | +4.3 % |
| Recall «Severo», Random Forest | 0.1555 | 0.1890 | +21.5 % |
| F1 macro, regresión logística | 0.2961 | 0.3364 | +13.6 % |
| Recall «Severo», regresión logística | 0.4218 | 0.4886 | +15.8 % |

La mejora es consistente en ambos modelos y afecta tanto al F1 macro como a la detección de
episodios severos. A diferencia de las variables de contexto, el estrés térmico acumulado
aporta señal **transferible**, lo que resulta coherente con su naturaleza de índice
fisiológicamente fundamentado y no meramente descriptivo del emplazamiento.

### Configuración óptima para arrecifes no observados

Combinando ambos hallazgos, la mejor detección de episodios severos en arrecifes nuevos no
corresponde al conjunto de predictores más amplio, sino al que descarta el contexto del sitio
e incorpora el estrés acumulado:

| Configuración | Recall «Severo» (agrupada) |
|---|---|
| Regresión logística, solo térmicas + DHW | 0.4886 |
| Regresión logística, base | 0.4218 |
| Random Forest, solo térmicas + DHW | 0.2312 |
| Random Forest, base | 0.1555 |

*Figura: `reports/figures/ablacion_transferibilidad.png`*

## Reproducibilidad

Script: `src/ablation_validation.py`. Semilla fija (`random_state=42`).
El preprocesado —imputación por la mediana, estandarización y codificación *one-hot*— se
ajusta de forma independiente dentro de cada pliegue de entrenamiento.
