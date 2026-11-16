# Anexos de las variables del proyecto KNN

Documento preparado el 13 de noviembre de 2026 a partir del código del proyecto, los archivos locales y las fuentes oficiales enlazadas. Describe la implementación actual; las razones económicas para incluir variables son hipótesis que deben evaluarse empíricamente.

## Alcance y notación

El objetivo es predecir la categoría de la inflación interanual de Lima Metropolitana en el mes t+1, utilizando información del mes de origen t y meses anteriores. La salida es una clase, no un porcentaje. El archivo local de inflación abarca enero de 2007 a septiembre de 2026. La cobertura local no equivale necesariamente a la última información publicada en las fuentes.

IPC es el índice de precios al consumidor; m es su variación porcentual mensual; a es su variación porcentual interanual. Un rezago es un dato de un mes anterior.

## Anexo A. Inflación mensual de Lima Metropolitana

- Fuente de consulta: BCRPData, serie PN01271PM, «Índice de precios Lima Metropolitana (var% mensual) - IPC».
- Enlace: https://estadisticas.bcrp.gob.pe/estadisticas/series/mensuales/resultados/PN01271PM/html
- Columna del programa: `mensual`.
- Unidad: porcentaje mensual.
- Definición: m_t = 100 × (IPC_t / IPC_(t−1) − 1).
- Tratamiento actual: la variación ya viene calculada en el CSV; el programa no la calcula a partir del nivel del IPC.
- Interpretación: 0,3 significa que los precios aumentaron 0,3 % respecto del mes anterior.
- Uso: entrada en t y base de dos rezagos. Permite representar movimientos recientes de precios; su contribución predictiva debe comprobarse.

## Anexo B. Inflación interanual de Lima Metropolitana

- Fuente de consulta: BCRPData, serie PN01273PM, «Índice de precios Lima Metropolitana (var% 12 meses) - IPC».
- Enlace: https://estadisticas.bcrp.gob.pe/estadisticas/series/mensuales/resultados/PN01273PM/html
- Columna: `interanual`.
- Unidad: porcentaje de variación en doce meses.
- Definición: a_t = 100 × (IPC_t / IPC_(t−12) − 1).
- Tratamiento actual: se importa la tasa ya calculada.
- Interpretación: 4 significa que el IPC es 4 % mayor que en el mismo mes del año anterior.
- Uso: a_t y a_(t−1) son entradas; la categoría de a_(t+1) es la respuesta que se aprende. Son observaciones de fechas diferentes.

## Anexo C. Rezagos de la inflación

No requieren nuevas fuentes: se construyen desplazando las series de los anexos A y B.

| Entrada | Dato usado para predecir t+1 | Construcción |
| --- | --- | --- |
| `mensual_anterior` | m_(t−1) | `mensual.shift(1)` |
| `mensual_dos_meses` | m_(t−2) | `mensual.shift(2)` |
| `interanual_anterior` | a_(t−1) | `interanual.shift(1)` |

Junto con `mensual` e `interanual`, forman las cinco entradas del KNN tradicional. Representan la evolución reciente; no constituyen cinco fuentes independientes.

## Anexo D. Variación del tipo de cambio

- Fuente: BCRPData, PN01246PM, «Tipo de cambio nominal promedio (S/ por US$)».
- Enlace: https://estadisticas.bcrp.gob.pe/estadisticas/series/mensuales/resultados/PN01246PM/html
- Columna derivada: `tc_var_pct`.
- Transformación documentada en el proyecto: 100 × (TC_t / TC_(t−1) − 1).
- Unidad usada: variación porcentual mensual, no soles por dólar.
- Interpretación: un valor positivo indica que aumentaron los soles necesarios para comprar un dólar; uno negativo indica que disminuyeron.
- Justificación a evaluar: puede aportar información sobre costos de importación. No implica un traslado automático ni proporcional a los precios al consumidor.
- Uso actual: se toma el valor de t−1 mediante `shift(1)`.

## Anexo E. Expectativa de inflación a doce meses

- Fuente: Encuesta de Expectativas Macroeconómicas del BCRP, PD12912AM.
- Enlace: https://estadisticas.bcrp.gob.pe/estadisticas/series/mensuales/expectativas-macroeconomicas
- Columna: `expectativa_inflacion_12m_pct`.
- Unidad: porcentaje de inflación esperada a doce meses.
- Tratamiento: se conserva la tasa publicada; no se calcula su variación mensual.
- Interpretación: 2,5 representa una expectativa de inflación a doce meses de 2,5 %. No es inflación observada ni una subida mensual de 2,5 %.
- Justificación a evaluar: incorporar información de expectativas como predictor adicional.
- Uso actual: valor de t−1. El horizonte de la expectativa no cambia el horizonte t+1 del clasificador.

## Anexo F. Variación del precio del petróleo WTI

- Fuente: U.S. Energy Information Administration (EIA), precio spot WTI en Cushing, serie mensual RWTC.
- Enlace: https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?f=M&n=PET&s=RWTC
- Serie original: dólares estadounidenses por barril.
- Columna derivada: `wti_var_pct`.
- Transformación documentada: 100 × (WTI_t / WTI_(t−1) − 1).
- Unidad usada: variación porcentual mensual.
- Interpretación: 5 indica un aumento mensual del precio WTI de 5 %, no de cinco dólares.
- Justificación a evaluar: representar cambios internacionales de costos energéticos y transporte. No mide directamente el precio del combustible en Lima.
- Uso actual: valor de t−1.

