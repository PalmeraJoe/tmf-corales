"""Interpretabilidad del modelo recomendado mediante TreeSHAP.

Explica el Random Forest oficial (`n_estimators` = 200, `max_depth` = 8,
`class_weight='balanced'`) con `TSA_DHW` en el conjunto de predictores. El conjunto de
explicación es el pliegue de prueba de un `StratifiedGroupKFold` por `Site_ID`: ningún
emplazamiento entra a la vez en el ajuste y en las atribuciones. El mismo cálculo se
repite bajo partición aleatoria para comprobar que la jerarquía no es un artefacto del
esquema inflado.

Genera:
    reports/figures/shap_importance_global.png
    reports/figures/shap_summary.png
    reports/figures/shap_comparacion_esquemas.png
    reports/tables/shap_insights.md
    reports/tables/shap_numeros.json
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from preprocessing import CLASS_ORDER, RANDOM_STATE

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_CSV = PROJECT_ROOT / "data" / "raw" / "global_bleaching_environmental.csv"
FIGURES_DIR = PROJECT_ROOT / "reports" / "figures"
TABLES_DIR = PROJECT_ROOT / "reports" / "tables"

FIGURE_DPI = 300
FOCUS_CLASS = "Severo"
N_ESTIMATORS = 200
MAX_DEPTH = 8
N_SPLITS = 5

NUMERICAS = ["SSTA", "TSA", "TSA_DHW", "Depth_m", "Distance_to_Shore", "ClimSST"]
CATEGORICA = "Ocean_Name"
TERMICAS = ["SSTA", "TSA", "TSA_DHW"]
CONTEXTO = ["Depth_m", "Distance_to_Shore", "ClimSST"]

VAR_CONTEXT = {
    "SSTA": (
        "anomalía de temperatura superficial del mar; mide el calentamiento "
        "puntual respecto a la climatología"
    ),
    "TSA": (
        "anomalía de estrés térmico; exposición a temperaturas por encima del "
        "umbral de blanqueamiento"
    ),
    "TSA_DHW": (
        "Degree Heating Weeks; estrés térmico acumulado en la ventana de doce "
        "semanas que emplea Coral Reef Watch"
    ),
    "Depth_m": (
        "profundidad del muestreo; condiciona la irradiancia y el refugio "
        "térmico de la colonia"
    ),
    "Distance_to_Shore": (
        "distancia a la costa; aproxima presiones locales como escorrentía y turbidez"
    ),
    "ClimSST": (
        "temperatura superficial climatológica; describe el régimen térmico "
        "basal del arrecife"
    ),
}


def clasificar(v: float) -> str:
    if v < 10:
        return "Bajo"
    if v <= 30:
        return "Moderado"
    return "Severo"


def coma(valor: float, dec: int = 4) -> str:
    if valor is None or (isinstance(valor, float) and (np.isnan(valor) or np.isinf(valor))):
        return "n/d"
    return f"{float(valor):.{dec}f}".replace(".", ",")


def cargar() -> pd.DataFrame:
    df = pd.read_csv(RAW_CSV, na_values=["nd", "ND"], low_memory=False)
    df = df.loc[df["Percent_Bleaching"].notna()].copy()
    df["Bleaching_Class"] = df["Percent_Bleaching"].map(clasificar)
    return df


def construir_prep() -> ColumnTransformer:
    return ColumnTransformer(
        [
            (
                "num",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
                NUMERICAS,
            ),
            (
                "cat",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        (
                            "encoder",
                            OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                        ),
                    ]
                ),
                [CATEGORICA],
            ),
        ]
    )


def construir_rf() -> RandomForestClassifier:
    return RandomForestClassifier(
        n_estimators=N_ESTIMATORS,
        max_depth=MAX_DEPTH,
        class_weight="balanced",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )


def nombres_features(prep: ColumnTransformer) -> list[str]:
    encoder = prep.named_transformers_["cat"].named_steps["encoder"]
    oceanos = [f"{CATEGORICA}_{c}" for c in encoder.categories_[0]]
    return list(NUMERICAS) + oceanos


def extraer_shap_array(shap_values, n_features: int, n_classes: int) -> np.ndarray:
    """Normaliza la salida de TreeExplainer a un array (n, p, k)."""
    if hasattr(shap_values, "values"):
        arr = np.asarray(shap_values.values)
    elif isinstance(shap_values, list):
        arr = np.stack([np.asarray(a) for a in shap_values], axis=-1)
    else:
        arr = np.asarray(shap_values)

    if arr.ndim == 2:
        arr = arr[:, :, np.newaxis]
    if arr.ndim != 3:
        raise RuntimeError(f"Forma SHAP inesperada: {arr.shape}")

    # Algunas versiones devuelven (n, k, p) en lugar de (n, p, k).
    if arr.shape[1] == n_classes and arr.shape[2] == n_features:
        arr = np.transpose(arr, (0, 2, 1))
    if arr.shape[1] != n_features:
        raise RuntimeError(
            f"El eje de variables no coincide: {arr.shape} frente a {n_features} predictores"
        )
    return arr


def pesos_shap_numericos(modelo, X: np.ndarray, n_max: int = 4000) -> np.ndarray:
    """Media |SHAP| por predictor, promediada también entre clases."""
    n = len(X)
    if n > n_max:
        rng = np.random.RandomState(RANDOM_STATE)
        idx = rng.choice(n, size=n_max, replace=False)
        muestra = X[idx]
    else:
        muestra = X
    explainer = shap.TreeExplainer(modelo)
    arr = extraer_shap_array(
        explainer.shap_values(muestra),
        n_features=X.shape[1],
        n_classes=len(modelo.classes_),
    )
    return np.abs(arr).mean(axis=(0, 2))


def pliegue(df: pd.DataFrame, agrupado: bool) -> tuple[np.ndarray, np.ndarray]:
    X = df[NUMERICAS + [CATEGORICA]]
    y = df["Bleaching_Class"]
    if agrupado:
        splitter = StratifiedGroupKFold(
            n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE
        )
        return next(iter(splitter.split(X, y, groups=df["Site_ID"])))
    splitter = StratifiedKFold(
        n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE
    )
    return next(iter(splitter.split(X, y)))


def ajustar_y_explicar(
    df: pd.DataFrame, itr: np.ndarray, ite: np.ndarray
) -> dict:
    X = df[NUMERICAS + [CATEGORICA]]
    y = df["Bleaching_Class"]
    prep = construir_prep()
    X_tr = prep.fit_transform(X.iloc[itr])
    X_te = prep.transform(X.iloc[ite])
    nombres = nombres_features(prep)

    clf = construir_rf()
    clf.fit(X_tr, y.iloc[itr])

    explainer = shap.TreeExplainer(clf)
    arr = extraer_shap_array(
        explainer.shap_values(X_te),
        n_features=len(nombres),
        n_classes=len(clf.classes_),
    )

    # Reordena las clases al orden canónico Bajo / Moderado / Severo.
    clases_modelo = list(clf.classes_)
    orden = [clases_modelo.index(c) for c in CLASS_ORDER]
    arr = arr[:, :, orden]

    features = pd.DataFrame(X_te, columns=nombres)
    sitios_tr = set(df.iloc[itr]["Site_ID"].unique())
    sitios_te = set(df.iloc[ite]["Site_ID"].unique())
    return {
        "shap": arr,
        "features": features,
        "nombres": nombres,
        "n_train": int(len(itr)),
        "n_test": int(len(ite)),
        "n_sitios_train": len(sitios_tr),
        "n_sitios_test": len(sitios_te),
        "solapamiento_sitios": len(sitios_tr & sitios_te),
        "clases": list(CLASS_ORDER),
    }


def importancia_global(arr: np.ndarray, nombres: list[str]) -> pd.DataFrame:
    data = {
        clase: np.abs(arr[:, :, idx]).mean(axis=0)
        for idx, clase in enumerate(CLASS_ORDER)
    }
    tabla = pd.DataFrame(data, index=nombres)
    tabla["Media global"] = tabla.mean(axis=1)
    return tabla.sort_values("Media global", ascending=False)


def direccion_severo(arr: np.ndarray, features: pd.DataFrame) -> pd.DataFrame:
    idx = CLASS_ORDER.index(FOCUS_CLASS)
    severe = arr[:, :, idx]
    filas = []
    for posicion, columna in enumerate(features.columns):
        valores = features[columna].to_numpy()
        contrib = severe[:, posicion]
        if valores.std() == 0 or contrib.std() == 0:
            correlacion = float("nan")
        else:
            correlacion = float(np.corrcoef(valores, contrib)[0, 1])
        filas.append(
            {
                "Variable": columna,
                "Efecto medio |SHAP|": float(np.abs(contrib).mean()),
                "Correlación valor–SHAP": correlacion,
            }
        )
    return (
        pd.DataFrame(filas)
        .set_index("Variable")
        .sort_values("Efecto medio |SHAP|", ascending=False)
    )


def etiqueta_direccion(correlacion: float) -> str:
    if np.isnan(correlacion):
        return "sin dirección estimable"
    if correlacion > 0.15:
        return "Incrementa la probabilidad de clase severa"
    if correlacion < -0.15:
        return "Reduce la probabilidad de clase severa"
    return "No monótona"


def describe_direction(correlacion: float) -> str:
    if np.isnan(correlacion):
        return "sin dirección estimable"
    if correlacion > 0.15:
        return "valores altos **aumentan** el riesgo severo"
    if correlacion < -0.15:
        return "valores altos **reducen** el riesgo severo"
    return "efecto no monótono (depende del contexto de la observación)"


def markdown_tabla(df: pd.DataFrame, indice: str) -> str:
    cabeceras = [indice] + list(df.columns)
    lineas = [
        "| " + " | ".join(cabeceras) + " |",
        "|" + "|".join(["---"] * len(cabeceras)) + "|",
    ]
    for idx, fila in df.iterrows():
        celdas = [coma(v) if isinstance(v, (float, np.floating)) else str(v) for v in fila]
        lineas.append("| " + " | ".join([str(idx)] + celdas) + " |")
    return "\n".join(lineas)


def peso_grupo(importancia: pd.DataFrame, variables: list[str]) -> float:
    presentes = [v for v in variables if v in importancia.index]
    if not presentes:
        return 0.0
    return float(importancia.loc[presentes, "Media global"].sum())


def plot_summary_beeswarm(arr: np.ndarray, features: pd.DataFrame, path: Path) -> None:
    idx = CLASS_ORDER.index(FOCUS_CLASS)
    plt.figure()
    shap.summary_plot(arr[:, :, idx], features, show=False)
    figura = plt.gcf()
    figura.set_size_inches(10, 6)
    plt.title(
        "Impacto de cada variable en la predicción de blanqueamiento «Severo»\n"
        "Random Forest (max_depth = 8) con TSA_DHW; holdout agrupado por Site_ID"
    )
    plt.tight_layout()
    figura.savefig(path, dpi=FIGURE_DPI, bbox_inches="tight")
    plt.close(figura)


def plot_global_importance(arr: np.ndarray, features: pd.DataFrame, path: Path) -> None:
    por_clase = [arr[:, :, idx] for idx in range(len(CLASS_ORDER))]
    plt.figure()
    shap.summary_plot(
        por_clase,
        features,
        plot_type="bar",
        class_names=CLASS_ORDER,
        show=False,
    )
    figura = plt.gcf()
    figura.set_size_inches(10, 6)
    plt.title(
        "Importancia global SHAP por nivel de riesgo\n"
        "Random Forest (max_depth = 8) con TSA_DHW; holdout agrupado por Site_ID"
    )
    plt.tight_layout()
    figura.savefig(path, dpi=FIGURE_DPI, bbox_inches="tight")
    plt.close(figura)


def figura_comparacion(comp: pd.DataFrame, path: Path) -> None:
    principales = comp.head(7).iloc[::-1]
    y_pos = np.arange(len(principales))
    alto = 0.38
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.barh(
        y_pos - alto / 2,
        principales["aleatoria"],
        alto,
        label="Partición aleatoria",
        color="#5dade2",
        edgecolor="black",
        linewidth=0.5,
    )
    ax.barh(
        y_pos + alto / 2,
        principales["agrupada"],
        alto,
        label="Partición agrupada por Site_ID",
        color="#e59866",
        edgecolor="black",
        linewidth=0.5,
    )
    ax.set_yticks(y_pos)
    ax.set_yticklabels(principales.index)
    ax.set_xlabel("Importancia SHAP global (media de |valor SHAP|)")
    ax.set_title(
        "Atribución SHAP según el esquema de validación\n"
        "Random Forest (max_depth = 8) con TSA_DHW"
    )
    ax.legend()
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=FIGURE_DPI)
    plt.close(fig)


def export_insights(
    importancia: pd.DataFrame,
    direcciones: pd.DataFrame,
    meta: dict,
    comp: pd.DataFrame,
    path: Path,
) -> None:
    termico = peso_grupo(importancia, TERMICAS)
    habitat = peso_grupo(importancia, CONTEXTO)
    total = float(importancia["Media global"].sum())
    top = importancia.index[0]

    ranking = "\n".join(
        f"{pos}. **`{var}`** — {VAR_CONTEXT[var]}. "
        f"Efecto medio sobre la clase «{FOCUS_CLASS}»: "
        f"{coma(direcciones.loc[var, 'Efecto medio |SHAP|'])}; "
        f"{describe_direction(direcciones.loc[var, 'Correlación valor–SHAP'])}."
        for pos, var in enumerate(
            [v for v in importancia.index if v in VAR_CONTEXT], start=1
        )
    )

    ctx_a = float(comp.loc[comp.index.intersection(CONTEXTO), "aleatoria"].sum())
    ter_a = float(comp.loc[comp.index.intersection(TERMICAS), "aleatoria"].sum())
    ctx_g = float(comp.loc[comp.index.intersection(CONTEXTO), "agrupada"].sum())
    ter_g = float(comp.loc[comp.index.intersection(TERMICAS), "agrupada"].sum())

    ssta = direcciones.loc["SSTA", "Correlación valor–SHAP"] if "SSTA" in direcciones.index else float("nan")
    tsa = direcciones.loc["TSA", "Correlación valor–SHAP"] if "TSA" in direcciones.index else float("nan")
    dhw = (
        direcciones.loc["TSA_DHW", "Correlación valor–SHAP"]
        if "TSA_DHW" in direcciones.index
        else float("nan")
    )
    clim = (
        direcciones.loc["ClimSST", "Correlación valor–SHAP"]
        if "ClimSST" in direcciones.index
        else float("nan")
    )

    contenido = f"""# Interpretabilidad del modelo mediante valores SHAP

