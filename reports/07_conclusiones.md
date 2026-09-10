# 7. Conclusiones

## 7.1. Aportaciones técnicas

El presente trabajo ha desarrollado un flujo de aprendizaje automático para clasificar la
severidad del blanqueamiento coralino observado, sobre 34 515 observaciones de cinco cuencas.
De su desarrollo se derivan nueve aportaciones. La novena es la validación externa sobre
Reef Check 2021–2026; las ocho primeras permanecen dentro de Sully et al. (2019). Lo que
sigue sin medirse —una AMP concreta y un pronóstico térmico— se formula en el apartado 7.4.

**Primera: `TSA_DHW` en el modelo principal.** El índice de estrés acumulado deja de ser un
apéndice. Completitud 99,65 %; fisiología en el apartado 4.1.4. En CV por `Site_ID`, el recall de
«Severo» de la logística pasa de 0,266 a 0,386 al incorporarlo, y a 0,445 si además se retiran
profundidad, distancia y cuenca.

**Segunda: la regla de Coral Reef Watch como término de comparación.** DHW ≥ 4 °C·semana detecta
el 33,8 % de los episodios severos (precisión 0,43) sin entrenamiento. En un corte temporal, esa
regla iguala a la logística en F1 de clase severa (0,422 frente a 0,416) y deja atrás al bosque
(recall 0,243). El competidor honesto de un sistema de alerta no es Random Forest.

**Tercera: la unidad experimental correcta y el I de Moran medido.** `Reef_ID` identifica
Reef_Check, no el conjunto. Agrupar por `Site_ID` sobre las 34 515 observaciones cambia la caída
del bosque libre de un 52 % a un 19,5 %. El I de Moran ($k = 8$) cuantifica por qué la ablación
no cerraba la brecha: `TSA_DHW` ($I = 0{,}53$) está más agrupado que el blanqueamiento
($I = 0{,}37$). El *leave-one-ocean-out* del bosque acotado —F1 0,456, recall 0,612— es la cifra
de cuenca nueva **dentro de Sully et al. (2019)**; su soporte se detalla en la séptima
aportación.

**Cuarta: la capacidad del modelo como parte del diagnóstico.** El competidor oficial es un
Random Forest con `max_depth` = 8 (caída de F1 −4,4 % por sitio). El bosque sin tope es una
ablación de capacidad (−19,5 %). Una parte grande del «colapso» era hiperparámetro.

**Quinta: PR-AUC en lugar de ROC-AUC como cifra de apertura.** Con prevalencia 0,124, el PR-AUC
espacial es 0,345 (logística + DHW) y 0,514 (RF profundidad 8). El 0,943 de ROC-AUC describe la
partición aleatoria y no el escenario de aplicación.

**Sexta: el leave-one-program-out cuantifica el sesgo de protocolo, no un océano nuevo.**
Entrenar en monitoreo rutinario (1,95 % de severos) y probar en documentación de evento
(51,4 %) deja una P(Severo) media de 0,29–0,38. McClanahan (77,4 % observado, 0,40 predicho)
mide el arrastre de la prevalencia del etiquetado. El experimento sigue siendo interno a la
síntesis.

**Séptima: el F1 de cuenca nueva no se comunica sin área de aplicabilidad.** El 37 % de los
puntos del ocean-out cae dentro del AOA de Meyer y Pebesma (2021); el Atlántico, el 0 %. Los
pesos del índice de disimilitud son TreeSHAP del propio bosque, no la impureza Gini que el
apartado 4.3.2 declara inconsistente. Un gestor atlántico no puede leer el 0,456 como su error
esperado.

