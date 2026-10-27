# -*- coding: utf-8 -*-
"""Buenavista OD v09.30 - referencia legítima -> punto aproximado -> zona KML.

No lee coordenadas de enlaces de Google Maps: sus URLs solo codifican búsquedas.
Usa lugares con coordenadas procedentes de OpenStreetMap/Mapcarta y evidencia
geográfica aportada por el equipo, con sus condiciones de atribución.
No usa resultados aprobados para resolver ubicaciones ni utiliza el catálogo de
colonias para fabricar puntos. Solo modifica las zonas PROPUESTAS al exportar.
"""
from __future__ import annotations
import argparse, collections, csv, json, math, pathlib, re, xml.etree.ElementTree as ET
from dataclasses import dataclass
from difflib import SequenceMatcher
from urllib.parse import urlparse,parse_qs, unquote_plus, quote
from typing import Optional
from geometry import Zones
from xlsx_read import read_sheet

ROOT=pathlib.Path(__file__).resolve().parent
DEFAULT_SAMPLE=ROOT/'data'/'PRUEBA_20.xlsx'
DEFAULT_FULL=ROOT/'data'/'DIA8_233.xlsx'
DEFAULT_KML=ROOT/'cartografia'/'Zonas_Buenavista_v1.kml'
DEFAULT_POI=ROOT/'data'/'REFERENCIAS_ABIERTAS.csv'
DEFAULT_GPX=ROOT/'cartografia'/'gpx'
STOP={'de','del','la','las','los','el','al','por','av','avenida','calle','calzada','parque','jardin','plaza','en','y','con','s','n'}
VAGUE={'','0','00','no sabe','desconocido','no se','ninguna','centro','zona centro','bodega','bodegas','parque','zona'}

def txt(v):return str(v).strip() if v is not None else ''
def norm(v):
 import unicodedata
 s=unicodedata.normalize('NFKD',txt(v).casefold())
 s=''.join(c for c in s if not unicodedata.combining(c))
 return ' '.join(re.findall(r'[a-z0-9]+',s))
def token(v):return [x for x in norm(v).split() if x not in STOP]
def good(v):return norm(v) not in VAGUE and bool(token(v))
def ratio(a,b):
 a,b=norm(a),norm(b)
 return SequenceMatcher(None,a,b).ratio() if a and b else 0.
def num(v):
 try:
  k=float(v);return k if math.isfinite(k) else None
 except (ValueError,TypeError):return None

def read_csv(path):
 p=pathlib.Path(path)
 if not p.exists():return []
 with p.open('r',encoding='utf-8-sig',newline='') as fp:return list(csv.DictReader(fp))
def write_csv(path,rows,headers):
 p=pathlib.Path(path);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('w',encoding='utf-8-sig',newline='') as fp:
  w=csv.DictWriter(fp,fieldnames=headers,extrasaction='ignore');w.writeheader();w.writerows(rows)

def haversine(a,b):
 la1,lo1=map(math.radians,a);la2,lo2=map(math.radians,b)
 dlat=la2-la1;dlon=lo2-lo1
 return 12742000*math.asin(min(1,math.sqrt(math.sin(dlat/2)**2+math.cos(la1)*math.cos(la2)*math.sin(dlon/2)**2)))

class Routes:
 """Utiliza GPX existentes del derrotero para apoyar/desempatar, nunca para inventar un domicilio.
     Distancia al segmento (no únicamente a vértices).
 """
 def __init__(self,folder):
  self.paths={};self.cache={};self.folder=pathlib.Path(folder)
  for file in self.folder.glob('*.gpx'):
   m=re.search(r'ID_(\d+)',file.name,re.I)
   if not m:continue
   try:
    points=[]
    for _,el in ET.iterparse(str(file),events=('start',)):
     if el.tag.rsplit('}',1)[-1] in ('trkpt','rtept'):
      la,lo=num(el.get('lat')),num(el.get('lon'))
      if la is not None and lo is not None:points.append((la,lo))
    if len(points)>=2:
     # Reducir trazado a puntos cada ~8-14 m; mantener los extremos.
     simplified=[points[0]]
     for p in points[1:-1]:
      if haversine(simplified[-1],p)>10:simplified.append(p)
     simplified.append(points[-1])
     self.paths[int(m.group(1))]=(file.name,simplified)
   except (OSError,ET.ParseError,ValueError):continue
 def nearest(self,derrotero,point):
  try:keyid=int(str(derrotero).strip())
  except ValueError:return None,''
  if keyid not in self.paths:return None,''
  name,coords=self.paths[keyid]
  key=(keyid,round(point[0],6),round(point[1],6))
  if key in self.cache:return self.cache[key],name
  lat,lon=point;coslat=math.cos(math.radians(lat));factor=111195.
  def xy(v):return ((v[1]-lon)*factor*coslat,(v[0]-lat)*factor)
  best=float('inf')
  prev=xy(coords[0]);best=min(best,math.hypot(*prev))
  for coord in coords[1:]:
   cur=xy(coord);vx,vy=cur[0]-prev[0],cur[1]-prev[1]
   den=vx*vx+vy*vy
   t=max(0.,min(1.,-((prev[0]*vx+prev[1]*vy)/den))) if den else 0
   best=min(best,math.hypot(prev[0]+t*vx,prev[1]+t*vy));prev=cur
  self.cache[key]=round(best,1)
  return self.cache[key],name

