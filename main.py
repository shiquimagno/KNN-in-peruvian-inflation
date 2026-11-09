from pathlib import Path

import pandas as pd
import questionary
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

CSV = Path(__file__).resolve().parent / "data/origiales/Mensuales-20261019-144216.csv"
MESES = [
    "ene",
    "feb",
    "mar",
    "abr",
    "may",
    "jun",
    "jul",
    "ago",
    "sep",
    "oct",
    "nov",
    "dic",
]


def cargar_datos():
    # La segunda fila describe las series. La primera contiene sus códigos.
    datos = pd.read_csv(
        CSV, encoding="cp1252", skiprows=[1]
    )  # Instanciamos pandas con datos
    fechas = datos.iloc[:, 0].str.lower()
    meses = fechas.str[:3].map({nombre: i for i, nombre in enumerate(MESES, 1)})
    fechas = pd.to_datetime(
        {
            "year": 2000 + fechas.str[3:].astype(int),
            "month": meses,
            "day": 1,
        }
    )
    datos.index = pd.PeriodIndex(fechas, freq="M")
    datos = datos[["PN01271PM", "PN01273PM"]].sort_index()
    datos.columns = ["mensual", "interanual"]
    datos = datos.apply(pd.to_numeric)
    if (
        len(datos) < 8
        or datos.isin([float("inf"), float("-inf")]).any().any()
        or datos.isna().any().any()
    ):
        raise ValueError(
            "Se necesitan al menos ocho meses con valores numéricos finitos."
        )
    if not datos.index.equals(
        pd.period_range(datos.index[0], datos.index[-1], freq="M")
    ):
        raise ValueError("El CSV tiene meses faltantes o repetidos.")
    return datos


def categoria(inflacion):
    if inflacion < 0:
        return "Deflación"
    if inflacion < 1:
        return "Por debajo del rango meta"
    if inflacion <= 3:
        return "Dentro del rango meta"
    return "Por encima del rango meta"


def pronosticar(datos):
    # Cada fila usa lo que se conoce en el mes t. shift(1) trae el mes anterior.
    entradas = datos.assign(
        mensual_anterior=datos.mensual.shift(1),
        mensual_dos_meses=datos.mensual.shift(2),
        interanual_anterior=datos.interanual.shift(1),
    ).dropna()
    # La fila t se entrena con la categoría observada en t+1.
    # La última fila solo sirve para pronosticar porque su respuesta aún falta.
    respuestas = datos.interanual.shift(-1).loc[entradas.index].iloc[:-1].map(categoria)
    modelo = make_pipeline(StandardScaler(), KNeighborsClassifier(n_neighbors=5))
    modelo.fit(entradas.iloc[:-1], respuestas)  # Entrenamiento
    return modelo.predict(entradas.iloc[[-1]])[0]  # Predicción


def menu():
    print("Inflación de Lima Metropolitana")
    # Después de cada consulta, el bucle vuelve a mostrar las opciones.
    while True:
        # 3. Menú tipo date usando textual para elegir la fecha en retrospectiva dentro del rango 2007 a 2026 octubre y se debe guardar en metrics.csv
        # 5. Resumen de KNN (cuando esté el KNN propuesto restringido se lo agrega al resumen). Debe incluir las métricas de precisión en promedio del metrics.cscv
        #
        try:
            opcion = questionary.select(
                "\nElige una opción: ",
                choices=[
                    questionary.Choice("1. Visualizar datos", value="datos"),
                    questionary.Choice(
                        "2. Pronosticar inflación con KNN tradicional",
                        value="knn_pronostico",
                    ),
                    questionary.Choice(
                        "3. Pronosticar en retrospectiva y evaluar pronóstico",
                        value="retrospectiva",
                    ),
                    questionary.Choice(
                        "4. Pronosticar con KNN restringido", value="knn_restringido"
                    ),
                    questionary.Choice(
                        "5. Mostrar resumen comparativo", value="resumen"
                    ),
                    questionary.Choice("6. Salir\n", value="salir"),
                ],
            ).ask()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        try:
            datos = cargar_datos()
            ultimo = datos.index[-1]
            if opcion == "datos":
                print(f"{len(datos)} meses, de {datos.index[0]} a {ultimo}.")
            elif opcion == "knn_pronostico":
                print(f"Pronóstico para {ultimo + 1}: {pronosticar(datos)}.")
            elif opcion == "restrospectiva":
                # Mostrar retrospectiva
                pass
            elif opcion == "knn_restringido":
                pass
            elif opcion == "resumen":
                ruta_metrics =(
                    Path(__file__).resolve().parent
                    /"data"
                    / "origiales"
                    / "metrics.csv"
                )
                generar_resumen(ruta_metrics)
            elif opcion == "salir":
                return
        except (KeyError, OSError, ValueError) as error:
            print(f"No se pudo completar la operación: {error}")


if __name__ == "__main__":
    menu()
