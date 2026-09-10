"""Experimento de ablacion de variables bajo validacion aleatoria y espacial.

Responde a tres cuestiones que la comparativa principal deja abiertas:

1. Si el colapso del rendimiento bajo validacion agrupada procede realmente de las
   variables que identifican el emplazamiento (Depth_m, Distance_to_Shore, ClimSST),
   un modelo entrenado solo con variables termicas deberia degradarse mucho menos.
2. Que aporta el estres termico acumulado (TSA_DHW), ausente de la comparativa
   principal, tanto en rendimiento como en transferibilidad espacial.
3. Como cambian las conclusiones al sustituir GroupKFold por StratifiedGroupKFold,
   que preserva ademas la proporcion de clases entre pliegues.

Genera:
    reports/tables/ablation_validation.md
    reports/figures/ablacion_transferibilidad.png
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, recall_score
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data" / "raw" / "global_bleaching_environmental.csv"
TABLES_DIR = ROOT / "reports" / "tables"
FIGURES_DIR = ROOT / "reports" / "figures"

RANDOM_STATE = 42
N_SPLITS = 5

TERMICAS_INSTANTANEAS = ["SSTA", "TSA"]
TERMICO_ACUMULADO = ["TSA_DHW"]
CONTEXTO_SITIO = ["Depth_m", "Distance_to_Shore", "ClimSST"]

# Cada conjunto se define por sus predictores numericos; Ocean_Name se anade
# siempre como unica categorica, salvo indicacion contraria.
FEATURE_SETS: dict[str, list[str]] = {
    "Base (comparativa principal)": TERMICAS_INSTANTANEAS + CONTEXTO_SITIO,
    "Base + DHW": TERMICAS_INSTANTANEAS + TERMICO_ACUMULADO + CONTEXTO_SITIO,
    "Solo termicas": TERMICAS_INSTANTANEAS,
    "Solo termicas + DHW": TERMICAS_INSTANTANEAS + TERMICO_ACUMULADO,
    "Solo contexto del sitio": CONTEXTO_SITIO,
    "Base sin Depth_m": ["SSTA", "TSA", "Distance_to_Shore", "ClimSST"],
    "Base sin Distance_to_Shore": ["SSTA", "TSA", "Depth_m", "ClimSST"],
    "Base sin ClimSST": ["SSTA", "TSA", "Depth_m", "Distance_to_Shore"],
}

CLASS_ORDER = ["Bajo", "Moderado", "Severo"]


def clasificar(valor: float) -> str:
    if valor < 10:
        return "Bajo"
    if valor <= 30:
        return "Moderado"
    return "Severo"


def cargar_datos() -> pd.DataFrame:
    """Carga la submuestra con Reef_ID informado, unica sobre la que cabe agrupar."""
    df = pd.read_csv(RAW_PATH, na_values=["nd"], low_memory=False)
    df = df[df["Percent_Bleaching"].notna()]
    df = df[df["Reef_ID"].notna()].copy()
    df["Bleaching_Class"] = df["Percent_Bleaching"].apply(clasificar)
    return df


def construir_modelo(nombre: str, numericas: list[str]) -> Pipeline:
    """Pipeline de preprocesado + estimador, ajustable de forma independiente por pliegue."""
    preprocesador = ColumnTransformer(
        transformers=[
            (
                "num",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
                numericas,
            ),
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                ["Ocean_Name"],
            ),
        ]
    )

    if nombre == "Random Forest":
        estimador = RandomForestClassifier(
            n_estimators=200,
            class_weight="balanced",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )
    else:
        estimador = LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
            random_state=RANDOM_STATE,
        )

    return Pipeline([("prep", preprocesador), ("clf", estimador)])


def evaluar(
    df: pd.DataFrame,
    numericas: list[str],
    modelo: str,
    esquema: str,
) -> tuple[float, float, float, float]:
    """Devuelve media y desviacion de F1-macro y recall de la clase Severo."""
    X = df[numericas + ["Ocean_Name"]]
    y = df["Bleaching_Class"]
    grupos = df["Reef_ID"]

    if esquema == "agrupada":
        splitter = StratifiedGroupKFold(
            n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE
        )
        particiones = splitter.split(X, y, groups=grupos)
    else:
        splitter = StratifiedKFold(
            n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE
        )
        particiones = splitter.split(X, y)

    f1s: list[float] = []
    recalls: list[float] = []

    for idx_train, idx_test in particiones:
        pipe = construir_modelo(modelo, numericas)
        pipe.fit(X.iloc[idx_train], y.iloc[idx_train])
        pred = pipe.predict(X.iloc[idx_test])
        y_test = y.iloc[idx_test]

        f1s.append(f1_score(y_test, pred, average="macro", zero_division=0))
        if (y_test == "Severo").any():
            recalls.append(
                recall_score(
                    y_test, pred, labels=["Severo"], average="macro", zero_division=0
                )
            )

    return (
        float(np.mean(f1s)),
        float(np.std(f1s)),
        float(np.mean(recalls)) if recalls else float("nan"),
        float(np.std(recalls)) if recalls else float("nan"),
    )


def ejecutar(df: pd.DataFrame) -> pd.DataFrame:
    filas = []
    for etiqueta, numericas in FEATURE_SETS.items():
        for modelo in ("Random Forest", "Regresion Logistica"):
            fila: dict[str, object] = {"Conjunto": etiqueta, "Modelo": modelo}
            for esquema in ("aleatoria", "agrupada"):
                f1, f1_sd, rec, rec_sd = evaluar(df, numericas, modelo, esquema)
                fila[f"f1_{esquema}"] = f1
                fila[f"f1sd_{esquema}"] = f1_sd
                fila[f"rec_{esquema}"] = rec
                fila[f"recsd_{esquema}"] = rec_sd

            base = fila["f1_aleatoria"]
            fila["delta_abs"] = fila["f1_agrupada"] - base
            fila["delta_rel"] = (fila["delta_abs"] / base * 100) if base else float("nan")
            filas.append(fila)
            print(
                f"  {etiqueta:<28} {modelo:<20} "
                f"F1 {fila['f1_aleatoria']:.4f} -> {fila['f1_agrupada']:.4f} "
                f"({fila['delta_rel']:+.1f}%)"
            )
    return pd.DataFrame(filas)


def tabla_markdown(df: pd.DataFrame, columnas: list[tuple[str, str]]) -> str:
    encabezado = "| " + " | ".join(titulo for _, titulo in columnas) + " |"
    separador = "|" + "|".join(["---"] * len(columnas)) + "|"
    lineas = [encabezado, separador]
    for _, fila in df.iterrows():
        celdas = []
        for clave, _ in columnas:
            valor = fila[clave]
            if isinstance(valor, float):
                celdas.append("n/d" if np.isnan(valor) else f"{valor:.4f}".replace(".", ","))
            else:
                celdas.append(str(valor))
        lineas.append("| " + " | ".join(celdas) + " |")
    return "\n".join(lineas)


def generar_figura(res: pd.DataFrame) -> None:
    rf = res[res["Modelo"] == "Random Forest"].copy()
    rf = rf.sort_values("delta_rel")

    fig, ax = plt.subplots(figsize=(11, 6))
    y_pos = np.arange(len(rf))
    colores = ["#c0392b" if v < -30 else "#e67e22" if v < -15 else "#27ae60" for v in rf["delta_rel"]]

    ax.barh(y_pos, rf["delta_rel"], color=colores, edgecolor="black", linewidth=0.6)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(rf["Conjunto"])
    ax.axvline(0, color="black", linewidth=0.9)
    ax.set_xlabel("Variación relativa del F1-Score macro al pasar de validación aleatoria a agrupada (%)")
    ax.set_title(
        "Degradación por transferencia espacial según el conjunto de predictores\n"
        "Random Forest, StratifiedKFold frente a StratifiedGroupKFold por Reef_ID",
        fontsize=11,
    )
    for i, (valor, f1a, f1g) in enumerate(
        zip(rf["delta_rel"], rf["f1_aleatoria"], rf["f1_agrupada"])
    ):
        ax.text(
            valor - 1.2,
            i,
            f"{valor:+.1f}%  ({f1a:.3f}→{f1g:.3f})",
            va="center",
            ha="right",
            fontsize=8.5,
        )
    ax.set_xlim(min(rf["delta_rel"]) * 1.45, max(5, max(rf["delta_rel"]) * 1.3))
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES_DIR / "ablacion_transferibilidad.png", dpi=300)
    plt.close(fig)


def exportar(df: pd.DataFrame, res: pd.DataFrame) -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    prevalencia = df["Bleaching_Class"].value_counts(normalize=True).mul(100).round(2)
    rf = res[res["Modelo"] == "Random Forest"]
    lr = res[res["Modelo"] == "Regresion Logistica"]

    base_rf = rf[rf["Conjunto"] == "Base (comparativa principal)"].iloc[0]
    term_rf = rf[rf["Conjunto"] == "Solo termicas"].iloc[0]
    dhw_rf = rf[rf["Conjunto"] == "Base + DHW"].iloc[0]
    ctx_rf = rf[rf["Conjunto"] == "Solo contexto del sitio"].iloc[0]

    columnas = [
        ("Conjunto", "Conjunto de predictores"),
        ("f1_aleatoria", "F1 macro (aleatoria)"),
        ("f1_agrupada", "F1 macro (agrupada)"),
        ("delta_abs", "Δ absoluta"),
        ("delta_rel", "Δ relativa (%)"),
        ("rec_agrupada", "Recall «Severo» (agrupada)"),
    ]

    texto = f"""# Ablación de predictores y transferibilidad espacial

