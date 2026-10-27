@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
echo ================================================
echo BUENAVISTA OD - ZONAS REPRESENTATIVAS POR COLONIA
echo ================================================
echo No usa Internet ni modifica el archivo DIA8_233.xlsx.
echo.
python resolver_colonias.py --base "DIA8_233.xlsx" --kml "Zonas_Buenavista_v1.kml"
if errorlevel 1 (echo ERROR al analizar. & pause & exit /b 1)
echo.
echo Generados DECISIONES_COLONIA.csv y ALTERNATIVAS_COLONIA.csv.
echo El libro XLSX de revision ya incluido fue procesado y validado por separado.
echo.
pause