**Octava: el contraste con Sully y las transferencias de dominio no abren un corpus nuevo.**
La media aritmética de SST en episodios de blanqueamiento sube de 28,29 °C (1998–2006) a
28,50 °C (2007–2017); el signo coincide con Sully, la magnitud y el Weibull de su Figura 4
no. En Reef_Check el salto es 27,82 °C a 28,12 °C, todavía distinto de 28,1 / 28,7. La
varianza de SST absoluta correlaciona en negativo y débil; la de la anomalía, no. Entrenar
en el Caribe (88 %) más Polinesia (12 %) y evaluar el resto deja a CRW con F1 0,417 frente
a 0,352 del bosque; la logística gana el PR-AUC (0,335 frente a 0,226 de CRW). El corte
2018–2020 tropieza con Reef_Check al 1,9 % de severos y DHW máximo 3,26: no hay 2021 en
BCO-DMO, y CRW no dispara. El jerárquico bayesiano de Sully no se ha reajustado.

**Novena: el holdout Reef Check 2021–2026, ajeno a BCO-DMO.** 2 555 encuestas, 74 severos
(2,90 %), DHW máximo 19,09 °C·semana. Entrenado solo en las 34 515 internas, CRW recupera
el 56,8 % de los severos (70,0 % en 2023–2024); el bosque, el 24,3 %; la logística gana el
PR-AUC (0,266). El 79,6 % de los censos revisita un entorno a ≤ 1 km; sobre 522 sitios más
lejanos el bosque gana el F1 (0,353). Sigue siendo Reef Check y concurrente.

A juicio del autor, la aportación de mayor solidez no es haber encontrado el mejor algoritmo,
sino haber corregido la unidad experimental, el competidor y la métrica a la luz de lo que los
datos permitían medir, y haber cerrado la laguna de un corpus posterior a 2020 sin fingir un
sistema de alerta.

## 7.2. Implicaciones para la gestión de Áreas Marinas Protegidas

Los resultados no admiten una lectura única. Exigen **tres escenarios**, no dos.

### 7.2.1. Sitio conocido: interpolación dentro de una red

En AMP con estaciones consolidadas, el escenario es interpolar dentro de una red. El bosque
acotado (`max_depth` = 8) con `TSA_DHW` conserva casi todo su F1 al agrupar por sitio (−4,4 %) y
alcanza un PR-AUC de 0,514 sobre «Severo». El Brier fuera de pliegue de P(Severo) es 0,099, mejor
que el de la logística (0,132) y que el de la regla CRW (0,139). Presenta **potencial utilidad
operativa** para priorizar campañas de inspección, no un uso inmediato: no hay prueba piloto en
una AMP concreta, y el umbral de decisión sigue siendo una función de coste del gestor.

### 7.2.2. Cuenca nueva: extrapolación biogeográfica

La CV por `Site_ID` evalúa transferibilidad entre arrecifes **del mismo contexto biogeográfico**.
La generalización a otra cuenca del mismo corpus es el *leave-one-ocean-out*: F1 0,456 y recall
0,612 para el bosque acotado; recall 0,527 para la logística térmica + DHW. Sigue siendo Sully
et al. (2019) con un océano retenido, no un conjunto independiente. Un gestor que lea solo el
recall 0,445 de la logística por sitio estaría leyendo sitios nuevos, no océanos nuevos.
La dispersión entre cuencas (Atlántico 0,417 de recall; Índico 0,662) no es un detalle: cuando el
Atlántico es la cuenca de prueba, el **0 %** de los puntos cae dentro del área de aplicabilidad
de Meyer y Pebesma (2021). El F1 0,456 no es intercambiable entre gestores. Entrenar solo en
Caribe y Pacífico Central y evaluar el Indo-Pacífico central es todavía más adverso para el
bosque en el punto de operación: CRW gana el F1 (0,417 frente a 0,352) aunque el 73 % de los
puntos esté en el AOA. El entrenamiento es un 88 % Caribe; el «Pacífico Central» es un
apéndice polinesio, no una segunda cuenca de peso comparable. La logística, con peor F1,
ordena mejor (PR-AUC 0,335 frente a 0,226 de CRW).

### 7.2.3. Temporada futura: la regla que ya existe

