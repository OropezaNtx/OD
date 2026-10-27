# Buenavista OD: zona representativa por colonia (v09.40, prototipo)

## Objetivo autorizado
Encontrar una colonia o referencia geográfica razonable por origen/destino y elegir una **zona representativa**, aunque no conozcamos la calle exacta. Este enfoque es distinto de geocodificar domicilios. Los códigos elegidos son **propuestas**, no coordenadas verificadas de cada encuesta.

## Resultado offline, día 8
- 233 encuestas, 466 extremos OD.
- 367 extremos con zona **representativa propuesta**; 99 siguen pendientes.
- 93 de los extremos propuestos tienen más de 1,600 m de dispersión entre los centros de sus zonas de catálogo: **revisarlos prioritariamente**. No significa que la distancia desde la encuesta sea de 1,600 m; es la dispersión del propio catálogo.
- F5 origen: referencia Jardín del Arte Sullivan, zona **2025 validada por el usuario**.
- F5 destino: Avenida de las Granjas, zona **19017 provisional para el tramo próximo a Tecnoparque**; no identifica una bodega particular.
- Los demás resultados son inferencias del catálogo, no puntos independientes observados.

## Prioridad de decisión
1. **Referencia identificable** (parque, estación, mercado, Tecnoparque, avenida claramente nombrada), compatible con la encuesta. Las coordenadas proceden de una pequeña base de referencias abiertas y fueron cruzadas previamente con el KML; no se usa Google Places para alimentar el KML.
2. **Colonia y municipio tal como se capturaron**, con coincidencia en el catálogo.
3. **Corrección ortográfica** de la colonia dentro del municipio.
4. **Colonia inequívoca con municipio declarado equivocado**, permitiendo corregir el contexto cuando hay respaldo suficiente.
5. **Codificación anterior** solo como propuesta de baja confianza cuando el nombre es compatible o la colonia original no está indicada.
6. No elegir zona cuando hay demasiada ambigüedad.

Cuando una colonia aparece en varias zonas del catálogo, se selecciona un **medoide geográfico de los centros de las zonas asociadas** (zona más central entre esas opciones), validando que su código exista en el KML. Esto no calcula el centro real de una colonia porque **NO tenemos todavía polígonos de colonias**. Las otras zonas se conservan como alternativas y se mide dispersión.

## Contenido del archivo Excel
- `Propuesta final`: las 181 columnas de la tabla oficial. Solo las columnas **Origen propuesto - Zona** y **Destino propuesto - Zona** pueden cambiar; no se modifican las 8 codificaciones oficiales ni cadenas/tiempos.
- `Decisiones colonia`: razón, colonia identificada, método, confianza, zona representativa y dispersiones.
- `Alternativas zonas`: zonas del catálogo consideradas, más propuestas de versiones anteriores, claramente identificadas como no verificadas.
- `Pendientes de colonia`: 99 extremos sin una propuesta suficiente.
- `Resumen metodo`: totales y criterios.

Este Excel es un **libro de revisión** y no reemplaza al original con sus otras hojas y formatos. Se incluye el archivo fuente por separado. La comparación automática de las 181 columnas confirmó **0 campos protegidos modificados** y **351 valores cambiados en las dos zonas propuestas**, incluyendo la eliminación de sugerencias antiguas sin respaldo.

## Archivos y ejecución Windows
1. Abra el XLSX ya procesado para revisar las zonas.
2. `EJECUTAR_DECISIONES_WINDOWS.bat` regenera los CSV de decisiones y alternativas sin acceso a internet, usando solo Python estándar.
3. El archivo `generar_excel.py` crea el libro de revisión XLSX utilizando `artifact_tool`, que requiere un entorno compatible. Si no dispone de esa dependencia en Windows, los CSV siguen siendo utilizables y el XLSX incluido ya está listo.
4. No publique datos de las encuestas ni llaves de API.

## Limitación importante
La cobertura del 78.8% es **porcentaje de propuestas**, NO porcentaje de exactitud validada. Algunos nombres de colonia y municipio de versiones anteriores podrían ser incorrectos. Los 99 casos pendientes y los 93 de elevada dispersión son los primeros que conviene revisar con el equipo.
