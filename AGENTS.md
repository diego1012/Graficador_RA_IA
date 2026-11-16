# AGENTS.md — Graficador Rockwell

Guía operativa para agentes que implementen o mantengan este proyecto.

- **Plan de referencia:** [`plan.md`](./plan.md) — versión `1.0.0` (2026-11-11).
- **Estado al crear esta guía:** preimplementación. Solo existen `plan.md` y
  `test_csv/`. El código debe construirse siguiendo las fases F1–F7 del plan.
- **Regla de oro:** si el código y `plan.md` divergen, actualizar el plan y esta
  guía en el mismo cambio. El plan es la fuente de verdad del alcance, los
  contratos y las versiones.

---

## 1. Qué se está construyendo

Aplicación web con backend Python/FastAPI que:

1. Recibe un archivo CSV de datos eléctricos Rockwell.
2. Detecta automáticamente uno de tres formatos: RA, CCW o BlackBox.
3. Limpia los datos **en un DataFrame en memoria**:
   - elimina filas con datos nulos,
   - elimina columnas tipo string,
   - conserva las variables numéricas.
4. Muestra al usuario el nombre y el color de cada variable **antes de graficar**.
5. Permite editar colores, seleccionar variables y elegir un subrango de todo el
   CSV con un range slider de doble asa.
6. Genera una gráfica interactiva de tiempo vs variables eléctricas con
   Plotly.js.

Los archivos de `test_csv/` son fixtures de referencia y **nunca se modifican**.

---

## 2. Stack y versiones

No cambiar estas versiones sin actualizar `plan.md` (§3 y §15) y ejecutar la
matriz de pruebas. La línea base usa Python 3.11 porque `numpy 2.5.x` exige
Python >= 3.12.

| Componente | Versión |
|---|---|
| Python | 3.11.2 validado; soportado `>=3.11,<3.12` |
| FastAPI | 0.162.4 |
| Uvicorn | 0.54.0 |
| pandas | 3.1.1 |
| NumPy | 2.4.6 |
| Plotly (Python) | 7.1.0 |
| Jinja2 | 3.1.6 |
| python-multipart | 0.0.33 |
| orjson | 3.13.0 |
| pytest | 9.2.0 |
| httpx | 0.28.1 |
| ruff | 0.17.4 |
| Plotly.js | bundle exacto incluido en `plotly==7.1.0` |
| noUiSlider | 15.8.1 |

Assets frontend:

- Servir Plotly.js y noUiSlider desde `app/static/vendor/`.
- Copiar `plotly.min.js` desde `plotly/package_data/plotly.min.js` del paquete
  Python instalado, para garantizar compatibilidad exacta.
- Registrar versión y hash de cada asset en
  `app/static/vendor/VERSIONS.md`.
- **No usar CDNs en producción.**

---

## 3. Estructura objetivo

```text
Graficador Rockwell/
├── app/
│   ├── main.py                 # Creación de FastAPI, montaje de estáticos
│   ├── config.py               # Límites, TTL, versiones, logging
│   ├── api/routes.py           # Endpoints HTTP
│   ├── models/schemas.py       # Pydantic v2: metadata, plot request/response
│   ├── services/
│   │   ├── ingest.py           # Codificación, delimitador, encabezado
│   │   ├── cleaning.py         # Limpieza y métricas
│   │   ├── palette.py          # Asignación determinista de colores
│   │   ├── plotting.py         # Figura Plotly
│   │   ├── store.py            # Almacén en memoria con TTL
│   │   └── formats/
│   │       ├── base.py
│   │       ├── ra.py
│   │       ├── ccw.py
│   │       ├── blackbox.py
│   │       ├── generic.py
│   │       └── registry.py
│   ├── templates/index.html
│   └── static/
│       ├── css/app.css
│       ├── js/app.js
│       └── vendor/
├── tests/
│   ├── test_formats.py
│   ├── test_cleaning.py
│   ├── test_plotting.py
│   └── test_api.py
├── test_csv/                   # Solo lectura
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── .python-version
├── run.sh
├── plan.md
└── AGENTS.md
```