Para el año que aún no ha ocurrido, NOAA no pierde frente a estos clasificadores. En el corte
≤ 2012 / ≥ 2013, DHW ≥ 4 y la logística empatan en F1 de clase severa; el bosque cae a un recall
de 0,243. Si el criterio es no omitir eventos, la logística desplaza el equilibrio (más recall,
más alarmas). Si el criterio es no movilizar recursos en falso, la regla de 4 °C·semana es
preferible. El corte 2018–2020, ya posterior a Sully y entero Reef_Check, deja a CRW sin un
solo acierto: no hay DHW ≥ 4 en esos 49 «Severo» (máximo 3,26). No desplaza al corte
2013–2020 como test térmico; lo complementa como prueba de etiquetado rutinario sin ola de
calor. El holdout Reef Check 2021–2026 (apartado 6.7.10) ya está fuera de BCO-DMO y sí contiene
olas de calor: CRW recupera el 70,0 % de los severos en 2023–2024, el bosque el 28,3 %.
Eso confirma el corte 2013–2020, no lo convierte en un pronóstico a 1–3 meses. El Brier temporal del bosque y el de la regla empatan (0,084) en 2013–2020; el ECE
de NOAA (0,051) es menor. Recalibrar el bosque con isotónica
mejora el ECE (0,024) y deja el recall en 0,037: sin reelegir el umbral, la calibración no es
una alerta. Esa elección de umbral es una función de coste del gestor, no un resultado
estadístico.

### 7.2.4. Recomendación operativa

Reportar tres números, no uno: rendimiento en sitio conocido, en cuenca nueva **dentro del área
de aplicabilidad**, y frente a Coral Reef Watch en una temporada no observada. Añadir, como
salvedad, que un cambio de protocolo (rutinario frente a evento) desplaza la probabilidad más
que un cambio de cuenca. Añadir el holdout 2021–2026 cuando se hable de años posteriores a
Sully: CRW no pierde el recall cuando hay DHW ≥ 4. Comunicar exclusivamente el F1 aleatorio o el ROC-AUC de 0,943
transmitiría la falsa confianza de la que advierten Ploton et al. (2020).

## 7.3. Limitaciones del estudio

La interpretación de las conclusiones precedentes debe atender a las limitaciones siguientes.

**Alcance de la variable de respuesta.** El modelo clasifica la severidad del blanqueamiento
observado de forma concurrente con el muestreo. El corte 2013–2020 estima transferencia a una
temporada no observada en el entrenamiento, no un pronóstico operativo. Toda alerta temprana
sigue condicionada a un pronóstico térmico obtenido por otra vía (apartado 7.4).

**Error irreducible biológico.** El desplazamiento de la comunidad simbionte dominante puede
modificar la tolerancia térmica del holobionte en 1–1,5 °C (Berkelmans y van Oppen, 2006;
LaJeunesse et al., 2018). Dos colonias bajo la misma anomalía pueden responder de forma distinta.
Esa heterogeneidad no está en los predictores satelitales y fija un techo a cualquier modelo de
esta familia (Suggett y Smith, 2020). No se descompone aquí como fracción de la brecha de
transferibilidad: esa cifra no se ha calculado.

**Heterogeneidad del registro.** Protocolos distintos, momento del censo (Claar y Baum, 2019) y
discrepancia satélite–*in situ* (Claar et al., 2019). `Depth_m` hereda esa estratificación. El
leave-one-program-out del apartado 6.7.5 cuantifica el sesgo; no lo corrige. No es validación
externa.

**Área de aplicabilidad.** El DI de Meyer y Pebesma (2021), ponderado por TreeSHAP, se calculó
sobre el ocean-out. El 37 % de los puntos de prueba queda dentro del umbral; el Atlántico, el
0 %. Un mapa operativo por arrecife candidato, con umbral acordado con una AMP, no se ha
producido. El holdout 2021–2026 del apartado 6.7.10 no sustituye ese mapa.

