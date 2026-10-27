# Auditoria geografica: referencia -> KML -> catalogo Excel

Este es un **paso de validacion adicional** al prototipo v09.40. No modifica `resolver_colonias.py`, los datos de las encuestas, las cadenas de viaje ni las zonas oficiales; la zona encontrada solo se escribe en una columna separada de la auditoria.

## Que resuelve

1. Recibe una coordenada de una **referencia localizada por separado** (no la deduce de la colonia, de una URL de busqueda de Maps ni de la zona anterior).
2. Calcula en que poligono del `Zonas_Buenavista_v1.kml` cae el punto (usando `geometry.py`, con soporte de huecos, multiples partes y superposiciones).
3. Si el radio de incertidumbre alcanza un limite de zona, **no** asigna una zona propuesta.
4. Comprueba que el codigo se encuentre entre las zonas del `Catalogo` de `DIA8_233.xlsx` y cruza colonia, municipio y CP declarados. Los posibles errores de captura **se reportan**, no se usan para desplazar un punto geografico bien respaldado a otra zona.
5. Genera archivos de revision para Excel.

**Importante:** la existencia de coordenadas documentadas no demuestra que representen el domicilio exacto. La calidad del punto de entrada sigue siendo una responsabilidad de revision en mapas/campo. **No se convierte un centroide de colonia en ubicacion exacta.**

## Ejecutar en Windows

Los archivos nuevos van en la misma carpeta que `DIA8_233.xlsx`, `Zonas_Buenavista_v1.kml`, `geometry.py` y `xlsx_read.py`. Ejecutar `EJECUTAR_VALIDACION_WINDOWS.bat` o:

```bat
python validar_zonas_od.py --base "DIA8_233.xlsx" --kml "Zonas_Buenavista_v1.kml" --puntos "PUNTOS_CONFIRMADOS.csv" --salida "SALIDA_KML_CATALOGO"
```

Solo necesita Python estándar. Si `PUNTOS_CONFIRMADOS.csv` todavía no existe, la ejecucion genera la plantilla, pero **no propone zonas sin puntos**.

1. Abrir `SALIDA_KML_CATALOGO/PLANTILLA_PUNTOS_A_LOCALIZAR.csv` en Excel.
2. Elegir las filas para las que hay evidencia geográfica y completar las siguientes columnas, sin cambiar ID/Extremo:
   - `Lugar`: el POI, cruce, estacion o tramo vial concreto identificado.
   - `Latitud` y `Longitud`: coordenadas WGS84 en grados decimales, por ejemplo `19.43303` y `-99.16201`. No invertir el orden.
   - `Radio_m`: incertidumbre en metros, por ejemplo 30 para un punto concreto o mayor para una referencia extensa; no inventar precision.
   - `Fuente`: cartografía abierta, levantamiento de campo u otra fuente trazable.
   - `Evidencia`: identificador, enlace o justificación de cómo se comprobó la ubicación.
3. Guardar una copia como CSV UTF-8, llamada `PUNTOS_CONFIRMADOS.csv`, en la carpeta principal del proyecto y volver a ejecutar el BAT. Las filas con esos campos vacíos se omiten.

## Archivos de salida

- `AUDITORIA_KML_CATALOGO.csv`: un registro por origen y por destino; incluye zona KML, propuesta validada, alternativas, diferencias con el catálogo y motivos.
- `PENDIENTES_Y_REVISION.csv`: solo extremos todavía pendientes de revisión (incluye conflictos administrativos aunque exista una propuesta geográfica).
- `PLANTILLA_PUNTOS_A_LOCALIZAR.csv`: 2 filas por encuesta y enlace de búsqueda Maps para revisar la ubicación en vez de asumir que un enlace es una coordenada.
- `RESUMEN_AUDITORIA.json`: conteos por estado, puntos recibidos y cobertura; **no** representa exactitud demostrada.

`Zona_propuesta_verificada` solo aparece cuando: el lugar tiene fuente, evidencia, coordenadas validas y radio; un unico poligono KML contiene el punto; el punto queda fuera del margen al limite; y la zona existe en el catalogo. Contradicciones en colonia/municipio/CP se reportan con el estado `ZONA_GEOGRAFICA_OK_REVISAR_CONTEXTO` sin descartar automaticamente un punto bien localizado.

Para el caso de referencia **F5 origen / Jardín del Arte Sullivan**, el equipo validó históricamente la **zona 2025**. Al completar la coordenada y fuente, comprobar que el KML confirme 2025: si no coincide, investigar el punto; **no forzar 2025 por el nombre Sullivan**. El destino de F5 sobre Av. de las Granjas requiere identificar el tramo, no repetir el codigo provisional `19017` indiscriminadamente.

## Pruebas

```bat
python -m unittest -v test_validar_zonas_od.py
```

Las pruebas incluyen la integridad de propuestas sin punto, disonancia administrativa, zona ausente de catálogo, incertidumbre junto a límites y puntos múltiples. Los tests usan KML sintético, por lo que **no sustituyen validación de campo o una corrida con el KML real**.
