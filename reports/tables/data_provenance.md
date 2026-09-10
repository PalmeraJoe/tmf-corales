# Procedencia de los datos y sus consecuencias metodologicas

Diagnostico de la estructura de origen del conjunto *Global Bleaching and Environmental
Data*, motivado por la fuerte asimetria de prevalencia entre la submuestra empleada en la
validacion agrupada y el conjunto completo.

## 1. Composicion por programa de origen

| Programa (`Data_Source`) | n | Severo (%) | Blanqueamiento medio (%) | Profundidad media (m) | `Reef_ID` informado (%) |
|---|---|---|---|---|---|
| Reef_Check | 22,531 | 2,11 | 2,53 | 6,51 | 100,0 |
| Donner | 5,770 | 51,89 | 35,05 | 9,82 | 0,0 |
| AGRRA | 2,848 | 0,74 | 3,31 | 7,01 | 0,0 |
| FRRP | 2,394 | 14,41 | 15,31 | 8,13 | 0,0 |
| Kumagai | 660 | 38,03 | 17,46 | 5,13 | 0,0 |
| McClanahan | 226 | 77,43 | 57,33 | 5,96 | 0,0 |
| Safaie | 77 | 25,97 | 24,35 | 5,01 | 0,0 |
| Nuryana | 5 | 60,00 | 30,90 | nan | 0,0 |
| Setiawan | 4 | 100,00 | 66,00 | nan | 0,0 |

## 2. Hallazgo principal: `Reef_ID` identifica un programa, no una cobertura general

De las 34,515 observaciones con blanqueamiento registrado, 22,531 tienen
`Reef_ID` informado. Esos registros pertenecen a un unico programa:
**Reef_Check**. La cobertura del campo es del 100 % en ese programa y del
0 % en todos los demas.

La consecuencia es directa. La validacion cruzada agrupada por `Reef_ID` **no estima la
transferencia a arrecifes nuevos en general**: estima la transferencia entre arrecifes
sometidos a un mismo protocolo de monitoreo rutinario. Los programas orientados a la
documentacion de episodios concretos —Donner, McClanahan, Kumagai— quedan integramente
excluidos de ese experimento.

Ello explica de forma completa la asimetria de prevalencia advertida en el apartado 6.4.1:
la submuestra agrupada presenta un 2.11 % de episodios severos frente al
12.42 % del conjunto completo, no por un artefacto de muestreo, sino porque
Reef_Check documenta el estado ordinario del arrecife mientras que otros programas
muestrean preferentemente durante eventos de blanqueamiento en curso.

**Correccion adoptada.** La agrupacion pasa a realizarse por `Site_ID`, campo con
cobertura del 100 % y 11,068 niveles distintos, lo que permite ejecutar la validacion
agrupada sobre las 34,515 observaciones y no sobre una fraccion sesgada.

## 3. La asociacion entre profundidad y blanqueamiento es un artefacto de estratificacion

| Estrato | n | r |
|---|---|---|
| Conjunto completo (bruta) | 32,834 | 0,1655 |
| Dentro de AGRRA | 2,820 | 0,2334 |
| Dentro de Donner | 4,126 | 0,0929 |
| Dentro de FRRP | 2,394 | -0,0228 |
| Dentro de Kumagai | 660 | -0,1686 |
| Dentro de McClanahan | 226 | 0,0042 |
| Dentro de Reef_Check | 22,531 | 0,0114 |
| Residualizada respecto a Data_Source | 32,834 | 0,0391 |

La correlacion bruta entre `Depth_m` y `Percent_Bleaching` desaparece al condicionar por
programa de origen. El mecanismo es el siguiente: los programas difieren simultaneamente en
la profundidad tipica de muestreo y en la prevalencia de blanqueamiento, de modo que la
asociacion agregada recoge la diferencia **entre** protocolos y no un efecto ecologico de la
profundidad **dentro** de ellos. Se trata de una manifestacion de la paradoja de Simpson.

En consecuencia, la contribucion SHAP de `Depth_m` documentada en el capitulo 6 no admite
lectura ecologica directa: la variable opera en gran medida como indicador del programa de
procedencia y, a traves de el, de la probabilidad a priori de observar un episodio severo.

*Figura: `reports/figures/procedencia_prevalencia.png`*

## Reproducibilidad

Script: `src/data_provenance.py`. El analisis es puramente descriptivo y no depende de
semilla aleatoria.
