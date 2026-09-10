# 4. Marco Teórico

## 4.1. Índices térmicos aplicados al seguimiento de arrecifes

El seguimiento operativo del estrés térmico en arrecifes de coral no se fundamenta en la
temperatura absoluta del agua, sino en índices que expresan la desviación respecto al régimen
térmico habitual de cada emplazamiento. Esta formulación relativa obedece a una razón ecológica
precisa, establecida por Hoegh-Guldberg (1999) y confirmada a escala global por Sully et al.
(2019): las comunidades coralinas se encuentran adaptadas a las condiciones locales, de modo que
una misma temperatura puede resultar inocua en una región y críticamente estresante en otra.

Las definiciones que siguen corresponden a la formulación operativa del programa Coral Reef Watch
de la NOAA, documentada en Liu et al. (2014). Sea $SST_{s,t}$ la temperatura superficial del mar
observada en el emplazamiento $s$ en el instante $t$, y sea $\mathcal{H}_s$ el conjunto de
observaciones históricas que definen el periodo climatológico de referencia.

### 4.1.1. Climatología de referencia (ClimSST)

La climatología $ClimSST$ se define como el valor esperado de la temperatura superficial para un
emplazamiento y un momento del año determinados, estimado sobre el periodo de referencia:

$$
ClimSST_{s,d} = \frac{1}{|\mathcal{Y}|} \sum_{y \in \mathcal{Y}} SST_{s,(y,d)}
$$

donde $d$ denota el día o mes del año y $\mathcal{Y}$ el conjunto de años del periodo
climatológico. Esta variable no describe un evento, sino el **régimen térmico basal** del arrecife,
y su interés radica precisamente en caracterizar el contexto de adaptación de la comunidad. En los
productos de 5 km descritos por Liu et al. (2014), la climatología se derivó del registro climático
Pathfinder (versión 5.2) para el periodo 1985–2012, con un ajuste de sesgo que garantizase la
consistencia con la serie operativa de temperatura superficial.

Reviste particular importancia la **media mensual máxima** (*Maximum Monthly Mean*, MMM), definida
como el valor más elevado de la climatología mensual:

$$
MMM_s = \max_{m \in \{1,\dots,12\}} ClimSST_{s,m}
$$

La MMM constituye una aproximación operativa al umbral térmico por encima del cual la comunidad
coralina local comienza a experimentar estrés fisiológico, en correspondencia con el umbral de
tolerancia descrito por Hoegh-Guldberg (1999).

### 4.1.2. Anomalía térmica superficial (SSTA)

La *Sea Surface Temperature Anomaly* cuantifica la desviación instantánea respecto a la
climatología correspondiente a la misma época del año:

$$
SSTA_{s,t} = SST_{s,t} - ClimSST_{s,d(t)}
$$

Un valor positivo indica aguas anómalamente cálidas para la estación considerada. Al eliminar el
ciclo estacional, $SSTA$ aísla la componente anómala del campo térmico. No obstante, un valor
positivo no implica necesariamente estrés: una anomalía de $+1{,}5$ °C en invierno puede situar la
temperatura muy por debajo del umbral de blanqueamiento. Liu et al. (2014) señalan que la utilidad
principal de este índice reside en la detección precoz de condiciones anómalas **con anterioridad**
a la temporada de blanqueamiento, más que en la cuantificación del estrés efectivo.

### 4.1.3. Anomalía de estrés térmico (TSA)

La *Thermal Stress Anomaly* se define en cambio respecto a la media mensual máxima:

$$
TSA_{s,t} = SST_{s,t} - MMM_s
$$

La diferencia conceptual con $SSTA$ resulta determinante. Mientras que $SSTA$ mide una desviación
respecto a lo esperable en cada estación, $TSA$ mide la **superación del umbral biológico de
tolerancia**. Únicamente los valores positivos de $TSA$ poseen significado en términos de estrés
térmico acumulable, motivo por el cual esta variable presenta habitualmente una asociación más
estrecha con la incidencia del blanqueamiento.

La relación entre ambos índices es directa:

$$
TSA_{s,t} = SSTA_{s,t} + \left( ClimSST_{s,d(t)} - MMM_s \right)
$$

de donde se deduce que, para un mismo emplazamiento, $SSTA$ y $TSA$ difieren en una cantidad que
depende exclusivamente de la época del año. Esta dependencia estructural —consecuencia de que ambos
índices se derivan del mismo campo de temperatura mediante los algoritmos de Liu et al. (2014)—
explica la elevada correlación empírica entre ambas variables, cuantificada en $r = 0{,}543$ en el
conjunto analizado, y anticipa los problemas de colinealidad que se discuten en el capítulo 6.

### 4.1.4. Estrés térmico acumulado (DHW)

El carácter acumulativo del daño fisiológico motiva la definición de índices integrados en el
tiempo. El más extendido es el *Degree Heating Weeks*, que acumula el exceso térmico sobre la MMM
a lo largo de una ventana móvil de doce semanas. Definido el *HotSpot* como

