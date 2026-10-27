"""XLSX data reader using Python standard-library XML/ZIP, no third-party dependencies."""
import zipfile,xml.etree.ElementTree as ET,re,datetime
NS='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
R='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
PK='{http://schemas.openxmlformats.org/package/2006/relationships}'
def _col(ref):
 t=re.match('[A-Z]+',ref or '');n=0
 for c in (t.group(0) if t else ''):n=n*26+ord(c)-64
 return n-1
def read_sheet(path,name,limit=None):
 with zipfile.ZipFile(path) as z:
  ws=ET.fromstring(z.read('xl/workbook.xml'))
  mapping={x.attrib['Id']:x.attrib['Target'] for x in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
  sheets={s.attrib['name']:s.attrib[R+'id'] for s in ws.find(NS+'sheets')}
  if name not in sheets:raise ValueError(f'Falta hoja {name}. Disponibles: {list(sheets)}')
  target=mapping[sheets[name]].lstrip('/')
  if not target.startswith('xl/'):target='xl/'+target
  shared=[]
  if 'xl/sharedStrings.xml' in z.namelist():
   with z.open('xl/sharedStrings.xml') as sf:
    for evt,el in ET.iterparse(sf,events=('end',)):
     if el.tag==NS+'si':shared.append(''.join(t.text or '' for t in el.iter(NS+'t')));el.clear()
  result=[]
  with z.open(target) as sf:
   for evt,el in ET.iterparse(sf,events=('end',)):
    if el.tag!=NS+'row':continue
    vals={}
    for c in el.findall(NS+'c'):
     ci=_col(c.get('r',''))
     if ci<0:continue
     t=c.get('t','');v=c.find(NS+'v');it=c.find(NS+'is')
     if t=='inlineStr' and it is not None:value=''.join(x.text or '' for x in it.iter(NS+'t'))
     elif v is None:value=None
     elif t=='s':value=shared[int(v.text)]
     elif t=='b':value=bool(int(v.text))
     elif t in ('str','d'):value=v.text
     elif t=='e':value=v.text
     else:
      value=v.text
      if value is not None:
       try:value=float(value) if '.' in value or 'E' in value.upper() else int(value)
       except (ValueError,TypeError):pass
     if value is not None:vals[ci]=value
    result.append(vals)
    el.clear()
    if limit and len(result)>=limit:break
  return result
if __name__=='__main__':
 from pathlib import Path
 p=Path('/mnt/data/Base_OD_Dia8_Entrega.xlsx')
 for sheet in ['Datos','Catalogo']:
  rows=read_sheet(p,sheet,limit=5)
  print(sheet,len(rows))
  for r in rows:print({k:str(v)[:50] for k,v in list(r.items())[:18]})
