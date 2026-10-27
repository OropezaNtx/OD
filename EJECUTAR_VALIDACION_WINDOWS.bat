@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
echo =========================================================
echo BUENAVISTA OD - VERIFICACION KML + CATALOGO EXCEL
echo =========================================================
echo.
echo La base original NO se modifica.
echo Las zonas solo se proponen para puntos documentados
 echo y situados con seguridad dentro de un poligono KML.
echo.
python validar_zonas_od.py --base "DIA8_233.xlsx" --kml "Zonas_Buenavista_v1.kml" --puntos "PUNTOS_CONFIRMADOS.csv" --salida "SALIDA_KML_CATALOGO"
if errorlevel 1 (
  echo ERROR: Verifica nombres y contenido de los archivos.
  pause
  exit /b 1
)
echo.
echo Listo. Revisa la carpeta SALIDA_KML_CATALOGO.
echo Para llenar ubicaciones, usa PLANTILLA_PUNTOS_A_LOCALIZAR.csv.
pause