### Responsabilidades

- `ingest.py`: no conoce detalles de negocio; devuelve bytes decodificados,
  delimitador y filas.
- `formats/*`: cada adaptador transforma su formato a un `ParsedDataset` con
  índice temporal y columnas numéricas candidatas.
- `cleaning.py`: aplica las reglas de limpieza y calcula métricas.
- `palette.py`: colores deterministas y validación `#RRGGBB`.
- `plotting.py`: valida variables/rango y construye la figura del subrango.
- `store.py`: UUID4, TTL 30 min, máximo 5 datasets, lock de acceso.
- `routes.py`: valida HTTP, delega en servicios, devuelve errores estructurados.

---

## 4. Comandos de trabajo

Cuando el proyecto esté implementado:

```bash
# Entorno
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# Ejecutar en desarrollo
uvicorn app.main:app --reload --port 8000
# o
./run.sh

# Calidad
ruff format .
ruff check .

# Pruebas
pytest -q
```

Abrir `http://127.0.0.1:8000`.

Si se agrega una dependencia:

1. Justificar por qué el plan la permite.
2. Fijar versión exacta en `requirements.txt` o `requirements-dev.txt`.
3. Actualizar `plan.md` §3 y el registro de cambios.
4. Ejecutar `ruff` y `pytest`.

---

## 5. Invariantes que no se negocian

| ID | Regla |
|---|---|
| INV-01 | `test_csv/` y cualquier CSV subido se abren en modo lectura; nunca se escriben. |
| INV-02 | La limpieza se aplica solo al DataFrame en memoria. |
| INV-03 | La columna temporal es el índice y no aparece como variable graficable. |
| INV-04 | Los colores cumplen `^#[0-9A-Fa-f]{6}$`. |
| INV-05 | El rango es inclusivo: `0 <= start_index <= end_index < rows_clean`. |
| INV-06 | BlackBox usa exactamente `0.001 s` por muestra. |
| INV-07 | Todas las series comparten el mismo eje Y (también las escaladas). |
| INV-08 | Se listan todas las variables numéricas, incluidas las constantes. |
| INV-09 | Número de trazas == número de variables válidas solicitadas. |
| INV-10 | Los nombres de variables se muestran tal como vienen en el CSV; el usuario puede asignar nombre de visualización y unidades, pero el original sigue visible y el dataset no cambia. |

Además:

- La interfaz y los mensajes de error van en **español**.
- Identificadores, docstrings y nombres de archivos Python van en **inglés**.
- JSON de API en `snake_case`.
- Sin CORS: mismo origen.
- Sin base de datos, sin autenticación y sin múltiples workers en v1.

---

## 6. Reglas de limpieza

Orden obligatorio:

1. Leer bytes y decodificar con `utf-8-sig`, `utf-16`, `cp1252`, `latin-1`.
2. Detectar delimitador con heurística de columnas estables. **No confiar solo en
   `csv.Sniffer`**: el `;` de los milisegundos de RA puede confundirse con
   separador.
3. Detectar el encabezado en las primeras 25 filas.
4. Construir el índice temporal.
5. Eliminar filas y columnas totalmente vacías.
6. Normalizar nulos: `""`, `NA`, `N/A`, `NaN`, `-`.
7. Convertir a numérico con `pd.to_numeric(errors="coerce")`.
8. Conservar una columna como numérica si al menos el **90 %** de sus valores no
   nulos son parseables; si no, clasificarla como string y descartarla.
9. Descartar columnas string que no sean el índice temporal.
10. Eliminar la fila completa si falta **cualquier** variable numérica.
11. Ordenar por tiempo.
12. Calcular métricas.

Consecuencias esperadas:

- `Date` y `Time` se usan para el índice y luego se excluyen.
- Las 14 columnas hex de BlackBox se descartan por ser string.
- Las columnas numéricas constantes se conservan y se marcan `is_constant`.
- No se eliminan duplicados temporales.
- No se escribe ningún CSV limpio.

