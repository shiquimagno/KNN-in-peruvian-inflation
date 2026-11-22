from os import path

import numpy as np
import pandas as pd
import questionary
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support
from sklearn.metrics.pairwise import manhattan_distances
from sklearn.preprocessing import StandardScaler

from src.menu import INSTRUCCION, VOLVER, elegir_intervalo, elegir_mes
from src.resultados import (
    NOMBRES,
    mostrar_datos,
    mostrar_evaluacion,
    mostrar_resultado,
    tabla_terminal,
)
from src.resumen import exportar_resumen, guardar_csv

# Rutas
RAIZ = path.dirname(path.realpath(__file__))
DATOS = path.join(RAIZ, "data")
CSV = path.join(DATOS, "originales", "ipc_lima_mensual_bcrp.csv")
FUENTES = path.join(DATOS, "entradas")
METRICAS = path.join(RAIZ, "resultados", "evaluaciones", "historial_evaluaciones.csv")
MESES = "ene feb mar abr may jun jul ago sep oct nov dic".split()


# IPC => lectura y validación del historial mensual
def cargar_datos():
    datos = pd.read_csv(CSV, encoding="cp1252", skiprows=[1])
    # La primera columna identifica cada mes con una etiqueta como Ene26
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


# Modelos
# Clases:
def categoria(inflacion):
    if inflacion < 0:
        return "Deflación"
    if inflacion < 1:
        return "Por debajo del rango meta"
    if inflacion <= 3:
        return "Dentro del rango meta"
    return "Por encima del rango meta"


CLASES = [categoria(x) for x in (-1, 0.5, 2, 4)]
# Vecinos elegidos:
K = 5
# Cambia la revisión si cambian los datos de entrada o las reglas de evaluación
REVISION_EVALUACION = "v2"
EXTERNAS = [
    "tc_var_pct",
    "expectativa_inflacion_12m_pct",
    "wti_var_pct",
    "fao_alimentos_var_pct",
]
# Modelos:
MODELOS = [
    ("Tradicional (5 variables)", False, False),
    (
        "General (9 variables)",
        True,
        False,
    ),
    ("Restringido (9 variables)", True, True),
]


# Variables externas (investigadas)
def cargar_externas():
    externas = pd.read_csv(
        path.join(FUENTES, "variables_externas_mensuales.csv"),
        index_col="mes_observacion",
    )
    externas.index = pd.PeriodIndex(externas.index, freq="M")
    return externas


def preparar_entradas(datos, ampliadas=True):
    entradas = datos.assign(
        mensual_anterior=datos.mensual.shift(1),
        mensual_dos_meses=datos.mensual.shift(2),
        interanual_anterior=datos.interanual.shift(1),
    )
    if ampliadas:
        externas = cargar_externas()
        # Para pronosticar abril con el IPC de marzo, las variables externas son de febrero.
        entradas = entradas.join(externas[EXTERNAS].reindex(datos.index).shift(1))
    return entradas.replace([np.inf, -np.inf], np.nan)


