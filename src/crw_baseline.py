"""Regla operativa de Coral Reef Watch como termino de comparacion sin entrenamiento.

La memoria comparaba cuatro algoritmos entre si, pero no frente al procedimiento que las
agencias de monitoreo ya emplean. El programa Coral Reef Watch declara alerta de nivel 1
cuando el estres termico acumulado alcanza 4 grados-semana y de nivel 2 a partir de 8
(Liu et al., 2014; Skirving et al., 2020). Convertida en clasificador, esa regla no requiere
ajuste alguno y constituye el competidor honesto de cualquier modelo de alerta.

Se evalua ademas un corte temporal —entrenamiento hasta 2012, prueba desde 2013— que
responde a la pregunta operativa real: predecir una temporada que aun no ha ocurrido.

Genera:
    reports/tables/crw_baseline.md
    reports/figures/baseline_crw.png
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
from sklearn.metrics import f1_score, precision_score, recall_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data" / "raw" / "global_bleaching_environmental.csv"
TABLES_DIR = ROOT / "reports" / "tables"
FIGURES_DIR = ROOT / "reports" / "figures"

RANDOM_STATE = 42
ANIO_CORTE = 2012
UMBRALES_CRW = [4.0, 8.0]

TERMICAS = ["SSTA", "TSA"]
ACUMULADO = ["TSA_DHW"]
CONTEXTO = ["Depth_m", "Distance_to_Shore", "ClimSST"]


def clasificar(v: float) -> str:
    if v < 10:
        return "Bajo"
    if v <= 30:
        return "Moderado"
    return "Severo"


def cargar() -> pd.DataFrame:
    df = pd.read_csv(RAW_PATH, na_values=["nd"], low_memory=False)
    df = df[df["Percent_Bleaching"].notna()].copy()
    df["Bleaching_Class"] = df["Percent_Bleaching"].apply(clasificar)
    df["es_severo"] = (df["Bleaching_Class"] == "Severo").astype(int)
    return df


def evaluar_regla(y_true: pd.Series, dhw: pd.Series, umbral: float) -> dict:
    """La regla predice episodio severo cuando el estres acumulado alcanza el umbral."""
    pred = (dhw >= umbral).astype(int)
    # Los valores ausentes de DHW se tratan como ausencia de alerta, criterio conservador
    # que coincide con el comportamiento operativo ante falta de dato.
    pred = pred.fillna(0)
    return {
        "recall": recall_score(y_true, pred, zero_division=0),
        "precision": precision_score(y_true, pred, zero_division=0),
        "f1_severo": f1_score(y_true, pred, zero_division=0),
        "n_alertas": int(pred.sum()),
        "pct_alertas": float(100 * pred.mean()),
    }


def construir(tipo: str, numericas: list[str], categoricas: list[str]) -> Pipeline:
    transformadores = [
        (
            "num",
            Pipeline(
                [("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]
            ),
            numericas,
        )
    ]
    if categoricas:
        transformadores.append(
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categoricas)
        )

    if tipo == "rf":
        est = RandomForestClassifier(
            n_estimators=200, max_depth=8, class_weight="balanced",
            random_state=RANDOM_STATE, n_jobs=-1,
        )
    elif tipo == "rf_libre":
        est = RandomForestClassifier(
            n_estimators=200, class_weight="balanced",
            random_state=RANDOM_STATE, n_jobs=-1,
        )
    else:
        est = LogisticRegression(
            max_iter=1000, class_weight="balanced", random_state=RANDOM_STATE
        )

    return Pipeline([("prep", ColumnTransformer(transformadores)), ("clf", est)])


def metricas_severo(y_true: pd.Series, pred: np.ndarray) -> dict:
    sev = (pred == "Severo").astype(int)
    return {
        "recall": recall_score(y_true, sev, zero_division=0),
        "precision": precision_score(y_true, sev, zero_division=0),
        "f1_severo": f1_score(y_true, sev, zero_division=0),
        "n_alertas": int(sev.sum()),
        "pct_alertas": float(100 * sev.mean()),
    }


def corte_temporal(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Entrena con las temporadas hasta el ano de corte y evalua sobre las posteriores."""
    tr = df[df["Date_Year"] <= ANIO_CORTE]
    te = df[df["Date_Year"] > ANIO_CORTE]

    contexto = {
        "n_train": len(tr),
        "n_test": len(te),
        "pct_sev_train": float(100 * tr["es_severo"].mean()),
        "pct_sev_test": float(100 * te["es_severo"].mean()),
        "anios_train": f"{int(tr['Date_Year'].min())}–{int(tr['Date_Year'].max())}",
        "anios_test": f"{int(te['Date_Year'].min())}–{int(te['Date_Year'].max())}",
    }

    filas = []
    for umbral in UMBRALES_CRW:
        m = evaluar_regla(te["es_severo"], te["TSA_DHW"], umbral)
        m["Metodo"] = f"Regla CRW: DHW >= {umbral:.0f}"
        m["Entrenamiento"] = "No requiere"
        filas.append(m)

    configuraciones = [
        ("Regresion logistica (termicas + DHW)", "lr", TERMICAS + ACUMULADO, []),
        ("Regresion logistica (base + DHW)", "lr", TERMICAS + ACUMULADO + CONTEXTO, ["Ocean_Name"]),
        ("Random Forest max_depth=8 (base + DHW)", "rf", TERMICAS + ACUMULADO + CONTEXTO, ["Ocean_Name"]),
        ("Random Forest sin tope (base + DHW)", "rf_libre", TERMICAS + ACUMULADO + CONTEXTO, ["Ocean_Name"]),
    ]

    for etiqueta, tipo, numericas, categoricas in configuraciones:
        pipe = construir(tipo, numericas, categoricas)
        pipe.fit(tr[numericas + categoricas], tr["Bleaching_Class"])
        pred = pipe.predict(te[numericas + categoricas])
        m = metricas_severo(te["es_severo"], pred)
        m["Metodo"] = etiqueta
        m["Entrenamiento"] = contexto["anios_train"]
        filas.append(m)

    return pd.DataFrame(filas), contexto


