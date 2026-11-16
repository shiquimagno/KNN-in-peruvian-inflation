"""Exportación del resumen y compatibilidad con su punto de entrada anterior."""

# Rutas, archivos temporales y tablas
from pathlib import Path
from tempfile import NamedTemporaryFile

import pandas as pd

# Esquema del CSV de métricas agregadas
COLUMNAS_EXPORTACION = [
    "version", "modelo", "mes_inicio", "mes_fin", "n_meses", "aciertos",
    "exactitud", "precision_macro", "recall_macro", "f1_macro",
]


# Escritura completa antes de reemplazar el archivo destino
def guardar_csv(tabla, archivo):
    archivo = Path(archivo)
    archivo.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=archivo.parent, suffix=".tmp", delete=False) as temporal:
        ruta_temporal = Path(temporal.name)
    try:
        tabla.to_csv(ruta_temporal, index=False)
        ruta_temporal.replace(archivo)
    finally:
        ruta_temporal.unlink(missing_ok=True)


# Preparación de las columnas para el informe académico
def exportar_resumen(resumen, archivo):
    if resumen is None or resumen.empty:
        exportacion = pd.DataFrame(columns=COLUMNAS_EXPORTACION)
    else:
        exportacion = resumen.rename(columns={
            "Versión": "version", "Modelo": "modelo", "Inicio": "mes_inicio",
            "Fin": "mes_fin", "Meses": "n_meses", "Aciertos": "aciertos",
            "Exactitud": "exactitud", "Precisión macro": "precision_macro",
            "Recall macro": "recall_macro", "F1 macro": "f1_macro",
        }).copy()
        from src.resultados import NOMBRES
        exportacion["modelo"] = exportacion.modelo.map(NOMBRES).fillna(exportacion.modelo)
        exportacion["aciertos"] = exportacion.aciertos.str.split("/").str[0].astype(int)
        exportacion = exportacion[COLUMNAS_EXPORTACION]
    guardar_csv(exportacion, archivo)


# Acceso auxiliar al mismo resumen que utiliza el menú
def generar_resumen(archivo_csv: Path | None = None) -> pd.DataFrame | None:
    """Comparte la ruta y las reglas del resumen del menú."""
    from main import generar_resumen as resumen_principal
    try:
        return resumen_principal(archivo_csv)
    except (AttributeError, KeyError, OSError, ValueError) as error:
        print(f"\nAviso: no se pudo leer el resumen. {error}\n")
        return None
