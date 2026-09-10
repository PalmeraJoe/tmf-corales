# Interpretabilidad del modelo mediante valores SHAP

## Modelo explicado y alcance

Se analiza el clasificador **Random Forest** recomendado en los apartados 5.5 y 6.4
(`n_estimators` = 200, `max_depth` = 8, `class_weight='balanced'`),
con los predictores `SSTA`, `TSA`, `TSA_DHW`, `Depth_m`, `Distance_to_Shore`, `ClimSST`
y `Ocean_Name`. Los valores SHAP se calculan con `TreeExplainer` (TreeSHAP exacto) sobre
el pliegue de prueba de un `StratifiedGroupKFold` por `Site_ID`
(6 903 observaciones; 2 238 emplazamientos).
Solapamiento de `Site_ID` entre entrenamiento y explicación: 0.

La profundidad máxima de 8 hace el cálculo exacto tratable: no es necesario sustituir el
bosque oficial por XGBoost ni recurrir a submuestreo. Los predictores numéricos llegan
estandarizados, de modo que en el diagrama de dispersión el color «alto» es una desviación
respecto a la media de entrenamiento, no una magnitud absoluta en °C o metros.

## Importancia global por nivel de riesgo

Magnitud media del efecto SHAP (|SHAP| promedio) de cada variable sobre cada clase:

| Variable | Bajo | Moderado | Severo | Media global |
|---|---|---|---|---|
| TSA_DHW | 0,0894 | 0,0197 | 0,0997 | 0,0696 |
| Ocean_Name_Atlantic | 0,0849 | 0,0666 | 0,0213 | 0,0576 |
| Distance_to_Shore | 0,0420 | 0,0294 | 0,0258 | 0,0324 |
| Ocean_Name_Pacific | 0,0421 | 0,0262 | 0,0185 | 0,0289 |
| Depth_m | 0,0328 | 0,0146 | 0,0339 | 0,0271 |
| ClimSST | 0,0293 | 0,0149 | 0,0262 | 0,0235 |
| TSA | 0,0308 | 0,0186 | 0,0163 | 0,0219 |
| SSTA | 0,0110 | 0,0073 | 0,0085 | 0,0089 |
| Ocean_Name_Red Sea | 0,0098 | 0,0039 | 0,0059 | 0,0065 |
| Ocean_Name_Indian | 0,0049 | 0,0021 | 0,0047 | 0,0039 |
| Ocean_Name_Arabian Gulf | 0,0006 | 0,0007 | 0,0003 | 0,0005 |

Figura: `reports/figures/shap_importance_global.png`.

## Impacto y dirección sobre la clase «Severo»

La columna «Correlación valor–SHAP» indica si los valores altos de la variable empujan la
predicción hacia el blanqueamiento severo (signo positivo) o la alejan de él (signo negativo).

| Variable | Efecto medio |SHAP| | Correlación valor–SHAP |
|---|---|---|
| TSA_DHW | 0,0997 | 0,6671 |
| Depth_m | 0,0339 | 0,2275 |
| ClimSST | 0,0262 | -0,4124 |
| Distance_to_Shore | 0,0258 | 0,1427 |
| Ocean_Name_Atlantic | 0,0213 | 0,7233 |
| Ocean_Name_Pacific | 0,0185 | -0,7412 |
| TSA | 0,0163 | 0,7934 |
| SSTA | 0,0085 | 0,7882 |
| Ocean_Name_Red Sea | 0,0059 | -0,8881 |
| Ocean_Name_Indian | 0,0047 | 0,7827 |
| Ocean_Name_Arabian Gulf | 0,0003 | -0,2955 |

Figura: `reports/figures/shap_summary.png`.

## Lectura ecológica de los predictores

1. **`TSA_DHW`** — Degree Heating Weeks; estrés térmico acumulado en la ventana de doce semanas que emplea Coral Reef Watch. Efecto medio sobre la clase «Severo»: 0,0997; valores altos **aumentan** el riesgo severo.
2. **`Distance_to_Shore`** — distancia a la costa; aproxima presiones locales como escorrentía y turbidez. Efecto medio sobre la clase «Severo»: 0,0258; efecto no monótono (depende del contexto de la observación).
3. **`Depth_m`** — profundidad del muestreo; condiciona la irradiancia y el refugio térmico de la colonia. Efecto medio sobre la clase «Severo»: 0,0339; valores altos **aumentan** el riesgo severo.
4. **`ClimSST`** — temperatura superficial climatológica; describe el régimen térmico basal del arrecife. Efecto medio sobre la clase «Severo»: 0,0262; valores altos **reducen** el riesgo severo.
5. **`TSA`** — anomalía de estrés térmico; exposición a temperaturas por encima del umbral de blanqueamiento. Efecto medio sobre la clase «Severo»: 0,0163; valores altos **aumentan** el riesgo severo.
6. **`SSTA`** — anomalía de temperatura superficial del mar; mide el calentamiento puntual respecto a la climatología. Efecto medio sobre la clase «Severo»: 0,0085; valores altos **aumentan** el riesgo severo.

La variable con mayor peso explicativo global es **`TSA_DHW`**.

## Anomalías interpretativas que requieren cautela

`SSTA`, `TSA` y `TSA_DHW` derivan del mismo campo de temperatura superficial (Liu et al.,
2014). El reparto SHAP entre predictores correlacionados no es identificable de forma
unívoca (apartado 4.3.3). Las correlaciones valor–SHAP sobre «Severo» son
`SSTA` = 0,7882, `TSA` = 0,7934, `TSA_DHW` = 0,6671.
Ningún signo aislado de `SSTA` debe presentarse como evidencia de que el calentamiento
reduzca el blanqueamiento; la lectura válida es la del bloque térmico conjunto.

`ClimSST` muestra correlación valor–SHAP de -0,4124. Una dirección negativa admitiría
la lectura de umbrales más elevados en aguas históricamente cálidas (Sully et al., 2019);
sigue siendo una hipótesis compatible con el modelo, no una relación causal.

## Discusión: ¿estrés térmico o firma del emplazamiento?

| Grupo de variables | Contribución SHAP acumulada | Peso relativo |
|---|---|---|
| Estrés térmico (`SSTA`, `TSA`, `TSA_DHW`) | 0,1004 | 35,8 % |
| Contexto del emplazamiento (`Depth_m`, `Distance_to_Shore`, `ClimSST`) | 0,0830 | 29,5 % |

Estos porcentajes miden cuánto se apoya **este** bosque en cada bloque, no la fracción
del blanqueamiento atribuible a cada factor. `TSA_DHW` forma parte del bloque térmico:
ya no es una línea de trabajo futura.

El mismo cálculo bajo partición aleatoria (figura `shap_comparacion_esquemas.png`) deja
una razón contexto/térmicas de 0.78 frente a 0.83 en el
holdout por `Site_ID`. La jerarquía no es un artefacto del esquema inflado.

## Implicaciones para la conservación y la gestión de AMP

En sitios con histórico, el bosque acotado combina la señal acumulada (`TSA_DHW`) con
descriptores del emplazamiento. En un sitio o una cuenca fuera del soporte, la parte
utilizable se reduce a los índices térmicos, y aun así el ocean-out del apartado 6.7
muestra que esa señal no basta. El holdout ajeno a BCO-DMO se presenta en el
apartado 6.7.10.