# Filtro de alertas del ENFEN (fenómeno del niño)
def cargar_alertas(ruta=None):
    archivo = (
        path.join(FUENTES, "alertas_enfen_mensuales.csv") if ruta is None else ruta
    )
    if ruta is None and not path.exists(archivo):
        return {}
    tabla = pd.read_csv(archivo, dtype=str, keep_default_na=False)
    requeridas = {"fecha_publicacion", "mes_objetivo", "estado", "episodio"}
    faltantes = requeridas - set(tabla.columns)
    if faltantes:
        raise ValueError(
            f"El archivo ENFEN carece de columnas: {', '.join(sorted(faltantes))}."
        )
    tabla["fecha_publicacion"] = pd.to_datetime(
        tabla.fecha_publicacion, format="%Y-%m-%d", errors="raise"
    )
    tabla["mes_objetivo"] = pd.PeriodIndex(tabla.mes_objetivo, freq="M")
    if tabla[["mes_objetivo", "fecha_publicacion"]].isna().any().any():
        raise ValueError("Falta el mes objetivo o la fecha de publicación de ENFEN.")
    if not tabla.estado.isin(["alerta", "sin_alerta", "desconocido"]).all():
        raise ValueError("Estado ENFEN desconocido en el archivo de comunicados.")
    if tabla.duplicated(["mes_objetivo", "fecha_publicacion"]).any():
        raise ValueError(
            "Hay dos estados ENFEN para el mismo mes y fecha de publicación."
        )
    # Solo cuentan los comunicados publicados hasta el primer día del mes objetivo.
    vigentes = tabla[tabla.fecha_publicacion <= tabla.mes_objetivo.dt.to_timestamp()]
    ultimos = vigentes.sort_values("fecha_publicacion").drop_duplicates(
        "mes_objetivo",
        keep="last",
    )
    return {
        r.mes_objetivo: (r.estado, r.episodio.strip()) for r in ultimos.itertuples()
    }


# Seleccionando vecinos para el KNN
class Resultado:
    def __init__(self):
        self.clase = None
        self.vecinos = []
        self.episodios = set()
        self.vecinos_sin_episodio = 0
        self.filtrado = False
        self.avisos = []


def clasificar(datos, entradas, origen, alertas, restringido=False):
    resultado = Resultado()
    estado = alertas.get(origen + 1, ("desconocido", ""))[0]
    if restringido and estado == "alerta":
        resultado.avisos.append(
            "ENFEN: alerta de El Niño Costero para el mes objetivo."
        )
    elif restringido and estado == "desconocido":
        resultado.avisos.append(
            "Estado ENFEN desconocido. Se usa el historial general."
        )

    if origen not in entradas.index or entradas.loc[origen].isna().any():
        resultado.avisos.append("Entradas incompletas para el mes de origen.")
        return resultado
    # Cada mes histórico vota con la categoría de su mes siguiente.
    etiquetas = datos.interanual.loc[:origen].shift(-1).dropna().map(categoria)
    historial = entradas.loc[entradas.index.intersection(etiquetas.index)].dropna()
    if len(historial) < K:
        resultado.avisos.append("Hay menos de cinco meses históricos utilizables.")
        return resultado

    # Las variantes de nueve variables comparten la escala
    escala = StandardScaler().fit(historial)
    candidatos = historial
    # Si la alerta deja menos de K vecinos posibles, se usa el historial general y se avisa
    if restringido and estado == "alerta":
        comparables = [
            m for m in historial.index if alertas.get(m + 1, ("", ""))[0] == "alerta"
        ]
        if len(comparables) >= K:
            candidatos = historial.loc[comparables]
            resultado.filtrado = True
        else:
            resultado.avisos.append(
                f"Solo {len(comparables)} antecedentes con alerta. Se usa el historial general."
            )

    consulta = escala.transform(entradas.loc[[origen]])
    distancias = manhattan_distances(consulta, escala.transform(candidatos))[0]
    cercanos = np.argsort(distancias, kind="stable")[:K]
    resultado.vecinos = candidatos.index[cercanos].tolist()
    clases = etiquetas.loc[resultado.vecinos]
    resultado.clase = clases[clases.isin(clases.mode())].iloc[0]
    for mes in resultado.vecinos:
        estado_vecino, episodio = alertas.get(mes + 1, ("desconocido", ""))
        if estado_vecino == "alerta":
            if episodio:
                resultado.episodios.add(episodio)
            else:
                resultado.vecinos_sin_episodio += 1
    return resultado


# Evaluación mensual
def version_evaluacion():
    return f"{REVISION_EVALUACION}-k{K}"


