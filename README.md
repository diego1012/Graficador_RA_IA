# Graficador Rockwell

Aplicación web local para cargar CSV eléctricos Rockwell, limpiarlos en memoria y
graficar su evolución temporal con variables y colores editables.

- Backend: **FastAPI** + **pandas** + **Plotly (Python)**.
- Frontend: **Jinja2** + JavaScript vanilla + **Plotly.js** y **noUiSlider**
  servidos localmente (sin CDN en ejecución).
- Formatos detectados automáticamente: **RA**, **CCW** y **BlackBox** (con
  respaldo genérico).
- Estado en memoria: UUID4, TTL de 30 minutos y máximo 5 datasets.
- Un solo worker de Uvicorn en esta versión.

## Requisitos

- Python **3.11** (`>=3.11,<3.12`).
- `pip` y un navegador moderno.

Las versiones exactas de Python y de las dependencias están registradas en
[`plan.md`](./plan.md) §3. No cambies versiones sin actualizar el plan y ejecutar
la matriz de pruebas.

## Instalación

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Para ejecutar solo la aplicación alcanza con `requirements.txt`:

```bash
pip install -r requirements.txt
```

## Ejecución

```bash
./run.sh
```

o, manualmente:

```bash
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Abrir <http://127.0.0.1:8000>. El puerto se puede cambiar con `PORT`, por
ejemplo `PORT=8765 ./run.sh`.

Para desarrollo con recarga automática:

```bash
.venv/bin/uvicorn app.main:app --reload --port 8000
```

## Uso

1. Arrastra o selecciona un CSV (`.csv`, máximo 50 MB).
2. La aplicación detecta el formato, limpia filas nulas y columnas de texto en
   memoria y muestra un resumen.
3. En la vista **Datos y opciones**, elige las variables con los checkboxes,
   edita sus colores y ajusta el rango con el slider de doble asa. Pulsa el
   nombre de una variable para abrir **Opciones de variable**: ahí puedes
   cambiar el nombre que aparece en la gráfica, agregar unidades (máximo 4
   caracteres, p. ej. `V`, `A`, `kW`) y el color, y activar **Escalar
   variable**: el rango real de la variable se convierte linealmente al
   mínimo y máximo que indiques (p. ej. `0 … 100`); al pasar el cursor por la
   gráfica se ve también el valor real. Confirma con **Aceptar** o descarta
   con **Cancelar**.
4. Pulsa **Generar gráfica**: la aplicación cambia a la vista **Gráfica**, donde
   la figura ocupa el alto disponible de la ventana. A la derecha, debajo de
   la leyenda, el recuadro **Mínimos y máximos** muestra con el color de cada
   variable su mínimo y su máximo en el rango graficado (escalados si la variable lo está); puedes
   arrastrarlo si tapa datos. Haz clic en un punto de la gráfica para
   **fijarlo**: queda una línea vertical con una etiqueta que muestra el
   tiempo y el valor de cada variable en ese instante. Clic en la etiqueta
   para quitarlo, o **Quitar puntos fijados** para quitarlos todos.
5. Explora con zoom, oculta series desde la leyenda y exporta a PNG con la barra
   de Plotly. Usa **Abrir en ventana** para ver la figura en una ventana
   independiente, **Volver a opciones** para cambiar la selección y
   **Actualizar gráfica** para refrescar la figura.

El botón **Modo oscuro** / **Modo claro** de la cabecera alterna el tema (por
defecto sigue la preferencia del sistema y se recuerda en el navegador); la
gráfica también cambia de tema.

La interfaz y los mensajes de error están en español. Los nombres de variables
se muestran tal como vienen en el CSV.

## Formatos soportados

| Formato | Detección | Eje temporal | Variables esperadas en los fixtures |
|---|---|---|---|
| RA | Encabezados `Date` y `Time` | Fecha y hora absoluta | 5 |
| CCW | Preámbulo de metadatos y encabezado con `Time` | Reloj de captura `mm:ss.s` (`16:42.3 → 22:29.1`) | 7 |
| BlackBox | Sin columna temporal y columnas hexadecimales | `fila × 0.001 s` | 49 (19 constantes) |

Los fixtures de `test_csv/` son de solo lectura y no se modifican al procesarlos.

> **Nota:** CCW no incluye fecha ni hora absoluta en el CSV; solo un reloj de
> captura `mm:ss.s`. Por eso la gráfica muestra ese reloj y no una fecha
> inventada. RA sí trae `Date` y `Time`, por lo que su eje es absoluto.

## API

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/` | Interfaz web. |
| `GET` | `/health` | Estado del servicio. |
| `POST` | `/api/datasets` | Subir, detectar y limpiar un CSV. |
| `GET` | `/api/datasets/{id}` | Metadatos del dataset. |
| `POST` | `/api/datasets/{id}/plot` | Generar la figura de Plotly. |
| `DELETE` | `/api/datasets/{id}` | Liberar el dataset. |

Los errores usan un cuerpo estructurado:

```json
{
  "detail": {
    "code": "INVALID_RANGE",
    "message": "El rango seleccionado está fuera de los límites del dataset.",
    "context": {}
  }
}
```

Los contratos completos y los códigos estables están en [`plan.md`](./plan.md)
§8. La documentación interactiva queda en `/docs` y `/redoc`.

## Pruebas y calidad

```bash
.venv/bin/ruff format .
.venv/bin/ruff check .
.venv/bin/pytest -q
```

La suite cubre detección de los tres formatos, reglas de limpieza, decimales con
coma, colores y rangos válidos/inválidos, datasets expirados y hashes de los
fixtures. Además se verificó el flujo completo en navegador con Playwright:
carga de los tres CSV, selección de variables, cambio de color, movimiento del
slider y generación de la gráfica.

Los CSV de referencia de `test_csv/` contienen datos reales de equipos y **no
se publican** en el repositorio (están en `.gitignore`). Sin ellos, los tests
que los necesitan se marcan como omitidos (`skipped`) y el resto se ejecuta
normalmente. Para la suite completa, copia `test_RA_CSV.CSV`, `CCW.csv` y
`blackbox.csv` en `test_csv/` (los hashes esperados están en `plan.md` §9).

## Estructura

```text
app/
├── main.py                 # App FastAPI, errores y cabeceras
├── config.py               # Límites, TTL y versiones
├── api/routes.py           # Endpoints HTTP
├── models/schemas.py       # Pydantic v2
├── services/
│   ├── ingest.py           # Decodificación, delimitador, encabezado
│   ├── cleaning.py         # Limpieza y métricas
│   ├── palette.py          # Colores deterministas
│   ├── plotting.py         # Figura Plotly
│   ├── store.py            # Almacén en memoria con TTL
│   └── formats/            # Adaptadores RA, CCW, BlackBox, genérico
├── templates/index.html
└── static/
    ├── css/app.css
    ├── js/app.js
    └── vendor/             # Plotly.js y noUiSlider con VERSIONS.md
tests/
test_csv/                   # Fixtures de solo lectura
```

## Límites

- Archivo máximo: 50 MB.
- Filas máximas: 500 000.
- Variables por gráfica: 50.
- TTL de dataset: 30 minutos.
- Máximo de datasets en memoria: 5.

## Documentación de referencia

- [`plan.md`](./plan.md): alcance, contratos, versiones, fixtures y criterios de
  aceptación. Es la fuente de verdad del proyecto.
- [`AGENTS.md`](./AGENTS.md): guía operativa para agentes y mantenedores.
- [`app/static/vendor/VERSIONS.md`](./app/static/vendor/VERSIONS.md): versiones y
  hashes de los assets vendorizados.