$$
HS_{s,t} = \max\left(0,\; SST_{s,t} - MMM_s\right)
$$

el índice se calcula, para observaciones diarias, mediante

$$
DHW_{s,t} = \frac{1}{7} \sum_{i=0}^{83} HS_{s,t-i} \cdot \mathbb{1}\left[HS_{s,t-i} \geq 1\right]
$$

donde $\mathbb{1}[\cdot]$ es la función indicadora, que restringe la acumulación a los excesos
iguales o superiores a 1 °C. Convencionalmente se considera que valores de $DHW$ próximos a
4 °C·semana anticipan blanqueamiento significativo, y que valores superiores a 8 °C·semana se
asocian a blanqueamiento severo con mortalidad (Liu et al., 2014). Skirving et al. (2020) ofrecen
la descripción operativa vigente de este producto dentro de la versión 3.1 del conjunto CoralTemp,
que armoniza el cálculo de la climatología y de la temperatura en tiempo casi real sobre una única
serie satelital.

La distinción entre $DHW$ y los índices instantáneos es conceptualmente central para este trabajo.
Mientras $SSTA$ y $TSA$ describen el estado térmico en un instante, $DHW$ integra intensidad y
duración, que es la combinación que la fisiología del holobionte determina como relevante
(Hoegh-Guldberg, 1999). Por esa razón `TSA_DHW` forma parte del **conjunto principal de
predictores**, y no de un apéndice experimental: su completitud en el conjunto de origen es del
99,65 %, y el apartado 6.4 cuantifica la señal transferible que aporta. Los umbrales operativos de
4 y 8 °C·semana se emplean además como **regla de referencia sin entrenamiento** frente a la que
debe justificarse cualquier clasificador (apartado 6.3).

## 4.2. Algoritmos de clasificación

Sea $\mathcal{D} = \{(\mathbf{x}_i, y_i)\}_{i=1}^{n}$ el conjunto de entrenamiento, donde
$\mathbf{x}_i \in \mathbb{R}^p$ representa el vector de predictores e
$y_i \in \{1, \dots, K\}$ la clase de severidad, con $K = 3$ en el presente estudio.

### 4.2.1. Regresión logística multinomial

La regresión logística multinomial modela la probabilidad de pertenencia a cada clase mediante la
función *softmax* aplicada a una combinación lineal de los predictores:

$$
P(y = k \mid \mathbf{x}) = \frac{\exp\left(\boldsymbol{\beta}_k^{\top}\mathbf{x} + \beta_{0k}\right)}
{\displaystyle\sum_{j=1}^{K} \exp\left(\boldsymbol{\beta}_j^{\top}\mathbf{x} + \beta_{0j}\right)}
$$

Los parámetros se estiman minimizando la entropía cruzada penalizada:

$$
\mathcal{L}(\boldsymbol{\beta}) = -\sum_{i=1}^{n} \omega_{y_i} \sum_{k=1}^{K}
\mathbb{1}[y_i = k] \log P(y = k \mid \mathbf{x}_i)
\;+\; \frac{1}{2C} \|\boldsymbol{\beta}\|_2^2
$$

donde $C$ es el parámetro de regularización y $\omega_k$ el peso asignado a la clase $k$. La
estrategia de compensación del desbalanceo empleada asigna

$$
\omega_k = \frac{n}{K \cdot n_k}
$$

siendo $n_k$ el número de observaciones de la clase $k$, de modo que las clases minoritarias
reciben un peso inversamente proporcional a su frecuencia.

La propiedad relevante de este modelo a efectos del presente trabajo es su **restricción
estructural**: la frontera de decisión es una función lineal de los predictores en el espacio de
las log-probabilidades relativas. Esta rigidez limita su capacidad de ajuste, pero le impide
simultáneamente memorizar combinaciones específicas de valores, característica cuya relevancia se
manifiesta en el análisis de transferibilidad espacial del capítulo 6.

### 4.2.2. Random Forest

Random Forest (Breiman, 2001) construye un conjunto de $B$ árboles de decisión ajustados sobre
muestras *bootstrap* del conjunto de entrenamiento. La predicción agregada se obtiene promediando
las probabilidades estimadas por los árboles individuales:

$$
\hat{P}(y = k \mid \mathbf{x}) = \frac{1}{B} \sum_{b=1}^{B} \hat{P}_b(y = k \mid \mathbf{x})
$$

Cada árbol selecciona en cada nodo la partición que maximiza la reducción de impureza, medida
habitualmente mediante el índice de Gini:

$$
G(\mathcal{N}) = 1 - \sum_{k=1}^{K} p_{k}^{2}(\mathcal{N})
$$

