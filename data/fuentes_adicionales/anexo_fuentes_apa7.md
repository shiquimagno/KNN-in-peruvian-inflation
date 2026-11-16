# Anexo A

**Obtención y preparación de las variables económicas y de la cronología de El Niño Costero**

El 12 de noviembre de 2026 consultamos las bases de las instituciones productoras de los datos. En BCRPData identificamos por código la expectativa de inflación a doce meses (Banco Central de Reserva del Perú, s. f.-a, serie PD12912AM) y el tipo de cambio nominal promedio mensual (Banco Central de Reserva del Perú, s. f.-b, serie PN01246PM). Descargamos ambas series mediante la API del BCRP. Para el petróleo, consultamos la tabla mensual del precio spot del West Texas Intermediate en Cushing, expresado en dólares por barril (U.S. Energy Information Administration, s. f.). Para los alimentos, descargamos el archivo CSV mensual de índices nominales y seleccionamos la columna del índice general (Food and Agriculture Organization of the United Nations, s. f.).

Unimos las cuatro series por año y mes. Para el tipo de cambio, el petróleo y los alimentos, calculamos la variación porcentual mensual como 100 × (valor del mes / valor del mes anterior − 1). Incluimos diciembre de 2006 como base para calcular enero de 2007. Conservamos las expectativas en su unidad original, porcentaje de inflación esperada a doce meses. Obtuvimos 237 observaciones mensuales completas entre enero de 2007 y septiembre de 2026. La fecha de cada fila representa el mes observado. Las fechas históricas de publicación y las versiones disponibles en cada fecha requieren una verificación independiente.

Para identificar los episodios observados de El Niño Costero, consultamos la tabla 3 de la Nota Técnica ENFEN 01-2024. Transcribimos el mes inicial, el mes final, la duración y la magnitud de los 25 episodios del período cubierto por la tabla, de 1950 a 2024 (Comisión Multisectorial encargada del Estudio Nacional del Fenómeno «El Niño», 2024, tabla 3). Esta cronología permite agrupar los resultados de la evaluación por presencia de episodios confirmados. Para reconstruir una alerta disponible al emitir un pronóstico histórico se requiere el comunicado oficial vigente en esa fecha.

**Referencias**

Banco Central de Reserva del Perú. (s. f.-a). *Expectativa de inflación a 12 meses* (Serie PD12912AM) [Conjunto de datos]. BCRPData. Recuperado el 12 de noviembre de 2026, de <https://estadisticas.bcrp.gob.pe/estadisticas/series/mensuales/resultados/PD12912AM/html>

Banco Central de Reserva del Perú. (s. f.-b). *Tipo de cambio nominal promedio (S/ por US$)* (Serie PN01246PM) [Conjunto de datos]. BCRPData. Recuperado el 12 de noviembre de 2026, de <https://estadisticas.bcrp.gob.pe/estadisticas/series/mensuales/resultados/PN01246PM/html>

Comisión Multisectorial encargada del Estudio Nacional del Fenómeno «El Niño». (2024). *Definición operacional de los eventos El Niño Costero y La Niña Costera en el Perú* (Nota Técnica ENFEN 01-2024). <https://enfen.imarpe.gob.pe/download/nota-tecnica-enfen-01-2024-definicion-operacional-de-los-eventos-el-nino-costero-y-la-nina-costera-en-el-peru/>

Food and Agriculture Organization of the United Nations. (s. f.). *FAO food price index* [Conjunto de datos]. Recuperado el 12 de noviembre de 2026, de <https://www.fao.org/worldfoodsituation/foodpricesindex/en/>

U.S. Energy Information Administration. (s. f.). *Cushing, OK WTI spot price FOB (dollars per barrel)* [Conjunto de datos]. Recuperado el 12 de noviembre de 2026, de <https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?f=M&n=PET&s=RWTC>