@dataclass
class OD:
 id:str;extremo:str;derrotero:str;sentido:str;mun:str;col:str;calle:str;cruce:str;ref:str
 url_maps:str;texto_maps:str;zona_anterior:str;rowidx:int

FIELDS=['ID','Extremo','ID_Derrotero','Sentido','Municipio_declarado','Colonia_declarada','Calle','Interseccion','Referencia','Texto_enlace_Maps','URL_Maps','Lugar_elegido','Latitud','Longitud','ZONA_KML','ZONA_PROPUESTA','Estado','Tipo_referencia','Fuente','URL_evidencia','Precision_referencial_m','Distancia_limite_KML_m','Distancia_a_derrotero_m','Archivo_GPX','Puntuacion','Zonas_alternativas','Justificacion']
CANDFIELDS=['ID','Extremo','Lugar','Tipo','Campo_coincidente','Coincidencia','Latitud','Longitud','Zona_KML','Zonas_adyacentes','Radio_referencia_m','Distancia_KML_m','Distancia_GPX_m','Archivo_GPX','Puntuacion','Fuente','URL_fuente','Justificacion','Seleccionado']
LINKFIELDS=['ID','Extremo','URL_Maps','Texto_de_busqueda_Maps','Tiene_coordenadas_explicitas','Se_uso_como_consulta','Observacion']

