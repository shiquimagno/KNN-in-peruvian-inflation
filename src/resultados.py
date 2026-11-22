"""Presentación de datos, pronósticos y evaluaciones en la terminal."""

import pandas as pd


# FORMATO - nombres, fechas y tablas
NOMBRES = {
    "Tradicional (5 variables)": "Tradicional (5)",
    "General (9 variables)": "Ampliado sin restricción (9)",
    "Restringido (9 variables)": "Restringido ENFEN (9)",
}
MESES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


def fecha_legible(mes):
    return f"{MESES[mes.month - 1]} de {mes.year}"


def tabla_terminal(tabla, indice=False):
    print(
        tabla.to_string(
            index=indice,
            na_rep="Sin dato",
            float_format=lambda x: f"{x:.3f}".replace(".", ","),
        )
    )


# HISTORIAL - datos observados por mes
def mostrar_datos(datos, externas, inicio, fin):
    if inicio > fin or inicio not in datos.index or fin not in datos.index:
        raise ValueError(
            "El intervalo debe estar dentro del historial y en orden cronológico."
        )
    print(f"\nDATOS OBSERVADOS · {inicio} a {fin}")
    print("Inflación de Lima Metropolitana · Variación porcentual del IPC\n")
    ipc = datos.loc[inicio:fin].rename(
        columns={"mensual": "Mensual (%)", "interanual": "Interanual (%)"}
    )
    ipc.index.name = "Mes"
    tabla_terminal(ipc, indice=True)
    print("\nVARIABLES EXTERNAS · Mes original de observación")
    print("Variaciones mensuales en %, excepto expectativa a 12 meses (%).\n")
    columnas = {
        "tc_var_pct": "Tipo de cambio",
        "expectativa_inflacion_12m_pct": "Expectativa 12m",
        "wti_var_pct": "Petróleo WTI",
        "fao_alimentos_var_pct": "Alimentos FAO",
    }
    # Aquí mostramos las variables externas en su mes de observación.
    tabla = externas.reindex(ipc.index)[list(columnas)].rename(columns=columnas)
    tabla_terminal(tabla, indice=True)
    print(
        "\nEl modelo utiliza las variables externas con un mes adicional de rezago.\n"
    )


# RESULTADOS - pronósticos y evaluaciones
def mostrar_vecinos(nombre, resultado):
    print(f"\n{NOMBRES.get(nombre, nombre)}")
    for aviso in resultado.avisos:
        print(f"  {aviso}")
    if resultado.filtrado:
        print("  Filtro aplicado · Solo antecedentes cuyo mes siguiente tenía alerta.")
    if resultado.vecinos:
        print("\n  VECINOS SELECCIONADOS · Del más cercano al más lejano")
        tabla = pd.DataFrame(
            {
                "Mes vecino": [str(m) for m in resultado.vecinos],
                # El voto de cada vecino corresponde a su mes siguiente.
                "Mes siguiente": [str(m + 1) for m in resultado.vecinos],
            }
        )
        tabla_terminal(tabla)
    if resultado.filtrado:
        print(
            f"  Episodios identificados entre los vecinos · {len(resultado.episodios)}"
        )
        if resultado.vecinos_sin_episodio:
            print(
                f"  Vecinos sin episodio identificado · {resultado.vecinos_sin_episodio}"
            )


def mostrar_fechas(objetivo, ampliadas=True, enfen=False):
    print(f"Inflación conocida hasta {fecha_legible(objetivo - 1)}.")
    if ampliadas:
        print(f"Variables externas utilizadas de {fecha_legible(objetivo - 2)}.")
    if enfen:
        print(
            f"Se admiten comunicados ENFEN fechados hasta el 1 de {fecha_legible(objetivo)}."
        )


def mostrar_resultado(nombre, objetivo, resultado, ampliadas=False, enfen=False):
    print(f"\nPRONÓSTICO DE INFLACIÓN INTERANUAL · {fecha_legible(objetivo)}")
    mostrar_fechas(objetivo, ampliadas, enfen)
    print(f"\nCategoría prevista · {resultado.clase or 'Sin estimación'}")
    mostrar_vecinos(nombre, resultado)
    print()


def mostrar_evaluacion(objetivo, inflacion, real, resultados):
    print(f"\nEVALUACIÓN DE INFLACIÓN INTERANUAL · {fecha_legible(objetivo)}")
    mostrar_fechas(objetivo, ampliadas=True, enfen=True)
    print("Rango meta · 1 % a 3 %")
    tasa = f"{inflacion:.2f}".replace(".", ",")
    print(f"\nObservado · {tasa} % · {real}\n")
    filas = [
        {
            "Modelo": NOMBRES.get(nombre, nombre),
            "Predicción": r.clase or "Sin estimación",
            "Resultado": "Sin evaluar"
            if r.clase is None
            else ("Acertó" if r.clase == real else "Falló"),
        }
        for nombre, r in resultados
    ]
    tabla_terminal(pd.DataFrame(filas))
    for nombre, r in resultados:
        mostrar_vecinos(nombre, r)
    print()
