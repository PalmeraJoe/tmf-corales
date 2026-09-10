# La regla de Coral Reef Watch como termino de comparacion

Todo modelo de alerta debe justificarse frente al procedimiento que las agencias ya emplean.
Coral Reef Watch declara alerta de nivel 1 al alcanzarse 4 grados-semana de estres termico
acumulado y de nivel 2 a partir de 8 (Liu et al., 2014; Skirving et al., 2020). Interpretada
como clasificador binario de la clase «Severo», esa regla no requiere entrenamiento, ajuste
de hiperparametros ni datos historicos del emplazamiento.

## 1. Rendimiento de la regla sobre el conjunto completo

| Regla | Alertas emitidas | Sobre el total | Recall | Precision | F1 de la clase severa |
|---|---|---|---|---|---|
| DHW ≥ 4 | 3,401 | 9,85 % | 0,3379 | 0,4261 | 0,3769 |
| DHW ≥ 8 | 945 | 2,74 % | 0,1031 | 0,4677 | 0,1689 |

El umbral de 4 grados-semana recupera el 33,8 % de los episodios
severos con una precision de 0,426, emitiendo alerta sobre el
9,9 % de las observaciones.

## 2. Corte temporal: la temporada que aun no ha ocurrido

La validacion agrupada mide transferencia en el espacio; la pregunta operativa anade la
dimension temporal. Se entrena con las campanas de 1980–2012
(24,109 observaciones, 14,45 % de severos) y se evalua
sobre 2013–2020 (10,406 observaciones,
7,74 % de severos).

| Metodo | Entrenamiento | Recall | Precision | F1 severa | Alertas emitidas |
|---|---|---|---|---|---|
| Regla CRW: DHW ≥ 4 | No requiere | 0,3975 | 0,4494 | 0,4219 | 6,8 % |
| Regla CRW: DHW ≥ 8 | No requiere | 0,0882 | 0,4610 | 0,1481 | 1,5 % |
| Regresion logistica (termicas + DHW) | 1980–2012 | 0,5043 | 0,3540 | 0,4160 | 11,0 % |
| Regresion logistica (base + DHW) | 1980–2012 | 0,3988 | 0,3078 | 0,3474 | 10,0 % |
| Random Forest max_depth=8 (base + DHW) | 1980–2012 | 0,2435 | 0,2988 | 0,2683 | 6,3 % |
| Random Forest sin tope (base + DHW) | 1980–2012 | 0,2373 | 0,3199 | 0,2725 | 5,7 % |

## 3. Lectura

La comparacion arroja un resultado incomodo para la narrativa habitual del aprendizaje
automatico aplicado a la alerta temprana, si bien exige precision al enunciarlo.

Medido sobre el **F1 de la clase severa**, que integra ambos tipos de error, la regla de
4 grados-semana (0,4219) y la regresion logistica con predictores
termicos y estres acumulado (0,4160) son practicamente indistinguibles.
La regla, que no ha visto un solo dato de entrenamiento, iguala al modelo ajustado.

La equivalencia global encubre, no obstante, un intercambio entre los dos tipos de error que
resulta pertinente para la gestion. La regresion logistica recupera mas episodios severos
—exhaustividad 0,5043 frente a 0,3975— al precio de
una precision inferior (0,3540 frente a 0,4494)
y de emitir alerta sobre el 11,0 % de las observaciones en lugar
del 6,8 %. Si el criterio de decision prioriza no omitir
episodios severos, el modelo aporta valor; si prioriza limitar las falsas alarmas, la regla
resulta preferible. La eleccion no la dirime la estadistica, sino la funcion de coste del
gestor.

El Random Forest, en cambio, queda claramente por detras de ambos:
0,2435 de exhaustividad con profundidad acotada y
0,2373 sin tope. El modelo que mejor rendia bajo particion aleatoria es
el que peor transfiere a una temporada futura, lo que reproduce en la dimension temporal el
patron ya documentado en la dimension espacial.

Debe advertirse que el periodo de prueba presenta una prevalencia de episodios severos
sensiblemente inferior a la del periodo de entrenamiento
(7,74 % frente a 14,45 %), de modo que
parte de la perdida de precision de los modelos obedece al desplazamiento de la clase base y
no unicamente a una degradacion de la capacidad discriminante.

La conclusion defendible no es que el aprendizaje automatico carezca de utilidad, sino que
**su valor anadido debe medirse frente al umbral operativo vigente y no frente a un
clasificador trivial**. En el escenario de mayor interes practico —un arrecife sin
historico, en una temporada aun no observada— ese valor anadido se reduce a la posibilidad
de desplazar el equilibrio entre falsos negativos y falsas alarmas, no a una mejora de la
capacidad discriminante global.

*Figura: `reports/figures/baseline_crw.png`*

## Reproducibilidad

Script: `src/crw_baseline.py`. Semilla fija (`random_state=42`).
Ano de corte: 2012. Los valores ausentes de `TSA_DHW` (0.35 %)
se tratan como ausencia de alerta.
