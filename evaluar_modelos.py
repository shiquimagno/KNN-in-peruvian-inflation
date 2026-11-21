"""Evalúa retrospectivamente las tres variantes KNN de AlertaIPC."""

from pathlib import Path

import pandas as pd
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator
from sklearn.metrics import classification_report, confusion_matrix

import main
from src.graficos import guardar_figura
from src.resultados import NOMBRES
from src.resumen import guardar_csv

ETIQUETAS = {
    NOMBRES["Tradicional (5 variables)"]: "KNN tradicional",
    NOMBRES["General (9 variables)"]: "KNN general",
    NOMBRES["Restringido (9 variables)"]: "KNN restringido",
}
# Usa None para cubrir todo el historial o indica un mes en formato AAAA-MM.
INICIO = None
FIN = None
SALIDA = Path(__file__).resolve().parent / "resultados" / "retrospectiva"
TAMANO_GRAFICO = (11.5, 4.4)


def evaluar(datos, alertas, inicio, fin):
    """Predice cada mes con el historial disponible hasta el mes anterior."""
    tradicionales = main.preparar_entradas(datos, ampliadas=False)
    ampliadas = main.preparar_entradas(datos)
    version = main.version_evaluacion()
    filas = []
    for objetivo in datos.loc[inicio:fin].index:
        origen = objetivo - 1
        historial = datos.loc[:origen]
        entradas_tradicionales = tradicionales.loc[:origen]
        entradas_ampliadas = ampliadas.loc[:origen]
        predicciones = {}
        filtro_aplicado = False
        for nombre, usar_ampliadas, restringido in main.MODELOS:
            entradas = entradas_ampliadas if usar_ampliadas else entradas_tradicionales
            prediccion = main.clasificar(historial, entradas, origen, alertas, restringido)
            predicciones[NOMBRES[nombre]] = prediccion.clase
            if restringido:
                filtro_aplicado = prediccion.filtrado

        comparable = all(clase is not None for clase in predicciones.values())
        estado, episodio = alertas.get(objetivo, ("desconocido", ""))
        inflacion = datos.loc[objetivo, "interanual"]
        real = main.categoria(inflacion)
        for modelo, estimacion in predicciones.items():
            filas.append({
                "version": version,
                "mes": str(objetivo),
                "modelo": modelo,
                "inflacion_interanual_pct": inflacion,
                "real": real,
                "estimacion": estimacion,
                "comparable": comparable,
                "estado_enfen": estado,
                "episodio_enfen": episodio,
                "filtro_enfen_aplicado": filtro_aplicado,
            })
    return pd.DataFrame(filas)


def calcular_metricas(predicciones):
    """Mide el desempeño sobre los mismos meses para todos los modelos."""
    comunes = predicciones.loc[predicciones.comparable]
    filtrados = comunes.loc[comunes.filtro_enfen_aplicado]
    supera_umbral = main.categoria(4)
    resumen, categorias, matrices = [], [], []
    for ambito, muestra in (("global", comunes), ("con_filtro_enfen", filtrados)):
        for modelo, grupo in muestra.groupby("modelo", sort=False):
            informe = classification_report(
                grupo.real, grupo.estimacion, labels=main.CLASES,
                output_dict=True, zero_division=0,
            )
            macro = informe["macro avg"]
            base = {"version": grupo.version.iloc[0], "ambito": ambito, "modelo": modelo}
            aciertos = int(grupo.real.eq(grupo.estimacion).sum())
            resumen.append({
                **base,
                "mes_inicio": grupo.mes.min(),
                "mes_fin": grupo.mes.max(),
                "n_meses": len(grupo),
                "aciertos": aciertos,
                "exactitud": aciertos / len(grupo),
                "exactitud_umbral_3_pct": grupo.real.eq(supera_umbral).eq(
                    grupo.estimacion.eq(supera_umbral)
                ).mean(),
                "precision_macro": macro["precision"],
                "recall_macro": macro["recall"],
                "f1_macro": macro["f1-score"],
            })
            matriz = confusion_matrix(grupo.real, grupo.estimacion, labels=main.CLASES)
            for i, clase in enumerate(main.CLASES):
                metricas = informe[clase]
                categorias.append({
                    **base,
                    "categoria": clase,
                    "casos_reales": int(metricas["support"]),
                    "casos_predichos": int(matriz[:, i].sum()),
                    "aciertos": int(matriz[i, i]),
                    "precision": metricas["precision"],
                    "recall": metricas["recall"],
                    "f1": metricas["f1-score"],
                })
                for predicha, casos in zip(main.CLASES, matriz[i]):
                    matrices.append({
                        **base, "real": clase, "predicha": predicha, "casos": casos,
                    })
    return pd.DataFrame(resumen), pd.DataFrame(categorias), pd.DataFrame(matrices)


