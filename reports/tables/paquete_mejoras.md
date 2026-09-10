# Leave-one-program-out, calibracion y area de aplicabilidad

Experimentos del paquete de mejoras. El leave-one-program-out permanece **dentro** de la
sintesis de Sully et al. (2019): mide transferencia entre protocolos, no validacion externa.

## 1. Leave-one-program-out

Se retiene como conjunto de prueba un programa con n ≥ 200 y se entrena con el resto.
`Ocean_Name` se codifica con `handle_unknown='ignore'`.

### Random Forest profundidad 8 + DHW

| Programa | n | Prevalencia test (%) | P(Severo) media | Recall | Precisión | F1 severa | Brier |
|---|---|---|---|---|---|---|---|
| Reef_Check | 22 531 | 2,1 | 0,442 | 0,459 | 0,027 | 0,051 | 0,217 |
| Donner | 5 770 | 51,9 | 0,311 | 0,280 | 0,637 | 0,389 | 0,297 |
| AGRRA | 2 848 | 0,7 | 0,295 | 0,000 | 0,000 | 0,000 | 0,099 |
| FRRP | 2 394 | 14,4 | 0,396 | 0,429 | 0,311 | 0,361 | 0,177 |
| Kumagai | 660 | 38,0 | 0,209 | 0,127 | 0,711 | 0,216 | 0,225 |
| McClanahan | 226 | 77,4 | 0,402 | 0,411 | 0,847 | 0,554 | 0,319 |

### Logistica termica + DHW (sin contexto ni cuenca)

| Programa | n | Prevalencia test (%) | P(Severo) media | Recall | Precisión | F1 severa | Brier |
|---|---|---|---|---|---|---|---|
| Reef_Check | 22 531 | 2,1 | 0,303 | 0,055 | 0,105 | 0,072 | 0,101 |
| Donner | 5 770 | 51,9 | 0,358 | 0,220 | 0,771 | 0,343 | 0,265 |
| AGRRA | 2 848 | 0,7 | 0,280 | 0,000 | 0,000 | 0,000 | 0,084 |
| FRRP | 2 394 | 14,4 | 0,338 | 0,246 | 0,394 | 0,303 | 0,156 |
| Kumagai | 660 | 38,0 | 0,323 | 0,187 | 0,855 | 0,307 | 0,202 |
| McClanahan | 226 | 77,4 | 0,396 | 0,189 | 0,892 | 0,311 | 0,312 |

## 2. Contraste de protocolo (rutina → evento)

Entrenamiento: Reef_Check + AGRRA (n = 25 379, prevalencia 1,95 %).
Prueba: Donner + McClanahan + Kumagai (n = 6 656, prevalencia 51,38 %).

| Modelo | n test | Prevalencia (%) | P(Severo) media | Recall | Precisión | F1 severa | Brier |
|---|---|---|---|---|---|---|---|
| Logistica termica + DHW | 6 656 | 51,4 | 0,379 | 0,278 | 0,715 | 0,400 | 0,257 |
| RF profundidad 8 + DHW | 6 656 | 51,4 | 0,290 | 0,164 | 0,711 | 0,266 | 0,294 |

## 3. Calibracion de P(Severo)

CV agrupada por `Site_ID` (probabilidades fuera de pliegue) y corte temporal
(entrenamiento ≤ 2012, prueba ≥ 2013). El ECE se calcula en 10 bins de cuantiles. El recall de esta tabla es el de
`predict` (argmax), salvo la isotonica, que solo calibra P(Severo) y se evalua a umbral 0,5.
La isotonica no sustituye las cifras oficiales de F1 del apartado 6.7.2.

### CV por Site_ID

| Modelo | Brier | ECE | P media | Recall (argmax) |
|---|---|---|---|---|
| Logistica termica + DHW | 0,1316 | 0,1823 | 0,307 | 0,445 |
| RF profundidad 8 + DHW | 0,0991 | 0,1302 | 0,254 | 0,550 |
| Regla CRW DHW >= 4 | 0,1388 | 0,1388 | 0,099 | 0,338 |

### Corte temporal

| Modelo | Brier | ECE | P media | Recall (argmax) |
|---|---|---|---|---|
| Logistica termica + DHW | 0,1154 | 0,2313 | 0,309 | 0,504 |
| RF profundidad 8 + DHW | 0,0839 | 0,1264 | 0,204 | 0,243 |
| RF profundidad 8 + isotonica | 0,0678 | 0,0239 | 0,083 | 0,037 |
| Regla CRW DHW >= 4 | 0,0843 | 0,0508 | 0,068 | 0,398 |

Prevalencia de prueba temporal: 7,74 %.

## 4. Area de aplicabilidad (Meyer y Pebesma, 2021)

Leave-one-ocean-out del Random Forest profundidad 8. Predictores numericos
`SSTA`, `TSA`, `TSA_DHW`, `Depth_m`, `Distance_to_Shore`, `ClimSST`, estandarizados
sobre el entrenamiento. Pesos: media |SHAP| del propio bosque de cada cuenca
(TreeSHAP; Lundberg et al., 2020), no la reduccion de impureza Gini. El umbral
del AOA es el bigote superior (Q3 + 1,5 IQR) del DI de cada punto de
entrenamiento a su vecino mas proximo.

| Cuenca | n | Severo (%) | Dentro del AOA (%) | DI mediano | Recall dentro | Recall fuera | Brier dentro | Brier fuera |
|---|---|---|---|---|---|---|---|---|
| Arabian Gulf | 369 | 8,7 | 8,1 | 0,103 | 0,000 | 0,531 | 0,022 | 0,091 |
| Atlantic | 13 319 | 18,0 | 0,0 | 0,084 | n/d | 0,302 | n/d | 0,139 |
| Indian | 2 327 | 16,7 | 22,9 | 0,056 | 0,116 | 0,493 | 0,080 | 0,129 |
| Pacific | 17 446 | 8,4 | 69,3 | 0,067 | 0,194 | 0,544 | 0,075 | 0,148 |
| Red Sea | 1 054 | 0,6 | 14,3 | 0,074 | 0,000 | 0,333 | 0,050 | 0,128 |

Media ponderada de observaciones de prueba dentro del AOA:
37,1 %.

Pesos TreeSHAP medios entre cuencas:
- `SSTA`: 0,012
- `TSA`: 0,031
- `TSA_DHW`: 0,073
- `Depth_m`: 0,040
- `Distance_to_Shore`: 0,049
- `ClimSST`: 0,036

## Reproducibilidad

Script: `src/paquete_mejoras.py`. Semilla `42`.
