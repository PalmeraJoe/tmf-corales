"""Análisis exploratorio del dataset global de blanqueamiento coralino."""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_CSV = PROJECT_ROOT / "data" / "raw" / "global_bleaching_environmental.csv"
FIGURES_DIR = PROJECT_ROOT / "reports" / "figures"
TABLES_DIR = PROJECT_ROOT / "reports" / "tables"

TARGET = "Percent_Bleaching"
THERMAL_VARS = [
    "SSTA",
    "TSA",
    "TSA_DHW",
    "ClimSST",
    "Depth_m",
    "Distance_to_Shore",
]
CORR_VARS = THERMAL_VARS + [TARGET]

FIGURE_DPI = 300

VAR_LABELS = {
    "SSTA": "SSTA (anomalía térmica superficial, °C)",
    "TSA": "TSA (anomalía de estrés térmico, °C)",
    "TSA_DHW": "TSA_DHW (Degree Heating Weeks, °C·semana)",
    "ClimSST": "ClimSST (climatología SST, K)",
    "Depth_m": "Profundidad (m)",
    "Distance_to_Shore": "Distancia a la costa (m)",
    "Percent_Bleaching": "Porcentaje de blanqueamiento (%)",
}


def load_dataset(path: Path) -> pd.DataFrame:
    """Carga el CSV crudo tratando 'nd' como valor faltante."""
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el dataset en: {path}")

    try:
        return pd.read_csv(path, na_values=["nd", "ND"], low_memory=False)
    except (OSError, pd.errors.ParserError) as exc:
        raise RuntimeError(f"Error al leer el CSV: {exc}") from exc


def ensure_output_dirs() -> None:
    """Crea los directorios de figuras y tablas si no existen."""
    try:
        FIGURES_DIR.mkdir(parents=True, exist_ok=True)
        TABLES_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(f"No se pudieron crear los directorios de reportes: {exc}") from exc


