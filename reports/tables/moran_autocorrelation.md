# Autocorrelacion espacial: indice I de Moran

Cuantificacion de la dependencia espacial que el capitulo 4 introduce de forma teorica y
que el diseno de validacion presupone.

## Diseno

- **Unidad**: emplazamiento (`Site_ID`), con las variables promediadas dentro de cada uno.
  11,068 emplazamientos con coordenadas validas.
- **Vecindad**: 8 vecinos mas proximos por distancia de haversine sobre la
  superficie terrestre. Distancia media al vecino mas proximo: 4.0 km.
- **Pesos**: binarios, estandarizados por fila.
- **Contraste**: 999 permutaciones aleatorias de los valores sobre las
  posiciones fijas. El p-valor es la proporcion de permutaciones que igualan o superan el
  indice observado.

## Resultados

| Variable | n emplazamientos | I de Moran | I medio bajo permutacion | p |
|---|---|---|---|---|
| Blanqueamiento observado (%) | 11,068 | 0,371 | +0,0021 | 0,001 |
| Anomalia de estres termico (TSA) | 11,047 | 0,330 | +0,0025 | 0,001 |
| Anomalia de temperatura (SSTA) | 11,047 | 0,279 | +0,0021 | 0,001 |
| Estres termico acumulado (TSA_DHW) | 11,047 | 0,528 | +0,0021 | 0,001 |
| Climatologia de referencia (ClimSST) | 11,058 | 0,543 | +0,0025 | 0,001 |
| Profundidad (m) | 9,586 | 0,456 | +0,0024 | 0,001 |

## Lectura

Todas las variables presentan autocorrelacion espacial positiva y estadisticamente
significativa: el valor observado supera en todos los casos al esperado bajo asignacion
aleatoria, que se situa proximo a cero.

El resultado de mayor relevancia metodologica es la **ordenacion**. El estres termico
acumulado alcanza I = 0.528 y la anomalia de estres termico I = 0.330,
frente a I = 0.371 de la propia respuesta. Los predictores termicos estan, por
tanto, **mas agrupados espacialmente que el fenomeno que pretenden explicar**.

Esta observacion resuelve la cuestion que el experimento de ablacion dejaba abierta. La
persistencia de la brecha entre validacion aleatoria y agrupada en el conjunto «solo
termicas» no obedece a una fuga residual a traves de variables de contexto omitidas: obedece
a que los propios campos termicos portan estructura espacial suficiente para que un
algoritmo con capacidad de memorizacion identifique la region de procedencia. No existe, en
consecuencia, un subconjunto de predictores espacialmente neutro al que replegarse.

## Reproducibilidad

Script: `src/spatial_autocorrelation.py`. Semilla fija (`random_state=42`).