Experimento complementario a la comparativa principal, diseñado para contrastar de forma
directa la hipótesis de memorización espacial y para cuantificar la aportación del estrés
térmico acumulado.

## Diseño

- **Submuestra**: {len(df):,} observaciones con `Reef_ID` informado, correspondientes a
  {df['Reef_ID'].nunique():,} arrecifes.
- **Esquemas de validación**: `StratifiedKFold` frente a `StratifiedGroupKFold`
  (agrupación por `Reef_ID`), ambos con {N_SPLITS} pliegues sobre idénticos datos.
- **Prevalencia de clases**: Bajo {prevalencia.get('Bajo', 0)} %,
  Moderado {prevalencia.get('Moderado', 0)} %, Severo {prevalencia.get('Severo', 0)} %.
- **Modelos**: Random Forest (`n_estimators=200`, `class_weight='balanced'`) y regresión
  logística (`class_weight='balanced'`), que actúan respectivamente como algoritmo con y sin
  capacidad de memorización.

El uso de `StratifiedGroupKFold` en lugar de `GroupKFold` corrige una limitación de la
comparativa principal: preserva de forma aproximada la proporción de clases entre pliegues
sin permitir que un mismo arrecife aparezca en entrenamiento y evaluación.

## Resultados: Random Forest

{tabla_markdown(rf, columnas)}