## Anexo G. Variación del índice de alimentos de la FAO

- Fuente: Food and Agriculture Organization of the United Nations, FAO Food Price Index.
- Enlace: https://www.fao.org/worldfoodsituation/foodpricesindex/en/
- Serie original seleccionada según el anexo de fuentes local: índice nominal general de precios de alimentos.
- Columna derivada: `fao_alimentos_var_pct`.
- Transformación documentada: 100 × (FAO_t / FAO_(t−1) − 1).
- Unidad usada: variación porcentual mensual.
- Interpretación: 2 indica que el índice internacional aumentó 2 % respecto del mes anterior. No significa que los alimentos en Lima subieran ese porcentaje.
- Justificación a evaluar: representar condiciones de precios internacionales de alimentos que podrían contribuir al pronóstico.
- Uso actual: valor de t−1.

## Anexo H. Información ENFEN para la restricción

- Fuente de episodios observados: Nota Técnica ENFEN 01-2024, tabla 3.
- Enlace: https://enfen.imarpe.gob.pe/download/nota-tecnica-enfen-01-2024-definicion-operacional-de-los-eventos-el-nino-costero-y-la-nina-costera-en-el-peru/
- Fuente para reconstruir alertas: https://enfen.imarpe.gob.pe/comunicados/
- Archivo local de episodios: `enfen_eventos_observados_hasta_2024.csv`; registra inicio, fin, duración y magnitud de episodios identificados retrospectivamente.
- El clasificador lee [alertas_enfen.csv](alertas_enfen.csv). Cada fila incluye el mes objetivo, la fecha del comunicado vigente al corte del día 1, el estado para el filtro, el episodio de alerta y el enlace al comunicado oficial. El registro cubre abril de 2015 a octubre de 2026. Los meses fuera de ese intervalo tienen estado desconocido.
- La fecha del comunicado se usa como fecha de publicación para simular el corte mensual. Solo la alerta de El Niño Costero activa la restricción. La vigilancia, la alerta de La Niña y el estado no activo se codifican como `sin_alerta` para este filtro. El identificador agrupa meses consecutivos bajo alerta y sirve para contar episodios entre los vecinos.
- ENFEN no es una décima entrada de distancia. Si el mes objetivo tiene alerta, el programa limita los candidatos a antecedentes cuyos meses siguientes también tenían alerta, siempre que existan al menos cinco candidatos utilizables.
- Si no hay suficientes candidatos o el estado es desconocido, utiliza el historial general.
- La cronología de episodios confirmados no demuestra qué alerta se conocía al emitir un pronóstico histórico. El código no convierte automáticamente esa cronología en alertas.

## Anexo I. Variable objetivo

Para cada fila histórica t, la etiqueta se obtiene de la inflación interanual del mes siguiente: y_t = categoría(a_(t+1)). Se implementa con `shift(-1)` y `map(categoria)`.

| Valor interanual del mes objetivo | Clase del programa |
| --- | --- |
| Menor que 0 % | Deflación |
| Desde 0 % hasta menos de 1 % | Por debajo del rango meta |
| Desde 1 % hasta 3 %, incluidos | Dentro del rango meta |
| Mayor que 3 % | Por encima del rango meta |

Para pronosticar octubre de 2026 con origen en septiembre de 2026, las cinco entradas tradicionales son: mensual de septiembre, interanual de septiembre, mensual de agosto, mensual de julio e interanual de agosto. El modelo ampliado añade las cuatro variables externas de agosto. La etiqueta de octubre no se utiliza para construir ese pronóstico.

## Preparación y evaluación que deben describirse en la metodología

1. Ordenar los datos por mes y comprobar continuidad y valores finitos.
2. Construir los rezagos y descartar filas incompletas.
3. Ajustar `StandardScaler` con el historial de entrenamiento; aplicar esa escala a candidatos y consulta.
4. Buscar cinco vecinos mediante distancia Manhattan y votar usando la categoría interanual del mes siguiente a cada vecino.
5. Comparar KNN tradicional, general ampliado y restringido sobre los mismos meses mediante una evaluación cronológica.
6. Informar exactitud, precisión por clase, recall, F1 macro, matriz de confusión y cantidad de casos por clase. Comparar también con una referencia sencilla, como repetir la categoría del mes de origen.

Las cuatro series externas locales contienen 237 meses, de enero de 2007 a septiembre de 2026, según el anexo de preparación existente. Se incluyó diciembre de 2006 como base de las variaciones de enero de 2007. Las transformaciones ya están almacenadas en `variables_mensuales.csv`; `main.py` las lee y aplica el rezago.

El rezago de un mes es una regla del programa, pero no acredita por sí solo que todos los valores estuvieran publicados en la fecha simulada. Falta verificar las fechas históricas de difusión y las revisiones. Las variables externas son candidatas a mejorar el pronóstico: la mejora y el efecto de la restricción deben demostrarse con resultados, no darse por supuestos.

Referencias y registro previo de obtención: `anexo_fuentes_apa7.md`. Ese registro declara una consulta el 12 de noviembre de 2026; no debe confundirse con una nueva descarga de las series en este documento.
