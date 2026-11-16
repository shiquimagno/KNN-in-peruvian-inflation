# Herramientas de Python y bibliotecas del proyecto
import ast
import hashlib
import inspect
import json
import textwrap
import tracemalloc
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd
import questionary
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
)
from sklearn.neighbors import KNeighborsClassifier
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

# Archivo de inflación y calendario de lectura
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


# Lectura y validación del historial de inflación
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


# Categorías de inflación respecto del rango meta
def categoria(inflacion):
    if inflacion < 0:
        return "Deflación"
    if inflacion < 1:
        return "Por debajo del rango meta"
    if inflacion <= 3:
        return "Dentro del rango meta"
    return "Por encima del rango meta"


# Rutas de trabajo y configuración de los tres modelos
FUENTES = CSV.parents[1] / "fuentes_adicionales"
METRICAS = CSV.parents[1] / "metrics.csv"
CLASES = [categoria(x) for x in (-1, 0.5, 2, 4)]
K = 5
EXTERNAS = [
    "tc_var_pct",
    "expectativa_inflacion_12m_pct",
    "wti_var_pct",
    "fao_alimentos_var_pct",
]


MODELOS = [
    ("Tradicional (5 variables)", False, False),
    ("General (9 variables)", True, False),
    ("Restringido (9 variables)", True, True),
]


# Preparación de variables y rezagos mensuales
def preparar_entradas(datos, ampliadas=True):
    entradas = datos.assign(
        mensual_anterior=datos.mensual.shift(1),
        mensual_dos_meses=datos.mensual.shift(2),
        interanual_anterior=datos.interanual.shift(1),
    )
    if ampliadas:
        externas = pd.read_csv(
            FUENTES / "variables_mensuales.csv", index_col="mes_observacion"
        )
        externas.index = pd.PeriodIndex(externas.index, freq="M")
        # Un mes de rezago en cada fila, también al simular pronósticos antiguos.
        entradas = entradas.join(externas[EXTERNAS].reindex(datos.index).shift(1))
    return entradas.replace([np.inf, -np.inf], np.nan)


# Lectura de alertas ENFEN disponibles en cada fecha
def cargar_alertas(ruta=None):
    """Una fila por comunicado y mes objetivo al que aplica (AAAA-MM).
    fecha_publicacion: AAAA-MM-DD; estado: alerta/sin_alerta/desconocido;
    episodio: identificador común a los comunicados del mismo episodio.
    """
    archivo = FUENTES / "alertas_enfen.csv" if ruta is None else Path(ruta)
    if ruta is None and not archivo.exists():
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
    # Corte simulado: primer día del mes objetivo, tras conocer el IPC de origen.
    vigentes = tabla[tabla.fecha_publicacion <= tabla.mes_objetivo.dt.to_timestamp()]
    ultimos = vigentes.sort_values("fecha_publicacion").drop_duplicates(
        "mes_objetivo", keep="last"
    )
    return {
        r.mes_objetivo: (r.estado, r.episodio.strip()) for r in ultimos.itertuples()
    }


# Datos que devuelve cada consulta al clasificador
@dataclass
class Resultado:
    clase: str | None = None
    vecinos: list = field(default_factory=list)
    episodios: set = field(default_factory=set)
    vecinos_sin_episodio: int = 0
    filtrado: bool = False
    avisos: list = field(default_factory=list)
    preparacion_ms: float | None = None
    consulta_ms: float | None = None
    votos: list = field(default_factory=list)