def leer_metricas(archivo):
    tabla = pd.read_csv(archivo)
    requeridas = {"mes", "modelo", "real", "estimacion"}
    faltantes = requeridas - set(tabla.columns)
    if faltantes:
        raise ValueError(
            f"El archivo de métricas carece de columnas: {', '.join(sorted(faltantes))}."
        )
    if "version" not in tabla:
        tabla["version"] = pd.NA
    return tabla


def retrospectiva(datos, objetivo, alertas):
    origen = objetivo - 1
    if objetivo not in datos.index or origen not in datos.index:
        raise ValueError(
            "El mes objetivo y su mes anterior deben estar en el historial."
        )
    historial = datos.loc[:origen]
    tradicionales = preparar_entradas(historial, ampliadas=False)
    ampliadas = preparar_entradas(historial)
    resultados = []
    for nombre, usar_ampliadas, restringido in MODELOS:
        entradas = ampliadas if usar_ampliadas else tradicionales
        r = clasificar(historial, entradas, origen, alertas, restringido)
        resultados.append((nombre, r))
    inflacion = datos.loc[objetivo, "interanual"]
    real = categoria(inflacion)
    mostrar_evaluacion(objetivo, inflacion, real, resultados)
    version = version_evaluacion()
    nuevos = pd.DataFrame(
        [
            {
                "mes": str(objetivo),
                "version": version,
                "modelo": nombre,
                "estimacion": r.clase,
                "filtro_aplicado": r.filtrado,
            }
            for nombre, r in resultados
        ]
    ).assign(real=real)
    if path.exists(METRICAS) and path.getsize(METRICAS):
        nuevos = pd.concat([leer_metricas(METRICAS), nuevos], ignore_index=True)
    nuevos = nuevos.drop_duplicates(["version", "mes", "modelo"], keep="last")
    guardar_csv(nuevos, METRICAS)
    print(f"Evaluación guardada en {METRICAS}.")
    try:
        generar_resumen(mostrar=False)
        destino = path.join(path.dirname(METRICAS), "resumen_metricas.csv")
        print(f"Resumen actualizado en {destino}.\n")
    except (OSError, ValueError) as error:
        print(
            f"La evaluación quedó guardada. No se pudo actualizar el resumen: {error}\n"
        )