class Engine:
 def __init__(self,entrada,kml,refs,gpx,salida,manual=None):
  self.entrada=pathlib.Path(entrada);self.zones=Zones(kml);self.refs=read_csv(refs);self.route=Routes(gpx)
  self.manual=read_csv(manual) if manual else []
  self.out=pathlib.Path(salida);self.out.mkdir(parents=True,exist_ok=True)
  self.records=read_sheet(self.entrada,'Propuesta final')
  if len(self.records)<3 or txt(self.records[1].get(0))!='ID' or len([self.records[1].get(i) for i in range(181) if self.records[1].get(i)])<165:
   raise ValueError('No se reconoció la plantilla oficial de 181 columnas en Propuesta final.')
  self.header1=self.records[0];self.header2=self.records[1]
  self.ods=[]
  for rn,r in enumerate(self.records[2:],3):
   ident=txt(r.get(0))
   if not ident:continue
   maplink=txt(r.get(158));parts={}
   if 'google.com/maps/dir/' in maplink:
    parts=parse_qs(urlparse(maplink).query)
   for ext,st,zc,key in [('Origen',11,164,'origin'),('Destino',25,173,'destination')]:
    desc=unquote_plus(parts.get(key,[''])[0])
    self.ods.append(OD(ident,ext,txt(r.get(5)),txt(r.get(9)),
     txt(r.get(st)),txt(r.get(st+1)),txt(r.get(st+3)),txt(r.get(st+4)),txt(r.get(st+5)),
     maplink,desc,txt(r.get(zc)),rn))
  ids=collections.Counter((o.id,o.extremo) for o in self.ods)
  if any(n!=1 for n in ids.values()):raise ValueError('ID OD duplicados.')
  self.points=[];self.decisions=[];self.links=[];self.reviews=[]

 def proposal(self,o,record,is_manual=False):
  lat,lon=num(record.get('Latitud')),num(record.get('Longitud'))
  if lat is None or lon is None or not(19.0<=lat<=20.0 and -100.0<=lon<=-98.0):return None
  label=txt(record.get('Lugar'))
  aliases=[a.strip() for a in txt(record.get('Alias_normalizados')).split('|') if good(a)]
  if label:aliases.append(label)
  fields=[('Referencia',o.ref,112),('Interseccion',o.cruce,102),('Calle',o.calle,90),('Colonia',o.col,68)]
  # Se aprovechan los segmentos de las búsquedas almacenadas en la ruta de
  # Google Maps. NO son coordenadas ni lugares ya verificados por Google.
  for segmento in [x.strip() for x in o.texto_maps.split(',')][:6]:
   if good(segmento):fields.append(('Texto_Maps',segmento,58))
  if is_manual:
   match_kind='PUNTO_APORTADO';found='Evidencia externa aportada';score=125
  else:
   candidate_matches=[]
   for col,original,base in fields:
    if not good(original):continue
    for alias in aliases:
     if not good(alias):continue
     similarity=ratio(original,alias)
     # Usar coincidencia explícita, no coincidencia parcial accidental.
     if norm(original)==norm(alias):quality=1.
     elif similarity>=.84 and min(len(norm(original)),len(norm(alias)))>=6:quality=similarity
     elif set(token(original))==set(token(alias)) and len(token(original))>=2:quality=.96
     else:continue
     candidate_matches.append((base*quality,col,original,alias))
   if not candidate_matches:return None
   score,match_kind,found,_=max(candidate_matches)
   if match_kind in ('Colonia','Texto_Maps') and txt(record.get('Tipo')) in ('POI','parque','estacion','mercado') and not (match_kind=='Texto_Maps' and score>=55 and any(norm(a)==norm(o.ref) or norm(a)==norm(o.cruce) for a in aliases)):
    # No asumir que un punto de un parque representa cualquier colonia homónima.
    return None
   tipo=txt(record.get('Tipo')).casefold()
   if match_kind=='Colonia' and tipo not in ('tramo_vial','toponimo'):
    return None
  typ=txt(record.get('Tipo'))
  route_dist,route_file=self.route.nearest(o.derrotero,(lat,lon))
  # GPX es apoyo: no veto; el origen puede requerir caminata u otro modo.
  if route_dist is not None:
   if route_dist<=400:score+=12
   elif route_dist<=1300:score+=7
   elif route_dist<=3000:score+=2
   elif route_dist>7000:score-=8
  # Municipio declarado = contexto, no restricción dura.
  context=norm(record.get('Contexto_alcaldia'))
  if context and norm(o.mun) and context in norm(o.mun):score+=5
  radius=num(record.get('Radio_m')) or 125
  # La zona del punto se obtiene SOLO del KML con coordenadas propias de fuente abierta.
  geo=self.zones.query(lat,lon,margin=0)
  zones=geo['zonas_interiores'];zone=zones[0] if len(zones)==1 else ''
  nearby=self.zones.query(lat,lon,margin=min(350,max(30,radius)))
  alternatives=sorted(set(nearby['zonas_cercanas_limite'])|set(zones),key=lambda t:int(t))
  if zone:
   d=geo['distancia_limite_m']
  else:d=None
  flag=('PUNTO_APORTADO' if is_manual else 'REFERENCIA_IDENTIFICADA' if match_kind in ('Referencia','Interseccion') else 'TOPONIMO_APROXIMADO')
  if zone and ((d or 0)<radius or len(alternatives)>1):flag+='_CERCA_LIMITES'
  return {'OD':o,'Lugar':label,'Tipo':typ,'Campo':match_kind,'Coincidencia':found,
   'Latitud':lat,'Longitud':lon,'Zona':zone,'Alternativas':alternatives,'Radio':radius,
   'Distancia_borde':d,'Distancia_ruta':route_dist,'Ruta':route_file,'Score':round(score,1),
   'Fuente':txt(record.get('Fuente')),'URL':txt(record.get('URL_fuente')),
   'Estado':flag,'Observacion':txt(record.get('Observaciones'))}

 def run(self):
  manual_by_key=collections.defaultdict(list)
  for m in self.manual:
   manual_by_key[(txt(m.get('ID')),txt(m.get('Extremo')).capitalize())].append(m)
  for o in self.ods:
   opts=[]
   for r in self.refs:
    p=self.proposal(o,r)
    if p:opts.append(p)
   for m in manual_by_key[(o.id,o.extremo)]:
    if not(txt(m.get('Nombre_lugar')) and txt(m.get('URL_fuente'))):continue
    point={'Latitud':m.get('Latitud'),'Longitud':m.get('Longitud'),'Lugar':m.get('Nombre_lugar'),
      'Tipo':txt(m.get('Tipo')) or 'PUNTO_ELEGIDO','Radio_m':m.get('Radio_m') or 75,
      'Fuente':'PUNTO_REVISADO_CON_EVIDENCIA','URL_fuente':m.get('URL_fuente')}
    p=self.proposal(o,point,True)
    if p:opts.append(p)
   opts.sort(key=lambda p:(-p['Score'],p['Radio'],p['Lugar'],p['Latitud']))
   valid=[p for p in opts if p['Zona']]
   chosen=valid[0] if valid else None
   # Distinguir dos sitios igualmente justificables. El que quede segundo sigue visible.
   if chosen and any(p['Zona']!=chosen['Zona'] and p['Score']>=chosen['Score']-5 for p in valid[1:]):
    state='REFERENCIAS_HOMONIMAS_CONFLICTO';chosen=None
   elif chosen:state=chosen['Estado']
   elif opts:state='PUNTOS_FUERA_POLIGONO'
   else:state='SIN_REFERENCIA_LOCALIZADA'
   alts=sorted(set(z for p in opts for z in p['Alternativas']),key=int)
   for p in opts:
    self.points.append({'ID':o.id,'Extremo':o.extremo,'Lugar':p['Lugar'],'Tipo':p['Tipo'],
     'Campo_coincidente':p['Campo'],'Coincidencia':p['Coincidencia'],
     'Latitud':p['Latitud'],'Longitud':p['Longitud'],'Zona_KML':p['Zona'],
     'Zonas_adyacentes':';'.join(p['Alternativas']),'Radio_referencia_m':p['Radio'],
     'Distancia_KML_m':p['Distancia_borde'] if p['Distancia_borde'] is not None else '',
     'Distancia_GPX_m':p['Distancia_ruta'] if p['Distancia_ruta'] is not None else '',
     'Archivo_GPX':p['Ruta'],'Puntuacion':p['Score'],'Fuente':p['Fuente'],
     'URL_fuente':p['URL'],'Justificacion':p['Observacion'],'Seleccionado':'SI' if p is chosen else 'NO'})
   source=chosen if chosen else None
   self.decisions.append({'ID':o.id,'Extremo':o.extremo,'ID_Derrotero':o.derrotero,'Sentido':o.sentido,
     'Municipio_declarado':o.mun,'Colonia_declarada':o.col,'Calle':o.calle,
     'Interseccion':o.cruce,'Referencia':o.ref,'Texto_enlace_Maps':o.texto_maps,'URL_Maps':o.url_maps,
     'Lugar_elegido':source['Lugar'] if source else '',
     'Latitud':source['Latitud'] if source else '', 'Longitud':source['Longitud'] if source else '',
     'ZONA_KML':source['Zona'] if source else '', 'ZONA_PROPUESTA':source['Zona'] if source else '',
     'Estado':state,'Tipo_referencia':source['Tipo'] if source else '',
     'Fuente':source['Fuente'] if source else '', 'URL_evidencia':source['URL'] if source else '',
     'Precision_referencial_m':source['Radio'] if source else '',
     'Distancia_limite_KML_m':source['Distancia_borde'] if source and source['Distancia_borde'] is not None else '',
     'Distancia_a_derrotero_m':source['Distancia_ruta'] if source and source['Distancia_ruta'] is not None else '',
     'Archivo_GPX':source['Ruta'] if source else '',
     'Puntuacion':source['Score'] if source else '',
     'Zonas_alternativas':';'.join(alts),
     'Justificacion':('Se utiliza un punto representativo, NO una dirección exacta. GPX solo apoya la elección. '
       'Los polígonos próximos al margen de incertidumbre se conservan como alternativas. '
       +source['Observacion']) if source else
       ('Varias referencias plausibles en distintas zonas: seleccionar en mapa.' if state=='REFERENCIAS_HOMONIMAS_CONFLICTO'
         else 'Sin lugar con coordenadas de fuente abierta reconocido entre las referencias disponibles.')})
   linktext=o.texto_maps
   self.links.append({'ID':o.id,'Extremo':o.extremo,'URL_Maps':o.url_maps,
     'Texto_de_busqueda_Maps':linktext,'Tiene_coordenadas_explicitas':'NO',
     'Se_uso_como_consulta':'SI' if linktext else 'NO',
     'Observacion':'El enlace ofrece texto de búsqueda, NO un punto devuelto por Google; las coordenadas proceden de otra fuente.'})
   if not chosen:
    self.reviews.append({'ID':o.id,'Extremo':o.extremo,'Latitud':'','Longitud':'',
      'Nombre_lugar':'','URL_fuente':'','Tipo':'referencia','Radio_m':150,
      'Sugerencia':o.ref or o.cruce or o.col,
      'Maps_para_revisar':o.url_maps or 'https://www.google.com/maps/search/?api=1&query='+quote(', '.join(x for x in [o.ref,o.cruce,o.col,o.mun] if good(x)))})
  self.export()

 def export(self):
  write_csv(self.out/'DECISIONES_REFERENCIA.csv',self.decisions,FIELDS)
  write_csv(self.out/'PUNTOS_ALTERNATIVOS.csv',self.points,CANDFIELDS)
  zoneopts=[]
  for p in self.points:
   for z in (p['Zonas_adyacentes'].split(';') if p.get('Zonas_adyacentes') else []):
    if z:
     zoneopts.append({'ID':p['ID'],'Extremo':p['Extremo'],'ZONA_CANDIDATA':z,
       'Coincide_con_punto': 'SI' if z==p['Zona_KML'] else 'LIMITE_APROXIMADO',
       'Lugar_origen':p['Lugar'],'Latitud':p['Latitud'],'Longitud':p['Longitud'],
       'Fuente_URL':p['URL_fuente'],'Seleccionado':'SI' if p['Seleccionado']=='SI' and z==p['Zona_KML'] else 'NO',
       'Justificacion':'Candidato por radio de incertidumbre' if z!=p['Zona_KML'] else 'Poligono que contiene el punto'})
  write_csv(self.out/'ALTERNATIVAS_ZONA.csv',zoneopts,
    ['ID','Extremo','ZONA_CANDIDATA','Coincide_con_punto','Lugar_origen','Latitud','Longitud','Fuente_URL','Seleccionado','Justificacion'])
  write_csv(self.out/'LINKS_MAPS_OD.csv',self.links,LINKFIELDS)
  rf=['ID','Extremo','Latitud','Longitud','Nombre_lugar','URL_fuente','Tipo','Radio_m','Sugerencia','Maps_para_revisar']
  write_csv(self.out/'PUNTOS_PARA_REVISION.csv',self.reviews,rf)
  states=dict(collections.Counter(d['Estado'] for d in self.decisions))
  report={'version':'v09.30_REFERENCIAS_MAPS_GPX','registros':len(self.ods)//2,'extremos':len(self.ods),
   'poligonos_kml':len(self.zones.ids),'gpx_derroteros_disponibles':len(self.route.paths),
   'puntos_catalogados':len(self.refs),'candidatos_coincidentes':len(self.points),
   'zonas_propuestas':sum(bool(d['ZONA_PROPUESTA']) for d in self.decisions),
   'zonas_confirmadas':0,'sin_zona':sum(not d['ZONA_PROPUESTA'] for d in self.decisions),
   'estados':states,'nota':'Propuestas referenciales; no corresponden necesariamente al domicilio exacto.',
   'atribucion':'© OpenStreetMap contributors (ODbL) / Mapcarta; verificar condiciones de atribución al redistribuir.'}
  (self.out/'CONTROL_REFERENCIAS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
  print(json.dumps(report,ensure_ascii=False,indent=2))
  return report

def main(argv=None):
 parser=argparse.ArgumentParser(description='Buenavista v09.30 - usar mapas textuales, referencia y GPX para proponer zona KML')
 parser.add_argument('--entrada',default=str(DEFAULT_SAMPLE));parser.add_argument('--salida',default=str(ROOT/'SALIDA_20'))
 parser.add_argument('--kml',default=str(DEFAULT_KML));parser.add_argument('--referencias',default=str(DEFAULT_POI));parser.add_argument('--gpx',default=str(DEFAULT_GPX));parser.add_argument('--puntos',default='')
 opt=parser.parse_args(argv)
 eng=Engine(opt.entrada,opt.kml,opt.referencias,opt.gpx,opt.salida,opt.puntos or None)
 eng.run();return eng
if __name__=='__main__':main()
