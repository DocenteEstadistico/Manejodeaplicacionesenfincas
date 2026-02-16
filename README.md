# Manejo de aplicaciones en fincas

Aplicación web en **Python + Flask** con plantillas HTML para llevar el control diario de aplicaciones químicas en caña de azúcar.

## ¿Qué hace?
- Crea automáticamente 10 fincas (`Finca 1` a `Finca 10`).
- Crea 7 lotes por finca (`Lote 1` a `Lote 7`), con 10 manzanas por lote (70 manzanas por finca).
- Permite registrar aplicaciones diarias por fecha, finca, lote y mezcla.
- Valida que no se ingresen más manzanas que el total del lote.
- Muestra cuántas manzanas faltan por aplicar en tiempo real al recargar por lote.
- Genera resumen por finca/lote/producto y total global por producto.
- Exporta reporte a Excel (`.xlsx`).

## Mezcla inicial de ejemplo
`Mezcla 1` con:
- Producto A: 1.5 litros/manzana
- Producto B: 2.0 litros/manzana
- Producto C: 0.5 litros/manzana

## Instalación
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Ejecutar
```bash
python app.py
```

Luego abrir: `http://127.0.0.1:5000`

## Ejecutar pruebas
```bash
pytest -q
```