# Resumen comparativo
def generar_resumen(archivo_csv=None, mostrar=True, matrices=False):
    if archivo_csv is None:
        archivo_csv = METRICAS
    destino = path.join(path.dirname(archivo_csv), "resumen_metricas.csv")
    if not path.exists(archivo_csv) or not path.getsize(archivo_csv):
        exportar_resumen(None, destino)
        if mostrar:
            print("Todavía no hay evaluaciones. Usa la opción 5 para evaluar un mes.")
        return None
    tabla = leer_metricas(archivo_csv)
    actual = version_evaluacion()
    coincide = tabla.version.eq(actual).fillna(False)
    excluidos = int((~coincide).sum())
    tabla = tabla[coincide].drop_duplicates(["mes", "modelo"], keep="last")
    if mostrar:
        print("\nCOMPARACIÓN DE MODELOS · Configuración actual")
        if excluidos:
            print(
                f"Se excluyeron {excluidos} registros de otras versiones o sin versión."
            )
    if tabla.empty:
        exportar_resumen(None, destino)
        if mostrar:
            print(
                "Usa la opción 5 para registrar evaluaciones con la configuración actual."
            )
            print(f"Resumen sin filas guardado en {destino}.\n")
        return None
    meses_validos = tabla.mes.astype("string").str.fullmatch(
        r"(?!0000)[0-9]{4}-(0[1-9]|1[0-2])", na=False
    )
    if not meses_validos.all():
        raise ValueError(
            "El registro contiene meses inválidos. Se espera el formato AAAA-MM."
        )
    if (
        not tabla.real.isin(CLASES).all()
        or not tabla.estimacion.dropna().isin(CLASES).all()
    ):
        raise ValueError(
            "El registro contiene categorías de clasificación desconocidas."
        )
    nombres = [nombre for nombre, _, _ in MODELOS]
    if not tabla.modelo.isin(nombres).all():
        raise ValueError("El registro contiene nombres de modelos desconocidos.")
    # La comparación incluye solo los meses con predicción de los tres modelos.
    conjuntos = [
        set(tabla.loc[tabla.modelo.eq(nombre) & tabla.estimacion.notna(), "mes"])
        for nombre in nombres
    ]
    comunes = set.intersection(*conjuntos)
    if not comunes:
        exportar_resumen(None, destino)
        if mostrar:
            print("Aún no hay meses evaluados por los tres modelos. Usa la opción 5.")
            print(f"Resumen sin filas guardado en {destino}.\n")
        return None
    pares = tabla[tabla.mes.isin(comunes)]
    if pares.groupby("mes").real.nunique().gt(1).any():
        raise ValueError(
            "Las respuestas reales difieren entre modelos para el mismo mes."
        )
    resumen = []
    detalles = []
    for nombre in nombres:
        grupo = pares[pares.modelo.eq(nombre)]
        aciertos = grupo.estimacion.eq(grupo.real).sum()
        precision, recall, f1, soporte = precision_recall_fscore_support(
            grupo.real, grupo.estimacion, labels=CLASES, zero_division=0
        )
        resumen.append(
            {
                "Versión": actual,
                "Modelo": nombre,
                "Inicio": min(comunes),
                "Fin": max(comunes),
                "Meses": len(grupo),
                "Aciertos": f"{aciertos}/{len(grupo)}",
                "Exactitud": aciertos / len(grupo),
                "Precisión macro": precision.mean(),
                "Recall macro": recall.mean(),
                "F1 macro": f1.mean(),
            }
        )
        detalle = pd.DataFrame(
            {
                "Categoría": CLASES,
                "Precisión": precision,
                "Recall": recall,
                "F1": f1,
                "Casos reales": soporte.astype(int),
            }
        )
        detalles.append((nombre, grupo, detalle))
    resumen = pd.DataFrame(resumen)
    exportar_resumen(resumen, destino)
    if not mostrar:
        return resumen
    print(f"Modelos comparados · {len(nombres)}")
    print(f"Meses evaluados por todos los modelos · {len(comunes)}")
    print(f"Intervalo evaluado · {min(comunes)} a {max(comunes)}")
    if len(comunes) <= 12:
        print(f"Meses incluidos · {', '.join(sorted(comunes))}")
    meses_intervalo = len(pd.period_range(min(comunes), max(comunes), freq="M"))
    if len(comunes) < meses_intervalo:
        print(
            "Hay meses sin evaluar dentro del intervalo. Las métricas usan solo los meses incluidos."
        )
    if len(comunes) == 1:
        print(
            "Solo hay un mes evaluado. Todavía hay poca evidencia para comparar el desempeño."
        )
    print()
    visible = resumen[
        [
            "Modelo",
            "Aciertos",
            "Exactitud",
            "Precisión macro",
            "Recall macro",
            "F1 macro",
        ]
    ].copy()
    visible["Modelo"] = visible.Modelo.map(NOMBRES)
    visible["Exactitud"] = visible.Exactitud.map(
        lambda x: f"{100 * x:.1f} %".replace(".", ",")
    )
    visible = visible.rename(columns={"Precisión macro": "Prec. macro"})
    tabla_terminal(visible)
    print(
        "\nExactitud = proporción de aciertos. Las métricas macro promedian las cuatro categorías."
    )
    print(
        "Las métricas indefinidas se fijan en 0. Revisa los casos reales de cada categoría."
    )
    for nombre, grupo, detalle in detalles:
        print(f"\n{NOMBRES[nombre]} · RESULTADOS POR CATEGORÍA")
        tabla_terminal(detalle)
        if detalle["Casos reales"].eq(0).any():
            print(
                "Hay categorías sin casos observados. Su detección aún no puede evaluarse."
            )
        if "filtro_aplicado" in grupo:
            aplicados = grupo.filtro_aplicado.astype(str).str.lower().eq("true").sum()
            if nombre == "Restringido (9 variables)":
                print(f"Filtro ENFEN aplicado en {aplicados} de {len(grupo)} meses.")
        if matrices:
            print("\nMatriz de confusión · Filas reales y columnas predichas")
            matriz = pd.DataFrame(
                confusion_matrix(grupo.real, grupo.estimacion, labels=CLASES),
                index=["Deflación", "Debajo", "Dentro", "Encima"],
                columns=["Deflación", "Debajo", "Dentro", "Encima"],
            )
            tabla_terminal(matriz, indice=True)
    if matrices:
        print(f"\nIdentificador técnico de configuración · {actual}")
    print(f"\nResumen CSV actualizado en {destino}.\n")
    return resumen


