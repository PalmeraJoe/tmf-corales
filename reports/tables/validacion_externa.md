# Validacion externa: Reef Check 2021-2026

Corpus ajeno a BCO-DMO 773466 / Sully et al. (2019). El modelo oficial
(RF profundidad 8 + DHW) se entrena solo sobre las 34 515
observaciones internas. La etiqueta es `Bleaching (% Of Population)`,
media de los segmentos S1-S4 con dato; los blancos no se imputan a cero.
`Bleaching (% Of Colony)` se retiene como auxiliar y no es el target.
`Distance_to_Shore` no consta en Belt (no se recibio Site.csv) y la
imputa el pipeline con la mediana del entrenamiento.

Acceso a los datos: 10 de septiembre de 2026. Licencia CC BY-NC 4.0.
Cita: Reef Check Foundation. Reef Check Global Reef Dataset.
data.reefcheck.org. Date Accessed (10 September 2026).

## Inventario

- Encuestas con al menos un segmento de poblacion: 2 555
- Emplazamientos (`site_id`): 834
- Episodios Severo (Percent_Bleaching > 30): 74 (2,90 %)
- Media de Percent_Bleaching: 3,20 %
- Reencuestas a <= 1 km de BCO-DMO: 2 033
- Sitios a > 1 km de cualquier registro BCO-DMO: 522
- Censos en Sabah (Malasia): 589
- TSA_DHW mediano / maximo: 0,00 / 19,09
- Censos con DHW >= 4: 241 (de ellos Severo: 42)

Anos: 2021 n=437, 2022 n=552, 2023 n=572, 2024 n=544, 2025 n=408, 2026 n=42.

## Metricas (umbral 0,5 sobre P(Severo); CRW = DHW >= 4)

| Subconjunto | Modelo | n | Severo (%) | Recall | Precision | F1 | PR-AUC | Brier |
|---|---|---|---|---|---|---|---|---|
| completo 2021-2026 | Regla CRW DHW >= 4 | 2 555 | 2,90 | 0,568 | 0,174 | 0,267 | 0,111 | 0,090 |
| completo 2021-2026 | Logistica termica + DHW | 2 555 | 2,90 | 0,405 | 0,211 | 0,278 | 0,266 | 0,106 |
| completo 2021-2026 | RF profundidad 8 + DHW | 2 555 | 2,90 | 0,243 | 0,200 | 0,220 | 0,165 | 0,060 |
| sitios >1 km | Regla CRW DHW >= 4 | 522 | 4,02 | 0,571 | 0,156 | 0,245 | 0,106 | 0,142 |
| sitios >1 km | Logistica termica + DHW | 522 | 4,02 | 0,571 | 0,231 | 0,329 | 0,367 | 0,113 |
| sitios >1 km | RF profundidad 8 + DHW | 522 | 4,02 | 0,429 | 0,300 | 0,353 | 0,233 | 0,069 |
| 2023-2024 | Regla CRW DHW >= 4 | 1 116 | 5,38 | 0,700 | 0,197 | 0,308 | 0,154 | 0,169 |
| 2023-2024 | Logistica termica + DHW | 1 116 | 5,38 | 0,500 | 0,231 | 0,316 | 0,317 | 0,129 |
| 2023-2024 | RF profundidad 8 + DHW | 1 116 | 5,38 | 0,283 | 0,274 | 0,279 | 0,221 | 0,082 |
| sin Malasia | Regla CRW DHW >= 4 | 1 245 | 3,13 | 0,436 | 0,177 | 0,252 | 0,095 | 0,081 |
| sin Malasia | Logistica termica + DHW | 1 245 | 3,13 | 0,410 | 0,258 | 0,317 | 0,350 | 0,103 |
| sin Malasia | RF profundidad 8 + DHW | 1 245 | 3,13 | 0,462 | 0,222 | 0,300 | 0,223 | 0,070 |

## Matrices binarias (conjunto completo, umbral 0,5)

- RF-8: TN 2409, FP 72, FN 56, TP 18
- Logistica: TN 2369, FP 112, FN 44, TP 30
- CRW: TN 2282, FP 199, FN 32, TP 42

## Condiciones de uso (extracto)

Agradecimiento a Reef Check Foundation, sus capitulos y voluntarios.
Los censos de Sabah requieren ademas reconocer al Sabah Biodiversity
Centre (SaBC) como autoridad de licencia y a Reef Check Malaysia (RCM)
como titular de la licencia de acceso. Los informes deben compartirse
con Reef Check Foundation y, por los datos de Sabah, con SaBC.

Script: `src/validacion_externa_reefcheck.py`.