---

## 7. Formatos de entrada

| Formato | Detección | Tiempo | Variables |
|---|---|---|---|
| RA | Encabezados `Date` y `Time` | `dd/mm/yyyy` + `HH:MM:SS;fff` | 5 numéricas |
| CCW | Preámbulo de metadatos y encabezado que inicia con `Time` | `mm:ss.s` → reloj original (`kind="clock"`, sin fecha) | 7 numéricas |
| BlackBox | Sin columna temporal y muchas columnas numéricas/hex | `fila × 0.001 s` | 49 numéricas |
| Genérico | Respaldo | Primera columna temporal o índice | Numéricas restantes |

### Fixtures de referencia

| Archivo | Líneas | SHA-256 |
|---|---:|---|
| `test_csv/test_RA_CSV.CSV` | 8095 | `3c3080ad9a0c6a14253687e17c017ba064cd93c285e9311e717b65158f1a1aa5` |
| `test_csv/CCW.csv` | 3494 | `0564489991583736eb57d7094d346f43ae91bab03ba03f4a0adf0c702f77e34d` |
| `test_csv/blackbox.csv` | 129 | `e046a2c8f4c8bdd375f8ee54d0d097f6b6225f7f4b873762d0eb79eb86554f9d` |

Si un hash cambia, actualizar `plan.md` §9 y revisar los adaptadores antes de
tocar los tests.

### Resultados esperados

| Archivo | `rows_raw` | `rows_clean` | Variables | Descartado |
|---|---:|---:|---:|---|
| RA | 8094 | 8094 | 5 | 2 columnas string (`Date`, `Time`) |
| CCW | 3488 | 3469 | 7 | 19 filas finales inválidas |
| BlackBox | 128 | 128 | 49 | 14 columnas hex string |

Rangos temporales:

- RA: `2026-07-17T17:06:14.499` → `2026-07-17T17:07:35.429`.
- CCW: `16:42.3` → `22:29.1` (reloj `mm:ss.s`; el archivo no trae fecha).
- BlackBox: `0.000` → `0.127 s`.

---

