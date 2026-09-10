"""Cuantificacion del indice I de Moran sobre la respuesta y los predictores.

El marco teorico introduce el indice de Moran (Moran, 1950) como medida de dependencia
espacial, pero la memoria no llegaba a calcularlo. Este script lo estima sobre los
emplazamientos, con una matriz de vecindad de k vecinos mas proximos y contraste por
permutaciones.

El resultado es relevante para interpretar el experimento de ablacion: si los indices
termicos estan mas agrupados espacialmente que la propia respuesta, la degradacion bajo
validacion agrupada no puede atribuirse solo a las variables de contexto del sitio.

Genera:
    reports/tables/moran_autocorrelation.md
    reports/figures/moran_autocorrelacion.png
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors

ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data" / "raw" / "global_bleaching_environmental.csv"
TABLES_DIR = ROOT / "reports" / "tables"
FIGURES_DIR = ROOT / "reports" / "figures"

RANDOM_STATE = 42
K_VECINOS = 8
N_PERMUTACIONES = 999
RADIO_TIERRA_KM = 6371.0

VARIABLES = {
    "Percent_Bleaching": "Blanqueamiento observado (%)",
    "TSA": "Anomalia de estres termico (TSA)",
    "SSTA": "Anomalia de temperatura (SSTA)",
    "TSA_DHW": "Estres termico acumulado (TSA_DHW)",
    "ClimSST": "Climatologia de referencia (ClimSST)",
    "Depth_m": "Profundidad (m)",
}


def cargar_sitios() -> pd.DataFrame:
    """Agrega a nivel de emplazamiento: la unidad sobre la que se define la vecindad."""
    df = pd.read_csv(RAW_PATH, na_values=["nd"], low_memory=False)
    df = df[df["Percent_Bleaching"].notna()]

    columnas = ["Latitude_Degrees", "Longitude_Degrees", *VARIABLES]
    sitios = df.groupby("Site_ID")[columnas].mean()
    sitios = sitios.dropna(subset=["Latitude_Degrees", "Longitude_Degrees"])
    return sitios


def matriz_vecindad(sitios: pd.DataFrame, k: int) -> tuple[np.ndarray, np.ndarray]:
    """Indices de los k vecinos mas proximos segun distancia de haversine."""
    coords = np.radians(sitios[["Latitude_Degrees", "Longitude_Degrees"]].to_numpy())
    nn = NearestNeighbors(n_neighbors=k + 1, metric="haversine", algorithm="ball_tree")
    nn.fit(coords)
    distancias, indices = nn.kneighbors(coords)
    # La primera columna es el propio punto y se descarta.
    return indices[:, 1:], distancias[:, 1:] * RADIO_TIERRA_KM


def moran_i(valores: np.ndarray, vecinos: np.ndarray) -> float:
    """I de Moran con pesos binarios estandarizados por fila."""
    z = valores - np.nanmean(valores)
    denominador = np.nansum(z**2)
    if denominador == 0:
        return float("nan")
    # Con pesos uniformes 1/k por fila, la suma total de pesos W iguala n.
    rezago = np.nanmean(z[vecinos], axis=1)
    numerador = np.nansum(z * rezago)
    return float(numerador / denominador)


def contraste_permutaciones(
    valores: np.ndarray, vecinos: np.ndarray, n_perm: int, rng: np.random.Generator
) -> tuple[float, float, float]:
    """Devuelve I observado, I medio bajo aleatorizacion y p-valor empirico."""
    observado = moran_i(valores, vecinos)
    simulados = np.empty(n_perm)
    for i in range(n_perm):
        simulados[i] = moran_i(rng.permutation(valores), vecinos)
    # p-valor de una cola: proporcion de permutaciones que igualan o superan lo observado.
    p = (np.sum(simulados >= observado) + 1) / (n_perm + 1)
    return observado, float(np.mean(simulados)), float(p)


def ejecutar(sitios: pd.DataFrame, vecinos: np.ndarray) -> pd.DataFrame:
    rng = np.random.default_rng(RANDOM_STATE)
    filas = []
    for variable, etiqueta in VARIABLES.items():
        serie = sitios[variable]
        validos = serie.notna().to_numpy()
        # La vecindad se recalcula sobre el subconjunto valido para no propagar NaN.
        if validos.all():
            valores = serie.to_numpy()
            vec = vecinos
        else:
            sub = sitios.loc[validos]
            vec, _ = matriz_vecindad(sub, K_VECINOS)
            valores = sub[variable].to_numpy()

        obs, esperado, p = contraste_permutaciones(valores, vec, N_PERMUTACIONES, rng)
        filas.append(
            {
                "Variable": etiqueta,
                "clave": variable,
                "n_sitios": int(validos.sum()),
                "I": obs,
                "I_esperado": esperado,
                "p": p,
            }
        )
        print(f"  {etiqueta:<42} I = {obs:6.3f}   p = {p:.3f}   (n = {validos.sum():,})")
    return pd.DataFrame(filas)


def figura(res: pd.DataFrame) -> None:
    datos = res.sort_values("I")
    fig, ax = plt.subplots(figsize=(10, 5.5))

    colores = ["#c0392b" if v >= 0.4 else "#e67e22" if v >= 0.25 else "#27ae60"
               for v in datos["I"]]
    y = np.arange(len(datos))
    ax.barh(y, datos["I"], color=colores, edgecolor="black", linewidth=0.6)
    ax.set_yticks(y)
    ax.set_yticklabels(datos["Variable"])
    ax.axvline(0, color="black", linewidth=0.9)
    ax.set_xlabel(f"Indice I de Moran (k = {K_VECINOS} vecinos mas proximos)")
    ax.set_title(
        "Autocorrelacion espacial de la respuesta y de los predictores\n"
        f"Agregacion por emplazamiento; contraste por {N_PERMUTACIONES} permutaciones",
        fontsize=11,
    )
    for i, (v, p) in enumerate(zip(datos["I"], datos["p"])):
        ax.text(v + 0.012, i, f"I = {v:.3f}  (p = {p:.3f})", va="center", fontsize=8.5)
    ax.set_xlim(min(0, datos["I"].min() * 1.2), datos["I"].max() * 1.35)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES_DIR / "moran_autocorrelacion.png", dpi=300)
    plt.close(fig)


def exportar(res: pd.DataFrame, n_sitios: int, dist_media: float) -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    filas = "\n".join(
        f"| {r['Variable']} | {r['n_sitios']:,} | "
        + f"{r['I']:.3f}".replace(".", ",")
        + " | "
        + f"{r['I_esperado']:+.4f}".replace(".", ",")
        + " | "
        + f"{r['p']:.3f}".replace(".", ",")
        + " |"
        for _, r in res.iterrows()
    )

    blq = res[res["clave"] == "Percent_Bleaching"].iloc[0]
    tsa = res[res["clave"] == "TSA"].iloc[0]
    ssta = res[res["clave"] == "SSTA"].iloc[0]
    dhw = res[res["clave"] == "TSA_DHW"].iloc[0]
    clim = res[res["clave"] == "ClimSST"].iloc[0]
    prof = res[res["clave"] == "Depth_m"].iloc[0]

    texto = f"""# Autocorrelacion espacial: indice I de Moran