$$
\Delta G = G(\mathcal{N}) - \frac{n_{\text{izq}}}{n_{\mathcal{N}}} G(\mathcal{N}_{\text{izq}})
- \frac{n_{\text{der}}}{n_{\mathcal{N}}} G(\mathcal{N}_{\text{der}})
$$

La descorrelación entre árboles se logra mediante dos mecanismos: el remuestreo *bootstrap* y la
selección aleatoria de un subconjunto de $m \approx \sqrt{p}$ predictores candidatos en cada nodo.
Breiman (2001) demostró que el error de generalización del conjunto converge casi seguramente a un
límite al aumentar $B$, y que dicho límite depende de dos magnitudes: la fuerza individual $s$ de
los árboles y la correlación media $\bar{\rho}$ entre ellos. La cota superior del error verifica

$$
PE^{*} \leq \frac{\bar{\rho}\,\left(1 - s^{2}\right)}{s^{2}}
$$

expresión que formaliza el compromiso central del algoritmo: la aleatorización en la selección de
variables reduce $\bar{\rho}$ a costa de disminuir $s$, y la mejora neta depende del equilibrio
entre ambos efectos.

Debe destacarse que, en ausencia de restricción de profundidad, cada árbol puede particionar el
espacio hasta aislar observaciones individuales. Esta capacidad, que confiere al algoritmo una
notable flexibilidad, constituye asimismo el sustrato del fenómeno de memorización analizado en el
capítulo 6: si un conjunto reducido de variables identifica de manera unívoca un emplazamiento, los
árboles pueden construir hojas específicas para él. No es casual que Ploton et al. (2020) eligieran
precisamente Random Forest para ilustrar el colapso del rendimiento bajo validación espacial.

### 4.2.3. XGBoost

El marco general de la potenciación del gradiente fue formulado por Friedman (2001), quien
interpretó el ajuste aditivo por etapas como un **descenso de gradiente en el espacio de
funciones**: en cada iteración se incorpora un aprendiz débil ajustado al gradiente negativo de la
función de pérdida evaluado sobre el modelo acumulado hasta ese momento. Esta formulación permite
optimizar pérdidas arbitrarias diferenciables y separa conceptualmente la función objetivo del
tipo de aprendiz empleado.

XGBoost (Chen y Guestrin, 2016) implementa esta idea añadiendo una expansión de segundo orden de la
pérdida y un término explícito de regularización sobre la complejidad del árbol. La predicción tras
$M$ iteraciones se expresa como

$$
\hat{y}_i^{(M)} = \sum_{m=1}^{M} f_m(\mathbf{x}_i), \qquad f_m \in \mathcal{F}
$$

donde $\mathcal{F}$ denota el espacio de los árboles de regresión. La función objetivo incorpora un
término explícito de regularización:

$$
\mathcal{L} = \sum_{i=1}^{n} l\left(y_i, \hat{y}_i\right)
+ \sum_{m=1}^{M} \Omega(f_m), \qquad
\Omega(f) = \gamma T + \frac{1}{2}\lambda \|\mathbf{w}\|^2
$$

siendo $T$ el número de hojas del árbol y $\mathbf{w}$ el vector de pesos asignados a las mismas.

La particularidad del algoritmo reside en la aproximación de segundo orden del objetivo. Definidos
el gradiente y el hessiano de la pérdida,

$$
g_i = \frac{\partial l(y_i, \hat{y}^{(m-1)})}{\partial \hat{y}^{(m-1)}}, \qquad
h_i = \frac{\partial^2 l(y_i, \hat{y}^{(m-1)})}{\partial (\hat{y}^{(m-1)})^2}
$$

el peso óptimo de la hoja $j$, con conjunto de observaciones $I_j$, resulta

$$
w_j^{*} = -\frac{\sum_{i \in I_j} g_i}{\sum_{i \in I_j} h_i + \lambda}
$$

y la ganancia asociada a una partición candidata viene dada por

$$
\mathcal{G} = \frac{1}{2}\left[
\frac{\left(\sum_{i \in I_L} g_i\right)^2}{\sum_{i \in I_L} h_i + \lambda} +
\frac{\left(\sum_{i \in I_R} g_i\right)^2}{\sum_{i \in I_R} h_i + \lambda} -
\frac{\left(\sum_{i \in I} g_i\right)^2}{\sum_{i \in I} h_i + \lambda}
\right] - \gamma
$$

La tasa de aprendizaje $\eta$ (`learning_rate`) atenúa la contribución de cada árbol,
$\hat{y}^{(m)} = \hat{y}^{(m-1)} + \eta f_m(\mathbf{x})$, mientras que `max_depth` acota la
profundidad. Ambos hiperparámetros fueron objeto de optimización en el presente trabajo.

Entre las aportaciones sistémicas descritas por Chen y Guestrin (2016) figuran el algoritmo
consciente de la dispersión (*sparsity-aware*), que aprende una dirección por defecto para los
valores ausentes en cada nodo, y el esbozo cuantílico ponderado (*weighted quantile sketch*) para
la búsqueda aproximada de puntos de corte. La primera resulta especialmente pertinente en datos
ecológicos, donde la ausencia de valor rara vez es aleatoria.

