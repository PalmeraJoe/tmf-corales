"""Estructura de procedencia del conjunto y sus consecuencias metodologicas.

Documenta dos hallazgos que condicionan la interpretacion de los capitulos 5 y 6:

1. `Reef_ID` no es un identificador de arrecife de cobertura general, sino un campo
   presente unica y exclusivamente en los registros del programa Reef_Check. La
   validacion agrupada por `Reef_ID` estima, por tanto, transferencia dentro de un
   unico programa de monitoreo rutinario, no transferencia global.
2. La asociacion entre profundidad y blanqueamiento es un artefacto de estratificacion
   por fuente: desaparece al condicionar por `Data_Source`.

Genera:
    reports/tables/data_provenance.md
    reports/figures/procedencia_prevalencia.png
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data" / "raw" / "global_bleaching_environmental.csv"
TABLES_DIR = ROOT / "reports" / "tables"
FIGURES_DIR = ROOT / "reports" / "figures"

UMBRAL_SEVERO = 30
MIN_N_CORR = 200


def cargar() -> pd.DataFrame:
    df = pd.read_csv(RAW_PATH, na_values=["nd"], low_memory=False)
    df = df[df["Percent_Bleaching"].notna()].copy()
    df["es_severo"] = df["Percent_Bleaching"] > UMBRAL_SEVERO
    return df


def resumen_por_fuente(df: pd.DataFrame) -> pd.DataFrame:
    """Prevalencia, profundidad y cobertura de Reef_ID en cada programa de origen."""
    tabla = (
        df.groupby("Data_Source")
        .agg(
            n=("Percent_Bleaching", "size"),
            pct_severo=("es_severo", lambda s: 100 * s.mean()),
            blanqueamiento_medio=("Percent_Bleaching", "mean"),
            profundidad_media=("Depth_m", "mean"),
            cobertura_reefid=("Reef_ID", lambda s: 100 * s.notna().mean()),
        )
        .sort_values("n", ascending=False)
    )
    return tabla


def correlaciones_profundidad(df: pd.DataFrame) -> pd.DataFrame:
    """Correlacion profundidad-blanqueamiento bruta, por fuente y residualizada."""
    filas = [
        {
            "Estrato": "Conjunto completo (bruta)",
            "n": int(df["Depth_m"].notna().sum()),
            "r": df["Depth_m"].corr(df["Percent_Bleaching"]),
        }
    ]

    for fuente, sub in df.groupby("Data_Source"):
        if len(sub) >= MIN_N_CORR and sub["Depth_m"].notna().sum() >= MIN_N_CORR:
            filas.append(
                {
                    "Estrato": f"Dentro de {fuente}",
                    "n": int(sub["Depth_m"].notna().sum()),
                    "r": sub["Depth_m"].corr(sub["Percent_Bleaching"]),
                }
            )

    # Residualizacion: se retira de ambas variables la media de su fuente, de modo que
    # la correlacion resultante recoge solo la variacion intra-programa.
    d = df.dropna(subset=["Depth_m", "Percent_Bleaching"]).copy()
    d["prof_res"] = d["Depth_m"] - d.groupby("Data_Source")["Depth_m"].transform("mean")
    d["blq_res"] = d["Percent_Bleaching"] - d.groupby("Data_Source")[
        "Percent_Bleaching"
    ].transform("mean")
    filas.append(
        {
            "Estrato": "Residualizada respecto a Data_Source",
            "n": len(d),
            "r": d["prof_res"].corr(d["blq_res"]),
        }
    )

    return pd.DataFrame(filas)


def figura(resumen: pd.DataFrame) -> None:
    datos = resumen[resumen["n"] >= 100].copy().sort_values("pct_severo")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5))

    colores = ["#2980b9" if c == 100 else "#c0392b" for c in datos["cobertura_reefid"]]
    ax1.barh(datos.index, datos["pct_severo"], color=colores, edgecolor="black", linewidth=0.6)
    ax1.set_xlabel("Observaciones de blanqueamiento severo (%)")
    ax1.set_title(
        "Prevalencia de episodios severos por programa de origen", fontsize=11
    )
    for i, (v, n) in enumerate(zip(datos["pct_severo"], datos["n"])):
        ax1.text(v + 1, i, f"{v:.1f} %  (n={n:,})", va="center", fontsize=8.5)
    ax1.set_xlim(0, max(datos["pct_severo"]) * 1.35)
    ax1.grid(axis="x", alpha=0.3)

    ax2.barh(datos.index, datos["cobertura_reefid"], color=colores,
             edgecolor="black", linewidth=0.6)
    ax2.set_xlabel("Registros con `Reef_ID` informado (%)")
    ax2.set_title("Cobertura del identificador de arrecife", fontsize=11)
    ax2.set_xlim(0, 115)
    ax2.grid(axis="x", alpha=0.3)

    fig.suptitle(
        "La submuestra empleada en la validacion agrupada coincide con un unico programa",
        fontsize=12.5,
    )
    fig.tight_layout()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES_DIR / "procedencia_prevalencia.png", dpi=300)
    plt.close(fig)


def md_tabla(df: pd.DataFrame, cols: list[tuple[str, str, str]], indice: str) -> str:
    cabecera = "| " + indice + " | " + " | ".join(t for _, t, _ in cols) + " |"
    sep = "|" + "|".join(["---"] * (len(cols) + 1)) + "|"
    lineas = [cabecera, sep]
    for idx, fila in df.iterrows():
        celdas = [str(idx)]
        for clave, _, fmt in cols:
            v = fila[clave]
            if fmt.endswith("d"):
                celdas.append(f"{int(v):,}")
            else:
                celdas.append(format(float(v), fmt).replace(".", ","))
        lineas.append("| " + " | ".join(celdas) + " |")
    return "\n".join(lineas)


def exportar(df: pd.DataFrame, resumen: pd.DataFrame, corr: pd.DataFrame) -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    n_total = len(df)
    con_reef = df[df["Reef_ID"].notna()]
    fuentes_reef = con_reef["Data_Source"].unique()
    pct_global = 100 * df["es_severo"].mean()
    pct_reefcheck = 100 * df[df["Data_Source"] == "Reef_Check"]["es_severo"].mean()
    n_sitios = df["Site_ID"].nunique()

    cols_resumen = [
        ("n", "n", ",d"),
        ("pct_severo", "Severo (%)", ".2f"),
        ("blanqueamiento_medio", "Blanqueamiento medio (%)", ".2f"),
        ("profundidad_media", "Profundidad media (m)", ".2f"),
        ("cobertura_reefid", "`Reef_ID` informado (%)", ".1f"),
    ]

    corr_md = "| Estrato | n | r |\n|---|---|---|\n" + "\n".join(
        f"| {r['Estrato']} | {int(r['n']):,} | {r['r']:.4f}".replace(".", ",") + " |"
        for _, r in corr.iterrows()
    )

    texto = f"""# Procedencia de los datos y sus consecuencias metodologicas

