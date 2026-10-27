# -*- coding: utf-8 -*-
"""Buenavista OD - colonia/POI referencial -> zona representativa.

No afirma coordenadas exactas ni asigna colonia/municipio administrativos oficiales.
Usa el KML para validar zonas catalogadas y sus centros APROXIMADOS, no para
certificar que la colonia tiene ese centro geográfico. Protege 179 campos.
Fuentes: Catalogo del propio Excel, POIs publicados y su validación por usuario.
"""
from __future__ import annotations
import csv, json, math, pathlib, re, sys
from difflib import SequenceMatcher
from collections import defaultdict, Counter
ROOT=pathlib.Path(__file__).resolve().parent
# Libraries supplied from v09.30
from xlsx_read import read_sheet
from geometry import Zones
from localizador_referencial import norm, good

FIELDS=['ID','Extremo','Colonia_declarada','Municipio_declarado','CP_declarado','Calle','Interseccion','Referencia','Colonia_previa','Municipio_previo','Zona_oficial_preexistente','Zona_propuesta_anterior','Colonia_seleccionada','Municipio_seleccionado','Zona_representativa','Tipo_decision','Confianza','Zonas_catalogo_compatibles','N_zonas','Dispersion_zonas_m','Punto_representativo_lat','Punto_representativo_lon','Fuente','Evidencia','Advertencia']
ALT=['ID','Extremo','Colonia','Municipio','Zona','Fuente_candidato','Es_zona_elegida','Notas']

def text(v):return '' if v is None else str(v).strip()
def valcp(v):
 s=''.join(c for c in text(v) if c.isdigit());return s.zfill(5) if s and 2<=len(s)<=5 and s!='0' else ''
def valzone(v):
 s=text(v)
 return str(int(s)) if s.isdigit() else ''