## 8. Contratos de API

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/` | Interfaz web. |
| `GET` | `/health` | Estado del servicio. |
| `POST` | `/api/datasets` | Subir, detectar y limpiar CSV. |
| `GET` | `/api/datasets/{id}` | Metadatos del dataset. |
| `POST` | `/api/datasets/{id}/plot` | Generar figura Plotly. |
| `DELETE` | `/api/datasets/{id}` | Liberar dataset. |

### Reglas de contrato

- `POST /api/datasets` devuelve `DatasetMetadata` con:
  - `dataset_id`, `filename`, `format`;
  - `rows_raw`, `rows_clean`;
  - métricas de descarte;
  - `time` (`kind`: `datetime` | `elapsed` | `clock`, `origin`, `start`, `end`,
    `label`, `sample_interval_s`, `values`); `values` contiene la serie temporal
    limpia completa (ISO para datetime, segundos de reloj para clock, segundos
    transcurridos para elapsed) para que el slider muestre el tiempo exacto de
    cada índice;
  - `variables` (`id`, `name`, `color`, `min`, `max`, `is_constant`).
- `POST /api/datasets/{id}/plot` recibe:
  - `variables`: lista de `{id, color, name?, unit?, scale?}`, no vacía,
    máximo 50, IDs únicos; `name` ≤ 80 caracteres y `unit` ≤ 4 (opcionales,
    vacío = sin personalizar); `scale` = `{min, max}` con `min < max` mapea
    linealmente el min/max real de todo el dataset a ese rango;
  - `range`: `{start_index, end_index}` inclusivo.
- La respuesta contiene `figure` (`data`, `layout`), `rows_plotted` y las
  variables efectivamente graficadas, cada una con `range_min`/`range_max`
  (extremos reales del subrango).
- No devolver el DataFrame completo ni el CSV al navegador.
- Errores estructurados:

```json
{
  "detail": {
    "code": "INVALID_RANGE",
    "message": "El rango seleccionado está fuera de los límites del dataset.",
    "context": {}
  }
}
```

Códigos estables: `EMPTY_FILE`, `UNSUPPORTED_FORMAT`, `NO_NUMERIC_COLUMNS`,
`NO_ROWS_AFTER_CLEANING`, `INVALID_VARIABLE`, `INVALID_COLOR`,
`INVALID_RANGE`, `DATASET_NOT_FOUND`, `FILE_TOO_LARGE`, `VALIDATION_ERROR`.

---

## 9. Frontend

- Jinja2 + JavaScript vanilla + Plotly.js. **No agregar React, Vue, Angular ni
  build de Node** sin aprobación y actualización del plan.
- Dos vistas (“Datos y opciones” y “Gráfica”), en español, responsive. La
  pestaña “Gráfica” se habilita cuando existe una figura y la gráfica ocupa el
  alto disponible del viewport.
- Antes de graficar mostrar:
  - checkbox de selección,
  - color editable (`input type="color"`),
  - nombre original,
  - mínimo/máximo,
  - badge de constante.
- Por defecto seleccionar las 3 primeras variables.
- El área del nombre de cada variable es un botón que abre el panel “Opciones
  de variable” (`<dialog>`): nombre en la gráfica, unidades (máx. 4), color,
  interruptor “Escalar variable” con mínimo/máximo, vista previa, “Aceptar” y
  “Cancelar”. Al aceptar, nombre y unidad se aplican al instante a la gráfica
  existente (`Plotly.update`): nombre, unidad, color y escalado (reescalado en
  el cliente con la misma fórmula del backend).
- Recuadro “Mínimos y máximos” en el margen derecho, debajo de la leyenda
  (fuera del área de trazado), una línea por variable con solo su color (sin
  nombre): anotación Plotly `name: "stats"` construida en el cliente desde `range_min/range_max`
  (reescalados si la variable está escalada); se reconstruye al aceptar el
  panel y al cambiar de tema, y es arrastrable. Texto de usuario escapado
  (`&`, `<`, `>`) porque Plotly interpreta pseudo-HTML.
- Puntos fijados: clic en la gráfica fija el instante (línea punteada +
  etiqueta `pin-<índice>` con el valor de cada variable por color); clic en la
  etiqueta o “Quitar puntos fijados” los quita. Se borran al regenerar la
  figura. Quitar debe ser idempotente (Plotly emite el clic de anotación dos
  veces).
- Botones: “Seleccionar todas”, “Limpiar selección”, “Restablecer colores”.
- Range slider con noUiSlider 15.8.1, doble asa, rango `0 … rows_clean - 1`.
- No regenerar la gráfica en cada movimiento del slider; hacerlo al pulsar
  “Generar gráfica” o “Actualizar gráfica”.
- Usar `Plotly.react` para actualizar la figura.
- Al cambiar de vista o redimensionar la ventana, llamar a
  `Plotly.Plots.resize` para que la figura use el alto disponible.
- “Abrir en ventana” crea una ventana independiente con la última figura
  generada, sin volver a solicitar datos al backend.
- Usar `scattergl` si una traza supera 5000 puntos; LTTB si supera 50 000.
- Modo oscuro: `theme.js` (en `<head>`, sin `defer`) fija `data-theme` en
  `<html>`; los colores van en variables CSS (no colores fijos nuevos fuera de
  `:root`). La figura se re-tematiza en el cliente con `Plotly.relayout`; el
  backend sigue devolviendo `plotly_white`.
- Escapar datos del CSV con `textContent`; nunca `innerHTML`.
- Sin estilos ni scripts inline si se puede evitar.
- Estados: spinner, toast de error, estado vacío.

### Paleta

- Paleta categórica inicial de 10 colores.
- A partir del color 11, generar tonos con ángulo áureo en HSL.
- Asignación determinista según orden de columnas.
- Colores editables y restaurables.

---

## 10. Límites y seguridad

- Archivo máximo: 50 MB.
- Filas máximas: 500 000.
- Variables por gráfica: 50.
- TTL de dataset: 30 minutos.
- Máximo de datasets en memoria: 5.
- UUID4 para IDs; no aceptar rutas del cliente.
- Un solo worker de Uvicorn en v1 (estado en memoria).
- Cabeceras: `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`,
  `Cache-Control: no-store` en API y `no-cache` en `/` y `/static/`.
- En la plantilla, referenciar estáticos con `asset_url('/ruta')` (añade
  `?v=<huella>`), nunca con `url_for('static', ...)` directo.
- No registrar contenido completo del CSV.
- No escribir en `test_csv/` ni en el directorio del archivo subido.

---

## 11. Pruebas obligatorias

Antes de dar por terminado un cambio:

```bash
ruff format .
ruff check .
pytest -q
```

`test_csv/` no se publica (datos reales, en `.gitignore`). Los tests obtienen
los CSV con `fixture_path()` de `tests/conftest.py`, que omite (`skip`) la
prueba si falta el archivo. Antes de dar por terminado un cambio, ejecutar la
suite **con** los fixtures presentes: sin omisiones.

Matriz mínima:

- Detección correcta de RA, CCW y BlackBox.
- Tiempo RA absoluto, CCW transcurrido, BlackBox 1 ms.
- Limpieza de filas con nulos y columnas string.
- Decimales con coma.
- Rango válido e inválido.
- Color inválido y variable inexistente.
- Dataset expirado.
- Archivo no soportado.
- Dos variables → dos trazas con los colores solicitados.
- Subrango → solo las filas seleccionadas.
- Hashes de `test_csv/` sin cambios.

Prueba manual:

1. Cargar los 3 CSV.
2. Verificar el resumen de limpieza.
3. Cambiar colores.
4. Mover el slider.
5. Generar la gráfica.
6. Hacer zoom, ocultar una serie y exportar PNG.

---

## 12. Flujo de trabajo para agentes

1. Leer `plan.md` y este `AGENTS.md` antes de modificar código.
2. Identificar la fase F1–F7 correspondiente.
3. Implementar en pasos pequeños y ejecutar pruebas.
4. Si cambia el comportamiento, actualizar:
   - `plan.md` (sección afectada y registro de cambios),
   - `AGENTS.md` si cambian reglas operativas,
   - tests.
5. No cambiar versiones ni agregar dependencias sin justificarlo.
6. No implementar nada de la lista “fuera de alcance” sin aprobación:
   - comparar varios CSV,
   - eje Y secundario o normalización automática (el escalado manual por
     variable ya está aprobado),
   - base de datos o autenticación,
   - graficar flags hexadecimales,
   - exportar CSV limpio,
   - múltiples workers.
7. Mantener la API en `snake_case` y los errores estructurados.
8. Verificar que los archivos de `test_csv/` sigan intactos.

### Definition of Done

- [ ] Código tipado y con `ruff` limpio.
- [ ] `pytest` verde.
- [ ] Los 3 fixtures cargan y grafican manualmente.
- [ ] No se modificó `test_csv/`.
- [ ] `plan.md` actualizado si cambió el alcance o el contrato.
- [ ] Versiones exactas registradas.
- [ ] README con instalación, ejecución y pruebas.
- [ ] Assets vendorizados con hashes.

---

## 13. Referencias rápidas

- Plan completo: [`plan.md`](./plan.md)
- Convenciones: `plan.md` §2.
- Versiones: `plan.md` §3.
- Requisitos e invariantes: `plan.md` §5.
- Formatos: `plan.md` §6.
- Limpieza: `plan.md` §7.
- Contratos: `plan.md` §8.
- Fixtures: `plan.md` §9.
- Pruebas: `plan.md` §10.
- Arquitectura: `plan.md` §11.
- Interfaz: `plan.md` §12.
- Fases: `plan.md` §13.
- Riesgos: `plan.md` §14.
- Registro de cambios: `plan.md` §15.

---

**Última sincronización con el plan:** v1.8.0 — 2026-11-12.
