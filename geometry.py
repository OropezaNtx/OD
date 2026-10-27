"""Consulta KML/KMZ WGS84. Incluye huecos, multipartes y cercanía a límites."""
import hashlib,math,xml.etree.ElementTree as ET,zipfile
from pathlib import Path
NS={'k':'http://www.opengis.net/kml/2.2'}
def ring_contains(point,ring):
    x,y=point;inside=False
    for (a,b),(c,d) in zip(ring,ring[1:]):
        if (b>y)!=(d>y) and x<(c-a)*(y-b)/(d-b)+a:inside=not inside
    return inside
def boundary_distance(point,ring):
    x,y=point;scale=111195;cs=math.cos(math.radians(y));best=math.inf
    for (a,b),(c,d) in zip(ring,ring[1:]):
        ax=(a-x)*scale*cs;ay=(b-y)*scale;dx=(c-a)*scale*cs;dy=(d-b)*scale
        length=dx*dx+dy*dy;t=max(0,min(1,-(ax*dx+ay*dy)/length)) if length else 0
        best=min(best,math.hypot(ax+t*dx,ay+t*dy))
    return best
class Zones:
    def __init__(self,path,catalog_zones=None):
        self.path=Path(path);raw=self.path.read_bytes();self.sha256=hashlib.sha256(raw).hexdigest()
        if self.path.suffix.lower()=='.kmz':
            with zipfile.ZipFile(self.path) as z:
                names=[x for x in z.namelist() if x.lower().endswith('.kml')]
                selected=next((x for x in names if x.lower()=='doc.kml'),None)
                if selected is None and len(names)!=1:raise ValueError('KMZ con varios KML: seleccione la capa de zonas explícitamente.')
                raw=z.read(selected or names[0])
        root=ET.fromstring(raw);self.polygons=[];self.ids=set();count=0
        for pm in root.findall('.//k:Placemark',NS):
            polygons=pm.findall('.//k:Polygon',NS)
            if not polygons:continue
            zone=(pm.findtext('k:name',default='',namespaces=NS)).strip()
            if not zone.isdigit() or zone in self.ids:raise ValueError('Identificador de zona vacío, no numérico o duplicado.')
            self.ids.add(zone)
            for p in polygons:
                def parse(path):
                    value=p.findtext(path,default='',namespaces=NS);r=[]
                    for pair in value.split():
                        coords=pair.split(',');lon,lat=map(float,coords[:2])
                        if not (math.isfinite(lon) and math.isfinite(lat) and -180<=lon<=180 and -90<=lat<=90):raise ValueError('Coordenada KML inválida.')
                        r.append((lon,lat))
                    if len(r)<4 or r[0]!=r[-1]:raise ValueError('Anillo KML abierto o insuficiente.')
                    return r
                outer=parse('k:outerBoundaryIs/k:LinearRing/k:coordinates');holes=[]
                for h in p.findall('k:innerBoundaryIs/k:LinearRing/k:coordinates',NS):
                    r=[tuple(map(float,c.split(',')[:2])) for c in h.text.split()]
                    if len(r)<4 or r[0]!=r[-1] or any(not(-180<=x<=180 and -90<=y<=90) for x,y in r):raise ValueError('Hueco KML inválido.')
                    holes.append(r)
                bbox=(min(x for x,y in outer),min(y for x,y in outer),max(x for x,y in outer),max(y for x,y in outer))
                self.polygons.append((zone,outer,holes,bbox));count+=1
        if not self.ids:raise ValueError('El KML no contiene zonas poligonales.')
        if catalog_zones is not None and self.ids!=set(catalog_zones):raise ValueError('Las zonas del KML no coinciden con las del catálogo; no se asignan códigos.')
        self.count=count
    def query(self,lat,lon,margin=20):
        lat,lon=float(lat),float(lon)
        if not (math.isfinite(lat) and math.isfinite(lon) and -90<=lat<=90 and -180<=lon<=180 and margin>=0):raise ValueError('Punto o margen inválido.')
        point=(lon,lat);inside=set();near=set();distances={}
        for zone,outer,holes,(xmin,ymin,xmax,ymax) in self.polygons:
            pad_y=margin/111195;pad_x=margin/(111195*max(.01,math.cos(math.radians(lat))))
            if not(xmin-pad_x<=lon<=xmax+pad_x and ymin-pad_y<=lat<=ymax+pad_y):continue
            d=min(boundary_distance(point,r) for r in [outer,*holes]);distances[zone]=min(distances.get(zone,math.inf),d)
            if ring_contains(point,outer) and not any(ring_contains(point,h) for h in holes):inside.add(zone)
            if d<=margin:near.add(zone)
        state='cerca_limite' if near else 'solapamiento' if len(inside)>1 else 'interior_unico' if len(inside)==1 else 'fuera_cobertura'
        return {'estado':state,'zonas_interiores':sorted(inside,key=int),'zonas_cercanas_limite':sorted(near,key=int),
                'zona_unica':next(iter(inside)) if state=='interior_unico' else '',
                'distancia_limite_m':round(min(distances.values()),2) if distances else None}
