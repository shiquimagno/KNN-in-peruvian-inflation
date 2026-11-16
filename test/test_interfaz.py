"""Regresiones de navegación, exportación y representación de los resultados."""

# Herramientas para probar la interfaz sin alterar datos reales
import hashlib
import inspect
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import main
from src.menu import VOLVER, elegir_intervalo, elegir_mes
from src.resultados import mostrar_datos, mostrar_resultado


# Pruebas de navegación, resultados, CSV y gráficos
class TestInterfaz(unittest.TestCase):
    # Datos y carpetas temporales para cada caso de prueba
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.carpeta = Path(self.temporal.name)
        self.datos = main.cargar_datos()
        self.alertas = main.cargar_alertas()

    # Estabilidad de la firma frente a cambios de presentación
    def test_firma_ignora_formato_y_comentarios(self):
        original = main.version_evaluacion()
        obtener = inspect.getsource
        with patch.object(main.inspect, "getsource", side_effect=lambda f: "# comentario\n\n" + obtener(f)):
            self.assertEqual(original, main.version_evaluacion())
        with patch.object(main.inspect, "getsource", side_effect=lambda f: obtener(f) + "\n\n"):
            self.assertEqual(original, main.version_evaluacion())

    # Fechas válidas, cancelación y consulta de observaciones
    def test_intervalo_un_mes_y_cancelacion(self):
        with patch("src.menu.questionary.autocomplete") as pregunta, redirect_stdout(StringIO()):
            pregunta.return_value.ask.side_effect = ["2019-02", "2019-02"]
            inicio, fin = elegir_intervalo(self.datos)
            opciones_finales = pregunta.call_args.kwargs["choices"]
            self.assertNotIn("2019-01", opciones_finales)
            self.assertEqual(inicio, fin)
            pregunta.return_value.ask.side_effect = [VOLVER]
            self.assertIsNone(elegir_intervalo(self.datos))
            pregunta.return_value.ask.side_effect = ["2019-02", VOLVER]
            self.assertIsNone(elegir_intervalo(self.datos))

    def test_fechas_invalidas_y_cancelacion_retrospectiva(self):
        with patch("src.menu.questionary.autocomplete") as pregunta, redirect_stdout(StringIO()):
            pregunta.return_value.ask.return_value = VOLVER
            self.assertIsNone(elegir_mes(self.datos, main.preparar_entradas(self.datos), main.K))
            validar = pregunta.call_args.kwargs["validate"]
            self.assertIs(validar("2019-02"), True)
            self.assertIsNot(validar("2026-13"), True)
            self.assertIsNot(validar("2026-10"), True)

    def test_datos_incluye_faltantes_e_intervalo_invertido(self):
        externas = pd.DataFrame(columns=main.EXTERNAS, index=pd.PeriodIndex([], freq="M"))
        mes = pd.Period("2019-02", "M")
        with redirect_stdout(StringIO()) as salida:
            mostrar_datos(self.datos, externas, mes, mes)
        self.assertIn("Sin dato", salida.getvalue())
        self.assertIn("Mensual (%)", salida.getvalue())
        self.assertIn("Expectativa 12m", salida.getvalue())
        with self.assertRaises(ValueError):
            mostrar_datos(self.datos, externas, mes + 1, mes)

    # Correspondencia entre opciones del menú y modelos
    def test_los_tres_pronosticos_desde_el_menu(self):
        with patch.object(main.questionary, "select") as pregunta, patch.object(
            main, "mostrar_resultado"
        ) as mostrar, redirect_stdout(StringIO()):
            pregunta.return_value.ask.side_effect = ["2", "3", "4", "7"]
            main.menu()
        self.assertEqual([c.args[0] for c in mostrar.call_args_list], [m[0] for m in main.MODELOS])
        self.assertEqual([c.args[3:] for c in mostrar.call_args_list], [(False, False), (True, False), (True, True)])
        self.assertTrue(mostrar.call_args.args[2].filtrado)
        self.assertEqual(pregunta.call_count, 4)

    def test_numeracion_retrospectiva_y_salida_conserva_archivos(self):
        archivo = self.carpeta / "metrics.csv"
        # La prueba también debe funcionar en un clon sin métricas personales.
        pd.DataFrame([dict(
            mes="2020-12", modelo=main.MODELOS[0][0],
            estimacion="Dentro del rango meta", real="Dentro del rango meta",
            version=main.version_evaluacion(),
        )]).to_csv(archivo, index=False)
        original = hashlib.sha256(archivo.read_bytes()).hexdigest()
        with patch.object(main, "METRICAS", archivo), patch.object(main.questionary, "select") as pregunta, patch.object(
            main, "elegir_mes", return_value=pd.Period("2019-02", "M")
        ), patch.object(main, "retrospectiva") as evaluar, redirect_stdout(StringIO()):
            pregunta.return_value.ask.side_effect = ["5", "7"]
            main.menu()
        self.assertEqual(str(evaluar.call_args.args[1]), "2019-02")
        self.assertEqual(hashlib.sha256(archivo.read_bytes()).hexdigest(), original)

    # Consistencia entre las métricas mostradas y exportadas
    def test_csv_y_tabla_mismas_metricas_y_resumen_vacio(self):
        archivo = self.carpeta / "metrics.csv"
        with patch.object(main, "METRICAS", archivo), redirect_stdout(StringIO()) as salida:
            main.retrospectiva(self.datos, pd.Period("2019-02", "M"), self.alertas)
            resumen = main.generar_resumen()
        exportado = pd.read_csv(archivo.with_name("resumen_metricas.csv"))
        self.assertEqual(len(exportado), 3)
        for columna_csv, columna_tabla in [("exactitud", "Exactitud"), ("f1_macro", "F1 macro"),
                                            ("precision_macro", "Precisión macro"), ("recall_macro", "Recall macro")]:
            for valor_csv, valor_tabla in zip(exportado[columna_csv], resumen[columna_tabla]):
                self.assertAlmostEqual(valor_csv, valor_tabla)
        self.assertIn("Evaluación guardada", salida.getvalue())
        self.assertIn("Solo hay un mes", salida.getvalue())
        with patch.object(main, "K", 6), redirect_stdout(StringIO()):
            self.assertIsNone(main.generar_resumen(archivo))
        self.assertTrue(pd.read_csv(archivo.with_name("resumen_metricas.csv")).empty)

    def test_mes_faltante_en_un_modelo_se_excluye(self):
        filas = [dict(mes="2026-01", modelo=n, estimacion="Dentro del rango meta",
                      real="Dentro del rango meta", version=main.version_evaluacion())
                 for n, _, _ in main.MODELOS[:2]]
        archivo = self.carpeta / "metrics.csv"
        pd.DataFrame(filas).to_csv(archivo, index=False)
        with redirect_stdout(StringIO()):
            self.assertIsNone(main.generar_resumen(archivo))

    def test_intervalo_evaluado_identifica_meses_sin_evaluacion(self):
        version = main.version_evaluacion()
        filas = [dict(mes=mes, modelo=nombre, estimacion="Dentro del rango meta",
                      real="Dentro del rango meta", version=version)
                 for mes in ("2026-01", "2026-03")
                 for nombre, _, _ in main.MODELOS]
        archivo = self.carpeta / "metrics.csv"
        pd.DataFrame(filas).to_csv(archivo, index=False)
        with redirect_stdout(StringIO()) as salida:
            resumen = main.generar_resumen(archivo)
        self.assertIn("Intervalo evaluado · 2026-01 a 2026-03", salida.getvalue())
        self.assertIn("Meses incluidos · 2026-01, 2026-03", salida.getvalue())
        self.assertIn("Hay meses sin evaluar", salida.getvalue())
        self.assertTrue(resumen.Meses.eq(2).all())

    # Presentación de vecinos y exportación auxiliar del gráfico
    def test_tabla_vecinos_y_exportacion_png_sin_gui(self):
        from src.graficos import graficar_comparacion
        origen = self.datos.index[-1]
        r = main.clasificar(self.datos, main.preparar_entradas(self.datos), origen, self.alertas, True)
        with redirect_stdout(StringIO()) as salida:
            mostrar_resultado(main.MODELOS[2][0], origen + 1, r, True, True)
        texto = salida.getvalue()
        self.assertIn("VECINOS SELECCIONADOS", texto)
        for vecino in r.vecinos:
            self.assertIn(str(vecino), texto)
        self.assertNotIn("Voto", texto)
        self.assertNotIn("Votación", texto)
        with patch.object(main, "METRICAS", self.carpeta / "metrics.csv"), redirect_stdout(StringIO()):
            main.retrospectiva(self.datos, pd.Period("2019-02", "M"), self.alertas)
            resumen = main.generar_resumen()
        comparacion_png = graficar_comparacion(resumen, self.carpeta)
        for archivo in (comparacion_png,):
            self.assertEqual(archivo.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
            self.assertGreater(archivo.stat().st_size, 10000)
        with self.assertRaises(OSError):
            graficar_comparacion(resumen, comparacion_png / "carpeta_invalida")

    # Conservación de la evaluación si falla el resumen
    def test_error_exportacion_no_borra_la_evaluacion(self):
        archivo = self.carpeta / "metrics.csv"
        with patch.object(main, "METRICAS", archivo), patch.object(main, "exportar_resumen", side_effect=OSError("sin permiso")), redirect_stdout(StringIO()) as salida:
            main.retrospectiva(self.datos, pd.Period("2019-02", "M"), self.alertas)
        self.assertEqual(len(pd.read_csv(archivo)), 3)
        self.assertIn("La evaluación quedó guardada", salida.getvalue())

    # Apertura del gráfico y manejo de entornos sin ventana
    def test_mostrar_grafico_abre_ventana_y_la_cierra(self):
        from matplotlib import pyplot as plt
        from matplotlib.backends.registry import backend_registry
        from src.graficos import mostrar_comparacion

        resumen = pd.DataFrame([{
            "Modelo": main.MODELOS[0][0], "Exactitud": 1.0, "F1 macro": .25,
            "Inicio": "2026-01", "Fin": "2026-01", "Meses": 1,
        }])
        # El backend de prueba es Agg. Se simula disponibilidad de ventana para
        # verificar la llamada de apertura sin abrir una GUI durante las pruebas.
        with patch.object(backend_registry, "resolve_backend", return_value=("agg", "macosx")), patch.object(
            plt, "show"
        ) as mostrar, redirect_stdout(StringIO()):
            mostrar_comparacion(resumen)
        mostrar.assert_called_once_with(block=True)
        self.assertEqual(plt.get_fignums(), [])

    def test_mostrar_grafico_avisa_si_no_hay_ventanas(self):
        from matplotlib import pyplot as plt
        from matplotlib.backends.registry import backend_registry
        from src.graficos import mostrar_comparacion

        with patch.object(backend_registry, "resolve_backend", return_value=("agg", None)), patch.object(
            plt, "show"
        ) as mostrar:
            with self.assertRaisesRegex(RuntimeError, "backend sin ventanas"):
                mostrar_comparacion(pd.DataFrame())
        mostrar.assert_not_called()

    def test_opcion_del_resumen_muestra_grafico_y_conserva_matrices(self):
        resumen = pd.DataFrame({"Modelo": [main.MODELOS[0][0]]})
        with patch.object(main, "generar_resumen", return_value=resumen), patch.object(
            main.questionary, "select"
        ) as pregunta, patch("src.graficos.mostrar_comparacion") as mostrar:
            pregunta.return_value.ask.side_effect = ["grafico", "volver"]
            main.consultar_resumen()
        mostrar.assert_called_once_with(resumen)
        etiquetas = [opcion.title for opcion in pregunta.call_args.kwargs["choices"]]
        self.assertIn("Mostrar gráfico comparativo", etiquetas)
        self.assertIn("Consultar matrices numéricas y versión", etiquetas)