def global_crw(df: pd.DataFrame) -> pd.DataFrame:
    filas = []
    for umbral in UMBRALES_CRW:
        m = evaluar_regla(df["es_severo"], df["TSA_DHW"], umbral)
        m["Metodo"] = f"DHW >= {umbral:.0f}"
        filas.append(m)
    return pd.DataFrame(filas)


def coma(v: float, dec: int = 4) -> str:
    return f"{v:.{dec}f}".replace(".", ",")


def figura(temporal: pd.DataFrame) -> None:
    datos = temporal.sort_values("recall")
    fig, ax = plt.subplots(figsize=(11, 5.5))
    y = np.arange(len(datos))

    colores = ["#2980b9" if "CRW" in m else "#e67e22" for m in datos["Metodo"]]
    ax.barh(y, datos["recall"], color=colores, edgecolor="black", linewidth=0.6)
    ax.set_yticks(y)
    ax.set_yticklabels(datos["Metodo"], fontsize=9)
    ax.set_xlabel("Exhaustividad sobre episodios severos en la temporada no observada")
    ax.set_title(
        "Corte temporal: entrenamiento hasta 2012, evaluacion desde 2013\n"
        "La regla operativa de Coral Reef Watch no requiere entrenamiento",
        fontsize=11,
    )
    for i, (r, p) in enumerate(zip(datos["recall"], datos["precision"])):
        ax.text(r + 0.008, i, f"recall {r:.3f} · precision {p:.3f}", va="center", fontsize=8.5)
    ax.set_xlim(0, max(datos["recall"]) * 1.45)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES_DIR / "baseline_crw.png", dpi=300)
    plt.close(fig)


