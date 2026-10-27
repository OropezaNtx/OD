import csv,json,unittest
from pathlib import Path
from xlsx_read import read_sheet
from geometry import Zones
ROOT=Path(__file__).resolve().parent
class BuenavistaColoniaTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  with (ROOT/'DECISIONES_COLONIA.csv').open(encoding='utf-8-sig',newline='') as f:cls.d=list(csv.DictReader(f))
  cls.dm={(r['ID'],r['Extremo']):r for r in cls.d}
  cls.src=read_sheet(ROOT/'DIA8_233.xlsx','Propuesta final')
  cls.out=read_sheet(ROOT/'Buenavista_Dia8_233_Zonas_Representativas_v0940.xlsx','Propuesta final')
  cls.zones=Zones(ROOT/'Zonas_Buenavista_v1.kml')
 def test_233_encuestas_466_extremos(self):
  self.assertEqual(233,len(self.out)-2);self.assertEqual(466,len(self.d))
 def test_f5_validacion_y_no_trancas(self):
  self.assertEqual('2025',self.dm['F5','Origen']['Zona_representativa'])
  self.assertEqual('San Rafael',self.dm['F5','Origen']['Colonia_seleccionada'])
  self.assertEqual('19017',self.dm['F5','Destino']['Zona_representativa'])
  self.assertNotEqual('18005',self.dm['F5','Destino']['Zona_representativa'])
 def test_no_inventa_zonas_fuera_de_kml(self):
  self.assertTrue(all((not x['Zona_representativa'] or x['Zona_representativa'] in self.zones.ids) for x in self.d))
 def test_181_columnas_y_campos_protegidos(self):
  self.assertEqual(len(self.src),len(self.out))
  for orig,new in zip(self.src,self.out):
   for c in range(181):
    if c in (164,173):continue
    self.assertEqual('' if orig.get(c) is None else str(orig.get(c)),'' if new.get(c) is None else str(new.get(c)),msg=f'ID {orig.get(0)} col {c}')
 def test_conserva_ceros_iniciales(self):
  self.assertEqual('0030327',self.out[2].get(8))
 def test_99_pendientes_a_la_vista(self):
  self.assertEqual(99,sum(not d['Zona_representativa'] for d in self.d))
 def test_homonimos_se_registran(self):
  f5=self.dm['F5','Origen'];self.assertEqual('Cuauhtémoc',f5['Municipio_seleccionado'])
  self.assertEqual('Ascapozalco',f5['Municipio_declarado'])
if __name__=='__main__':unittest.main(verbosity=2)