# Entrenamiento y consulta del modelo KNN
def clasificar(datos, entradas, origen, alertas, restringido=False):
    inicio_preparacion = perf_counter()
    resultado = Resultado()
    # Condición climática del mes que se quiere predecir
    estado = alertas.get(origen + 1, ("desconocido", ""))[0]
    if restringido and estado == "alerta":
        resultado.avisos.append(
            "ENFEN: alerta de El Niño Costero para el mes objetivo."
        )
    elif restringido and estado == "desconocido":
        resultado.avisos.append(
            "Estado ENFEN desconocido. Se usa el historial general."
        )

    # Entradas completas y antecedentes con respuesta conocida
    if origen not in entradas.index or entradas.loc[origen].isna().any():
        resultado.avisos.append("Entradas incompletas para el mes de origen.")
        return resultado
    etiquetas = datos.interanual.loc[:origen].shift(-1).dropna().map(categoria)
    historial = entradas.loc[entradas.index.intersection(etiquetas.index)].dropna()
    if len(historial) < K:
        resultado.avisos.append("Hay menos de cinco meses históricos utilizables.")
        return resultado

    # La escala es idéntica en ambos KNN. Solo cambia el conjunto que puede votar.
    escala = StandardScaler().fit(historial)
    candidatos = historial
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

    # Ajuste del buscador con los candidatos admitidos
    modelo = KNeighborsClassifier(
        n_neighbors=K, metric="manhattan", weights="uniform", algorithm="brute"
    )
    modelo.fit(escala.transform(candidatos), etiquetas.loc[candidatos.index])
    resultado.preparacion_ms = (perf_counter() - inicio_preparacion) * 1000
    inicio_consulta = perf_counter()
    # Búsqueda de vecinos y orden reproducible ante distancias iguales
    consulta = escala.transform(entradas.loc[[origen]])
    # Distancias iguales: primero el mes más antiguo. Empate de votos: el vecino
    # más cercano entre las clases empatadas, usando el mismo orden reproducible.
    distancias, indices = modelo.kneighbors(consulta, n_neighbors=len(candidatos))
    orden = sorted(zip(distancias[0], indices[0]), key=lambda par: (par[0], par[1]))
    resultado.vecinos = [candidatos.index[i] for _, i in orden[:K]]
    # Clasificación por mayoría y resolución de empates
    votos = etiquetas.loc[resultado.vecinos].tolist()
    resultado.votos = votos
    conteo = Counter(votos)
    resultado.clase = next(
        voto for voto in votos if conteo[voto] == max(conteo.values())
    )
    # Episodios climáticos representados entre los vecinos
    for mes in resultado.vecinos:
        estado_vecino, episodio = alertas.get(mes + 1, ("desconocido", ""))
        if estado_vecino == "alerta":
            if episodio:
                resultado.episodios.add(episodio)
            else:
                resultado.vecinos_sin_episodio += 1
    resultado.consulta_ms = (perf_counter() - inicio_consulta) * 1000
    return resultado


# Acceso breve al pronóstico tradicional
def pronosticar(datos):
    """Pronóstico tradicional del menú con las cinco variables originales."""
    return clasificar(datos, preparar_entradas(datos, False), datos.index[-1], {}).clase


# Identificación de reglas y datos para separar evaluaciones
def version_evaluacion(alertas=None):
    """Identifica los datos, las reglas y la configuración usados al evaluar."""
    if alertas is None:
        alertas = cargar_alertas()
    firma = hashlib.sha256()
    configuracion = {
        "k": K,
        "externas": EXTERNAS,
        "clases": CLASES,
        "alertas": sorted(
            (str(m), estado, episodio) for m, (estado, episodio) in alertas.items()
        ),
    }
    firma.update(json.dumps(configuracion, sort_keys=True).encode())
    for funcion in (
        cargar_datos,
        preparar_entradas,
        cargar_alertas,
        categoria,
        clasificar,
    ):
        fuente = textwrap.dedent(inspect.getsource(funcion))
        firma.update(ast.dump(ast.parse(fuente), include_attributes=False).encode())
    for ruta in (CSV, FUENTES / "variables_mensuales.csv"):
        firma.update(ruta.read_bytes())
    return firma.hexdigest()[:16]


# Lectura del historial de evaluaciones guardadas
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