def exportar(df: pd.DataFrame, glob: pd.DataFrame, temporal: pd.DataFrame, ctx: dict) -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    glob_md = "\n".join(
        f"| {r['Metodo']} | {int(r['n_alertas']):,} | {coma(r['pct_alertas'], 2)} % | "
        f"{coma(r['recall'])} | {coma(r['precision'])} | {coma(r['f1_severo'])} |"
        for _, r in glob.iterrows()
    )

    temp_md = "\n".join(
        f"| {r['Metodo']} | {r['Entrenamiento']} | {coma(r['recall'])} | "
        f"{coma(r['precision'])} | {coma(r['f1_severo'])} | {coma(r['pct_alertas'], 1)} % |"
        for _, r in temporal.iterrows()
    )

    crw4 = glob[glob["Metodo"] == "DHW >= 4"].iloc[0]
    t_crw4 = temporal[temporal["Metodo"] == "Regla CRW: DHW >= 4"].iloc[0]
    t_lr = temporal[temporal["Metodo"] == "Regresion logistica (termicas + DHW)"].iloc[0]
    t_rf = temporal[temporal["Metodo"] == "Random Forest max_depth=8 (base + DHW)"].iloc[0]
    t_rfl = temporal[temporal["Metodo"] == "Random Forest sin tope (base + DHW)"].iloc[0]

    texto = f"""# La regla de Coral Reef Watch como termino de comparacion

Todo modelo de alerta debe justificarse frente al procedimiento que las agencias ya emplean.
Coral Reef Watch declara alerta de nivel 1 al alcanzarse 4 grados-semana de estres termico
acumulado y de nivel 2 a partir de 8 (Liu et al., 2014; Skirving et al., 2020). Interpretada
como clasificador binario de la clase «Severo», esa regla no requiere entrenamiento, ajuste
de hiperparametros ni datos historicos del emplazamiento.

## 1. Rendimiento de la regla sobre el conjunto completo

| Regla | Alertas emitidas | Sobre el total | Recall | Precision | F1 de la clase severa |
|---|---|---|---|---|---|
{glob_md}

El umbral de 4 grados-semana recupera el {coma(100 * crw4['recall'], 1)} % de los episodios
severos con una precision de {coma(crw4['precision'], 3)}, emitiendo alerta sobre el
{coma(crw4['pct_alertas'], 1)} % de las observaciones.

## 2. Corte temporal: la temporada que aun no ha ocurrido

La validacion agrupada mide transferencia en el espacio; la pregunta operativa anade la
dimension temporal. Se entrena con las campanas de {ctx['anios_train']}
({ctx['n_train']:,} observaciones, {coma(ctx['pct_sev_train'], 2)} % de severos) y se evalua
sobre {ctx['anios_test']} ({ctx['n_test']:,} observaciones,
{coma(ctx['pct_sev_test'], 2)} % de severos).

| Metodo | Entrenamiento | Recall | Precision | F1 severa | Alertas emitidas |
|---|---|---|---|---|---|
{temp_md}

## 3. Lectura

La comparacion arroja un resultado incomodo para la narrativa habitual del aprendizaje
automatico aplicado a la alerta temprana, si bien exige precision al enunciarlo.

Medido sobre el **F1 de la clase severa**, que integra ambos tipos de error, la regla de
4 grados-semana ({coma(t_crw4['f1_severo'], 4)}) y la regresion logistica con predictores
termicos y estres acumulado ({coma(t_lr['f1_severo'], 4)}) son practicamente indistinguibles.
La regla, que no ha visto un solo dato de entrenamiento, iguala al modelo ajustado.

La equivalencia global encubre, no obstante, un intercambio entre los dos tipos de error que
resulta pertinente para la gestion. La regresion logistica recupera mas episodios severos
—exhaustividad {coma(t_lr['recall'], 4)} frente a {coma(t_crw4['recall'], 4)}— al precio de
una precision inferior ({coma(t_lr['precision'], 4)} frente a {coma(t_crw4['precision'], 4)})
y de emitir alerta sobre el {coma(t_lr['pct_alertas'], 1)} % de las observaciones en lugar
del {coma(t_crw4['pct_alertas'], 1)} %. Si el criterio de decision prioriza no omitir
episodios severos, el modelo aporta valor; si prioriza limitar las falsas alarmas, la regla
resulta preferible. La eleccion no la dirime la estadistica, sino la funcion de coste del
gestor.

El Random Forest, en cambio, queda claramente por detras de ambos:
{coma(t_rf['recall'], 4)} de exhaustividad con profundidad acotada y
{coma(t_rfl['recall'], 4)} sin tope. El modelo que mejor rendia bajo particion aleatoria es
el que peor transfiere a una temporada futura, lo que reproduce en la dimension temporal el
patron ya documentado en la dimension espacial.

Debe advertirse que el periodo de prueba presenta una prevalencia de episodios severos
sensiblemente inferior a la del periodo de entrenamiento
({coma(ctx['pct_sev_test'], 2)} % frente a {coma(ctx['pct_sev_train'], 2)} %), de modo que
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

Script: `src/crw_baseline.py`. Semilla fija (`random_state={RANDOM_STATE}`).
Ano de corte: {ANIO_CORTE}. Los valores ausentes de `TSA_DHW` ({100 * df['TSA_DHW'].isna().mean():.2f} %)
se tratan como ausencia de alerta.
"""

    # El simbolo se introduce solo en la exportacion: la consola de Windows no lo admite.
    (TABLES_DIR / "crw_baseline.md").write_text(texto.replace(">=", "≥"), encoding="utf-8")


def main() -> None:
    df = cargar()
    print(f"Observaciones: {len(df):,}  | severos: {100 * df['es_severo'].mean():.2f} %")
    print(f"TSA_DHW ausente: {100 * df['TSA_DHW'].isna().mean():.2f} %")

    print("\n=== Regla CRW sobre el conjunto completo ===")
    glob = global_crw(df)
    print(glob[["Metodo", "recall", "precision", "f1_severo", "pct_alertas"]].round(4).to_string(index=False))

    print(f"\n=== Corte temporal (entrena <= {ANIO_CORTE}, evalua > {ANIO_CORTE}) ===")
    temporal, ctx = corte_temporal(df)
    print(f"  train {ctx['anios_train']}: {ctx['n_train']:,} obs, {ctx['pct_sev_train']:.2f} % severos")
    print(f"  test  {ctx['anios_test']}: {ctx['n_test']:,} obs, {ctx['pct_sev_test']:.2f} % severos\n")
    print(temporal[["Metodo", "recall", "precision", "f1_severo", "pct_alertas"]].round(4).to_string(index=False))

    figura(temporal)
    exportar(df, glob, temporal, ctx)
    print("\nExportado a reports/tables/crw_baseline.md")


if __name__ == "__main__":
    main()
