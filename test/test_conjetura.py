"""Comparación temporal del filtro ENFEN.

Ejecutar: .venv/bin/python test/test_conjetura.py [--alertas archivo.csv]
El archivo usa las columnas fecha_publicacion,mes_objetivo,estado,episodio
descritas en main.cargar_alertas. Sin archivo se informa la cobertura disponible.
Por defecto se conserva el bloque final (desde octubre de 2022) para evaluación.
Pruebas del flujo: .venv/bin/python -m unittest discover -s test
"""

# Bibliotecas para el contraste y las pruebas del filtro
import argparse
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd
from sklearn.metrics import f1_score

# Acceso al programa al ejecutar este archivo directamente
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from main import (
    K,
    cargar_alertas,
    cargar_datos,
    categoria,
    clasificar,
    preparar_entradas,
)


# Contraste retrospectivo en los meses con alerta ENFEN
def comparar(desde, hasta, alertas):
    datos = cargar_datos()
    if not datos.index[0] < desde <= hasta <= datos.index[-1]:
        raise ValueError(
            "El intervalo debe tener etiquetas observadas y un mes de origen anterior."
        )
    entradas = preparar_entradas(datos)
    meses = pd.period_range(desde, hasta, freq="M")
    evaluados = []
    sin_estimacion = 0
    desconocidos = 0
    for objetivo in meses:
        estado, episodio = alertas.get(objetivo, ("desconocido", ""))
        if estado == "desconocido":
            desconocidos += 1
        if estado != "alerta":
            continue
        origen = objetivo - 1
        general = clasificar(datos, entradas, origen, alertas)
        restringido = clasificar(datos, entradas, origen, alertas, True)
        if general.clase is None or restringido.clase is None:
            sin_estimacion += 1
            continue
        evaluados.append(
            {
                "mes": str(objetivo),
                "episodio": episodio,
                "real": categoria(datos.loc[objetivo, "interanual"]),
                "general": general.clase,
                "restringido": restringido.clase,
                "filtrado": restringido.filtrado,
                "meses_vecinos": ",".join(map(str, restringido.vecinos)),
                "episodios_vecinos_identificados": len(restringido.episodios),
                "vecinos_alerta_sin_id": restringido.vecinos_sin_episodio,
            }
        )

    print(
        f"{desde} a {hasta}: {len(meses)} meses, {desconocidos} con estado desconocido; "
        f"{len(evaluados)} pares evaluados con alerta y {sin_estimacion} sin estimación con alerta."
    )
    if not evaluados:
        print(
            "Sin pares para contrastar la conjetura. Se necesitan comunicados ENFEN fechados."
        )
        return
    pares = pd.DataFrame(evaluados)
    print(pares.to_string(index=False))
    clases = [categoria(x) for x in (-1, 0.5, 2, 4)]
    for titulo, grupo in [
        ("Todas las alertas", pares),
        ("Filtro aplicado", pares[pares.filtrado]),
    ]:
        if grupo.empty:
            print("El filtro no llegó a aplicarse en este período.")
            continue
        episodios = grupo.episodio.replace("", pd.NA).nunique()
        print(f"{titulo}: {len(grupo)} meses y {episodios} episodios identificados.")
        for modelo in ["general", "restringido"]:
            aciertos = grupo[modelo].eq(grupo.real).sum()
            f1 = f1_score(
                grupo.real,
                grupo[modelo],
                labels=clases,
                average="macro",
                zero_division=0,
            )
            print(
                f"  {modelo}: {aciertos}/{len(grupo)} aciertos; F1 macro (4 clases): {f1:.3f}"
            )


# Pruebas del filtro climático y del orden temporal
class TestConjetura(unittest.TestCase):
    def setUp(self):
        self.datos = cargar_datos().iloc[:40]
        self.entradas = preparar_entradas(self.datos)
        self.origen = self.datos.index[-2]
        self.objetivo = self.origen + 1

    def test_selecciona_solo_candidatos_comparables(self):
        meses = self.datos.index[3 : 3 + K]
        alertas = {
            m + 1: ("alerta", "A" if i < 3 else "B") for i, m in enumerate(meses)
        }
        alertas[self.objetivo] = ("alerta", "C")
        r = clasificar(self.datos, self.entradas, self.origen, alertas, True)
        self.assertTrue(r.filtrado)
        self.assertEqual(set(r.vecinos), set(meses))
        self.assertEqual(r.episodios, {"A", "B"})

    def test_retorna_al_historial_general(self):
        for estado in ["alerta", "sin_alerta", "desconocido"]:
            meses = self.datos.index[3 : 3 + K - 1]
            alertas = {m + 1: ("alerta", "A") for m in meses}
            alertas[self.objetivo] = (estado, "")
            a = clasificar(self.datos, self.entradas, self.origen, alertas)
            b = clasificar(self.datos, self.entradas, self.origen, alertas, True)
            self.assertFalse(b.filtrado)
            self.assertEqual((a.vecinos, a.clase), (b.vecinos, b.clase))
            self.assertEqual(bool(b.avisos), estado != "sin_alerta")

    def test_desempata_por_mes_y_por_cercania_de_la_categoria(self):
        meses = pd.period_range("2020-01", periods=8, freq="M")
        datos = pd.DataFrame({"interanual": [2, -1, 4, .5, .5, 4, .5, 2]}, index=meses)
        entradas = pd.DataFrame({"entrada": [9, 8, 7, 6, 5, 5, 10, 10]}, index=meses)
        origen = meses[-1]
        alertas = {mes: ("alerta", "A") for mes in meses[1:7]}
        alertas[origen + 1] = ("alerta", "B")

        resultado = clasificar(datos, entradas, origen, alertas, restringido=True)

        self.assertTrue(resultado.filtrado)
        self.assertEqual(resultado.vecinos, list(meses[:K]))
        self.assertEqual(resultado.clase, categoria(4))

    def test_oculta_la_respuesta_y_los_comunicados_posteriores(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "alertas.csv"
            dia = self.objetivo.start_time
            ruta.write_text(
                "fecha_publicacion,mes_objetivo,estado,episodio\n"
                f"{dia:%Y-%m-%d},{self.objetivo},sin_alerta,\n"
                f"{dia + pd.Timedelta(days=1):%Y-%m-%d},{self.objetivo},alerta,A\n"
            )
            alertas = cargar_alertas(ruta)
        self.assertEqual(alertas[self.objetivo][0], "sin_alerta")
        a = clasificar(self.datos, self.entradas, self.origen, alertas, True)
        alterados = self.datos.copy()
        alterados.loc[self.objetivo] = -9999
        b = clasificar(
            alterados, preparar_entradas(alterados), self.origen, alertas, True
        )
        self.assertEqual((a.vecinos, a.clase), (b.vecinos, b.clase))
        self.assertTrue(all(m < self.origen for m in a.vecinos))


# Argumentos para ejecutar el contraste desde la terminal
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Contrastar el filtro ENFEN en meses con alerta."
    )
    parser.add_argument("--alertas", type=Path, help="CSV de estados ENFEN publicados.")
    parser.add_argument("--desde", default="2015-01", help="Primer mes objetivo.")
    parser.add_argument("--hasta", default="2022-09", help="Último mes objetivo.")
    args = parser.parse_args()
    try:
        comparar(
            pd.Period(args.desde, freq="M"),
            pd.Period(args.hasta, freq="M"),
            cargar_alertas(args.alertas),
        )
    except (KeyError, OSError, ValueError) as error:
        parser.exit(2, f"Error en los datos: {error}\n")