Cuantificacion de la dependencia espacial que el capitulo 4 introduce de forma teorica y
que el diseno de validacion presupone.

## Diseno

- **Unidad**: emplazamiento (`Site_ID`), con las variables promediadas dentro de cada uno.
  {n_sitios:,} emplazamientos con coordenadas validas.
- **Vecindad**: {K_VECINOS} vecinos mas proximos por distancia de haversine sobre la
  superficie terrestre. Distancia media al vecino mas proximo: {dist_media:.1f} km.
- **Pesos**: binarios, estandarizados por fila.
- **Contraste**: {N_PERMUTACIONES} permutaciones aleatorias de los valores sobre las
  posiciones fijas. El p-valor es la proporcion de permutaciones que igualan o superan el
  indice observado.

## Resultados

| Variable | n emplazamientos | I de Moran | I medio bajo permutacion | p |
|---|---|---|---|---|
{filas}

## Lectura

Todas las variables presentan autocorrelacion espacial positiva y estadisticamente
significativa: el valor observado supera en todos los casos al esperado bajo asignacion
aleatoria, que se situa proximo a cero.

La **ordenacion** de los indices exige una lectura matizada. La respuesta presenta
I = {blq['I']:.3f}. Por encima de ese valor se situan la climatologia de referencia
(I = {clim['I']:.3f}), el estres termico acumulado (I = {dhw['I']:.3f}) y la profundidad
(I = {prof['I']:.3f}); por debajo, las dos anomalias instantaneas, TSA
(I = {tsa['I']:.3f}) y SSTA (I = {ssta['I']:.3f}).

No cabe afirmar, por tanto, que todos los predictores termicos esten mas agrupados que el
fenomeno que explican: las anomalias instantaneas lo estan algo menos. Lo relevante es otra
cosa: **ninguno de ellos es espacialmente neutro**, y los dos indices con mayor contenido
fisiologico —la climatologia, que resume el regimen historico, y el estres acumulado, que
integra intensidad y duracion— son precisamente los mas agrupados de todo el conjunto.

Ello resuelve la cuestion que el experimento de ablacion dejaba abierta. La persistencia de
la brecha entre validacion aleatoria y agrupada en el conjunto «solo termicas» no obedece a
una fuga residual a traves de variables de contexto omitidas: aun con I proximo a 0,3, los
campos termicos portan estructura espacial suficiente para que un algoritmo con capacidad de
memorizacion identifique la region de procedencia. No existe, en consecuencia, un
subconjunto de predictores al que replegarse para eludir la validacion espacial.

Cabe subrayar una consecuencia de signo contrario para la interpretacion ecologica. Que
`ClimSST` y `TSA_DHW` encabecen la autocorrelacion no los invalida como predictores: refleja
que el regimen termico de un arrecife es una propiedad geografica genuina, no un artefacto.
La distincion de Legendre (1993) entre dependencia inducida y autocorrelacion verdadera es
aqui pertinente, y es la que impide leer estos valores como prueba de que dichas variables
operen como meros sustitutos de la localizacion.

## Reproducibilidad

Script: `src/spatial_autocorrelation.py`. Semilla fija (`random_state={RANDOM_STATE}`).
"""

    (TABLES_DIR / "moran_autocorrelation.md").write_text(texto, encoding="utf-8")


def main() -> None:
    print("Agregando por emplazamiento...")
    sitios = cargar_sitios()
    print(f"  {len(sitios):,} emplazamientos con coordenadas validas")

    vecinos, distancias = matriz_vecindad(sitios, K_VECINOS)
    dist_media = float(np.mean(distancias[:, 0]))
    print(f"  distancia media al vecino mas proximo: {dist_media:.1f} km")

    print(f"\nCalculando I de Moran ({N_PERMUTACIONES} permutaciones por variable)...")
    res = ejecutar(sitios, vecinos)

    figura(res)
    exportar(res, len(sitios), dist_media)
    print("\nExportado a reports/tables/moran_autocorrelation.md")


if __name__ == "__main__":
    main()