def writecsv(path,rows,fields):
 with open(path,'w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)

def poly_center(outer):
 """Area-weighted centroid (may lie outside a concave polygon; only used for ranking)."""
 xx=yy=area=0.
 for (x0,y0),(x1,y1) in zip(outer,outer[1:]):
  cross=x0*y1-x1*y0;area+=cross;xx+=(x0+x1)*cross;yy+=(y0+y1)*cross
 if abs(area)>1e-12:return yy/(3*area),xx/(3*area)
 return sum(y for x,y in outer)/len(outer),sum(x for x,y in outer)/len(outer)

class Resolver:
 def __init__(self,entrada,kml):
  self.entrada=pathlib.Path(entrada)
  self.zones=Zones(kml)
  self.ids=self.zones.ids
  self.catalog=read_sheet(entrada,'Catalogo')[1:]
  self.data=read_sheet(entrada,'Propuesta final')
  self.ind=defaultdict(list);self.byname=defaultdict(list);self.bymun=defaultdict(list)
  self.catalog_cps=defaultdict(set)
  for r in self.catalog:
   zone=valzone(r.get(1));name=norm(r.get(3));mun=norm(r.get(8));cp=valcp(r.get(4))
   if zone not in self.ids or not name or not mun:continue
   record={'name':text(r.get(3)),'mun':text(r.get(8)),'zone':zone,'cp':cp,'colid':text(r.get(2))}
   self.ind[(name,mun)].append(record);self.byname[name].append(record);self.bymun[mun].append(record)
  self.centers=defaultdict(list)
  for z,outer,holes,bounds in self.zones.polygons:
   c=poly_center(outer)
   # Prefer larger polygon when zone has multipart geometries.
   area=(bounds[2]-bounds[0])*(bounds[3]-bounds[1])
   self.centers[z].append((c,area))
  self.centers={z:max(items,key=lambda t:t[1])[0] for z,items in self.centers.items()}
  self.rows=[];self.alternatives=[]

 def choose_zone(self,records):
  zones=sorted({x['zone'] for x in records},key=int)
  if len(zones)==1:return zones[0],zones
  # Geometrically representative among associated catalog zones. Not a colonia centroid.
  xy={z:self.centers[z] for z in zones if z in self.centers}
  if not xy:return '',zones
  def metric(z):
   lat,lon=xy[z]
   return (sum(math.hypot((lon-l2)*math.cos(math.radians((lat+l1)/2)),lat-l1) for l1,l2 in xy.values()),int(z))
  return min(xy,key=metric),zones

 def exact(self,c,m):
  return self.ind.get((norm(c),norm(m)),[])

 def best_in_mun(self,c,m,cutoff=.82):
  cc,mm=norm(c),norm(m)
  if not cc or not mm or cc in ('no se','no sabe','ninguna','desconocido','centro','zona centro','0','000'):return []
  unique={norm(r['name']):r['name'] for r in self.bymun.get(mm,[])}
  scored=sorted(((SequenceMatcher(None,cc,k).ratio(),k) for k in unique if abs(len(cc)-len(k))<=max(5,len(cc)//3)),reverse=True)
  if not scored or scored[0][0]<cutoff:return []
  if len(scored)>1 and scored[0][0]-scored[1][0]<.045:return []
  return self.exact(scored[0][1],m)

 def resolve(self, row, s, ext):
  survey=text(row.get(0));mun=text(row.get(s));col=text(row.get(s+1));cp=valcp(row.get(s+2))
  calle=text(row.get(s+3));cruce=text(row.get(s+4));ref=text(row.get(s+5))
  prev_zone=valzone(row.get(s+6));prev_proposed=valzone(row.get(164 if ext=='Origen' else 173));prev_col=text(row.get(s+8));prev_mun=text(row.get(s+13));prev_cp=valcp(row.get(s+9))
  evidence='';typ='';conf='';warn='';accepted=[];name='';municipality='';chosen='';lat=lon=''
  combined=norm(' '.join([col,calle,cruce,ref]))
  # Only distinctive, localized POIs. 'Las Granjas' can mean an avenue in Azcapotzalco,
  # not the homonymous colonia in Otumba. Never accept generic 'bodega' as a POI.
  if ('suliban' in combined or 'sullivan' in combined or 'surlibano' in combined) and ext=='Origen':
   typ='REFERENCIA_PUNTUAL_VALIDADA';conf='Alta para lugar referencial';chosen='2025';name='San Rafael';municipality='Cuauhtémoc'
   evidence='Referencia Sullivan -> Jardin del Arte Sullivan; ZONA 2025 validada por usuario; punto POI abierto'
   lat,lon='19.43303','-99.16201'
   warn='Punto de parque, no ubicación exacta del encuestado. Alcaldía declarada puede estar equivocada.'
  elif 'tecnoparque' in combined.replace(' ','') or 'tecno parque' in combined:
   typ='REFERENCIA_PUNTUAL_CARTOGRAFICA';conf='Media-alta';chosen='19017';name='Colonia pendiente de confirmar';municipality='Azcapotzalco'
   evidence='Referencia específica Tecnoparque; POI abierto en Avenida de las Granjas';lat,lon='19.50407','-99.17846'
   warn='Punto representativo del POI; no domicilio exacto.'
  elif any(t in combined for t in ('arena cdmx','arena ciudad de mexico','arena cuidad de mexico')):
   typ='REFERENCIA_PUNTUAL_CARTOGRAFICA';conf='Media-alta';chosen='19006';name='Colonia pendiente de confirmar';municipality='Azcapotzalco'
   evidence='Lugar identificable Arena Ciudad de México; punto publicado en cartografía abierta';lat,lon='19.49765','-99.1752';warn='POI, no domicilio exacto.'
  elif any(t in combined for t in ('clinica 40','umf 40','imss 40')):
   typ='REFERENCIA_PUNTUAL_CARTOGRAFICA';conf='Media-alta';chosen='19007';name='Colonia pendiente de confirmar';municipality='Azcapotzalco'
   evidence='Referencia específica clínica UMF 40 IMSS';lat,lon='19.4949','-99.17895';warn='POI, no domicilio exacto.'
  elif 'mercado azcapotzalco' in combined:
   typ='REFERENCIA_PUNTUAL_CARTOGRAFICA';conf='Media-alta';chosen='20001';name='Colonia pendiente de confirmar';municipality='Azcapotzalco'
   evidence='Mercado Azcapotzalco como POI';lat,lon='19.48292','-99.1855';warn='POI, no domicilio exacto.'
  elif 'metro normal' in combined:
   typ='REFERENCIA_PUNTUAL_CARTOGRAFICA';conf='Media-alta';chosen='21021';name='Colonia pendiente de confirmar';municipality='Miguel Hidalgo'
   evidence='Estación Metro Normal como POI';lat,lon='19.44499','-99.16739';warn='Estación/centro aproximado; cerca de fronteras de zona.'
  elif ('las granjas' in combined or 'av de las granjas' in combined or 'avenida de las granjas' in combined) and (norm(mun)=='azcapotzalco' or norm(prev_mun)=='azcapotzalco'):
   # no general automatic cross-city matching
   typ='REFERENCIA_VIAL_APROXIMADA';conf='Media-baja';chosen='19017';name='Colonia pendiente de confirmar';municipality='Azcapotzalco'
   evidence='Referencia Avenida de las Granjas; punto abierto sobre un tramo conocido';lat,lon='19.50407','-99.17846'
   warn='La avenida abarca varias zonas. Zona propuesta de un tramo, no de la bodega exacta.'
  else:
   candidates=self.exact(col,mun)
   if candidates:
    typ='COLONIA_MUNICIPIO_DECLARADOS';conf='Media';accepted=candidates
    evidence='Coincidencia directa de colonia y municipio originales con catálogo territorial'
   if not candidates:
    candidates=self.best_in_mun(col,mun)
    if candidates:
     typ='COLONIA_NORMALIZADA_EN_MUNICIPIO';conf='Media';accepted=candidates
     evidence='Corrección ortográfica aproximada de colonia en municipio declarado; revisar homónimos'
   if not candidates and norm(col) in self.byname and norm(col) not in ('no se','centro','las granjas','zona centro'):
    variants=self.byname[norm(col)]
    munkeys={norm(x['mun']) for x in variants}
    support=norm(prev_mun)
    if len(munkeys)==1 or (support in munkeys and norm(prev_col)==norm(col)):
     mm=next(iter(munkeys)) if len(munkeys)==1 else support
     candidates=[r for r in variants if norm(r['mun'])==mm]
     typ='COLONIA_DECLARADA_OTRA_ALCALDIA';conf='Media-baja';accepted=candidates
     evidence='Colonia declarada localizada en otro municipio; corregir contexto administrativo'
     warn='La alcaldía original no coincide: usar como propuesta, no como certeza.'
   if not candidates and prev_col and prev_mun and norm(prev_col) not in ('no se','centro','zona centro'):
    # Legacy candidates may be wrong: make a proposal only if raw input is similar
    # or raw colony is absent/vague; otherwise require manual review.
    sim=SequenceMatcher(None,norm(col),norm(prev_col)).ratio() if norm(col) else 0
    vague=norm(col) in ('','0','000','no se','no sabe','desconocido','no recuerdo','nose')
    if sim>=.68 or vague:
     candidates=self.exact(prev_col,prev_mun)
     if candidates:
      typ='COLONIA_CODIFICACION_ANTERIOR';conf='Baja';accepted=candidates
      evidence='Colonia de codificación previa como alternativa; aún no verificada'
      warn='Codificación heredada; podría contener errores. Revisar si municipio anterior contradice las referencias.'
   if not candidates and col and mun:
    # relaxed matching in declared municipality if original has multiple words
    candidates=self.best_in_mun(col,mun,cutoff=.75)
    if candidates:
     typ='COLONIA_FUZZY_REVISAR';conf='Baja';accepted=candidates
     evidence='Similitud ortográfica, propuesta sujeta a revisión'
     warn='Confianza baja: validar que se refiere a la colonia indicada.'
   if candidates:
    chosen,zones=self.choose_zone(candidates)
    exemplar=next((x for x in candidates if x['zone']==chosen),candidates[0]);name=exemplar['name'];municipality=exemplar['mun']
    lat,lon=('', '')
    if len(zones)>1:
     warn=(warn+' ' if warn else '')+'Colonia asociada con '+str(len(zones))+' zonas KML. Zona seleccionada como medoid cartográfico, no centro confirmado de colonia.'
   else:
    typ='SIN_COLONIA_IDENTIFICADA';conf='Pendiente';chosen='';name='';municipality=''
    evidence='No hubo coincidencia administrativa ni referencia suficiente para elegir con seguridad.'
    warn='Revisar colonia original y referencias. No se inventa una zona municipal.'
  zones=sorted({r['zone'] for r in accepted},key=int) if accepted else ([chosen] if chosen else [])
  dispersion=0
  if chosen and len(zones)>1 and chosen in self.centers:
   la,lo=self.centers[chosen]
   dispersion=round(max(math.hypot((lo-self.centers[z][1])*math.cos(math.radians(la)),la-self.centers[z][0])*111195 for z in zones if z in self.centers),0)
   if dispersion>1600:
    warn=(warn+' ' if warn else '')+f'La colonia aparece en zonas cuyos centros se separan hasta {int(dispersion)} m; revisar que sea la colonia correcta.'
  if chosen not in self.ids:
   warn+=' La zona propuesta no existe en KML; se descarta.';chosen=''
  if chosen and chosen not in zones:zones=[chosen]+zones
  base={'ID':survey,'Extremo':ext,'Colonia_declarada':col,'Municipio_declarado':mun,'CP_declarado':cp,'Calle':calle,'Interseccion':cruce,'Referencia':ref,
   'Colonia_previa':prev_col,'Municipio_previo':prev_mun,'Zona_oficial_preexistente':prev_zone,'Zona_propuesta_anterior':prev_proposed,
   'Colonia_seleccionada':name,'Municipio_seleccionado':municipality,'Zona_representativa':chosen,
   'Tipo_decision':typ,'Confianza':conf,'Zonas_catalogo_compatibles':';'.join(zones),'N_zonas':len(zones),'Dispersion_zonas_m':dispersion,'Punto_representativo_lat':lat,'Punto_representativo_lon':lon,'Fuente':'Referencia abierta/KML' if 'REFERENCIA_' in typ else 'Catálogo territorial + KML' if chosen else 'Revisión pendiente',
   'Evidencia':evidence,'Advertencia':warn}
  for z in zones:self.alternatives.append({'ID':survey,'Extremo':ext,'Colonia':name,'Municipio':municipality,'Zona':z,'Fuente_candidato':typ,'Es_zona_elegida':'SI' if z==chosen else 'NO','Notas':'Zona de catálogo para colonia; NO ubicación puntual confirmada' if accepted else 'Referencia localizada'})
  if prev_proposed and prev_proposed in self.ids and prev_proposed not in zones:
   self.alternatives.append({'ID':survey,'Extremo':ext,'Colonia':prev_col,'Municipio':prev_mun,
     'Zona':prev_proposed,'Fuente_candidato':'PROPUESTA_ANTERIOR_NO_VALIDADA','Es_zona_elegida':'NO',
     'Notas':'Se conserva como alternativa histórica; puede corresponder a una colonia incorrecta.'})
  self.rows.append(base)
  return base

 def run(self):
  for r in self.data[2:]:
   if not text(r.get(0)):continue
   self.resolve(r,11,'Origen');self.resolve(r,25,'Destino')
  if len(self.rows)!=466:raise AssertionError('Esperados 466 extremos, procesados '+str(len(self.rows)))
  control={'registros':len(self.rows)//2,'extremos':len(self.rows),'con_zona_representativa':sum(bool(r['Zona_representativa']) for r in self.rows),
   'sin_zona':sum(not r['Zona_representativa'] for r in self.rows),'metodos':dict(Counter(r['Tipo_decision'] for r in self.rows)),
   'kml_ids':len(self.ids),'advertencia':'ZONA REPRESENTATIVA no equivale a coordenada exacta ni a verificación independiente de colonia. No se modifican datos oficiales.'}
  writecsv(ROOT/'DECISIONES_COLONIA.csv',self.rows,FIELDS)
  writecsv(ROOT/'ALTERNATIVAS_COLONIA.csv',self.alternatives,ALT)
  (ROOT/'CONTROL_v0940.json').write_text(json.dumps(control,ensure_ascii=False,indent=2),encoding='utf-8')
  print(json.dumps(control,indent=2,ensure_ascii=False))
  for r in self.rows:
   if r['ID'] in ('F5','F11'):print('CASO',r['ID'],r['Extremo'],r['Colonia_declarada'],'=>',r['Colonia_seleccionada'],r['Zona_representativa'],r['Tipo_decision'])
  return control

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--base',default=str(ROOT/'DIA8_233.xlsx'));p.add_argument('--kml',default=str(ROOT/'Zonas_Buenavista_v1.kml'));a=p.parse_args()
 Resolver(a.base,a.kml).run()