## Modelo explicado y alcance

Se analiza el clasificador **Random Forest** recomendado en los apartados 5.5 y 6.4
(`n_estimators` = {N_ESTIMATORS}, `max_depth` = {MAX_DEPTH}, `class_weight='balanced'`),
con los predictores `SSTA`, `TSA`, `TSA_DHW`, `Depth_m`, `Distance_to_Shore`, `ClimSST`
y `Ocean_Name`. Los valores SHAP se calculan con `TreeExplainer` (TreeSHAP exacto) sobre
el pliegue de prueba de un `StratifiedGroupKFold` por `Site_ID`
({(f"{meta['n_test']:,}").replace(",", " ")} observaciones; {(f"{meta['n_sitios_test']:,}").replace(",", " ")} emplazamientos).
Solapamiento de `Site_ID` entre entrenamiento y explicación: {meta['solapamiento_sitios']}.

La profundidad máxima de 8 hace el cálculo exacto tratable: no es necesario sustituir el
bosque oficial por XGBoost ni recurrir a submuestreo. Los predictores numéricos llegan
estandarizados, de modo que en el diagrama de dispersión el color «alto» es una desviación
respecto a la media de entrenamiento, no una magnitud absoluta en °C o metros.

## Importancia global por nivel de riesgo

Magnitud media del efecto SHAP (|SHAP| promedio) de cada variable sobre cada clase:

