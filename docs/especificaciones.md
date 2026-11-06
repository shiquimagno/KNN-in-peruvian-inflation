# Especificaciones del proyecto

Estado: borrador para discusión, previo a la implementación.
Fecha: 5 de noviembre de 2026.

## 1. Objetivo

Evaluar la capacidad de KNN para predecir la categoría de inflación interanual
de Lima Metropolitana del mes siguiente, usando datos históricos publicados
por el BCRP y una evaluación temporal frente a una regla de persistencia.

El alcance propuesto distingue cuatro categorías: deflación, por debajo,
dentro y por encima del rango meta. Esto amplía el planteamiento inicial de
tres categorías al separar la deflación del resto de valores inferiores al 1 %.

## 2. Categorías de clasificación

La variable que se clasifica es la inflación interanual, no la mensual.
Los datos se expresan en porcentaje: el valor 1.5 significa 1.5 %.

| Identificador | Categoría                 | Condición               | Color de presentación |
| ------------- | ------------------------- | ----------------------- | --------------------- |
| deflacion     | Deflación                 | inflación < 0 %         | Azul                  |
| debajo        | Por debajo del rango meta | 0 % <= inflación < 1 %  | Amarillo              |
| dentro        | Dentro del rango meta     | 1 % <= inflación <= 3 % | Verde                 |
| encima        | Por encima del rango meta | inflación > 3 %         | Rojo                  |

## 3. Datos y variables

- Fuente y características del archivo: consultar `data/referencias.md`.
- Usar el CSV local ya descargado; no descargar datos durante la ejecución.
- Conservar el archivo original sin cambios.
- Leer sus dos filas de encabezado y su codificación Windows-1252.
- Interpretar los meses en español y ordenar cronológicamente.
- Verificar fechas únicas, continuidad mensual y valores numéricos finitos.

Para un mes de origen t, las cinco entradas iniciales propuestas son:

1. Inflación mensual de t.
2. Inflación mensual de t-1. # Mes anterior
3. Inflación mensual de t-2.
4. Inflación interanual de t.
5. Inflación interanual de t-1.

La respuesta es la categoría de inflación interanual de t+1. Eliminar de la
evaluación las filas sin historial suficiente o sin respuesta conocida. La
última fila con entradas completas puede usarse para un pronóstico futuro,
pero no para calcular métricas si todavía no se conoce su respuesta.

El pronóstico se emite después de publicarse los datos de t. Es una evaluación
retrospectiva con la versión descargada de los datos; no simula revisiones
históricas ni sus fechas de publicación si no se dispone de esa información.

## 4. Requisitos funcionales

| ID    | Requisito                       | Criterio de aceptación                                                                                             |
| ----- | ------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| RF-01 | Cargar y validar el CSV local   | Mostrar periodo, cantidad de meses y problemas detectados; impedir el entrenamiento si hay errores de estructura.  |
| RF-02 | Construir variables y etiquetas | Cada fila relaciona entradas de t con la categoría de t+1; informar las filas descartadas.                         |
| RF-03 | Clasificar la inflación         | Aplicar las cuatro reglas de la sección 2 sin huecos ni solapamientos.                                             |
| RF-04 | Entrenar KNN                    | Usar un Pipeline con StandardScaler y KNeighborsClassifier.                                                        |
| RF-05 | Seleccionar hiperparámetros     | Comparar número de vecinos, ponderación y distancia mediante validación temporal dentro del periodo de desarrollo. |
| RF-06 | Evaluar temporalmente           | Reservar un bloque final de meses y pronosticar cada mes usando únicamente respuestas ya conocidas en ese momento. |
| RF-07 | Implementar persistencia        | Pronosticar para t+1 la categoría observada en t, sin ajustar parámetros.                                          |
| RF-08 | Comparar los métodos            | Evaluar ambos sobre exactamente los mismos meses y exportar sus predicciones.                                      |
| RF-09 | Mostrar métricas                | Presentar F1 macro, accuracy, balanced accuracy, matriz de confusión y cantidad de observaciones por categoría.    |
| RF-10 | Consultar el próximo pronóstico | Mostrar mes de origen, mes objetivo y categoría estimada; aclarar que su resultado aún no está evaluado.           |
| RF-11 | Ofrecer un menú de terminal     | Permitir seleccionar opciones, volver al menú y salir; informar si faltan datos o resultados previos.              |
| RF-12 | Exportar resultados             | Guardar predicciones y métricas en CSV, gráficos y configuración utilizada en outputs/.                            |

## 5. Protocolo de evaluación

- Separar cronológicamente desarrollo y evaluación final; no mezclar meses al azar.
- Elegir los parámetros con TimeSeriesSplit y GridSearchCV solo en desarrollo.
- Ajustar el escalador dentro del Pipeline en cada entrenamiento.
- En la evaluación final, usar una ventana de entrenamiento expansiva y avanzar
  un mes cada vez. Mantener fijos los hiperparámetros seleccionados.
- Para predecir t+1 con entradas de t, solo entrenar con ejemplos cuya respuesta
  ya sea conocida hasta t. La fila de entradas de t no pertenece al entrenamiento.
- Comprobar que cada entrenamiento tenga suficientes ejemplos para el k elegido.
- Mantener visibles las cuatro clases en las matrices y reportar las clases
  ausentes en cada periodo. Definir explícitamente la política para métricas
  indefinidas antes de comparar resultados.
- Reportar la diferencia entre KNN y persistencia, incluso si KNN resulta peor.

Pendiente antes de experimentar: fijar fecha de corte, tamaño inicial de
entrenamiento, cantidad y tamaño de particiones, rejilla de parámetros y
tratamiento de métricas sin soporte. Decidir estos puntos sin consultar los
resultados del bloque final.

## 6. Menú propuesto

1. Ver datos y validaciones.
2. Ejecutar entrenamiento y evaluación temporal.
3. Ver comparación KNN vs. persistencia.
4. Ver pronóstico del mes siguiente al último dato disponible.
5. Exportar resultados y gráficos.
6. Ver metodología y significado de categorías.
7. Salir.

## 7. Stack y presentación

- Python; pandas y NumPy para datos; scikit-learn para modelado y evaluación.
- Seaborn para gráficos en una etapa posterior.
- Menú numerado con `input()` y `print()` de Python.
- venv y pip para el entorno; requirements.txt para dependencias; Git y GitHub
  para control de versiones y colaboración.

El borrador actual usa un solo archivo Python con un menú y KNN básico.
Los requisitos de evaluación y exportación describen el alcance posterior.

## 8. Requisitos de calidad y alcance

- Mantener el cálculo separado de la interfaz: menu.py presenta opciones;
  los módulos de datos, modelo y evaluación realizan las operaciones.
- Escribir funciones pequeñas y comentarios educativos que expliquen el
  propósito, la alineación temporal y las decisiones del código.
- Resolver rutas desde la ubicación del proyecto, sin depender del directorio
  desde el que se ejecute el comando.
- Mostrar errores comprensibles para archivos ausentes, entradas inválidas y
  cancelaciones del menú; no inventar resultados cuando una operación falle.
- Registrar versiones, configuración, periodo evaluado y parámetros elegidos
  para reproducir los resultados.
- El alcance inicial es una aplicación local de consola para aprendizaje y
  evaluación académica; no incluye servidor web, base de datos ni actualización automática.
