# Peruvian-inflation-by-KNN-

### Datos curiosos del proyecto

- Estructura de carpetas basada en separación de responsabilidades
- Somos 5 integrantes
- Usamos un filtro de fenoméno del Niño buscar los meses vecinos (siguientes, porque ahí se siente el impacto de la inflación) que presentaron el mismo fenóneno climático
- En este documento de word pueden ver el informe o si lo prefieren en el portafolio del autor principal:
- La predicción usa la categoría más frecuente entre los 5 vecinos más cercanos. En caso de empate, gana la categoría empatada que aparece primero por distancia.
- Al cambiar los datos de entrada o las reglas de evaluación, actualiza `REVISION_EVALUACION` en `main.py`. El resumen usa esa revisión y el valor de `K` para seleccionar las evaluaciones comparables.