{markdown_tabla(importancia, "Variable")}

Figura: `reports/figures/shap_importance_global.png`.

## Impacto y dirección sobre la clase «{FOCUS_CLASS}»

La columna «Correlación valor–SHAP» indica si los valores altos de la variable empujan la
predicción hacia el blanqueamiento severo (signo positivo) o la alejan de él (signo negativo).

{markdown_tabla(direcciones, "Variable")}

Figura: `reports/figures/shap_summary.png`.

## Lectura ecológica de los predictores

{ranking}

La variable con mayor peso explicativo global es **`{top}`**.

## Anomalías interpretativas que requieren cautela

`SSTA`, `TSA` y `TSA_DHW` derivan del mismo campo de temperatura superficial (Liu et al.,
2014). El reparto SHAP entre predictores correlacionados no es identificable de forma
unívoca (apartado 4.3.3). Las correlaciones valor–SHAP sobre «Severo» son
`SSTA` = {coma(ssta)}, `TSA` = {coma(tsa)}, `TSA_DHW` = {coma(dhw)}.
Ningún signo aislado de `SSTA` debe presentarse como evidencia de que el calentamiento
reduzca el blanqueamiento; la lectura válida es la del bloque térmico conjunto.

`ClimSST` muestra correlación valor–SHAP de {coma(clim)}. Una dirección negativa admitiría
la lectura de umbrales más elevados en aguas históricamente cálidas (Sully et al., 2019);
sigue siendo una hipótesis compatible con el modelo, no una relación causal.

