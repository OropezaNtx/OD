# -*- coding:utf-8 -*-
"""Create reviewer spreadsheet with artifact_tool; no editing base source."""
from pathlib import Path
import csv,json,time
from artifact_tool import Workbook, SpreadsheetFile
from xlsx_read import read_sheet
p=Path(__file__).resolve().parent
start=time.monotonic()

def log(s):print(s,round(time.monotonic()-start,1),flush=True)
def csvdata(name):
 with (p/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

source=read_sheet(p/'DIA8_233.xlsx','Propuesta final')
ids=[str(r.get(0)) for r in source[2:] if r.get(0)]
decisions=csvdata('DECISIONES_COLONIA.csv'); alternatives=csvdata('ALTERNATIVAS_COLONIA.csv')
mapd={(r['ID'],r['Extremo']):r for r in decisions}
assert len(ids)==233 and len(mapd)==466 and len(source)==235
# Only edit two proposed ZONA fields (indices 164 and 173)
matrix=[];original=[]
for rn,row in enumerate(source):
 values=[row.get(i) for i in range(181)]
 if rn>=2:
  i=str(row.get(0))
  if i:
   values[164]=mapd[(i,'Origen')]['Zona_representativa'] or None
   values[173]=mapd[(i,'Destino')]['Zona_representativa'] or None
 matrix.append(values)
 original.append([row.get(i) for i in range(181)])
log('Loaded base 181 and decisions')
wb=Workbook.create()
sh=wb.worksheets.add('Propuesta final')
# Chunk writes to bound latency/memory while keeping full official 181 fields
for startrow in range(0,len(matrix),60):
 chunk=matrix[startrow:startrow+60]
 sh.get_range_by_indexes(startrow,0,len(chunk),181).values=chunk
log('Wrote Propuesta final')
try:
 sh.get_range_by_indexes(0,0,2,181).format={"fill":"#1E3A5F","font":{"bold":True,"color":"#FFFFFF"},"row_height":27,"wrap_text":True}
 sh.get_range_by_indexes(2,164,233,1).format.fill='#ECFDF5'
 sh.get_range_by_indexes(2,173,233,1).format.fill='#ECFDF5'
 sh.get_range_by_indexes(0,0,235,1).format.column_width=12
 sh.get_range_by_indexes(0,11,235,1).format.column_width=18
 sh.get_range_by_indexes(0,25,235,1).format.column_width=18
except Exception as ex:log('Styling warning: '+str(ex)[:200])

def tab(name,records,columns=None,batch=150):
 sheet=wb.worksheets.add(name)
 keys=columns or list(records[0].keys())
 sheet.get_range_by_indexes(0,0,1,len(keys)).values=[keys]
 for off in range(0,len(records),batch):
  piece=records[off:off+batch]
  rows=[[r.get(c,'') for c in keys] for r in piece]
  sheet.get_range_by_indexes(off+1,0,len(rows),len(keys)).values=rows
 try:
  sheet.get_range_by_indexes(0,0,1,len(keys)).format={"fill":"#14532D","font":{"bold":True,"color":"#FFFFFF"},"row_height":27}
  sheet.get_range_by_indexes(0,0,len(records)+1,1).format.column_width=13
  for key in ('Evidencia','Advertencia','Notas'):
   if key in keys:sheet.get_range_by_indexes(0,keys.index(key),len(records)+1,1).format.column_width=54
 except Exception:pass
 log(f'Wrote {name} {len(records)}')
 return sheet

tab('Decisiones colonia',decisions)
tab('Alternativas zonas',alternatives)
pend=[d for d in decisions if not d['Zona_representativa']]
tab('Pendientes de colonia',pend)
ctl=json.loads((p/'CONTROL_v0940.json').read_text(encoding='utf8'))
summary=[{'Indicador':'Encuestas','Valor':233},
 {'Indicador':'Extremos','Valor':466},
 {'Indicador':'Zonas representativas propuestas','Valor':ctl['con_zona_representativa']},
 {'Indicador':'Pendientes de colonia','Valor':ctl['sin_zona']},
 {'Indicador':'F5 origen - Parque Sullivan','Valor':'2025 (referencia confirmada por usuario)'},
 {'Indicador':'F5 destino - Av. de las Granjas','Valor':'19017 (aproximación de un tramo, no bodega exacta)'},
 {'Indicador':'Norma de modificación','Valor':'Solo Origen propuesto - Zona y Destino propuesto - Zona'},
 {'Indicador':'Zona por colonia','Valor':'Medoide geográfico de las zonas KML asociadas a la colonia en catálogo; NO un punto geocodificado'},
 {'Indicador':'Campos oficiales','Valor':'Sin cambio; también se conservan los datos y los tiempos originales'},
 {'Indicador':'Evaluación','Valor':'Cobertura de propuestas, NO porcentaje de acierto verificado'}]
for k,v in ctl['metodos'].items():summary.append({'Indicador':k,'Valor':v})
tab('Resumen metodo',summary)
output=p/'Buenavista_Dia8_233_Zonas_Representativas_v0940.xlsx'
log('Export starts')
SpreadsheetFile.export_xlsx(wb).save(str(output))
log('Export complete '+str(output))
# Verify exported content and every protected cell independently with XML read.
res=read_sheet(output,'Propuesta final')
assert len(res)==len(source) and len(res)==235
changes=0
for r1,r2 in zip(source,res):
 for ix in range(181):
  a=r1.get(ix);b=r2.get(ix)
  if ix in (164,173):
   if ('' if a is None else str(a))!=('' if b is None else str(b)):changes+=1
  else:
   if ('' if a is None else str(a))!=('' if b is None else str(b)):
    raise AssertionError(f'Protected data changed at ID={r1.get(0)} col={ix}, {a!r} -> {b!r}')
assert len([r for r in res[2:] if r.get(0)])==233
r5=next(r for r in res if r.get(0)=='F5')
assert str(r5.get(164))=='2025' and str(r5.get(173))=='19017',r5
log('Verified all original 179 protected columns unchanged; zone changes: '+str(changes))
(p/'COMPROBACION_v0940.json').write_text(json.dumps({'registros':233,'extremos':466,'columnas':181,'campos_protegidos_modificados':0,'zonas_propuestas':ctl['con_zona_representativa'],'zonas_pendientes':ctl['sin_zona'],'celdas_zona_modificadas':changes,'F5_origen':str(r5.get(164)),'F5_destino':str(r5.get(173))},indent=2,ensure_ascii=False),encoding='utf8')
