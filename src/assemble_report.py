"""Ensambla los capitulos de reports/ en un unico documento Markdown.

Genera reports/TFM_memoria_completa.md con portada, indice automatico
construido a partir de los encabezados y las figuras incrustadas como
imagenes en lugar de referencias textuales.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"
OUTPUT_PATH = REPORTS_DIR / "TFM_memoria_completa.md"

CHAPTERS = [
    "01_resumen_abstract.md",
    "02_introduccion_y_antecedentes.md",
    "03_objetivos.md",
    "04_marco_teorico.md",
    "05_material_y_metodos.md",
    "06_resultados_y_discusion.md",
    "07_conclusiones.md",
    "08_referencias_bibliograficas.md",
]

TITLE = (
    "Clasificación de la severidad del blanqueamiento coralino "
    "mediante aprendizaje automático"
)
SUBTITLE = (
    "Evaluación crítica de la transferibilidad espacial de modelos predictivos "
    "sobre datos globales de arrecifes"
)

# Pies de figura, indexados por nombre de fichero.
CAPTIONS = {
    "distribucion_percent_bleaching.png": (
        "Distribución de la variable `Percent_Bleaching` sobre las 34 515 observaciones "
        "depuradas. La asimetría positiva refleja un régimen basal de estabilidad "
        "interrumpido por episodios agudos de estrés térmico."
    ),
    "matriz_correlacion.png": (
        "Matriz de correlación de Pearson entre los seis predictores numéricos oficiales y "
        "`Percent_Bleaching`. `TSA_DHW` encabeza la asociación con la respuesta (r = 0,228 "
        "listwise; 0,272 bivariante). Entre `SSTA` y `TSA` se mantiene r = 0,543."
    ),
    "ssta_vs_bleaching.png": (
        "Relación entre la anomalía térmica superficial (`SSTA`) y el porcentaje de "
        "blanqueamiento, con ajuste lineal. Las bandas horizontales evidencian protocolos "
        "de campo con registro por umbrales discretos."
    ),
    "confusion_matrix_random_forest.png": "Matriz de confusión de Random Forest.",
    "confusion_matrix_xgboost_gridsearchcv.png": "Matriz de confusión de XGBoost optimizado.",
    "confusion_matrix_lightgbm.png": "Matriz de confusión de LightGBM.",
    "confusion_matrix_regresion_logistica.png": "Matriz de confusión de la regresión logística.",
    "validacion_grupos_reef_id.png": (
        "Comparación del F1-Score macro bajo validación cruzada aleatoria estratificada y "
        "validación agrupada por `Reef_ID`, ejecutadas sobre idéntica submuestra."
    ),
    "shap_importance_global.png": (
        "Importancia global SHAP del Random Forest recomendado (`max_depth` = 8, con "
        "`TSA_DHW`) sobre un holdout agrupado por `Site_ID`."
    ),
    "shap_summary.png": (
        "Diagrama SHAP de resumen para la clase «Severo» del Random Forest de profundidad 8. "
        "El color codifica el valor estandarizado; `TSA_DHW` encabeza la contribución."
    ),
    "ablacion_transferibilidad.png": (
        "Degradación del F1-Score macro al pasar de validación aleatoria a agrupada, según el "
        "conjunto de predictores. La persistencia de la caída en el conjunto «Solo térmicas» "
        "muestra que el sobreajuste espacial no procede únicamente de las variables de contexto."
    ),
    "shap_comparacion_esquemas.png": (
        "Importancia SHAP global del Random Forest de profundidad 8 con `TSA_DHW`, bajo "
        "partición aleatoria y bajo partición agrupada por `Site_ID`. `TSA_DHW` encabeza ambas."
    ),
    "moran_autocorrelacion.png": (
        "Índice I de Moran sobre centroides de emplazamiento (k = 8 vecinos). Los predictores "
        "térmicos, en particular `TSA_DHW`, están más agrupados espacialmente que el blanqueamiento "
        "observado."
    ),
    "procedencia_prevalencia.png": (
        "Prevalencia de episodios severos y profundidad media según el programa de origen. "
        "`Reef_ID` está informado únicamente en Reef_Check."
    ),
    "esquemas_validacion.png": (
        "F1-Score macro bajo validación aleatoria y agrupada por `Site_ID`, según la capacidad "
        "del Random Forest y la inclusión de `TSA_DHW`."
    ),
    "baseline_crw.png": (
        "Detección de episodios severos: regla de Coral Reef Watch (DHW ≥ 4 °C·semana) frente a "
        "regresión logística y Random Forest en el corte temporal 2013–2020."
    ),
    "calibracion_severo.png": (
        "Diagrama de fiabilidad de P(Severo) bajo CV agrupada por Site_ID y bajo el corte "
        "temporal 2013–2020. La isotónica se ajusta solo sobre el entrenamiento."
    ),
    "leave_one_program.png": (
        "Leave-one-program-out del Random Forest de profundidad 8: prevalencia observada frente "
        "a probabilidad media predicha. El desfase mide el sesgo de protocolo, no un océano nuevo."
    ),
    "area_aplicabilidad.png": (
        "Índice de disimilitud de Meyer y Pebesma (2021) sobre el leave-one-ocean-out, "
        "ponderado por TreeSHAP del Random Forest de profundidad 8. Fuera del área de "
        "aplicabilidad el error de probabilidad aumenta; el Atlántico queda íntegramente "
        "fuera del soporte. El experimento permanece dentro de Sully et al. (2019)."
    ),
    "contraste_sully.png": (
        "Media aritmética de SST (`Temperature_Kelvin`) en observaciones con blanqueamiento "
        "sobre este extracto BCO-DMO, no el Weibull de Sully et al. (2019); y relación "
        "emplazamiento a emplazamiento entre la desviación de SST y la proporción de episodios "
        "severos."
    ),
    "transferencia_dominio.png": (
        "Recall y F1 de «Severo» al entrenar en el Caribe más un apéndice polinesio y al "
        "cortar 2010–2017 / 2018–2020, frente a Coral Reef Watch. El corpus interno acaba en "
        "2020; 2018–2020 no contiene DHW ≥ 4 entre los 49 episodios severos."
    ),
    "validacion_externa.png": (
        "Recall, F1 y PR-AUC de «Severo» sobre Reef Check 2021–2026, con el RF-8, la logística "
        "térmica y la regla CRW entrenados solo en BCO-DMO. El holdout es ajeno a Sully et al. "
        "(2019); el protocolo sigue siendo Reef Check."
    ),
    "validacion_externa_dhw.png": (
        "Porcentaje de colonias blanqueadas (media S1–S4 de Bleaching (% Of Population)) frente "
        "al DHW de Coral Reef Watch del día del censo, Reef Check 2021–2026. La línea vertical "
        "marca el umbral operativo de 4 °C·semana."
    ),
    "pipeline_pronostico.png": (
        "Acoplamiento conceptual entre el clasificador concurrente de este trabajo y un "
        "pronóstico térmico a 1–3 meses. La fila inferior no se ha implementado."
    ),
}

FIGURE_RE = re.compile(r"^\*Figura ([\d.a-z]+): `reports/figures/(.+?)`\*$")
CONFUSION_RE = re.compile(r"^\*Figuras: `reports/figures/confusion_matrix_\*\.png`\*$")
HEADING_RE = re.compile(r"^(#{1,3}) (.+)$")


def embed_figures(text: str) -> tuple[str, int]:
    """Sustituye las referencias textuales a figuras por imágenes incrustadas."""
    out: list[str] = []
    embedded = 0

    for line in text.splitlines():
        figure = FIGURE_RE.match(line)
        if figure:
            number, filename = figure.groups()
            caption = CAPTIONS.get(filename, "")
            out.append(f"![Figura {number}](figures/{filename})")
            out.append("")
            out.append(f"***Figura {number}.*** *{caption}*")
            embedded += 1
            continue

        if CONFUSION_RE.match(line):
            # Las matrices de la comparativa aleatoria histórica no se incrustan:
            # describen un bosque sin tope y sin TSA_DHW, no el sistema recomendado.
            continue

        out.append(line)

    return "\n".join(out), embedded


def build_index(chapter_texts: list[str]) -> str:
    """Construye el índice a partir de los encabezados de nivel 1 a 3."""
    lines = ["## Índice", ""]

    for text in chapter_texts:
        for line in text.splitlines():
            heading = HEADING_RE.match(line)
            if not heading:
                continue
            hashes, title = heading.groups()
            indent = "  " * (len(hashes) - 1)
            marker = "- **" if len(hashes) == 1 else "- "
            suffix = "**" if len(hashes) == 1 else ""
            lines.append(f"{indent}{marker}{title}{suffix}")
        lines.append("")

    return "\n".join(lines)


def build_front_matter(index: str) -> str:
    today = date.today().strftime("%d/%m/%Y")
    return "\n".join(
        [
            f"# {TITLE}",
            "",
            f"### {SUBTITLE}",
            "",
            "**Trabajo Fin de Máster**",
            "",
            "| | |",
            "|---|---|",
            "| Autor | *(completar)* |",
            "| Director/a | *(completar)* |",
            "| Titulación | *(completar)* |",
            "| Universidad | *(completar)* |",
            f"| Fecha de compilación | {today} |",
            "",
            "---",
            "",
            index,
            "---",
            "",
            "> Documento generado automáticamente por `src/assemble_report.py` a partir de los",
            "> capítulos individuales de `reports/`. No debe editarse directamente: cualquier",
            "> corrección debe aplicarse al capítulo correspondiente y regenerarse el ensamblado.",
            "",
            "---",
            "",
        ]
    )


def main() -> None:
    chapter_texts: list[str] = []
    total_embedded = 0

    for name in CHAPTERS:
        path = REPORTS_DIR / name
        if not path.exists():
            raise FileNotFoundError(f"No se encuentra el capitulo {name}")
        text = path.read_text(encoding="utf-8").strip()
        text, embedded = embed_figures(text)
        total_embedded += embedded
        chapter_texts.append(text)

    index = build_index(chapter_texts)
    body = "\n\n---\n\n".join(chapter_texts)
    document = build_front_matter(index) + body + "\n"

    OUTPUT_PATH.write_text(document, encoding="utf-8")

    words = len(re.findall(r"\b\w+\b", document))
    print(f"Documento generado: {OUTPUT_PATH}")
    print(f"Capitulos ensamblados : {len(chapter_texts)}")
    print(f"Figuras incrustadas   : {total_embedded}")
    print(f"Palabras aproximadas  : {words:,}".replace(",", "."))
    print(f"Tamano                : {OUTPUT_PATH.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