def mostrar_aciertos(resultados):
    """Presenta los aciertos de cada KNN y destaca el mayor conteo."""
    total = resultados.n_meses.iloc[0]
    ganadores = resultados.loc[resultados.aciertos.eq(resultados.aciertos.max())]
    nombres = " y ".join(ganadores.modelo.map(ETIQUETAS))
    aciertos = ganadores.aciertos.iloc[0]
    porcentaje = f"{aciertos / total:.1%}".replace(".", ",")
    encabezado = "KNN con más aciertos" if len(ganadores) == 1 else "Empate entre KNN"
    print(f"{encabezado} · {nombres} · {aciertos} de {total} meses ({porcentaje}).")
    print("Un acierto significa que la categoría pronosticada coincide con la observada.\n")

    mostrar_tabla_aciertos(resultados)


def mostrar_tabla_aciertos(resultados):
    tabla = pd.DataFrame({
        "Pronóstico": resultados.modelo.map(ETIQUETAS),
        "Meses acertados": resultados.aciertos,
        "Exactitud": resultados.exactitud.map(lambda valor: f"{valor:.1%}".replace(".", ",")),
    })
    print(tabla.to_string(index=False))


def dibujar_barras(eje, resultados):
    total = resultados.n_meses.iloc[0]
    maximo = resultados.aciertos.max()
    colores = ["#176B52" if aciertos == maximo else "#3881A9"
               for aciertos in resultados.aciertos]
    barras = eje.barh(
        resultados.modelo.map(ETIQUETAS),
        resultados.aciertos,
        color=colores,
    )
    etiquetas = [f"{aciertos}/{total}" for aciertos in resultados.aciertos]
    eje.bar_label(barras, labels=etiquetas, padding=6)
    eje.set_xlabel("Número de meses acertados")
    eje.set_xlim(0, total * 1.24)
    eje.xaxis.set_major_locator(MaxNLocator(nbins=6, integer=True))
    eje.set_axisbelow(True)
    eje.grid(axis="x", alpha=0.25)
    eje.spines[["top", "right"]].set_visible(False)


def dibujar_grafico(figura, resultados, con_alerta, con_filtro):
    """Muestra los aciertos globales y el uso de ENFEN en el KNN restringido."""
    globales, enfen = figura.subplots(1, 2)
    fila = resultados.iloc[0]
    periodo = fila.mes_inicio
    if fila.mes_inicio != fila.mes_fin:
        periodo = f"{fila.mes_inicio} a {fila.mes_fin}"
    total = fila.n_meses
    figura.suptitle(f"Evaluación de los modelos KNN · {periodo}")
    globales.set_title(f"Aciertos globales · {total} meses")
    dibujar_barras(globales, resultados)
    globales.invert_yaxis()

    enfen.set_title(
        f"Uso del filtro ENFEN · KNN restringido\nAplicado en {con_filtro} de {total} meses comparables"
    )
    if con_alerta == 0:
        enfen.set_axis_off()
        enfen.text(0.5, 0.5, "Sin meses con alerta ENFEN",
                   ha="center", va="center", transform=enfen.transAxes)
        return

    conteos = [con_filtro, con_alerta - con_filtro]
    barras = enfen.barh(["Aplicó el filtro", "Usó el historial general"],
                       conteos, color=["#176B52", "#737D86"])
    enfen.bar_label(barras, labels=[f"{cantidad}/{con_alerta}" for cantidad in conteos],
                    padding=6)
    enfen.set_xlabel("Meses con alerta ENFEN")
    enfen.set_xlim(0, con_alerta * 1.24)
    enfen.xaxis.set_major_locator(MaxNLocator(nbins=6, integer=True))
    enfen.set_axisbelow(True)
    enfen.grid(axis="x", alpha=0.25)
    enfen.spines[["top", "right"]].set_visible(False)
    enfen.invert_yaxis()