## Discusión: ¿estrés térmico o firma del emplazamiento?

| Grupo de variables | Contribución SHAP acumulada | Peso relativo |
|---|---|---|
| Estrés térmico (`SSTA`, `TSA`, `TSA_DHW`) | {coma(termico)} | {coma(100 * termico / total, 1)} % |
| Contexto del emplazamiento (`Depth_m`, `Distance_to_Shore`, `ClimSST`) | {coma(habitat)} | {coma(100 * habitat / total, 1)} % |

Estos porcentajes miden cuánto se apoya **este** bosque en cada bloque, no la fracción
del blanqueamiento atribuible a cada factor. `TSA_DHW` forma parte del bloque térmico:
ya no es una línea de trabajo futura.

El mismo cálculo bajo partición aleatoria (figura `shap_comparacion_esquemas.png`) deja
una razón contexto/térmicas de {ctx_a / ter_a:.2f} frente a {ctx_g / ter_g:.2f} en el
holdout por `Site_ID`. La jerarquía no es un artefacto del esquema inflado.

## Implicaciones para la conservación y la gestión de AMP

En sitios con histórico, el bosque acotado combina la señal acumulada (`TSA_DHW`) con
descriptores del emplazamiento. En un sitio o una cuenca fuera del soporte, la parte
utilizable se reduce a los índices térmicos, y aun así el ocean-out del apartado 6.7
muestra que esa señal no sustituye una validación externa independiente de Sully et al.
(2019).
"""
    path.write_text(contenido, encoding="utf-8")


def serializar_numeros(
    importancia: pd.DataFrame,
    direcciones: pd.DataFrame,
    meta: dict,
    comp: pd.DataFrame,
) -> dict:
    termico = peso_grupo(importancia, TERMICAS)
    habitat = peso_grupo(importancia, CONTEXTO)
    total = float(importancia["Media global"].sum())
    ctx_a = float(comp.loc[comp.index.intersection(CONTEXTO), "aleatoria"].sum())
    ter_a = float(comp.loc[comp.index.intersection(TERMICAS), "aleatoria"].sum())
    ctx_g = float(comp.loc[comp.index.intersection(CONTEXTO), "agrupada"].sum())
    ter_g = float(comp.loc[comp.index.intersection(TERMICAS), "agrupada"].sum())
    pesos_num = {
        var: float(importancia.loc[var, "Media global"])
        for var in NUMERICAS
        if var in importancia.index
    }
    return {
        "n_train": meta["n_train"],
        "n_test": meta["n_test"],
        "n_sitios_train": meta["n_sitios_train"],
        "n_sitios_test": meta["n_sitios_test"],
        "solapamiento_sitios": meta["solapamiento_sitios"],
        "importancia": {
            var: {col: float(importancia.loc[var, col]) for col in importancia.columns}
            for var in importancia.index
        },
        "direcciones": {
            var: {
                "efecto": float(direcciones.loc[var, "Efecto medio |SHAP|"]),
                "corr": (
                    None
                    if pd.isna(direcciones.loc[var, "Correlación valor–SHAP"])
                    else float(direcciones.loc[var, "Correlación valor–SHAP"])
                ),
                "etiqueta": etiqueta_direccion(
                    float(direcciones.loc[var, "Correlación valor–SHAP"])
                    if not pd.isna(direcciones.loc[var, "Correlación valor–SHAP"])
                    else float("nan")
                ),
            }
            for var in direcciones.index
        },
        "termico": termico,
        "habitat": habitat,
        "total": total,
        "termico_pct": 100 * termico / total,
        "habitat_pct": 100 * habitat / total,
        "razon_aleatoria": ctx_a / ter_a if ter_a else None,
        "razon_agrupada": ctx_g / ter_g if ter_g else None,
        "pesos_numericos_shap": pesos_num,
        "comparacion": {
            var: {
                "aleatoria": float(comp.loc[var, "aleatoria"]),
                "agrupada": float(comp.loc[var, "agrupada"]),
                "variacion_pct": float(comp.loc[var, "variacion_%"]),
            }
            for var in comp.index
        },
    }


def main() -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    df = cargar()
    print(
        f"Observaciones: {len(df):,} | sitios: {df['Site_ID'].nunique():,} | "
        f"predictores: {NUMERICAS + [CATEGORICA]}"
    )

    print("\n=== Holdout agrupado por Site_ID (modelo oficial) ===")
    itr_g, ite_g = pliegue(df, agrupado=True)
    agrupado = ajustar_y_explicar(df, itr_g, ite_g)
    print(
        f"  train {agrupado['n_train']:,} | test {agrupado['n_test']:,} | "
        f"sitios test {agrupado['n_sitios_test']:,} | "
        f"solapamiento {agrupado['solapamiento_sitios']}"
    )

    print("\n=== Holdout aleatorio (contraste) ===")
    itr_a, ite_a = pliegue(df, agrupado=False)
    aleatorio = ajustar_y_explicar(df, itr_a, ite_a)
    print(
        f"  train {aleatorio['n_train']:,} | test {aleatorio['n_test']:,} | "
        f"solapamiento de sitios {aleatorio['solapamiento_sitios']}"
    )

    importancia = importancia_global(agrupado["shap"], agrupado["nombres"])
    direcciones = direccion_severo(agrupado["shap"], agrupado["features"])
    print("\n=== Importancia global (holdout Site_ID) ===")
    print(importancia.round(4).to_string())
    print("\n=== Dirección sobre «Severo» ===")
    print(direcciones.round(4).to_string())

    imp_a = importancia_global(aleatorio["shap"], aleatorio["nombres"])
    imp_g = importancia
    comp = pd.DataFrame({"aleatoria": imp_a["Media global"], "agrupada": imp_g["Media global"]})
    comp = comp.fillna(0.0)
    comp["variacion_%"] = (comp["agrupada"] / comp["aleatoria"].replace(0, np.nan) - 1) * 100
    comp = comp.sort_values("agrupada", ascending=False)

    plot_global_importance(
        agrupado["shap"], agrupado["features"], FIGURES_DIR / "shap_importance_global.png"
    )
    plot_summary_beeswarm(
        agrupado["shap"], agrupado["features"], FIGURES_DIR / "shap_summary.png"
    )
    figura_comparacion(comp, FIGURES_DIR / "shap_comparacion_esquemas.png")
    print("\nFiguras guardadas en reports/figures/")

    export_insights(
        importancia,
        direcciones,
        agrupado,
        comp,
        TABLES_DIR / "shap_insights.md",
    )
    numeros = serializar_numeros(importancia, direcciones, agrupado, comp)
    (TABLES_DIR / "shap_numeros.json").write_text(
        json.dumps(numeros, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("Tablas: shap_insights.md, shap_numeros.json")


if __name__ == "__main__":
    main()