def filter_target_not_null(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Elimina filas sin Percent_Bleaching y devuelve el resumen del filtrado."""
    if TARGET not in df.columns:
        raise KeyError(f"La columna objetivo '{TARGET}' no está en el dataset.")

    n_raw = len(df)
    df_filtered = df.dropna(subset=[TARGET]).copy()
    n_kept = len(df_filtered)
    n_removed = n_raw - n_kept

    summary = {
        "n_raw": n_raw,
        "n_kept": n_kept,
        "n_removed": n_removed,
        "pct_removed": (n_removed / n_raw * 100) if n_raw else 0.0,
    }
    return df_filtered, summary


def summarize_target(series: pd.Series) -> pd.Series:
    """Calcula media, mediana, desviación y percentiles de Percent_Bleaching."""
    percentiles = [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]
    stats = series.describe(percentiles=percentiles)
    stats["median"] = series.median()
    stats["std"] = series.std()
    return stats


def plot_bleaching_histogram(series: pd.Series, output_path: Path) -> None:
    """Guarda el histograma de la variable objetivo a 300 DPI."""
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.histplot(series, bins=40, kde=True, color="#1f6f8b", ax=ax)
    ax.set_title("Distribución del porcentaje de blanqueamiento coralino")
    ax.set_xlabel(VAR_LABELS[TARGET])
    ax.set_ylabel("Frecuencia de observaciones")
    ax.axvline(series.median(), color="#c0392b", linestyle="--", label=f"Mediana = {series.median():.2f}%")
    ax.axvline(series.mean(), color="#1a5276", linestyle=":", label=f"Media = {series.mean():.2f}%")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(fig)


def compute_pearson_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Matriz de correlación de Pearson entre estrés térmico, hábitat y blanqueamiento."""
    missing = [col for col in CORR_VARS if col not in df.columns]
    if missing:
        raise KeyError(f"Faltan columnas para la correlación: {missing}")

    corr_df = df[CORR_VARS].dropna()
    if corr_df.empty:
        raise ValueError("No hay filas completas para calcular la matriz de correlación.")
    return corr_df.corr(method="pearson")


def plot_correlation_heatmap(corr: pd.DataFrame, output_path: Path) -> None:
    """Exporta el mapa de calor de correlaciones de Pearson a 300 DPI."""
    labeled = corr.rename(index=VAR_LABELS, columns=VAR_LABELS)
    fig, ax = plt.subplots(figsize=(11, 9))
    sns.heatmap(
        labeled,
        annot=True,
        fmt=".2f",
        cmap="RdBu_r",
        center=0,
        vmin=-1,
        vmax=1,
        square=True,
        ax=ax,
    )
    ax.set_title("Correlación de Pearson: estrés térmico, hábitat y blanqueamiento")
    fig.tight_layout()
    fig.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(fig)


def plot_ssta_vs_bleaching(df: pd.DataFrame, output_path: Path) -> None:
    """Gráfico de dispersión con tendencia entre SSTA y Percent_Bleaching."""
    plot_df = df[["SSTA", TARGET]].dropna()
    if plot_df.empty:
        raise ValueError("No hay pares SSTA–Percent_Bleaching válidos para el gráfico.")

    fig, ax = plt.subplots(figsize=(10, 6))
    sns.regplot(
        data=plot_df,
        x="SSTA",
        y=TARGET,
        scatter_kws={"alpha": 0.15, "s": 10, "color": "#2874a6"},
        line_kws={"color": "#922b21", "linewidth": 2},
        ax=ax,
    )
    ax.set_title("Relación entre la anomalía térmica superficial (SSTA) y el blanqueamiento")
    ax.set_xlabel(VAR_LABELS["SSTA"])
    ax.set_ylabel(VAR_LABELS[TARGET])
    fig.tight_layout()
    fig.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(fig)


def interpret_correlation(value: float) -> str:
    """Traduce un coeficiente de Pearson a una lectura ecológica breve."""
    magnitude = abs(value)
    if magnitude < 0.10:
        strength = "asociación muy débil"
    elif magnitude < 0.30:
        strength = "asociación débil"
    elif magnitude < 0.50:
        strength = "asociación moderada"
    else:
        strength = "asociación fuerte"

    direction = "positiva" if value > 0 else "negativa" if value < 0 else "nula"
    return f"{strength} {direction} (r = {value:.3f})"


def export_insights(
    filter_summary: dict,
    target_stats: pd.Series,
    corr: pd.DataFrame,
    output_path: Path,
) -> None:
    """Exporta los hallazgos numéricos del EDA en Markdown académico."""
    ssta_r = corr.loc["SSTA", TARGET]
    tsa_r = corr.loc["TSA", TARGET]
    dhw_r = corr.loc["TSA_DHW", TARGET]
    clim_r = corr.loc["ClimSST", TARGET]
    depth_r = corr.loc["Depth_m", TARGET]
    shore_r = corr.loc["Distance_to_Shore", TARGET]
    ssta_tsa = corr.loc["SSTA", "TSA"]

    orden = sorted(THERMAL_VARS, key=lambda v: abs(corr.loc[v, TARGET]), reverse=True)
    corr_rows = "\n".join(
        f"| `{var}` | {VAR_LABELS[var]} | {corr.loc[var, TARGET]:.3f} |"
        for var in orden
    )

    content = f"""# Hallazgos del análisis exploratorio de datos

## 1. Filtrado de la variable objetivo

Se excluyeron las observaciones sin `Percent_Bleaching` (marcadas como `nd` o nulas), porque no permiten estimar la magnitud del evento de blanqueamiento.

| Indicador | Valor |
|---|---|
| Observaciones originales | {filter_summary["n_raw"]:,} |
| Observaciones eliminadas (sin `{TARGET}`) | {filter_summary["n_removed"]:,} ({filter_summary["pct_removed"]:.2f}%) |
| **Observaciones retenidas para el EDA** | **{filter_summary["n_kept"]:,}** |

## 2. Distribución de `Percent_Bleaching`

`Percent_Bleaching` expresa el porcentaje de colonias o cobertura coralina afectada por blanqueamiento en cada muestreo. Una distribución sesgada hacia valores bajos es coherente con un régimen en el que predominan arrecifes sin evento agudo, interrumpido por picos de mortalidad térmica.

| Estadístico | Valor |
|---|---|
| Media (%) | {target_stats["mean"]:.3f} |
| Mediana (%) | {target_stats["median"]:.3f} |
| Desviación estándar (%) | {target_stats["std"]:.3f} |
| Mínimo (%) | {target_stats["min"]:.3f} |
| Percentil 1 (%) | {target_stats["1%"]:.3f} |
| Percentil 5 (%) | {target_stats["5%"]:.3f} |
| Percentil 10 (%) | {target_stats["10%"]:.3f} |
| Percentil 25 (%) | {target_stats["25%"]:.3f} |
| Percentil 50 (%) | {target_stats["50%"]:.3f} |
| Percentil 75 (%) | {target_stats["75%"]:.3f} |
| Percentil 90 (%) | {target_stats["90%"]:.3f} |
| Percentil 95 (%) | {target_stats["95%"]:.3f} |
| Percentil 99 (%) | {target_stats["99%"]:.3f} |
| Máximo (%) | {target_stats["max"]:.3f} |

Figura: `reports/figures/distribucion_percent_bleaching.png`.

## 3. Correlación de Pearson con variables térmicas y de hábitat

Las variables se interpretan con su significado ecológico:

- **SSTA** (*Sea Surface Temperature Anomaly*): desviación de la temperatura superficial respecto a la climatología.
- **TSA** (*Thermal Stress Anomaly*): exposición a temperaturas por encima del umbral de blanqueamiento.
- **`TSA_DHW`** (*Degree Heating Weeks*): integral del estrés térmico en las doce semanas precedentes.
- **`ClimSST`**: temperatura superficial climatológica (kelvin).
- **`Depth_m`**: profundidad del muestreo.
- **`Distance_to_Shore`**: distancia a la costa.

| Variable | Contexto ecológico | r de Pearson con `{TARGET}` |
|---|---|---|
{corr_rows}

Correlación `SSTA`–`TSA`: {ssta_tsa:.3f}.

Lectura ecológica de los coeficientes:

- `TSA_DHW` y `{TARGET}`: {interpret_correlation(dhw_r)}. Es el predictor lineal más asociado a la respuesta y justifica su inclusión en el modelo principal.
- TSA y `{TARGET}`: {interpret_correlation(tsa_r)}.
- Profundidad y `{TARGET}`: {interpret_correlation(depth_r)}. El signo positivo no coincide con la expectativa clásica de mayor blanqueamiento en arrecifes someros; el apartado 6.1.3 muestra que recoge estratificación por programa.
- SSTA y `{TARGET}`: {interpret_correlation(ssta_r)}.
- `ClimSST` y `{TARGET}`: {interpret_correlation(clim_r)}.
- Distancia a la costa y `{TARGET}`: {interpret_correlation(shore_r)}. A escala global, la distancia a la costa apenas se asocia linealmente con el blanqueamiento.

Figura: `reports/figures/matriz_correlacion.png`.

## 4. Relación SSTA–blanqueamiento

El gráfico `reports/figures/ssta_vs_bleaching.png` muestra la nube de puntos y la tendencia lineal (`regplot`) entre la anomalía térmica superficial y el porcentaje de blanqueamiento. Una pendiente positiva, aunque sea débil a escala global, es coherente con el mecanismo de estrés por calor. La nube es heterocedástica y con bandas en 0%, 30%, 75% y 100%, típicas de protocolos de campo que reportan umbrales discretos.

Para la gestión de Áreas Marinas Protegidas (AMP), el índice lineal más asociado a la respuesta es `TSA_DHW`, no SSTA. La magnitud lineal global de las anomalías puntuales sigue siendo baja; el seguimiento operativo debe apoyarse en el estrés acumulado y en umbrales locales, no en un único gradiente costa–profundidad.
"""

    try:
        output_path.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"No se pudo escribir la tabla de hallazgos: {exc}") from exc


