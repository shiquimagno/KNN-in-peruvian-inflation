# Resumen comparativo y gráficos

from contextlib import suppress
from os import makedirs, path, replace, unlink
from tempfile import NamedTemporaryFile

import pandas as pd

# Formato
COLUMNAS_EXPORTACION = [
    "version",
    "modelo",
    "mes_inicio",
    "mes_fin",
    "n_meses",
    "aciertos",
    "exactitud",
    "precision_macro",
    "recall_macro",
    "f1_macro",
]


def guardar_csv(tabla, archivo):
    carpeta = path.dirname(path.abspath(archivo))
    makedirs(carpeta, exist_ok=True)
    # El temporal queda en la misma carpeta para reemplazar el CSV de una vez.
    with NamedTemporaryFile(dir=carpeta, suffix=".tmp", delete=False) as temporal:
        ruta_temporal = temporal.name
    try:
        tabla.to_csv(ruta_temporal, index=False)
        replace(ruta_temporal, archivo)
    finally:
        with suppress(FileNotFoundError):
            unlink(ruta_temporal)


def exportar_resumen(resumen, archivo):
    if resumen is None or resumen.empty:
        exportacion = pd.DataFrame(columns=COLUMNAS_EXPORTACION)
    else:
        exportacion = resumen.rename(
            columns={
                "Versión": "version",
                "Modelo": "modelo",
                "Inicio": "mes_inicio",
                "Fin": "mes_fin",
                "Meses": "n_meses",
                "Aciertos": "aciertos",
                "Exactitud": "exactitud",
                "Precisión macro": "precision_macro",
                "Recall macro": "recall_macro",
                "F1 macro": "f1_macro",
            }
        ).copy()
        from src.resultados import NOMBRES

        exportacion["modelo"] = exportacion.modelo.map(NOMBRES).fillna(
            exportacion.modelo
        )
        exportacion["aciertos"] = exportacion.aciertos.str.split("/").str[0].astype(int)
        exportacion = exportacion[COLUMNAS_EXPORTACION]
    guardar_csv(exportacion, archivo)
