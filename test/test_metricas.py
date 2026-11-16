"""Regresiones del registro versionado y del resumen del menú."""

# Archivos aislados y herramientas de comprobación
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import main
from src.resumen import generar_resumen


# Pruebas de métricas, versiones y conservación de registros
class TestMetricas(unittest.TestCase):
    # Preparación de una carpeta independiente para cada prueba
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.archivo = Path(self.temporal.name) / "metrics.csv"

    # Identificación de cambios en reglas y datos
    def test_firma_cambia_con_configuracion_alertas_y_datos(self):
        original = main.version_evaluacion()
        self.assertEqual(original, main.version_evaluacion())
        with patch.object(main, "K", main.K + 1):
            self.assertNotEqual(original, main.version_evaluacion())
        self.assertNotEqual(original, main.version_evaluacion({}))
        copia = Path(self.temporal.name) / "ipc.csv"
        copia.write_bytes(main.CSV.read_bytes() + b"\n")
        with patch.object(main, "CSV", copia):
            self.assertNotEqual(original, main.version_evaluacion())

    # Selección de resultados comparables para el resumen
    def test_resumen_excluye_versiones_ajenas_y_legadas(self):
        base = dict(mes="2026-01", modelo="General (9 variables)",
                    real="Dentro del rango meta")
        pd.DataFrame([
            *[dict(base, modelo=nombre, version=main.version_evaluacion(), estimacion=base["real"])
              for nombre, _, _ in main.MODELOS],
            dict(base, version="anterior", estimacion="Deflación"),
            dict(base, version=None, estimacion="Deflación"),
        ]).to_csv(self.archivo, index=False)
        with redirect_stdout(StringIO()) as salida:
            resumen = main.generar_resumen(self.archivo)
        self.assertEqual(resumen.iloc[0]["Aciertos"], "1/1")
        self.assertEqual(resumen.iloc[0]["Exactitud"], 1)
        self.assertEqual(resumen.iloc[0]["F1 macro"], 0.25)
        self.assertIn("Precisión macro", resumen.columns)
        self.assertIn("Recall macro", resumen.columns)
        self.assertIn("2 registros", salida.getvalue())
        self.assertNotIn("EFICIENCIA", salida.getvalue())
        self.assertNotIn("ms)", salida.getvalue())

    # Persistencia, duplicados y recuperación ante archivos incompletos
    def test_guardado_conserva_versiones_y_reemplaza_repeticiones(self):
        datos = main.cargar_datos()
        alertas = main.cargar_alertas()
        with patch.object(main, "METRICAS", self.archivo), redirect_stdout(StringIO()):
            for k in (5, 6, 5):
                with patch.object(main, "K", k):
                    main.retrospectiva(datos, pd.Period("2019-02", "M"), alertas)
        tabla = pd.read_csv(self.archivo)
        self.assertEqual(len(tabla), 6)
        self.assertEqual(tabla.version.nunique(), 2)

    def test_columnas_faltantes_y_menu_continua(self):
        pd.DataFrame({"mes_objetivo": ["2026-01"]}).to_csv(self.archivo, index=False)
        with self.assertRaisesRegex(ValueError, "fecha_publicacion"):
            main.cargar_alertas(self.archivo)
        with self.assertRaisesRegex(ValueError, "real"):
            main.generar_resumen(self.archivo)
        with patch.object(main, "METRICAS", self.archivo), patch.object(
            main.questionary, "select"
        ) as pregunta, redirect_stdout(StringIO()) as salida:
            pregunta.return_value.ask.side_effect = ["6", "7"]
            main.menu()
        self.assertEqual(pregunta.call_count, 2)
        self.assertIn("carece de columnas", salida.getvalue())

    # Compatibilidad del resumen auxiliar con la ruta del menú
    def test_resumen_auxiliar_usa_ruta_del_menu(self):
        pd.DataFrame([dict(
            mes="2026-01", modelo=nombre,
            real="Dentro del rango meta", estimacion="Dentro del rango meta",
            version=main.version_evaluacion(),
        ) for nombre, _, _ in main.MODELOS]).to_csv(self.archivo, index=False)
        with patch.object(main, "METRICAS", self.archivo), redirect_stdout(StringIO()):
            resumen = generar_resumen()
        self.assertEqual(resumen.iloc[0]["Aciertos"], "1/1")

    def test_registro_antiguo_se_conserva_sin_atribuirle_version(self):
        pd.DataFrame([dict(
            mes="2019-02", modelo="General (9 variables)",
            real="Dentro del rango meta", estimacion="Dentro del rango meta",
        )]).to_csv(self.archivo, index=False)
        with patch.object(main, "METRICAS", self.archivo), redirect_stdout(StringIO()):
            main.retrospectiva(main.cargar_datos(), pd.Period("2019-02", "M"),
                               main.cargar_alertas())
        tabla = pd.read_csv(self.archivo)
        self.assertEqual(len(tabla), 4)
        self.assertEqual(tabla.version.isna().sum(), 1)
