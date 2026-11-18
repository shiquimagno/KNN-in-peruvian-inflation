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


# Pruebas de métricas, versiones y conservación de registros
class TestMetricas(unittest.TestCase):
    # Preparación de una carpeta independiente para cada prueba
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.archivo = Path(self.temporal.name) / "metrics.csv"

    def test_version_cambia_con_k_y_con_la_revision(self):
        original = main.version_evaluacion()
        self.assertEqual(original, main.version_evaluacion())
        with patch.object(main, "K", main.K + 1):
            self.assertNotEqual(original, main.version_evaluacion())
        with patch.object(main, "REVISION_EVALUACION", "otra-revision"):
            self.assertNotEqual(original, main.version_evaluacion())

    # Selección de resultados comparables para el resumen
    def test_resumen_excluye_versiones_ajenas_y_legadas(self):
        base = dict(mes="2026-01", modelo="General (9 variables)",
                    real="Dentro del rango meta")
        pd.DataFrame([
            *[dict(base, modelo=nombre, version=main.version_evaluacion(), estimacion=base["real"])
              for nombre, _, _ in main.MODELOS],
            dict(base, mes="mes-invalido", version="anterior", estimacion="Deflación"),
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

    def test_mes_invalido_no_reemplaza_el_resumen(self):
        categoria = main.categoria(2)
        tabla = pd.DataFrame([
            dict(mes="2017-06", modelo=nombre, real=categoria, estimacion=categoria,
                 version=main.version_evaluacion())
            for nombre, _, _ in main.MODELOS
        ])
        tabla.to_csv(self.archivo, index=False)
        main.generar_resumen(self.archivo, mostrar=False)
        destino = self.archivo.with_name("resumen_metricas.csv")
        original = destino.read_bytes()
        for mes in ("mes-invalido", "2017-6", "2017-13", "0000-01", None):
            tabla.assign(mes=mes).to_csv(self.archivo, index=False)
            for mostrar in (False, True):
                with self.subTest(mes=mes, mostrar=mostrar), redirect_stdout(StringIO()):
                    with self.assertRaisesRegex(ValueError, "meses inválidos"):
                        main.generar_resumen(self.archivo, mostrar=mostrar)
                    self.assertEqual(destino.read_bytes(), original)

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
        instrumentacion = {"preparacion_ms", "consulta_ms", "memoria_python_kib"}
        self.assertTrue(instrumentacion.isdisjoint(tabla.columns))

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

    def test_retrospectiva_lee_las_externas_una_vez_y_guarda_el_csv_simplificado(self):
        with patch.object(main, "METRICAS", self.archivo), patch.object(
            main, "cargar_externas", wraps=main.cargar_externas
        ) as cargar, redirect_stdout(StringIO()):
            main.retrospectiva(main.cargar_datos(), pd.Period("2019-02", "M"),
                               main.cargar_alertas())
        cargar.assert_called_once()
        self.assertNotIn("precision", pd.read_csv(self.archivo).columns)

    def test_registro_antiguo_se_conserva_sin_atribuirle_version(self):
        pd.DataFrame([dict(
            mes="2019-02", modelo="General (9 variables)",
            real="Dentro del rango meta", estimacion="Dentro del rango meta", precision=1,
        )]).to_csv(self.archivo, index=False)
        with patch.object(main, "METRICAS", self.archivo), redirect_stdout(StringIO()):
            main.retrospectiva(main.cargar_datos(), pd.Period("2019-02", "M"),
                               main.cargar_alertas())
        tabla = pd.read_csv(self.archivo)
        self.assertEqual(len(tabla), 4)
        self.assertEqual(tabla.version.isna().sum(), 1)
        self.assertEqual(tabla.precision.dropna().tolist(), [1])
