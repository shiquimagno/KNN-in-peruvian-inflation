# Todos los gráficos

from os import fspath, makedirs, path

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from src.resultados import NOMBRES


def guardar_figura(figura, destino):
    destino = fspath(destino)
    makedirs(path.dirname(path.abspath(destino)), exist_ok=True)
    # Agg permite guardar el PNG sin abrir una ventana.
    FigureCanvasAgg(figura)
    figura.savefig(destino, dpi=180, bbox_inches="tight")
    figura.clear()
    return destino


# Comparación de F1 y exactitud
def crear_comparacion(resumen, figura=None):
    if resumen is None or resumen.empty:
        raise ValueError("Todavía no hay meses comparables para graficar.")
    if figura is None:
        figura = Figure(figsize=(10, 5.5), layout="constrained")
    eje = figura.subplots()
    posiciones = list(range(len(resumen)))
    etiquetas = [
        NOMBRES.get(m, m).replace(" sin restricción", "") for m in resumen.Modelo
    ]
    # Desplaza cada barra medio ancho para que queden juntas.
    exactitud = eje.bar(
        [x - 0.18 for x in posiciones],
        resumen.Exactitud,
        width=0.36,
        label="Exactitud",
        color="#3673a6",
    )
    f1 = eje.bar(
        [x + 0.18 for x in posiciones],
        resumen["F1 macro"],
        width=0.36,
        label="F1 macro",
        color="#358365",
    )
    eje.bar_label(exactitud, fmt="%.3f", padding=3)
    eje.bar_label(f1, fmt="%.3f", padding=3)
    eje.set_xticks(posiciones, etiquetas)
    eje.set_ylim(0, 1.12)
    eje.set_yticks([0, 0.25, 0.5, 0.75, 1])
    eje.set_ylabel("Valor de la métrica (0 a 1)")
    fila = resumen.iloc[0]
    cantidad = (
        "1 mes evaluado" if fila["Meses"] == 1 else f"{fila['Meses']} meses evaluados"
    )
    eje.set_title(
        f"Comparación retrospectiva · {fila['Inicio']} a {fila['Fin']}\n"
        f"{cantidad} por los tres modelos"
    )
    eje.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncols=2)
    if fila["Meses"] == 1:
        figura.text(
            0.5,
            -0.02,
            "Un único mes aporta poca evidencia sobre el desempeño general.",
            ha="center",
            fontsize=9,
        )
    return figura


def graficar_comparacion(resumen, carpeta):
    figura = crear_comparacion(resumen)
    version = resumen.iloc[0]["Versión"]
    return guardar_figura(figura, path.join(carpeta, f"comparacion_{version}.png"))


def mostrar_comparacion(resumen):
    from matplotlib import pyplot as plt
    from matplotlib.backends.registry import backend_registry

    _, interfaz = backend_registry.resolve_backend(plt.get_backend())
    if interfaz is None:
        raise RuntimeError(
            "Matplotlib está usando un backend sin ventanas. Ejecuta el programa "
            "en una terminal con entorno gráfico y un backend interactivo."
        )
    figura = plt.figure(figsize=(10, 5.5), layout="constrained")
    try:
        crear_comparacion(resumen, figura)
        print("\nCierra la ventana del gráfico para regresar al resumen.\n")
        plt.show(block=True)
    finally:
        plt.close(figura)