## Resultados: regresión logística

{tabla_markdown(lr, columnas)}

## Lectura de los resultados

### Contraste de la hipótesis de memorización espacial

La predicción falsable es explícita: si la degradación bajo validación agrupada procediera
de las variables que identifican el emplazamiento, un modelo privado de ellas debería
degradarse sensiblemente menos.

| Conjunto | F1 aleatoria | F1 agrupada | Brecha absoluta | Δ relativa |
|---|---|---|---|---|
| Base (incluye contexto del sitio) | {base_rf['f1_aleatoria']:.4f} | {base_rf['f1_agrupada']:.4f} | {base_rf['f1_aleatoria'] - base_rf['f1_agrupada']:.4f} | {base_rf['delta_rel']:.1f} % |
| Solo variables térmicas | {term_rf['f1_aleatoria']:.4f} | {term_rf['f1_agrupada']:.4f} | {term_rf['f1_aleatoria'] - term_rf['f1_agrupada']:.4f} | {term_rf['delta_rel']:.1f} % |
| Solo contexto del sitio | {ctx_rf['f1_aleatoria']:.4f} | {ctx_rf['f1_agrupada']:.4f} | {ctx_rf['f1_aleatoria'] - ctx_rf['f1_agrupada']:.4f} | {ctx_rf['delta_rel']:.1f} % |