Diagnostico de la estructura de origen del conjunto *Global Bleaching and Environmental
Data*, motivado por la fuerte asimetria de prevalencia entre la submuestra empleada en la
validacion agrupada y el conjunto completo.

## 1. Composicion por programa de origen

{md_tabla(resumen, cols_resumen, "Programa (`Data_Source`)")}

## 2. Hallazgo principal: `Reef_ID` identifica un programa, no una cobertura general

De las {n_total:,} observaciones con blanqueamiento registrado, {len(con_reef):,} tienen
`Reef_ID` informado. Esos registros pertenecen a un unico programa:
**{', '.join(fuentes_reef)}**. La cobertura del campo es del 100 % en ese programa y del
0 % en todos los demas.

La consecuencia es directa. La validacion cruzada agrupada por `Reef_ID` **no estima la
transferencia a arrecifes nuevos en general**: estima la transferencia entre arrecifes
sometidos a un mismo protocolo de monitoreo rutinario. Los programas orientados a la
documentacion de episodios concretos —Donner, McClanahan, Kumagai— quedan integramente
excluidos de ese experimento.

Ello explica de forma completa la asimetria de prevalencia advertida en el apartado 6.4.1:
la submuestra agrupada presenta un {pct_reefcheck:.2f} % de episodios severos frente al
{pct_global:.2f} % del conjunto completo, no por un artefacto de muestreo, sino porque
Reef_Check documenta el estado ordinario del arrecife mientras que otros programas
muestrean preferentemente durante eventos de blanqueamiento en curso.

**Correccion adoptada.** La agrupacion pasa a realizarse por `Site_ID`, campo con
cobertura del 100 % y {n_sitios:,} niveles distintos, lo que permite ejecutar la validacion
agrupada sobre las {n_total:,} observaciones y no sobre una fraccion sesgada.

## 3. La asociacion entre profundidad y blanqueamiento es un artefacto de estratificacion

{corr_md}

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
"""

    (TABLES_DIR / "data_provenance.md").write_text(texto, encoding="utf-8")


def main() -> None:
    df = cargar()
    print(f"Observaciones: {len(df):,}")

    resumen = resumen_por_fuente(df)
    print("\n=== Composicion por programa ===")
    print(resumen.round(2).to_string())

    corr = correlaciones_profundidad(df)
    print("\n=== Profundidad frente a blanqueamiento ===")
    print(corr.round(4).to_string(index=False))

    con_reef = df[df["Reef_ID"].notna()]
    print("\n=== Cobertura de Reef_ID ===")
    print(f"Registros con Reef_ID: {len(con_reef):,}")
    print(f"Programas representados: {list(con_reef['Data_Source'].unique())}")
    print(f"Site_ID unicos en el conjunto completo: {df['Site_ID'].nunique():,}")

    figura(resumen)
    exportar(df, resumen, corr)
    print("\nExportado a reports/tables/data_provenance.md")


if __name__ == "__main__":
    main()