def main() -> None:
    """Ejecuta el EDA completo, exporta figuras a 300 DPI y la tabla de hallazgos."""
    sns.set_theme(style="whitegrid")
    ensure_output_dirs()

    df_raw = load_dataset(RAW_CSV)
    df, filter_summary = filter_target_not_null(df_raw)

    print("=== Filtrado de Percent_Bleaching ===")
    print(f"Observaciones originales: {filter_summary['n_raw']:,}")
    print(f"Eliminadas (nulas): {filter_summary['n_removed']:,} ({filter_summary['pct_removed']:.2f}%)")
    print(f"Observaciones retenidas: {filter_summary['n_kept']:,}")

    target_stats = summarize_target(df[TARGET])
    print("\n=== Distribución de Percent_Bleaching ===")
    print(target_stats.to_string())

    hist_path = FIGURES_DIR / "distribucion_percent_bleaching.png"
    plot_bleaching_histogram(df[TARGET], hist_path)
    print(f"\nHistograma guardado en: {hist_path}")

    corr = compute_pearson_matrix(df)
    print("\n=== Matriz de correlación de Pearson ===")
    print(corr.round(3).to_string())

    corr_path = FIGURES_DIR / "matriz_correlacion.png"
    plot_correlation_heatmap(corr, corr_path)
    print(f"Mapa de calor guardado en: {corr_path}")

    scatter_path = FIGURES_DIR / "ssta_vs_bleaching.png"
    plot_ssta_vs_bleaching(df, scatter_path)
    print(f"Dispersión SSTA vs blanqueamiento guardada en: {scatter_path}")

    insights_path = TABLES_DIR / "eda_insights.md"
    export_insights(filter_summary, target_stats, corr, insights_path)
    print(f"\nHallazgos exportados en: {insights_path}")


if __name__ == "__main__":
    main()
