# Referencias y procedencia de los datos

## Fuente

- **Portal de descarga:** BCRPData, Banco Central de Reserva del Perú.
- **Fuente estadística indicada:** Instituto Nacional de Estadística e Informática (INEI).
- **Enlace:** https://estadisticas.bcrp.gob.pe/estadisticas/series/mensuales/inflacion
- **Fecha de descarga:** 19 de octubre de 2026.
- **Archivo descargado:** `Mensuales-20261019-144216.csv`
- **Cobertura geográfica:** Lima Metropolitana.
- **Frecuencia:** mensual.
- **Periodo seleccionado:** enero de 2007 a septiembre de 2026.

## Series seleccionadas

| Código | Descripción | Unidad |
|---|---|---|
| PN01271PM | Variación del IPC respecto al mes anterior | Porcentaje mensual |
| PN01273PM | Variación del IPC respecto al mismo mes del año anterior | Porcentaje en doce meses |

IPC significa Índice de Precios al Consumidor.

## Justificación de la selección

Estas dos series permiten construir las cinco variables de entrada acordadas: inflación mensual del mes consultado y de los dos meses anteriores, e inflación en doce meses del mes consultado y del anterior.

La variación en doce meses del mes siguiente permitirá construir la etiqueta de clasificación. El borrador actual distingue cuatro categorías: deflación, por debajo, dentro y por encima del rango meta, con los límites definidos en `docs/especificaciones.md`. Esa información futura se utilizará como respuesta durante el entrenamiento y la evaluación, sin incluirse entre las entradas de la predicción.

## Revisión del archivo

- Contiene 237 registros mensuales.
- No se detectaron meses faltantes ni repetidos.
- No se detectaron valores vacíos o no numéricos en las dos series.
- Contiene dos filas de encabezado.
- Se pudo leer utilizando la codificación Windows-1252.
- Se conserva el archivo original sin modificar su contenido.

Esta revisión comprueba la estructura y continuidad del archivo; no constituye una auditoría de las cifras publicadas.
