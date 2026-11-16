# Fuentes para el diseño del KNN

Consulta del 12 de noviembre de 2026. Los 237 registros de `variables_mensuales.csv` están fechados por mes de observación. Para reproducir una predicción pasada hay que verificar cuándo estuvo disponible cada valor y qué revisiones pudo haber. La tabla por sí sola no contiene ese historial de publicación.

| Columna | Serie y tratamiento |
| --- | --- |
| tc_var_pct | PN01246PM, variación porcentual del tipo de cambio nominal promedio mensual en soles por dólar |
| expectativa_inflacion_12m_pct | PD12912AM, expectativa a doce meses en porcentaje, tomada en nivel |
| wti_var_pct | Variación porcentual del precio spot WTI mensual en Cushing, en dólares por barril |
| fao_alimentos_var_pct | Variación porcentual del índice nominal general de precios de alimentos de la FAO |

Cada variación se calculó como 100 × (nivel del mes / nivel anterior − 1), incluyendo diciembre de 2006 para calcular enero de 2007. Las cifras derivadas se redondearon a ocho decimales.

Fuentes económicas: [consulta BCRP de las dos series](https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PN01246PM-PD12912AM/json/2006-12/2026-09/esp), [tabla mensual WTI de EIA](https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?f=M&n=PET&s=RWTC), [CSV mensual nominal de FAO](https://www.fao.org/worldfoodsituation/foodpricesindex/en/).

`enfen_eventos_observados_hasta_2024.csv` reproduce los intervalos y magnitudes de la tabla 3 de la [Nota Técnica ENFEN 01-2024](https://enfen.imarpe.gob.pe/download/nota-tecnica-enfen-01-2024-definicion-operacional-de-los-eventos-el-nino-costero-y-la-nina-costera-en-el-peru/?wpdmdl=1905). Describe episodios identificados retrospectivamente. Para activar avisos en simulaciones históricas se requiere la fecha de emisión y el estado aplicable del [comunicado ENFEN](https://enfen.imarpe.gob.pe/comunicados/) disponible al emitir el pronóstico. Los meses posteriores a la cobertura de la nota quedan sin determinar en esta tabla.
