# Contraste con Sully et al. (2019) y transferencias de dominio

Los tres experimentos permanecen dentro de la sintesis BCO-DMO. No sustituyen un corpus
independiente (Reef Check posterior a 2020, NOAA, una AMP concreta).

## 1. Contraste empirico con Sully et al. (2019)

Sully et al. analizaron Reef Check (9 215 puntos, 3 351 sitios, 1998-2017) con CoRTAD y un
modelo jerarquico bayesiano. Las 28,1 °C / 28,7 °C proceden de la distribucion de SST en
blanqueamiento (Figura 4, Weibull), no de la media aritmetica de este extracto. Aqui no se
reajusta ese modelo: se reporta Temperature_Kelvin - 273,15 sobre las 34 515 observaciones.

| Periodo | Definición | n | SST media (°C) | DE |
|---|---|---|---|---|
| 1998-2006 (Sully) | cualquier blanqueamiento | 9 081 | 28,29 | 1,58 |
| 1998-2006 (Sully) | Severo | 2 955 | 28,38 | 1,53 |
| 2007-2017 (Sully) | cualquier blanqueamiento | 7 907 | 28,50 | 2,28 |
| 2007-2017 (Sully) | Severo | 1 182 | 29,22 | 1,96 |
| 2018-2020 (post Sully) | cualquier blanqueamiento | 710 | 28,68 | 1,42 |
| 2018-2020 (post Sully) | Severo | 45 | 29,83 | 0,99 |

Solo Reef_Check, cualquier blanqueamiento (Percent_Bleaching > 0):
- 1998-2006 Reef_Check: n = 2 031, media 27,82 °C
- 2007-2017 Reef_Check: n = 4 870, media 28,12 °C

Spearman entre emplazamientos (n = 2 972, al menos 3 censos):
desviacion tipica de SST frente a blanqueamiento medio ρ = -0,079;
frente a proporcion de «Severo» ρ = -0,032.
`ClimSST` frente a proporcion de «Severo» ρ = -0,132.
`SSTA_Standard_Deviation` frente a «Severo» ρ = 0,272 (signo opuesto
a la varianza absoluta; no replica el coeficiente protector de Sully sobre anomalías).

Figura: `reports/figures/contraste_sully.png`.

## 2. Transferencia geografica: Caribe + apendice polinesio → resto

Entrenamiento: ecorregiones del Gran Caribe y reino *Eastern Indo-Pacific* (Polinesia,
Hawai, Line, Phoenix, Marshall). Ese reino no es el *Central Indo-Pacific* de Spalding.
n = 14 628, sitios 5 598,
prevalencia «Severo» 16,9 %.
Composicion: 12 914 Tropical Atlantic (88 %)
y 1 714 Eastern Indo-Pacific (12 %).
Prueba: el resto del corpus. n = 19 887, sitios 5 470,
prevalencia 9,2 %. `Ocean_Name` se excluye: la dummy
Pacifico se compartiria entre Polinesia (train) y la Gran Barrera (test).

| Modelo | n | Prevalencia (%) | P media | Recall | Precisión | F1 severa | PR-AUC | Brier |
|---|---|---|---|---|---|---|---|---|
| Regla CRW DHW >= 4 | 19 887 | 9,2 | 0,101 | 0,439 | 0,397 | 0,417 | 0,226 | 0,113 |
| Logistica termica + DHW | 19 887 | 9,2 | 0,321 | 0,169 | 0,472 | 0,248 | 0,335 | 0,125 |
| RF profundidad 8 + DHW | 19 887 | 9,2 | 0,253 | 0,346 | 0,358 | 0,352 | 0,280 | 0,103 |

AOA (TreeSHAP) del bosque entrenado en Caribe + Eastern Indo-Pacific: 72,6 %
de los puntos de prueba dentro del umbral. DI mediano 0,087.
CRW gana F1; la logistica gana PR-AUC.

## 3. Transferencia temporal: 2010-2017 → 2018-2020

El CSV no contiene 2021 ni anos posteriores (maximo 2020, n = 90 ese ano). El ancla
honesta del pedido «2010-2021 y los siguientes» es entrenar en 2010-2017 —ultimo ano de
la ventana de Sully— y evaluar 2018-2020, posterior a esa publicacion. No sustituye al
corte 2013-2020 como test termico: ninguno de los 49 «Severo» de prueba alcanza DHW >= 4.

Entrenamiento: n = 12 276, sitios 3 922,
prevalencia 7,8 %.
Prueba 2018-2020: n = 2 521, sitios 567,
prevalencia 1,9 %. El 100 % de esa prueba es Reef_Check.
Sitios de prueba que ya aparecian en 2010-2017: 344 de
567. Severos en sitios ya vistos: 34
de 49.

### Todas las observaciones 2018-2020

| Modelo | n | Prevalencia (%) | P media | Recall | Precisión | F1 severa | PR-AUC | Brier |
|---|---|---|---|---|---|---|---|---|
| Regla CRW DHW >= 4 | 2 521 | 1,9 | 0,030 | 0,000 | 0,000 | 0,000 | 0,019 | 0,050 |
| Logistica termica + DHW | 2 521 | 1,9 | 0,250 | 0,000 | 0,000 | 0,000 | 0,040 | 0,077 |
| RF profundidad 8 + DHW | 2 521 | 1,9 | 0,137 | 0,122 | 0,130 | 0,126 | 0,074 | 0,040 |

### Solo sitios no observados en 2010-2017

| Modelo | n | Prevalencia (%) | P media | Recall | Precisión | F1 severa | PR-AUC | Brier |
|---|---|---|---|---|---|---|---|---|
| Regla CRW DHW >= 4 | 803 | 1,9 | 0,010 | 0,000 | 0,000 | 0,000 | 0,019 | 0,029 |
| Logistica termica + DHW | 803 | 1,9 | 0,242 | 0,000 | 0,000 | 0,000 | 0,050 | 0,074 |
| RF profundidad 8 + DHW | 803 | 1,9 | 0,156 | 0,400 | 0,214 | 0,279 | 0,171 | 0,047 |

Figura: `reports/figures/transferencia_dominio.png`.

## Reproducibilidad

Script: `src/contraste_sully_transferencia.py`. Semilla 42.