## 7.4. Líneas de trabajo futuras

**El holdout Reef Check 2021–2026 ya está en el flujo principal.** Cierra la laguna de un
corpus ajeno a BCO-DMO 773466 (apartados 5.4.9 y 6.7.10). Lo que sigue abierto no es «otro
CSV del mismo programa», sino una campaña en una AMP concreta —con umbral de coste acordado— y
un segundo protocolo de campo (por ejemplo FRRP o AIMS LTMP) que no sea Reef Check. El 79,6 %
de este holdout revisita entornos a ≤ 1 km; una AMP con estaciones propias mediría otra cosa.

**Acoplamiento a un pronóstico térmico.** El clasificador de este trabajo es concurrente: estima
la severidad dada la SST (y el DHW) del momento del censo. El holdout 2021–2026 también lo es.
Convertirlo en alerta a 1–3 meses no exige otro algoritmo; exige **otra entrada**. La vía
operativa es alimentar el mismo clasificador con un DHW derivado de un pronóstico numérico ya
existente —por ejemplo, CFSv2 o el conjunto NMME de la NOAA—, no reentrenar un modelo «de
futuro» sobre las etiquetas de Sully et al. (2019) ni sobre Reef Check 2021–2026. El corte
2013–2020 y el holdout 2023–2024 miden transferencia a una temporada no vista, no ese
acoplamiento.

*Figura 7.1: `reports/figures/pipeline_pronostico.png`*

La fila superior es lo que este TFM mide, ahora también sobre 2021–2026. La inferior no se ha
implementado: requiere un producto de pronóstico, una verificación del DHW previsto y un
umbral de alerta acordado con el gestor. Mientras esa fila no exista, «temporada futura»
significa lo que 6.7.2 y 6.7.10 dicen: un corte retrospectivo frente a Coral Reef Watch.

**Contraste con la modelización jerárquica bayesiana.** El apartado 6.7.7 muestra que la media
aritmética de este extracto no recupera las 28,1 °C / 28,7 °C de Sully et al. (2019), ni
siquiera en Reef_Check. Confrontar SHAP con la partición de varianza de *su* modelo, el
Weibull de su Figura 4 sobre el recorte de 9 215 puntos, y el signo de `ClimSST` condicionado
al efecto de sitio, sigue pendiente.

**Regresión para `[0, 1]` con exceso de ceros.** Conservaría la información que la
discretización descarta. Un experimento preliminar (beta inflada en cero u ordinal) cabe en un
apéndice; no es el núcleo que faltaba.

**Desfase temporal explícito.** Construir $P(\text{severidad en } t+\Delta \mid \text{DHW en } t)$
sobre observaciones repetidas del mismo sitio convertiría la tarea en predicción temporal
genuina, distinta del acoplamiento a un pronóstico ajeno. El Belt 2021–2026 contiene
reencuestas (`site_id` repetido) que permitirían ese diseño sin salir de Reef Check.

## 7.5. Agradecimientos

Se agradece a Reef Check Foundation, a sus capítulos y a los voluntarios que han dedicado
incontables horas a recoger estos datos. Esta memoria no habría sido posible sin su
contribución. Los datos del programa tropical 2021–2026 se usan bajo licencia Creative Commons
Reconocimiento–NoComercial 4.0 Internacional (CC BY-NC 4.0). Cita: Reef Check Foundation.
*Reef Check Global Reef Dataset*. data.reefcheck.org. Consultado el 10 de septiembre de 2026.

Una copia de esta memoria se compartirá con Reef Check Foundation, conforme a las condiciones
de uso del export.

Los censos realizados en Sabah (Malasia) se usan reconociendo al Sabah Biodiversity Centre
(SaBC) como autoridad de licencia para la investigación en biodiversidad en Sabah y a Reef
Check Malaysia (RCM) como titular de la licencia de acceso. Los resultados derivados de esos
datos se compartirán con SaBC.
