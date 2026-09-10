# Esquemas de validacion sobre el conjunto completo

Revision del experimento de transferibilidad espacial, corrigiendo tres limitaciones del
diseno original: la submuestra empleada, la capacidad no regularizada del Random Forest y la
ausencia de una metrica sensible al desbalanceo.

## Diseno

- **Datos**: 34,515 observaciones, 11,068 emplazamientos,
  113 ecorregiones, 5 cuencas.
  Prevalencia de la clase «Severo»: 12.42 %.
- **Agrupacion**: `Site_ID`, con cobertura del 100 %, en sustitucion de `Reef_ID`, que
  cubre unicamente el programa Reef_Check (vease `reports/tables/data_provenance.md`).
- **Esquemas**: `StratifiedKFold` frente a `StratifiedGroupKFold` por emplazamiento,
  ambos con 5 pliegues sobre identicos datos.
- **Metricas**: F1 macro, exhaustividad de la clase «Severo» y precision media
  (`average_precision_score`), equivalente al area bajo la curva de precision-exhaustividad.
  La linea base de esta ultima es la prevalencia, 0.1242.

## 1. Efecto del conjunto de predictores y de la capacidad del modelo

### Conjunto «Base» (sin estres acumulado)

| Modelo | F1 aleatoria | F1 por sitio | Δ relativa | Recall «Severo» | PR-AUC «Severo» |
|---|---|---|---|---|---|
| Regresion logistica | 0,3931 | 0,3917 | -0,4 % | 0,2656 | 0,2220 |
| Random Forest (max_depth=8) | 0,5351 | 0,5108 | -4,5 % | 0,5121 | 0,4243 |
| Random Forest (max_depth=16) | 0,7036 | 0,5816 | -17,3 % | 0,5993 | 0,5579 |
| Random Forest (sin tope) | 0,7471 | 0,5944 | -20,4 % | 0,5865 | 0,6038 |

### Conjunto «Base + DHW»

| Modelo | F1 aleatoria | F1 por sitio | Δ relativa | Recall «Severo» | PR-AUC «Severo» |
|---|---|---|---|---|---|
| Regresion logistica | 0,4512 | 0,4487 | -0,5 % | 0,3860 | 0,3455 |
| Random Forest (max_depth=8) | 0,5549 | 0,5310 | -4,3 % | 0,5504 | 0,5138 |
| Random Forest (max_depth=16) | 0,7271 | 0,6048 | -16,8 % | 0,6506 | 0,6335 |
| Random Forest (sin tope) | 0,7609 | 0,6169 | -18,9 % | 0,6513 | 0,6609 |

### Conjunto «Termicas + DHW», sin contexto del sitio ni cuenca

| Modelo | F1 aleatoria | F1 por sitio | Δ relativa | Recall «Severo» | PR-AUC «Severo» |
|---|---|---|---|---|---|
| Regresion logistica | 0,4556 | 0,4540 | -0,4 % | 0,4450 | 0,3226 |
| Random Forest (max_depth=8) | 0,4936 | 0,4692 | -4,9 % | 0,5387 | 0,4192 |
| Random Forest (max_depth=16) | 0,6560 | 0,5310 | -19,1 % | 0,5961 | 0,5064 |
| Random Forest (sin tope) | 0,6868 | 0,5362 | -21,9 % | 0,6054 | 0,4870 |

## 2. Lectura

### La capacidad del modelo explica buena parte del colapso

Bajo el conjunto «Base + DHW» y agrupacion por emplazamiento, la degradacion del F1 macro
depende fuertemente del tope de profundidad del Random Forest:

| Configuracion | Δ relativa del F1 macro |
|---|---|
| `max_depth=8` | -4,3 % |
| `max_depth=16` | -16,8 % |
| Sin tope | -18,9 % |

El desplome documentado en la version anterior de este trabajo no es, por tanto, una
propiedad inevitable de los metodos de conjunto: es en parte consecuencia de haber comparado
un modelo lineal regularizado con un bosque de profundidad ilimitada. Un Random Forest
acotado conserva la mayor parte de su rendimiento al cambiar de esquema. El bosque sin tope
queda reinterpretado como lo que realmente es, una **ablacion de capacidad**.

### El estres acumulado aporta senal transferible

Bajo agrupacion por emplazamiento, la exhaustividad sobre episodios severos de la regresion
logistica evoluciona del modo siguiente:

| Configuracion | Recall «Severo» (agrupada por sitio) |
|---|---|
| Base | 0,2656 |
| Base + DHW | 0,3860 |
| Termicas + DHW, sin contexto ni cuenca | 0,4450 |

La mejora se obtiene **anadiendo** el indice fisiologicamente fundamentado y **retirando**
los descriptores del emplazamiento. Ello justifica la incorporacion de `TSA_DHW` al conjunto
principal de predictores y no su tratamiento como apendice.

## 3. Bloqueo geografico

Validacion por ecorregion y leave-one-ocean-out sobre el conjunto «Base + DHW». En la
segunda, `Ocean_Name` se excluye de los predictores por ser constante en cada conjunto de
prueba.

| Modelo | F1 (ecorregion) | Recall sev. | PR-AUC | F1 (cuenca nueva) | Recall sev. | PR-AUC |
|---|---|---|---|---|---|---|
| Regresion logistica | 0,3801 | 0,3894 | 0,2983 | 0,4079 | 0,4944 | 0,3651 |
| Random Forest (max_depth=8) | 0,4407 | 0,5308 | 0,3695 | 0,4592 | 0,6283 | 0,3358 |
| Random Forest (max_depth=16) | 0,4527 | 0,4622 | 0,3560 | 0,4136 | 0,4746 | 0,3275 |
| Random Forest (sin tope) | 0,4427 | 0,4445 | 0,3563 | 0,4186 | 0,4698 | 0,3291 |

Detalle por cuenca, Random Forest con `max_depth=8`:

| Cuenca excluida del entrenamiento | n prueba | Severos | F1 macro | Recall «Severo» |
|---|---|---|---|---|
| Arabian Gulf | 369 | 8,67 % | 0,6997 | 0,6562 |
| Atlantic | 13,319 | 17,97 % | 0,4359 | 0,4169 |
| Indian | 2,327 | 16,67 % | 0,4414 | 0,6624 |
| Pacific | 17,446 | 8,41 % | 0,4190 | 0,5729 |
| Red Sea | 1,054 | 0,57 % | 0,2998 | 0,8333 |

## Reproducibilidad

Script: `src/validation_schemes.py`. Semilla fija (`random_state=42`).
El preprocesado se ajusta de forma independiente dentro de cada pliegue de entrenamiento.

*Figura: `reports/figures/esquemas_validacion.png`*