# Evaluación retrospectiva de los tres modelos
def retrospectiva(datos, objetivo, alertas):
    origen = objetivo - 1
    if objetivo not in datos.index or origen not in datos.index:
        raise ValueError(
            "El mes objetivo y su mes anterior deben estar en el historial."
        )
    historial = datos.loc[:origen]
    version = version_evaluacion(alertas)
    resultados = []
    filas = []
    for nombre, ampliadas, restringido in MODELOS:
        # Memoria rastreada de Python durante preparación y clasificación.
        # Se detiene incluso si la consulta produce un error.
        tracemalloc.start()
        try:
            inicio = perf_counter()
            entradas = preparar_entradas(historial, ampliadas)
            entradas_ms = (perf_counter() - inicio) * 1000
            r = clasificar(historial, entradas, origen, alertas, restringido)
            pico_kib = tracemalloc.get_traced_memory()[1] / 1024
        finally:
            tracemalloc.stop()
        resultados.append((nombre, r))
        filas.append(
            {
                "mes": str(objetivo),
                "version": version,
                "modelo": nombre,
                "estimacion": r.clase,
                "filtro_aplicado": r.filtrado,
                "preparacion_ms": entradas_ms + r.preparacion_ms
                if r.preparacion_ms is not None
                else None,
                "consulta_ms": r.consulta_ms,
                "memoria_python_kib": pico_kib,
            }
        )
    # Comparación con la categoría observada y registro del acierto
    real = categoria(datos.loc[objetivo, "interanual"])
    mostrar_evaluacion(objetivo, datos.loc[objetivo, "interanual"], real, resultados)
    nuevos = pd.DataFrame(filas).assign(real=real)
    nuevos["precision"] = (
        nuevos.estimacion.eq(real).astype(float).where(nuevos.estimacion.notna())
    )
    if METRICAS.exists() and METRICAS.stat().st_size:
        nuevos = pd.concat([leer_metricas(METRICAS), nuevos], ignore_index=True)
    nuevos = nuevos.drop_duplicates(["version", "mes", "modelo"], keep="last")
    # Guardado del historial y actualización del resumen académico
    guardar_csv(nuevos, METRICAS)
    print(f"Evaluación guardada en {METRICAS}.")
    try:
        generar_resumen(mostrar=False)
        print(f"Resumen actualizado en {METRICAS.with_name('resumen_metricas.csv')}.\n")
    except (OSError, ValueError) as error:
        print(
            f"La evaluación quedó guardada. No se pudo actualizar el resumen: {error}\n"
        )


# Cálculo y presentación de las métricas comparativas
def generar_resumen(archivo_csv=None, mostrar=True, matrices=False):
    archivo_csv = Path(archivo_csv) if archivo_csv is not None else METRICAS
    destino = archivo_csv.with_name("resumen_metricas.csv")
    if not archivo_csv.exists() or not archivo_csv.stat().st_size:
        exportar_resumen(None, destino)
        if mostrar:
            print("Todavía no hay evaluaciones. Usa la opción 5 para evaluar un mes.")
        return None
    tabla = leer_metricas(archivo_csv)
    # Comparación limitada a la configuración actual
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
    # Meses con predicción disponible para los tres modelos
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
    # Métricas agregadas y resultados por categoría
    resumen = []
    detalles = []
    for nombre in nombres:
        grupo = pares[pares.modelo.eq(nombre)]
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
                "Aciertos": f"{grupo.estimacion.eq(grupo.real).sum()}/{len(grupo)}",
                "Exactitud": accuracy_score(grupo.real, grupo.estimacion),
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
    # Tabla principal e intervalo realmente evaluado
    print(f"Modelos comparados · {len(nombres)}")
    print(f"Meses evaluados por todos los modelos · {len(comunes)}")
    print(f"Intervalo evaluado · {min(comunes)} a {max(comunes)}")
    if len(comunes) <= 12:
        print(f"Meses incluidos · {', '.join(sorted(comunes))}")
    meses_intervalo = len(pd.period_range(min(comunes), max(comunes), freq="M"))
    if len(comunes) < meses_intervalo:
        print("Hay meses sin evaluar dentro del intervalo. Las métricas usan solo los meses incluidos.")
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
    # Soporte de cada categoría y matrices numéricas opcionales
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


# Acciones adicionales del resumen comparativo
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
                questionary.Choice(
                    "Mostrar gráfico comparativo", value="grafico"
                ),
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


# Menú principal y manejo de errores de la aplicación
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
                    externas = pd.read_csv(
                        FUENTES / "variables_mensuales.csv", index_col="mes_observacion"
                    )
                    externas.index = pd.PeriodIndex(externas.index, freq="M")
                    mostrar_datos(datos, externas, *intervalo)
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


# Inicio del programa al ejecutarlo desde la terminal
if __name__ == "__main__":
    menu()
