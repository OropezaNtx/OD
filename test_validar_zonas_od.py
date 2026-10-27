import tempfile
import unittest
from pathlib import Path

from geometry import Zones
from validar_zonas_od import catalog_index, validacion

KML='''<?xml version="1.0"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>
<Placemark><name>2025</name><Polygon><outerBoundaryIs><LinearRing><coordinates>-99.17,19.43 -99.16,19.43 -99.16,19.44 -99.17,19.44 -99.17,19.43</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>
<Placemark><name>19017</name><Polygon><outerBoundaryIs><LinearRing><coordinates>-99.16,19.43 -99.15,19.43 -99.15,19.44 -99.16,19.44 -99.16,19.43</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>
</Document></kml>'''

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        kml = Path(self.tmp.name) / 'zonas.kml'
        kml.write_text(KML)
        self.zones = Zones(kml)
        self.catalog, self.by_col = catalog_index([{},
            {1:2025, 3:'San Rafael',4:'06470',8:'Cuauhtémoc'},
            {1:19017,3:'Otra',4:'02300',8:'Azcapotzalco'}])
        self.od={'ID':'F5','Extremo':'Origen','Municipio_declarado':'Ascapozalco',
             'Colonia_declarada':'Sullivan','CP_declarado':'',
             'Zona_actual_oficial':'100','Zona_propuesta_anterior':'200'}
        self.point={'Lugar':'Jardin del Arte Sullivan','Latitud':'19.435',
             'Longitud':'-99.165', 'Radio_m':'30','Fuente':'Campo',
             'Evidencia':'Punto documentado'}

    def tearDown(self):
        self.tmp.cleanup()

    def test_sin_punto_no_propone(self):
        d=validacion(self.od, [], self.zones, self.catalog, self.by_col)
        self.assertEqual('SIN_PUNTO',d['Estado'])
        self.assertFalse(d['Zona_propuesta_verificada'])

    def test_punto_kml_y_discrepancia_administrativa(self):
        d=validacion(self.od, [self.point], self.zones, self.catalog, self.by_col)
        self.assertEqual('2025',d['Zona_KML_del_punto'])
        self.assertEqual('2025',d['Zona_propuesta_verificada'])
        self.assertEqual('ZONA_GEOGRAFICA_OK_REVISAR_CONTEXTO',d['Estado'])
        self.assertEqual('NO',d['Coincide_municipio'])
        self.assertEqual('100',d['Zona_actual_oficial'])

    def test_limite_entre_zonas_no_propone(self):
        p={**self.point,'Longitud':'-99.15999'}
        d=validacion(self.od,[p], self.zones,self.catalog,self.by_col)
        self.assertEqual('CERCA_DE_LIMITE_KML',d['Estado'])
        self.assertEqual('',d['Zona_propuesta_verificada'])

    def test_huerfano_catalogo_no_propone(self):
        catalog={'19017':self.catalog['19017']}
        d=validacion(self.od,[self.point],self.zones,catalog,self.by_col)
        self.assertEqual('ZONA_FALTA_EN_CATALOGO',d['Estado'])
        self.assertFalse(d['Zona_propuesta_verificada'])

    def test_coordenadas_invalidas(self):
        p={**self.point,'Latitud':'texto'}
        d=validacion(self.od,[p],self.zones,self.catalog,self.by_col)
        self.assertEqual('COORDENADAS_INVALIDAS',d['Estado'])

    def test_requiere_evidencia_y_radio(self):
        p={**self.point,'Fuente':''}
        self.assertEqual('EVIDENCIA_INCOMPLETA',validacion(self.od,[p],self.zones,self.catalog,self.by_col)['Estado'])
        p={**self.point,'Radio_m':''}
        self.assertEqual('RADIO_INVALIDO',validacion(self.od,[p],self.zones,self.catalog,self.by_col)['Estado'])

    def test_multiples_puntos_no_decide(self):
        self.assertEqual('PUNTOS_MULTIPLES_REVISAR',validacion(self.od,[self.point,self.point],self.zones,self.catalog,self.by_col)['Estado'])

    def test_contexto_coincidente(self):
        od={**self.od,'Municipio_declarado':'Cuauhtémoc','Colonia_declarada':'San Rafael','CP_declarado':'06470'}
        result=validacion(od,[self.point],self.zones,self.catalog,self.by_col)
        self.assertEqual('ZONA_GEOGRAFICA_Y_CATALOGO_OK',result['Estado'])
        self.assertEqual('SI',result['Coincide_CP'])

if __name__=='__main__':
    unittest.main(verbosity=2)
