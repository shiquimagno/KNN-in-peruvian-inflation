from pathlib import Path
import pandas as pd


def generar_resumen(archivo_csv: Path | None = None) -> pd.DataFrame | None:
    """Lee data/origiales/metrics.csv y muestra las métricas comparativas."""
    if archivo_csv is None:
        # Sube desde src/ hasta la raíz y entra a data/origiales/metrics.csv
        archivo_csv = (
            Path(__file__).resolve().parent.parent
            / "data"
            / "origiales"
            / "metrics.csv"
        )

    if not archivo_csv.exists():
        print(f"\n[!] El archivo de métricas '{archivo_csv.name}' no existe en {archivo_csv.parent}.")
        print("Ejecuta primero la opción 3 para registrar métricas.")
        return None

    try:
        df_metrics = pd.read_csv(archivo_csv)

        if df_metrics.empty:
            print(f"\n[!] El archivo '{archivo_csv.name}' está vacío.")
            return None

        print("\n" + "=" * 55)
        print("          RESUMEN COMPARATIVO DE MÉTRICAS (KNN)")
        print("=" * 55)

        # Muestra el historial registrado
        print("\n--- Historial de Evaluaciones ---")
        print(df_metrics.tail(10).to_string(index=False))

        # Precisión promedio por tipo de modelo si existe la columna 'modelo'
        if "precision" in df_metrics.columns:
            print("\n--- Precisión Promedio ---")
            if "modelo" in df_metrics.columns:
                promedios = df_metrics.groupby("modelo")["precision"].mean()
                for modelo, prec in promedios.items():
                    print(f" • {modelo}: {prec * 100:.2f}%")
            else:
                promedio_general = df_metrics["precision"].mean()
                print(f" • General: {promedio_general * 100:.2f}%")

        print("=" * 55 + "\n")
        return df_metrics

    except Exception as error:
        print(f"\n[ERROR] No se pudo leer el archivo de métricas: {error}")
        return None