### 4.2.4. LightGBM

LightGBM, propuesto por Ke et al. (2017), comparte el fundamento de la potenciación del gradiente e
introduce tres modificaciones orientadas a la eficiencia computacional. La motivación declarada por
los autores es el cuello de botella que supone, en las implementaciones convencionales, la
necesidad de recorrer todas las observaciones para cada variable con el fin de estimar la ganancia
de información de cada punto de corte candidato.

En primer lugar, el **crecimiento por hojas** (*leaf-wise*): en lugar de expandir simultáneamente
todos los nodos de un nivel, el algoritmo selecciona en cada iteración la hoja cuya división
produce la mayor reducción de pérdida. Esta estrategia alcanza menor error con igual número de
nodos, si bien tiende a generar árboles asimétricos y más propensos al sobreajuste.

En segundo lugar, el **muestreo unilateral basado en el gradiente** (*Gradient-based One-Side
Sampling*, GOSS), que conserva las observaciones con gradiente elevado —peor ajustadas— y
submuestrea aleatoriamente las restantes. Ke et al. (2017) demuestran que, dado que las
observaciones de mayor gradiente dominan el cálculo de la ganancia de información, este esquema
mantiene una estimación precisa con un tamaño muestral sensiblemente menor.

En tercer lugar, la **agrupación exclusiva de variables** (*Exclusive Feature Bundling*, EFB), que
combina predictores mutuamente excluyentes —situación frecuente tras una codificación *one-hot*—
en una única variable, disminuyendo la dimensionalidad efectiva. Los autores prueban que la
obtención del agrupamiento óptimo es un problema NP-difícil, si bien una heurística voraz alcanza
una aproximación suficiente en la práctica.

La combinación de ambas técnicas acelera el entrenamiento hasta en un factor de veinte respecto de
la potenciación del gradiente convencional, con una exactitud comparable (Ke et al., 2017). En el
presente trabajo LightGBM **no se reentrena** bajo validación agrupada ni entra en el análisis
SHAP: figura únicamente en la comparativa aleatoria histórica del apartado 6.3.1, con
hiperparámetros por defecto y sin `TSA_DHW`.

El tratamiento del desbalanceo se activa mediante el parámetro `is_unbalance`, que reescala
automáticamente los pesos en función de la frecuencia de cada clase.

## 4.3. Explicabilidad aditiva mediante valores SHAP

### 4.3.1. Modelos de atribución aditiva

Los algoritmos de conjunto descritos en el apartado anterior producen funciones de decisión cuya
inspección directa no resulta practicable. Lundberg y Lee (2017) propusieron un marco unificado que
resuelve esta dificultad mediante la noción de **modelo de explicación**: una aproximación local e
interpretable $g$ del modelo original $f$ en el entorno de una observación concreta $\mathbf{x}$.

Formalmente, un método de atribución aditiva de variables adopta la forma

