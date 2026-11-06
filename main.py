from pathlib import Path

import pandas as pd
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
        print("\n1. Ver datos\n2. Pronosticar con KNN\n3. Salir")
        try:
            opcion = input("Elige una opción: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if opcion == "3":
            return
        if opcion not in {"1", "2"}:
            print("Elige 1, 2 o 3.")
            continue

        try:
            datos = cargar_datos()
            ultimo = datos.index[-1]
            if opcion == "1":
                print(f"{len(datos)} meses, de {datos.index[0]} a {ultimo}.")
            else:
                print(f"Pronóstico para {ultimo + 1}: {pronosticar(datos)}.")
        except (KeyError, OSError, ValueError) as error:
            print(f"No se pudo completar la operación: {error}")


if __name__ == "__main__":
    menu()