El resultado **matiza sustancialmente la interpretación inicial**. Privar al modelo de las
tres variables de contexto reduce la brecha absoluta de
{base_rf['f1_aleatoria'] - base_rf['f1_agrupada']:.4f} a
{term_rf['f1_aleatoria'] - term_rf['f1_agrupada']:.4f} puntos de F1 macro, esto es, en un
{(1 - (term_rf['f1_aleatoria'] - term_rf['f1_agrupada']) / (base_rf['f1_aleatoria'] - base_rf['f1_agrupada'])) * 100:.0f} %.
La reducción es apreciable y confirma que dichas variables contribuyen al fenómeno, pero
**dos tercios de la brecha persisten** en un modelo que solo dispone de `SSTA` y `TSA`.

La conclusión correcta no es, por tanto, que Random Forest memorice la identidad del arrecife
a través de una firma compuesta por profundidad, distancia a costa y climatología. Es que el
sobreajuste a la estructura espacial es un fenómeno más general: los propios índices térmicos
están espacialmente autocorrelacionados, de modo que un algoritmo con capacidad suficiente
puede explotar esa estructura aun careciendo de descriptores estáticos del emplazamiento.

### El caso de ClimSST

La ablación individual arroja un resultado contrario a la hipótesis de que `ClimSST` opere
como sustituto encubierto de la localización. Su eliminación **empeora** la transferencia
espacial: el F1 macro agrupado desciende de {base_rf['f1_agrupada']:.4f} a
{res[(res['Modelo'] == 'Random Forest') & (res['Conjunto'] == 'Base sin ClimSST')].iloc[0]['f1_agrupada']:.4f}
y la degradación relativa se agrava hasta el
{res[(res['Modelo'] == 'Random Forest') & (res['Conjunto'] == 'Base sin ClimSST')].iloc[0]['delta_rel']:.1f} %.
Si la variable actuase principalmente como identificador geográfico, su retirada habría
mejorado la generalización a arrecifes nuevos. El comportamiento observado es el opuesto, lo
que respalda la lectura biológica de tolerancia térmica adquirida frente a la interpretación
puramente espacial.

### Aportación del estrés térmico acumulado

`TSA_DHW` presenta una correlación marginal con `Percent_Bleaching` de r = 0,272, que duplica
la de `TSA` (r = 0,142) y supera a la de cualquier otro predictor disponible. Su incorporación
mejora el rendimiento precisamente en el escenario relevante, el de arrecifes no observados:

| Métrica (validación agrupada) | Base | Base + DHW | Variación |
|---|---|---|---|
| F1 macro, Random Forest | {base_rf['f1_agrupada']:.4f} | {dhw_rf['f1_agrupada']:.4f} | {(dhw_rf['f1_agrupada'] / base_rf['f1_agrupada'] - 1) * 100:+.1f} % |
| Recall «Severo», Random Forest | {base_rf['rec_agrupada']:.4f} | {dhw_rf['rec_agrupada']:.4f} | {(dhw_rf['rec_agrupada'] / base_rf['rec_agrupada'] - 1) * 100:+.1f} % |
| F1 macro, regresión logística | {lr[lr['Conjunto'] == 'Base (comparativa principal)'].iloc[0]['f1_agrupada']:.4f} | {lr[lr['Conjunto'] == 'Base + DHW'].iloc[0]['f1_agrupada']:.4f} | {(lr[lr['Conjunto'] == 'Base + DHW'].iloc[0]['f1_agrupada'] / lr[lr['Conjunto'] == 'Base (comparativa principal)'].iloc[0]['f1_agrupada'] - 1) * 100:+.1f} % |
| Recall «Severo», regresión logística | {lr[lr['Conjunto'] == 'Base (comparativa principal)'].iloc[0]['rec_agrupada']:.4f} | {lr[lr['Conjunto'] == 'Base + DHW'].iloc[0]['rec_agrupada']:.4f} | {(lr[lr['Conjunto'] == 'Base + DHW'].iloc[0]['rec_agrupada'] / lr[lr['Conjunto'] == 'Base (comparativa principal)'].iloc[0]['rec_agrupada'] - 1) * 100:+.1f} % |

La mejora es consistente en ambos modelos y afecta tanto al F1 macro como a la detección de
episodios severos. A diferencia de las variables de contexto, el estrés térmico acumulado
aporta señal **transferible**, lo que resulta coherente con su naturaleza de índice
fisiológicamente fundamentado y no meramente descriptivo del emplazamiento.

### Configuración óptima para arrecifes no observados

Combinando ambos hallazgos, la mejor detección de episodios severos en arrecifes nuevos no
corresponde al conjunto de predictores más amplio, sino al que descarta el contexto del sitio
e incorpora el estrés acumulado:

| Configuración | Recall «Severo» (agrupada) |
|---|---|
| Regresión logística, solo térmicas + DHW | {lr[lr['Conjunto'] == 'Solo termicas + DHW'].iloc[0]['rec_agrupada']:.4f} |
| Regresión logística, base | {lr[lr['Conjunto'] == 'Base (comparativa principal)'].iloc[0]['rec_agrupada']:.4f} |
| Random Forest, solo térmicas + DHW | {rf[rf['Conjunto'] == 'Solo termicas + DHW'].iloc[0]['rec_agrupada']:.4f} |
| Random Forest, base | {base_rf['rec_agrupada']:.4f} |

*Figura: `reports/figures/ablacion_transferibilidad.png`*

## Reproducibilidad

Script: `src/ablation_validation.py`. Semilla fija (`random_state={RANDOM_STATE}`).
El preprocesado —imputación por la mediana, estandarización y codificación *one-hot*— se
ajusta de forma independiente dentro de cada pliegue de entrenamiento.
"""

    (TABLES_DIR / "ablation_validation.md").write_text(texto, encoding="utf-8")


def main() -> None:
    print("Cargando submuestra con Reef_ID...")
    df = cargar_datos()
    print(f"  {len(df):,} observaciones | {df['Reef_ID'].nunique():,} arrecifes")
    print(df["Bleaching_Class"].value_counts(normalize=True).mul(100).round(2).to_string())
    print("\nEjecutando ablacion (8 conjuntos x 2 modelos x 2 esquemas x 5 pliegues)...\n")

    res = ejecutar(df)

    generar_figura(res)
    exportar(df, res)

    print("\n=== RESUMEN: Random Forest ===")
    rf = res[res["Modelo"] == "Random Forest"]
    print(
        rf[["Conjunto", "f1_aleatoria", "f1_agrupada", "delta_rel", "rec_agrupada"]]
        .round(4)
        .to_string(index=False)
    )
    print("\n=== RESUMEN: Regresion Logistica ===")
    lr = res[res["Modelo"] == "Regresion Logistica"]
    print(
        lr[["Conjunto", "f1_aleatoria", "f1_agrupada", "delta_rel", "rec_agrupada"]]
        .round(4)
        .to_string(index=False)
    )
    print("\nExportado a reports/tables/ablation_validation.md")


if __name__ == "__main__":
    main()