$$
g(\mathbf{z}') = \phi_0 + \sum_{j=1}^{M} \phi_j\, z'_j,
\qquad \mathbf{z}' \in \{0,1\}^{M}
$$

donde $\mathbf{z}'$ es un vector binario que indica la presencia o ausencia de cada variable,
$M$ el número de predictores, $\phi_0$ el valor esperado de la salida del modelo y
$\phi_j \in \mathbb{R}$ la contribución atribuida a la variable $j$. Lundberg y Lee (2017)
demostraron que seis métodos de interpretabilidad previamente propuestos de forma independiente
—entre ellos LIME y DeepLIFT— pertenecen a esta misma clase.

### 4.3.2. Los valores de Shapley como solución única

La aportación teórica central del trabajo consiste en establecer que, dentro de esta clase, existe
una **única** asignación de coeficientes que satisface simultáneamente tres propiedades deseables:

- **Precisión local** (*local accuracy*): la suma de las atribuciones reproduce exactamente la
  salida del modelo, $f(\mathbf{x}) = \phi_0 + \sum_{j} \phi_j$.
- **Ausencia** (*missingness*): una variable no presente en la observación recibe atribución nula.
- **Consistencia** (*consistency*): si al modificar un modelo la contribución marginal de una
  variable aumenta o se mantiene para toda posible coalición, su atribución no puede disminuir.

Dicha solución única corresponde a los **valores de Shapley** de la teoría de juegos cooperativos.
Shapley (1953) planteó el problema de repartir la ganancia total de una coalición entre sus
participantes y demostró que los axiomas de eficiencia, simetría, jugador nulo y aditividad
determinan una asignación única, dada por la contribución marginal media de cada jugador sobre
todos los órdenes posibles de formación de la coalición. Lundberg y Lee (2017) establecen la
correspondencia entre ambos marcos identificando las variables del modelo con los jugadores y la
predicción con la ganancia a repartir:

$$
\phi_j = \sum_{S \subseteq F \setminus \{j\}}
\frac{|S|!\,\left(|F| - |S| - 1\right)!}{|F|!}
\left[ f_{S \cup \{j\}}\!\left(\mathbf{x}_{S \cup \{j\}}\right) - f_{S}\!\left(\mathbf{x}_{S}\right) \right]
$$

donde $F$ denota el conjunto completo de predictores y $S$ un subconjunto cualquiera que excluye la
variable $j$. La expresión promedia la contribución marginal de $j$ sobre todos los órdenes
posibles de incorporación de las variables, ponderando cada coalición por la probabilidad de que se
forme bajo una permutación aleatoria.

El cálculo exacto exige evaluar $2^{|F|}$ subconjuntos, lo que resulta inabordable salvo para
dimensionalidades reducidas. Para modelos basados en árboles, Lundberg et al. (2020) desarrollaron
la variante **TreeSHAP**, que reduce esta complejidad a un orden polinómico $O(T L D^{2})$, siendo
$T$ el número de árboles, $L$ el número máximo de hojas y $D$ la profundidad, lo que permite la
explicación exacta de conjuntos de datos de gran tamaño. El competidor oficial —Random Forest con
`max_depth` = 8— cae de lleno en ese régimen: la profundidad acotada hace el cálculo exacto
tratable, y no es necesario sustituirlo por XGBoost para poder explicarlo.

Lundberg et al. (2020) aportan además el argumento que justifica prescindir de las medidas de
importancia nativas de los modelos de árboles: tanto la basada en la reducción de impureza como la
derivada de la frecuencia de división resultan **inconsistentes**, en el sentido de que una
modificación del modelo que incremente la dependencia real respecto de una variable puede reducir
su importancia declarada. Los valores de Shapley, al satisfacer por construcción la propiedad de
consistencia, no presentan este comportamiento.

### 4.3.3. Interpretación de la importancia global y limitaciones

La agregación de los valores locales proporciona una medida de importancia global de cada
predictor:

$$
I_j = \frac{1}{n} \sum_{i=1}^{n} \left| \phi_j^{(i)} \right|
$$

y el signo de la correlación entre el valor de la variable y su atribución,
$\mathrm{corr}\left(x_j^{(i)}, \phi_j^{(i)}\right)$, informa sobre la dirección predominante del
efecto.

Debe advertirse, no obstante, una limitación de particular relevancia para este trabajo. Cuando dos
predictores están correlacionados, el reparto de la contribución conjunta entre ambos **no es
identificable de forma unívoca**: los valores de Shapley distribuyen la atribución conforme a la
estructura concreta del modelo ajustado, de manera que una variable puede recibir un signo contrario
al de su asociación marginal con la respuesta. Este fenómeno resulta determinante en la
interpretación del bloque $SSTA$–$TSA$–$TSA_{DHW}$, y se analiza en detalle en el apartado 6.6.3.

El origen formal de esta indeterminación fue caracterizado por Aas, Jullum y Løland (2021). La formulación
original de KernelSHAP aproxima el valor de la función sobre un subconjunto $S$ integrando las
variables ausentes conforme a su **distribución marginal**, lo que equivale a suponer independencia
entre predictores. Cuando tal supuesto no se cumple, el procedimiento evalúa el modelo sobre
combinaciones de valores que no pertenecen al soporte de la distribución conjunta —por ejemplo, una
anomalía térmica elevada acompañada de una anomalía de estrés nula—, y las atribuciones resultantes
pueden desviarse apreciablemente de los valores de Shapley definidos sobre la distribución
condicional. Los autores proponen estimaciones alternativas basadas en dicha distribución
condicional y muestran que la discrepancia crece con la magnitud de la correlación.

De ello se sigue una regla de lectura que se aplica de forma sistemática en el capítulo 6: en
presencia de predictores fuertemente correlacionados, la interpretación debe recaer sobre la
**contribución agregada del bloque** de variables relacionadas y no sobre el reparto interno entre
ellas, que es un artefacto de la estructura concreta del modelo ajustado.

## 4.4. Métricas de evaluación en problemas desbalanceados

Sea la matriz de confusión de un problema con $K$ clases, y denotemos por $TP_k$, $FP_k$ y $FN_k$
los verdaderos positivos, falsos positivos y falsos negativos de la clase $k$.

### 4.4.1. Precisión, exhaustividad y F1-Score

$$
\text{Precision}_k = \frac{TP_k}{TP_k + FP_k}, \qquad
\text{Recall}_k = \frac{TP_k}{TP_k + FN_k}
$$

$$
F1_k = 2 \cdot \frac{\text{Precision}_k \cdot \text{Recall}_k}
{\text{Precision}_k + \text{Recall}_k}
$$

La precisión responde a la pregunta «de las observaciones clasificadas como blanqueamiento severo,
¿qué proporción lo era realmente?», mientras que la exhaustividad responde a «de los eventos
severos ocurridos, ¿qué proporción fue detectada?». En el contexto de la alerta temprana, la
segunda cuestión resulta prioritaria, dado que el coste de un falso negativo —no activar el
protocolo de vigilancia ante un evento real— supera al de una falsa alarma.

### 4.4.2. Promediado macro

El promedio macro asigna idéntico peso a todas las clases con independencia de su frecuencia:

$$
F1_{\text{macro}} = \frac{1}{K} \sum_{k=1}^{K} F1_k
$$

Esta propiedad lo hace preferible al promedio ponderado en problemas desbalanceados. Considérese
un clasificador que asignase sistemáticamente la clase mayoritaria en el conjunto analizado: su
exactitud alcanzaría el 78,93 %, mientras que su $F1_{\text{macro}}$ sería

$$
F1_{\text{macro}} = \frac{1}{3}\left(0{,}88 + 0 + 0\right) \approx 0{,}29
$$

lo que refleja adecuadamente su nula utilidad práctica. Por este motivo el $F1_{\text{macro}}$ se
adopta como criterio principal de comparación entre modelos.

### 4.4.3. Área bajo la curva ROC en problemas multiclase

La curva ROC representa la tasa de verdaderos positivos frente a la tasa de falsos positivos al
recorrer el umbral de decisión. Su área,

$$
\text{AUC}_k = \int_{0}^{1} \text{TPR}_k\left(\text{FPR}_k^{-1}(u)\right) \, du
$$

admite la interpretación de probabilidad de que el modelo asigne mayor puntuación a una
observación positiva escogida al azar que a una negativa. La extensión multiclase adoptada es la
formulación *One-vs-Rest* con promediado ponderado por la prevalencia de cada clase:

$$
\text{AUC}_{\text{OvR}} = \sum_{k=1}^{K} \frac{n_k}{n} \cdot \text{AUC}_k
$$

Su principal ventaja reside en la independencia respecto al umbral de clasificación, lo que
permite evaluar la capacidad discriminante intrínseca del modelo.

Esta métrica exige, sin embargo, una cautela interpretativa que resulta pertinente en el presente
trabajo. Saito y Rehmsmeier (2015) demostraron que, ante un desbalance acusado, la curva ROC
transmite una impresión excesivamente optimista del rendimiento: al calcularse la tasa de falsos
positivos sobre el total de negativos —muy numerosos—, un incremento sustancial del número absoluto
de falsas alarmas apenas desplaza la curva. Los autores muestran que la representación de precisión
frente a exhaustividad, cuyo eje horizontal se refiere únicamente a la clase minoritaria, refleja
con mayor fidelidad la utilidad del clasificador en tales escenarios.

Esta observación explica una discordancia que se documenta en el capítulo 6: varios modelos
alcanzan valores de $\text{AUC}_{\text{OvR}}$ próximos a 0,9 mientras recuperan menos de un tercio
de los episodios severos. Por este motivo el AUC se reporta como métrica complementaria, y la
valoración de la utilidad práctica descansa sobre el $F1_{\text{macro}}$ y, de forma específica,
sobre la exhaustividad de la clase «Severo».

## 4.5. Autocorrelación espacial, pseudorreplicación y validación agrupada

### 4.5.1. Dependencia espacial en datos ecológicos

Los métodos estadísticos convencionales de estimación del error de generalización descansan sobre
el supuesto de que las observaciones son independientes e idénticamente distribuidas. En el
análisis de datos ecológicos este supuesto se incumple sistemáticamente, conforme al principio
enunciado por Tobler (1970) y conocido como **primera ley de la geografía**: todo guarda relación
con todo lo demás, pero las cosas próximas mantienen una relación más estrecha que las distantes.
Roberts et al. (2017) documentan que esta dependencia afecta, además de a la dimensión espacial, a
las estructuras temporal, jerárquica —de efectos aleatorios— y filogenética.

Legendre (1993) precisó una distinción conceptual necesaria para interpretar correctamente este
fenómeno. La estructura espacial observada puede obedecer a dos orígenes: la **dependencia
espacial inducida**, en la que la respuesta hereda la estructura de variables ambientales que a su
vez están autocorrelacionadas, y la **autocorrelación espacial verdadera**, generada por procesos
endógenos de contagio o dispersión. Ambas producen un patrón agregado semejante, pero solo la
primera resulta explicable mediante predictores ambientales. El autor argumentó asimismo que esta
estructura no debe tratarse únicamente como una violación de supuestos a corregir, sino como
información ecológica con valor propio. Esta distinción es la que se dirime experimentalmente en el
apartado 6.7.1, al contrastar si la degradación del rendimiento bajo validación agrupada procede de
las variables de contexto del emplazamiento o de la propia autocorrelación de los índices térmicos.

La magnitud de esta dependencia puede cuantificarse mediante el índice de Moran (Moran, 1950):

$$
I = \frac{n}{W} \cdot
\frac{\displaystyle\sum_{i=1}^{n}\sum_{j=1}^{n} w_{ij}\,(x_i - \bar{x})(x_j - \bar{x})}
{\displaystyle\sum_{i=1}^{n} (x_i - \bar{x})^2}, \qquad
W = \sum_{i=1}^{n}\sum_{j=1}^{n} w_{ij}
$$

donde $w_{ij}$ representa el peso de vecindad entre las observaciones $i$ y $j$. Valores de $I$
significativamente superiores a su esperanza bajo independencia, $\mathbb{E}[I] = -1/(n-1)$,
indican agrupamiento espacial.

Este índice no se deja aquí como formalismo. Sobre los 11 068 emplazamientos del conjunto, con
$k = 8$ vecinos más próximos y 999 permutaciones, el blanqueamiento observado alcanza
$I = 0{,}371$, la anomalía de estrés térmico $I = 0{,}330$ y el estrés acumulado
$I = 0{,}528$ ($p = 0{,}001$ en los tres casos). Los predictores térmicos están, por tanto,
**más agrupados espacialmente que la propia respuesta**. Esa ordenación explica por qué la ablación
de las variables de contexto no elimina la brecha entre validación aleatoria y agrupada: no existe
un subconjunto de predictores espacialmente neutro al que replegarse. El detalle del cálculo se
presenta en el apartado 6.1.4.

### 4.5.2. Pseudorreplicación

Hurlbert (1984) definió la **pseudorreplicación** como el empleo de estadística inferencial para
contrastar efectos con datos en los que las réplicas no son estadísticamente independientes o los
tratamientos no están replicados. En terminología de análisis de la varianza, consiste en evaluar
un efecto con un término de error inapropiado para la hipótesis considerada.

La revisión de 176 estudios experimentales publicados entre 1960 y 1984 reveló que el 27 % de ellos
—el 48 % de los que aplicaban estadística inferencial— incurrían en esta práctica, con incidencia
especialmente elevada, señaló el autor, en los estudios de **bentos marino**. La consecuencia
estadística es que el tamaño muestral efectivo resulta inferior al número nominal de registros y que
los intervalos de confianza calculados bajo el supuesto de independencia resultan indebidamente
estrechos.

En el conjunto analizado en este trabajo, las 34 515 observaciones proceden de 11 068
emplazamientos distintos, lo que arroja una media de 3,1 muestreos por arrecife. El número efectivo
de unidades independientes es, por tanto, sustancialmente menor que el número de filas del conjunto
de datos, configurando exactamente el escenario descrito por Hurlbert (1984).

### 4.5.3. Fuga de información a nivel de grupo

La consecuencia de mayor calado para el modelado predictivo se produce cuando los predictores
contienen información que identifica de manera aproximadamente unívoca la unidad espacial.
Formalmente, si existe una aplicación $\phi: \mathbb{R}^p \rightarrow \mathcal{S}$ tal que
$\phi(\mathbf{x}_i) \approx s_i$ para el emplazamiento $s_i$, entonces un modelo con capacidad
suficiente puede aprender la aplicación compuesta

$$
\mathbf{x} \;\longmapsto\; \phi(\mathbf{x}) \;\longmapsto\; \hat{y}
$$

esto es, predecir a partir de la identidad del emplazamiento en lugar de hacerlo a partir del
proceso ecológico subyacente. Bajo una partición aleatoria, en la que el mismo emplazamiento
aparece en ambos subconjuntos, esta estrategia produce métricas elevadas que no reflejan capacidad
alguna de generalización a localizaciones nuevas.

Roberts et al. (2017) identifican precisamente este mecanismo al advertir que los datos
estructurados «proporcionan amplia oportunidad de sobreajuste con predictores no causales», y
subrayan que el problema persiste aunque se recurra a modelos autorregresivos, mínimos cuadrados
generalizados o modelos mixtos, puesto que afecta al procedimiento de **evaluación** y no
únicamente al de ajuste.

Esta situación se denomina **fuga de información a nivel de grupo** (*group-level leakage*) y debe
distinguirse conceptualmente del *Data Leakage* clásico. En este último, los estadísticos de
preprocesado se estiman sobre datos de prueba; en aquél, el preprocesado puede ser
metodológicamente impecable y persistir, no obstante, la dependencia entre particiones a través de
la estructura de los propios datos.

### 4.5.4. Validación cruzada agrupada

La corrección consiste en imponer que las particiones respeten la estructura de agrupación. Sea
$g_i \in \mathcal{G}$ el grupo al que pertenece la observación $i$ —en el presente caso, el
identificador de emplazamiento (`Site_ID`)—. El procedimiento `StratifiedGroupKFold` construye una
partición $\{\mathcal{F}_1, \dots, \mathcal{F}_V\}$ del conjunto de datos que verifica

$$
\forall\, v \neq v': \quad
\{g_i : i \in \mathcal{F}_v\} \cap \{g_i : i \in \mathcal{F}_{v'}\} = \emptyset
$$

es decir, ningún grupo aparece en dos pliegues distintos. En consecuencia, al evaluar sobre el
pliegue $\mathcal{F}_v$, la totalidad de sus emplazamientos resulta completamente desconocida para
el modelo entrenado sobre el resto. Esta construcción constituye una forma de *block
cross-validation* en el sentido de Roberts et al. (2017), quienes concluyen, a partir de
simulaciones y estudios de caso, que la validación por bloques resulta «casi universalmente más
apropiada» que la aleatoria cuando el objetivo es predecir sobre datos nuevos o seleccionar
predictores causales. El identificador de arrecife (`Reef_ID`) no se emplea como unidad de
agrupación en el experimento principal: en este conjunto cubre únicamente Reef_Check, como se
detalla en el apartado 5.4.2.

La estimación del error se obtiene promediando sobre los pliegues:

$$
\widehat{\text{Err}}_{\text{grupo}} = \frac{1}{V} \sum_{v=1}^{V}
\mathcal{M}\left(\mathcal{F}_v; \; \hat{f}^{(-v)}\right)
$$

donde $\hat{f}^{(-v)}$ denota el modelo ajustado excluyendo el pliegue $v$ y $\mathcal{M}$ la
métrica de evaluación.

La diferencia entre ambas estimaciones,

$$
\Delta = \widehat{\text{Err}}_{\text{grupo}} - \widehat{\text{Err}}_{\text{aleatoria}}
$$

admite una interpretación directa: cuantifica la fracción del rendimiento atribuible al
reconocimiento de unidades espaciales previamente observadas. Su magnitud constituye, por tanto,
una medida del grado de memorización espacial del modelo. Ploton et al. (2020) emplearon esta misma
lógica comparativa para demostrar que un modelo de cartografía de biomasa forestal aparentemente
capaz de explicar más de la mitad de la varianza carecía en realidad de capacidad predictiva fuera
del rango de autocorrelación de los datos. El análisis de esta brecha vertebra los resultados
expuestos en el capítulo 6.

El procedimiento principal es `StratifiedGroupKFold`: agrupa por emplazamiento y, en la medida en
que los grupos lo permiten, preserva las proporciones de clase entre pliegues. `GroupKFold`, que
respeta los grupos pero no la estratificación, se retiene únicamente como referencia conceptual.

### 4.5.5. Agrupación por unidad frente a bloqueo geográfico

La agrupación por identificador de unidad, adoptada en este trabajo, constituye una de las
estrategias posibles dentro de un espectro más amplio. Valavi, Elith, Lahoz-Monfort y Guillera-Arroita (2019) sistematizan las
alternativas disponibles en su paquete `blockCV` y distinguen tres procedimientos de asignación de
pliegues: el **bloqueo espacial**, que define bloques rectangulares o hexagonales de tamaño
determinado a partir del rango de autocorrelación estimado en las variables; el **bloqueo
ambiental**, que agrupa las observaciones por similitud en el espacio de predictores con
independencia de su proximidad geográfica; y la exclusión por **buffer** o *leave-one-out*
espacial, que retira de cada entrenamiento las observaciones situadas a menos de una distancia dada
del punto evaluado. Los autores subrayan que la elección del tamaño de bloque debe orientarse por
el rango de autocorrelación medido, y no fijarse arbitrariamente.

Situada en este marco, la agrupación por `Site_ID` equivale a un bloqueo de grano fino: separa las
réplicas de un mismo emplazamiento, pero no impide que sitios contiguos —y por tanto sometidos a un
régimen térmico prácticamente idéntico— queden repartidos entre entrenamiento y prueba. Por ello el
diseño de validación del apartado 5.4 añade dos esquemas de grano más grueso: validación cruzada
por ecorregión y *leave-one-ocean-out*. La cifra de «cuenca nueva» es la que debe comunicarse
cuando el gestor pregunta por un arrecife fuera de las regiones observadas.

Un desarrollo posterior de esta línea, propuesto por Meyer y Pebesma (2021), consiste en delimitar
el **área de aplicabilidad** del modelo: en lugar de resumir el rendimiento en una única cifra, los
autores definen un índice de disimilitud que mide, para cada localización objetivo, la distancia al
dato de entrenamiento más próximo en el espacio de predictores ponderado por su relevancia, y
restringen la validez de la estimación de error a la región que queda por debajo de un umbral de
dicho índice. Esta aproximación resulta especialmente pertinente para la pregunta que motiva el
presente trabajo —determinar sobre qué arrecifes nuevos cabe confiar en la predicción— y se
implementa sobre el *leave-one-ocean-out* en los apartados 5.4.7 y 6.7.6.