def mostrar_grafico_aciertos(resultados, con_alerta, con_filtro):
    from matplotlib import pyplot as plt
    from matplotlib.backends.registry import backend_registry

    try:
        _, interfaz = backend_registry.resolve_backend(plt.get_backend())
        if interfaz is None:
            print("Abre el PNG guardado para ver el gráfico en este entorno.")
            return
        figura = plt.figure(figsize=TAMANO_GRAFICO, layout="constrained")
        try:
            dibujar_grafico(figura, resultados, con_alerta, con_filtro)
            plt.show(block=True)
        finally:
            plt.close(figura)
    except (ImportError, OSError, RuntimeError) as error:
        print(f"Abre el PNG guardado para ver el gráfico. {error}")


def ejecutar(mostrar_grafico=False):
    datos = main.cargar_datos()
    alertas = main.cargar_alertas()
    desde, hasta = datos.index[1], datos.index[-1]
    inicio = desde if INICIO is None else pd.Period(INICIO, freq="M")
    fin = hasta if FIN is None else pd.Period(FIN, freq="M")
    if not desde <= inicio <= fin <= hasta:
        raise ValueError(f"El intervalo debe estar en orden y dentro de {desde} a {hasta}.")

    predicciones = evaluar(datos, alertas, inicio, fin)
    if not predicciones.comparable.any():
        raise ValueError("El intervalo no contiene meses con predicción de los tres KNN.")
    resumen, categorias, matrices = calcular_metricas(predicciones)
    guardar_csv(predicciones, SALIDA / "predicciones.csv")
    guardar_csv(resumen, SALIDA / "resumen.csv")
    guardar_csv(categorias, SALIDA / "por_categoria.csv")
    guardar_csv(matrices, SALIDA / "matrices_confusion.csv")

    resultados = resumen.loc[resumen.ambito.eq("global")]
    filtrados = resumen.loc[resumen.ambito.eq("con_filtro_enfen")]
    meses = predicciones.loc[predicciones.comparable].drop_duplicates("mes")
    cobertura = meses.estado_enfen.value_counts()
    con_alerta = cobertura.get("alerta", 0)
    con_filtro = meses.filtro_enfen_aplicado.sum()

    grafico = SALIDA / "frecuencia_aciertos.png"
    figura = Figure(figsize=TAMANO_GRAFICO, layout="constrained")
    dibujar_grafico(figura, resultados, con_alerta, con_filtro)
    guardar_figura(figura, grafico)
    mostrar_aciertos(resultados)

    print(f"\nMeses comparables · {len(meses)} de {predicciones.mes.nunique()} solicitados")
    print(f"ENFEN · {con_alerta} con alerta, "
          f"{cobertura.get('sin_alerta', 0)} sin alerta, "
          f"{cobertura.get('desconocido', 0)} con estado desconocido.")
    print(f"El KNN restringido aplicó el filtro en {con_filtro} de {len(meses)} meses comparables.")
    if con_alerta > con_filtro:
        print(f"En {con_alerta - con_filtro} meses con alerta usó el historial general "
              f"porque había menos de {main.K} antecedentes con alerta.")
    if not filtrados.empty:
        print(f"\nAciertos en los {con_filtro} meses en que el KNN restringido aplicó el filtro")
        mostrar_tabla_aciertos(filtrados)

    print("Simulación con las series recopiladas. La disponibilidad y las revisiones "
          "históricas de los datos económicos quedan por verificar.")
    print(f"Gráfico de aciertos · {grafico.resolve()}")
    print(f"Archivos CSV guardados en {SALIDA.resolve()}.")
    if mostrar_grafico:
        mostrar_grafico_aciertos(resultados, con_alerta, con_filtro)


if __name__ == "__main__":
    try:
        ejecutar(mostrar_grafico=True)
    except (OSError, KeyError, ValueError) as error:
        raise SystemExit(f"No se pudo ejecutar la evaluación. {error}") from None
