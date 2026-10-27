# -*- coding: utf-8 -*-
"""Valida puntos documentados: coordenada -> poligono KML -> catalogo Excel.

No geocodifica texto, no inventa coordenadas y NO cambia columnas oficiales.
Ejecutar desde la carpeta del repositorio OD con Python 3.9+.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import math
import re
import unicodedata
from pathlib import Path
from urllib.parse import quote

from geometry import Zones
from xlsx_read import read_sheet

ROOT = Path(__file__).resolve().parent
HEADERS = [
    'ID', 'Extremo', 'Municipio_declarado', 'Colonia_declarada', 'CP_declarado',
    'Calle', 'Cruce', 'Referencia', 'Lugar_localizado', 'Latitud', 'Longitud',
    'Radio_incertidumbre_m', 'Fuente_coordenadas', 'Evidencia', 'Zona_actual_oficial',
    'Zona_propuesta_anterior', 'Zona_KML_del_punto', 'Zona_propuesta_verificada',
    'Estado', 'Distancia_al_limite_m', 'Zonas_cercanas', 'Zonas_catalogo_colonia',
    'Colonias_catalogo_zona', 'Municipios_catalogo_zona', 'CPs_catalogo_zona',
    'Coincide_colonia', 'Coincide_municipio', 'Coincide_CP', 'Observacion'
]
POINT_HEADERS = ['ID', 'Extremo', 'Lugar', 'Latitud', 'Longitud',
                 'Radio_m', 'Fuente', 'Evidencia']
TEMPLATE_HEADERS = ['ID', 'Extremo', 'Municipio_declarado', 'Colonia_declarada',
                    'CP_declarado', 'Calle', 'Cruce', 'Referencia', 'Buscar_en_Maps',
                    *POINT_HEADERS[2:]]


def value(raw):
    return '' if raw is None else str(raw).strip()


def normalized(raw):
    text = unicodedata.normalize('NFKD', value(raw).casefold())
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    return ' '.join(re.findall(r'[a-z0-9]+', text))


def zone_code(raw):
    text = value(raw)
    if re.fullmatch(r'\d+(?:\.0+)?', text):
        return str(int(float(text)))
    return ''


def postal(raw):
    text = value(raw)
    if re.fullmatch(r'\d+(?:\.0+)?', text):
        digits = str(int(float(text)))
        if digits != '0' and len(digits) <= 5:
            return digits.zfill(5)
    return ''


def number(raw):
    try:
        n = float(value(raw))
        return n if math.isfinite(n) else None
    except (ValueError, TypeError):
        return None


def read_points(path):
    path = Path(path)
    if not path.exists():
        return {}
    with path.open('r', encoding='utf-8-sig', newline='') as fh:
        reader = csv.DictReader(fh)
        missing = set(POINT_HEADERS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError('Al archivo de puntos le faltan columnas: ' + ', '.join(sorted(missing)))
        result = collections.defaultdict(list)
        for line, record in enumerate(reader, 2):
            key = (value(record['ID']), value(record['Extremo']).capitalize())
            if not key[0] or key[1] not in ('Origen', 'Destino'):
                raise ValueError(f'ID o Extremo invalido en {path.name}, fila {line}')
            # La plantilla contiene todos los extremos: filas sin punto se omiten.
            if not any(value(record.get(col)) for col in POINT_HEADERS[2:]):
                continue
            result[key].append(record)
        return dict(result)


def write_csv(path, records, columns):
    with Path(path).open('w', encoding='utf-8-sig', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(records)


def catalog_index(rows):
    """Catalogo del DIA8_233.xlsx: zona B, id colonia C, colonia D, CP E, municipio I."""
    by_zone = collections.defaultdict(list)
    by_col = collections.defaultdict(set)
    for row in rows[1:]:
        zone = zone_code(row.get(1))
        if not zone:
            continue
        item = {'zona': zone, 'id_colonia': value(row.get(2)),
                'colonia': value(row.get(3)), 'cp': postal(row.get(4)),
                'municipio': value(row.get(8))}
        by_zone[zone].append(item)
        if normalized(item['colonia']):
            by_col[(normalized(item['colonia']), normalized(item['municipio']))].add(zone)
    return by_zone, by_col


def joined(items):
    return '; '.join(sorted({x for x in items if x}))


def validacion(record, candidates, zones, catalog, by_col, margen=30):
    """Mantiene independiente la zona geometrica y la coherencia administrativa."""
    answer = dict(record)
    answer.update({key: '' for key in HEADERS if key not in answer})
    answer['Zona_propuesta_verificada'] = ''
    answer['Zona_KML_del_punto'] = ''
    answer['Estado'] = 'SIN_PUNTO'
    answer['Observacion'] = 'Falta localizar una referencia concreta con coordenadas documentadas.'
    answer['Zonas_catalogo_colonia'] = joined(by_col.get(
        (normalized(record['Colonia_declarada']), normalized(record['Municipio_declarado'])), set()))
    if not candidates:
        return answer
    if len(candidates) != 1:
        answer['Estado'] = 'PUNTOS_MULTIPLES_REVISAR'
        answer['Observacion'] = 'Hay varios puntos para el mismo ID y extremo: seleccionar uno con evidencia.'
        return answer

    p = candidates[0]
    for key, field in [('Lugar_localizado', 'Lugar'), ('Latitud', 'Latitud'),
                       ('Longitud', 'Longitud'), ('Radio_incertidumbre_m', 'Radio_m'),
                       ('Fuente_coordenadas', 'Fuente'), ('Evidencia', 'Evidencia')]:
        answer[key] = value(p.get(field))
    lat, lon, radius = number(p['Latitud']), number(p['Longitud']), number(p['Radio_m'])
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        answer['Estado'] = 'COORDENADAS_INVALIDAS'
        answer['Observacion'] = 'Las coordenadas deben ser numericas WGS84: latitud, longitud.'
        return answer
    if radius is None or radius < 0 or radius > 3000:
        answer['Estado'] = 'RADIO_INVALIDO'
        answer['Observacion'] = 'Indicar incertidumbre entre 0 y 3000 metros; no suponer exactitud.'
        return answer
    if not value(p['Lugar']) or not (value(p['Fuente']) and value(p['Evidencia'])):
        answer['Estado'] = 'EVIDENCIA_INCOMPLETA'
        answer['Observacion'] = 'Completar Lugar, Fuente y Evidencia antes de proponer una zona.'
        return answer

    geo = zones.query(lat, lon, margin=max(margen, radius))
    inside = geo['zonas_interiores']
    nearby = geo['zonas_cercanas_limite']
    answer['Zonas_cercanas'] = joined(set(inside) | set(nearby))
    answer['Distancia_al_limite_m'] = geo['distancia_limite_m'] if geo['distancia_limite_m'] is not None else ''
    if not inside:
        answer['Estado'] = 'FUERA_DE_ZONAS_KML'
        answer['Observacion'] = 'El punto no cae dentro de ningun poligono; verificar lugar/coordenadas.'
        return answer
    if len(inside) != 1:
        answer['Estado'] = 'SOLAPAMIENTO_KML'
        answer['Observacion'] = 'El punto pertenece a varias zonas; resolver la superposicion antes de codificar.'
        return answer

    zone = inside[0]
    answer['Zona_KML_del_punto'] = zone
    entries = catalog.get(zone, [])
    answer['Colonias_catalogo_zona'] = joined(x['colonia'] for x in entries)
    answer['Municipios_catalogo_zona'] = joined(x['municipio'] for x in entries)
    answer['CPs_catalogo_zona'] = joined(x['cp'] for x in entries)
    answer['Coincide_colonia'] = 'SI' if any(normalized(x['colonia']) == normalized(record['Colonia_declarada']) for x in entries) else 'NO'
    answer['Coincide_municipio'] = 'SI' if any(normalized(x['municipio']) == normalized(record['Municipio_declarado']) for x in entries) else 'NO'
    cp = postal(record['CP_declarado'])
    answer['Coincide_CP'] = ('SIN_DATO' if not cp else 'SI' if any(x['cp'] == cp for x in entries) else 'NO')
    if zone not in zones.ids or not entries:
        answer['Estado'] = 'ZONA_FALTA_EN_CATALOGO'
        answer['Observacion'] = 'La zona calculada no tiene una fila correspondiente en el catalogo Excel.'
        return answer
    distance = geo['distancia_limite_m']
    if nearby or distance is None or distance <= max(margen, radius):
        answer['Estado'] = 'CERCA_DE_LIMITE_KML'
        answer['Observacion'] = 'La incertidumbre de la referencia alcanza un limite; verificar punto mas preciso.'
        return answer

    answer['Zona_propuesta_verificada'] = zone
    contrad = [field for field in ('colonia', 'municipio', 'CP') if answer['Coincide_' + field] == 'NO']
    if contrad:
        answer['Estado'] = 'ZONA_GEOGRAFICA_OK_REVISAR_CONTEXTO'
        answer['Observacion'] = ('Punto dentro de zona KML, presente en catalogo; discrepa ' + ', '.join(contrad)
                                 + '. NO corregir declaraciones automaticamente.')
    else:
        answer['Estado'] = 'ZONA_GEOGRAFICA_Y_CATALOGO_OK'
        answer['Observacion'] = 'Punto en poligono unico lejos de limites, zona existente en el catalogo.'
    return answer


def generate(base, kml, points, output, margen=30):
    sheet = read_sheet(base, 'Propuesta final')
    if len(sheet) < 3 or value(sheet[1].get(0)) != 'ID':
        raise ValueError('No se reconoce Propuesta final, encabezado ID en segunda fila.')
    if any(len(row) > 181 for row in sheet[2:]):
        raise ValueError('La fuente tiene mas de 181 columnas; revisar version de la plantilla.')
    catalog, by_col = catalog_index(read_sheet(base, 'Catalogo'))
    polygons = Zones(kml)
    if not catalog:
        raise ValueError('El catalogo Excel no contiene claves de zonas validas.')
    pts = read_points(points)
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    decisions, template = [], []
    seen = set()
    for row in sheet[2:]:
        ident = value(row.get(0))
        if not ident:
            continue
        for ext, start, proposed in [('Origen', 11, 164), ('Destino', 25, 173)]:
            key = (ident, ext)
            if key in seen:
                raise ValueError(f'ID y extremo duplicados: {key}')
            seen.add(key)
            raw = {'ID': ident, 'Extremo': ext,
                   'Municipio_declarado': value(row.get(start)),
                   'Colonia_declarada': value(row.get(start+1)),
                   'CP_declarado': postal(row.get(start+2)),
                   'Calle': value(row.get(start+3)), 'Cruce': value(row.get(start+4)),
                   'Referencia': value(row.get(start+5)),
                   'Zona_actual_oficial': zone_code(row.get(start+6)),
                   'Zona_propuesta_anterior': zone_code(row.get(proposed))}
            decisions.append(validacion(raw, pts.get(key, []), polygons, catalog, by_col, margen))
            search = ', '.join(x for x in [raw['Referencia'],raw['Calle'],raw['Cruce'],
                                        raw['Colonia_declarada'],raw['Municipio_declarado'], 'Mexico'] if x)
            template.append({**raw, 'Buscar_en_Maps': 'https://www.google.com/maps/search/?api=1&query=' + quote(search),
                             **{h: '' for h in POINT_HEADERS[2:]}})
    extra = set(pts) - seen
    if extra:
        raise ValueError(f'Hay puntos con ID/Extremo inexistentes en base: {sorted(extra)[:6]}')
    write_csv(out/'AUDITORIA_KML_CATALOGO.csv', decisions, HEADERS)
    write_csv(out/'PENDIENTES_Y_REVISION.csv', [x for x in decisions if x['Estado'] != 'ZONA_GEOGRAFICA_Y_CATALOGO_OK'], HEADERS)
    write_csv(out/'PLANTILLA_PUNTOS_A_LOCALIZAR.csv', template, TEMPLATE_HEADERS)
    summary = {'registros':len(decisions)//2, 'extremos':len(decisions), 'puntos_recibidos':sum(len(v) for v in pts.values()),
               'zonas_kml':len(polygons.ids), 'zonas_catalogo':len(catalog),
               'zonas_propuestas_con_punto_documentado':sum(bool(x['Zona_propuesta_verificada']) for x in decisions),
               'estados':dict(collections.Counter(x['Estado'] for x in decisions)),
               'nota':'Zona por ubicacion de punto aportado; no valida automaticamente la identidad del lugar ni la direccion exacta.'}
    (out/'RESUMEN_AUDITORIA.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main():
    p = argparse.ArgumentParser(description='Verifica referencias documentadas contra poligonos KML y catalogo Excel')
    p.add_argument('--base', default=str(ROOT/'DIA8_233.xlsx'))
    p.add_argument('--kml', default=str(ROOT/'Zonas_Buenavista_v1.kml'))
    p.add_argument('--puntos', default=str(ROOT/'PUNTOS_CONFIRMADOS.csv'))
    p.add_argument('--salida', default=str(ROOT/'SALIDA_KML_CATALOGO'))
    p.add_argument('--margen', type=float, default=30, help='Metros minimos de seguridad al limite KML')
    args = p.parse_args()
    if not 0 <= args.margen <= 3000:
        p.error('--margen debe estar entre 0 y 3000 metros')
    generate(args.base, args.kml, args.puntos, args.salida, args.margen)


if __name__ == '__main__':
    main()