# MENÚS - resumen comparativo y opciones principales
def consultar_resumen():
    resumen = generar_resumen()
    if resumen is None:
        return
    while True:
        accion = questionary.select(
            "Detalle del resumen",
            choices=[
                questionary.Choice(VOLVER, value="volver"),
                questionary.Choice(
                    "Consultar matrices numéricas y versión", value="matrices"
                ),
                questionary.Choice("Mostrar gráfico comparativo", value="grafico"),
            ],
            instruction=INSTRUCCION,
        ).ask()
        if accion in (None, "volver"):
            return
        if accion == "matrices":
            resumen = generar_resumen(matrices=True)
        elif accion == "grafico":
            from src.graficos import mostrar_comparacion

            mostrar_comparacion(resumen)


def menu():
    opciones = [
        "Consultar datos por intervalo",
        "Pronosticar el próximo mes · KNN tradicional (5 variables)",
        "Pronosticar el próximo mes · KNN ampliado sin restricción (9 variables)",
        "Pronosticar el próximo mes · KNN restringido por alerta ENFEN (9 variables)",
        "Evaluar un mes en retrospectiva · Los tres modelos",
        "Mostrar resumen comparativo",
        "Salir",
    ]
    print("\nINFLACIÓN INTERANUAL DE LIMA METROPOLITANA")
    while True:
        print()
        try:
            opcion = questionary.select(
                "Elige una opción",
                choices=[
                    questionary.Choice(f"{i}. {nombre}", value=str(i))
                    for i, nombre in enumerate(opciones, 1)
                ],
                instruction=INSTRUCCION,
            ).ask()
            print()
            if opcion in (None, "7"):
                print("Sesión finalizada. Las evaluaciones guardadas se conservan.\n")
                return
            if opcion == "6":
                consultar_resumen()
                continue
            datos = cargar_datos()
            ultimo = datos.index[-1]
            if opcion == "1":
                intervalo = elegir_intervalo(datos)
                if intervalo is not None:
                    mostrar_datos(datos, cargar_externas(), *intervalo)
            elif opcion == "5":
                mes = elegir_mes(datos, preparar_entradas(datos), K)
                if mes is not None:
                    retrospectiva(datos, pd.Period(mes, freq="M"), cargar_alertas())
            elif opcion in ("2", "3", "4"):
                nombre, ampliadas, restringido = MODELOS[int(opcion) - 2]
                r = clasificar(
                    datos,
                    preparar_entradas(datos, ampliadas),
                    ultimo,
                    cargar_alertas() if restringido else {},
                    restringido,
                )
                mostrar_resultado(nombre, ultimo + 1, r, ampliadas, restringido)
        except (EOFError, KeyboardInterrupt):
            return
        except (
            AttributeError,
            ImportError,
            KeyError,
            OSError,
            ValueError,
            RuntimeError,
        ) as error:
            print(f"\nAviso: no se pudo completar la consulta. {error}\n")


if __name__ == "__main__":
    menu()
