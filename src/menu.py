"""Preguntas de navegación y selección de fechas."""

# Bibliotecas para fechas y preguntas de terminal
import pandas as pd
import questionary

# Textos compartidos de navegación
VOLVER = "Volver al menú"
INSTRUCCION = "(Flechas para elegir · Enter para confirmar)"


# Selección de una fecha válida o regreso al menú
def elegir_fecha(mensaje, meses):
    opciones = [str(mes) for mes in meses]
    seleccion = questionary.autocomplete(
        mensaje,
        choices=[VOLVER, *opciones],
        match_middle=True,
        validate=lambda valor: valor in opciones or valor == VOLVER
        or "Elige una fecha de la lista con formato AAAA-MM.",
    ).ask()
    return None if seleccion in (None, VOLVER) else pd.Period(seleccion, freq="M")


# Meses con suficiente historial para la retrospectiva
def elegir_mes(datos, entradas, k):
    completos = entradas.dropna().index
    meses = [
        origen + 1
        for posicion, origen in enumerate(completos)
        if posicion >= k and origen + 1 in datos.index
    ][::-1]
    if not meses:
        print("Todavía no hay meses con suficientes datos para evaluar los modelos.")
        return None
    print(f"\nMeses evaluables de {meses[-1]} a {meses[0]}.")
    print("Escribe un año o mes y elige una sugerencia, o selecciona Volver al menú.\n")
    return elegir_fecha("Mes que quieres evaluar (AAAA-MM)", meses)


# Intervalo de observaciones que se mostrará en las tablas
def elegir_intervalo(datos):
    print(f"\nHistorial disponible de {datos.index[0]} a {datos.index[-1]}.")
    print("Escribe AAAA-MM y elige una sugerencia, o selecciona Volver al menú.\n")
    inicio = elegir_fecha("Primer mes", datos.index)
    if inicio is None:
        return None
    # Las opciones del final impiden seleccionar un intervalo invertido.
    fin = elegir_fecha("Último mes", datos.index[datos.index >= inicio])
    return None if fin is None else (inicio, fin)
