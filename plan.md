---
plan: graficador-rockwell
version: 1.8.0
status: baseline
date: 2026-11-12
python: "3.11"
---

# Plan de implementación — Graficador Rockwell

> **Ubicación canónica:** `plan.md` en la raíz del repositorio.
>
> Este documento es la línea base para comparar futuros cambios. Toda
> modificación de alcance, contrato de API, formato de CSV o versión de
> dependencia debe reflejarse aquí y en el registro de cambios.

## 1. Resumen ejecutivo

Aplicación web con backend Python/FastAPI que carga archivos CSV de datos
eléctricos Rockwell, limpia los datos en memoria y genera gráficas interactivas
de tiempo contra variables eléctricas.

Antes de graficar, la interfaz muestra el nombre y el color de cada variable.
El usuario puede cambiar los colores, seleccionar variables y elegir un
subrango de todo el CSV mediante un control deslizante de doble asa.

### 1.1 Decisiones confirmadas

| ID | Decisión |
|---|---|
| ADR-01 | Frontend con Jinja2 + JavaScript vanilla + Plotly.js, sin build de Node. |
| ADR-02 | Una sola gráfica a la vez; se puede cargar otro archivo sin recargar la página. |
| ADR-03 | Eje de tiempo absoluto para RA, transcurrido para CCW y `1 ms fijo` para BlackBox. |
| ADR-04 | Eje Y compartido para todas las variables. |
| ADR-05 | Se muestran todas las variables numéricas, incluidas las constantes. |
| ADR-06 | Limpieza únicamente en el DataFrame; los CSV de entrada son de solo lectura. |
| ADR-07 | Metadatos y DataFrame limpio en almacén temporal en memoria. |
| ADR-08 | Plotly.js y noUiSlider se sirven localmente para funcionar sin internet. |

---

## 2. Convenciones del proyecto

### 2.1 Idioma y nomenclatura

- **Código, identificadores, nombres de archivos Python y docstrings:** inglés.
- **Textos de interfaz, mensajes de error y documentación de usuario:** español.
- **Python:** `snake_case` para variables y funciones; `PascalCase` para clases y
  modelos Pydantic.
- **JavaScript:** `camelCase` para variables y funciones; `PascalCase` para
  clases.
- **CSS:** clases en `kebab-case`; variables CSS con prefijo `--gr-`.
- **JSON de la API:** claves en `snake_case`.
- **Fechas:** ISO 8601. RA no trae zona horaria, por lo que se conserva como
  fecha/hora local sin zona.
- **Colores:** formato hexadecimal `#RRGGBB`, validado en backend y frontend.

### 2.2 Estilo de código

- Python compatible con PEP 8, tipado en funciones y endpoints públicos.
- Formateo y lint con `ruff` (`ruff format` y `ruff check`).
- Longitud máxima de línea: 100 caracteres.
- Modelos de request/response con Pydantic v2.
- JavaScript moderno (ES2022), sin frameworks y sin variables globales.
- No usar `innerHTML` con datos del CSV; usar `textContent` y creación de nodos.
- CSS con variables para colores, espaciados y tipografía.
- Evitar lógica de negocio duplicada entre backend y frontend: el backend
  valida y genera la figura; el frontend solo presenta y envía selecciones.

### 2.3 API

- Prefijo funcional: `/api`.
- Formato de error uniforme:

```json
{
  "detail": {
    "code": "INVALID_RANGE",
    "message": "El rango seleccionado está fuera de los límites del dataset.",
    "context": {
      "start_index": 5000,
      "end_index": 9000,
      "rows_clean": 3469
    }
  }
}
```

- Códigos de error estables:

| Código | HTTP | Causa |
|---|---:|---|
| `EMPTY_FILE` | 400 | Archivo vacío o sin filas de datos. |
| `UNSUPPORTED_FORMAT` | 400 | No se pudo detectar un formato conocido. |
| `NO_NUMERIC_COLUMNS` | 422 | Tras limpiar no quedan variables numéricas. |
| `NO_ROWS_AFTER_CLEANING` | 422 | Todas las filas fueron descartadas. |
| `INVALID_VARIABLE` | 422 | Variable inexistente o no numérica. |
| `INVALID_COLOR` | 422 | Color fuera del formato `#RRGGBB`. |
| `INVALID_RANGE` | 422 | Índices invertidos o fuera de límites. |
| `DATASET_NOT_FOUND` | 404 | Dataset expirado o inexistente. |
| `FILE_TOO_LARGE` | 413 | Supera el límite configurado. |
| `VALIDATION_ERROR` | 422 | Cuerpo de la petición inválido fuera de las validaciones específicas anteriores. |

- Sin CORS: frontend y API comparten origen.
- Documentación automática disponible en `/docs` y `/redoc`.

### 2.4 Seguridad y límites

- Tamaño máximo de archivo: **50 MB** (configurable por variable de entorno).
- Máximo de filas procesadas: **500 000**.
- Máximo de variables seleccionables por gráfica: **50**.
- El archivo se recibe como `UploadFile`, se procesa en memoria y se descarta.
- No se escribe nada en `test_csv/` ni en el directorio del archivo subido.
- IDs de dataset con UUID4; no se aceptan rutas del cliente.
- Almacén en memoria con TTL de **30 minutos** y máximo de **5 datasets**.
- Cabeceras base: `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: no-referrer`, `Cache-Control: no-store` para respuestas API y `Cache-Control: no-cache`
  para `/` y `/static/` (revalidación por ETag). Además, la plantilla
  referencia los recursos con `asset_url()`, que añade `?v=<sha256[:12]>` del
  contenido: al cambiar un archivo cambia su URL y el navegador no puede
  reutilizar una copia vieja, aunque la tuviera en caché heurística.
- El frontend escapa todo texto proveniente del CSV.

### 2.5 Logging y observabilidad

- `logging` estándar de Python, nivel configurable con `LOG_LEVEL`.
- Registrar: formato detectado, filas originales/limpias, columnas descartadas,
  tiempo de procesamiento y errores de validación.
- No registrar el contenido completo del CSV ni datos sensibles.
- `GET /health` devuelve estado, versión de la app y cantidad de datasets en
  memoria.

### 2.6 Git y cambios

- Commits con Conventional Commits: `feat:`, `fix:`, `docs:`, `test:`,
  `refactor:`, `chore:`.
- Cada cambio que altere el plan debe actualizar este archivo en el mismo
  commit.
- Los cambios incompatibles de API o de contrato de datos requieren incremento
  de versión MAJOR del plan.
- Los CSV de `test_csv/` se consideran fixtures de referencia; si cambian, se
  deben actualizar los hashes y las expectativas de la sección 9.

---

## 3. Versiones y dependencias

### 3.1 Entorno base

| Componente | Versión | Política |
|---|---|---|
| Python | **3.11.2** validado | Soportado `>=3.11,<3.12` en la línea base. |
| Sistema validado | Linux x86_64 | Desarrollo y ejecución local. |
| Navegador | Chrome/Edge/Firefox últimas 2 versiones | Requiere ES2022 y Fetch API. |
| Sistema de archivos | Local | Sin base de datos en v1. |

> `numpy 2.5.x` requiere Python >= 3.12. Por eso la línea base con Python 3.11
> fija `numpy==2.4.6`, la última versión compatible con esa rama.

### 3.2 Dependencias Python

| Paquete | Versión exacta | Uso |
|---|---|---|
| `fastapi` | **0.162.4** | API HTTP y validación. |
| `uvicorn[standard]` | **0.54.0** | Servidor ASGI. |
| `pandas` | **3.1.1** | Lectura y limpieza de DataFrames. |
| `numpy` | **2.4.6** | Operaciones numéricas. |
| `plotly` | **7.1.0** | Construcción de figuras en backend. |
| `python-multipart` | **0.0.33** | Carga de archivos multipart. |
| `jinja2` | **3.1.6** | Plantilla HTML. |
| `orjson` | **3.13.0** | Serialización JSON rápida (opcional pero fijada). |

### 3.3 Dependencias de desarrollo

| Paquete | Versión exacta | Uso |
|---|---|---|
| `pytest` | **9.2.0** | Pruebas. |
| `httpx` | **0.28.1** | Cliente de pruebas para FastAPI. |
| `ruff` | **0.17.4** | Lint y formato. |

### 3.4 Dependencias frontend

| Componente | Versión | Origen |
|---|---|---|
| Plotly.js | **Bundle exacto incluido en `plotly==7.1.0`** | Copiado desde `plotly/package_data/plotly.min.js` a `static/vendor/`. |
| noUiSlider | **15.8.1** | Copiado a `static/vendor/`. |

No se usan CDNs en producción. El archivo `static/vendor/VERSIONS.md` debe
registrar la versión y el hash SHA-256 de cada asset vendorizado.

### 3.5 Política de actualización

1. Las dependencias directas se fijan de forma exacta en `requirements.txt` y
   `requirements-dev.txt`.
2. Un upgrade PATCH de dependencia no cambia el comportamiento esperado; se
   registra como PATCH del plan.
3. Un upgrade MINOR/MAJOR de dependencia requiere revisar tests, contratos y
   este documento; se registra como MINOR o MAJOR según impacto.
4. No se actualiza una dependencia sin ejecutar la matriz de pruebas de la
   sección 10.
5. `pip freeze` se conserva como referencia de reproducibilidad si el entorno
   agrega dependencias transitivas.

---

## 4. Alcance

### 4.1 Dentro del alcance v1

- Carga de un CSV por vez.
- Detección automática de los formatos RA, CCW, BlackBox y un adaptador
  genérico de respaldo.
- Limpieza en DataFrame: filas nulas y columnas string.
- Listado de variables con color asignado y editable antes de graficar.
- Range slider de doble asa sobre todo el dataset limpio.
- Gráfica interactiva de tiempo vs variables eléctricas.
- Descarga de la gráfica como imagen desde la barra de Plotly.
- Mensajes de error claros y resumen de limpieza.
- Escalado lineal opcional por variable hacia un rango definido por el
  usuario (aprobado en v1.6.0), siempre sobre el eje Y compartido.

### 4.2 Fuera del alcance v1

- Comparar varios CSV en la misma gráfica.
- Eje Y secundario o normalización automática 0-1 (el escalado manual por
  variable de v1.6.0 sí está dentro del alcance).
- Persistencia en base de datos o autenticación de usuarios.
- Graficar columnas categóricas o flags hexadecimales.
- Editar o exportar el CSV limpio.
- Procesamiento en streaming para archivos mayores a 50 MB.
- Colas de trabajo o múltiples workers con estado compartido.

Estas exclusiones son parte de la línea base y deben reevaluarse antes de
agregarlas.

---

## 5. Requisitos

### 5.1 Requisitos funcionales

| ID | Requisito | Prioridad |
|---|---|---|
| RF-01 | Subir un archivo `.csv` desde la interfaz. | Must |
| RF-02 | Detectar automáticamente RA, CCW, BlackBox y variantes genéricas. | Must |
| RF-03 | Construir el eje temporal según el formato detectado. | Must |
| RF-04 | Eliminar filas con datos nulos en el DataFrame. | Must |
| RF-05 | Eliminar columnas tipo string del conjunto de variables. | Must |
| RF-06 | Mostrar nombre y color de cada variable antes de graficar. | Must |
| RF-07 | Permitir editar el color de cada variable. | Must |
| RF-08 | Permitir seleccionar qué variables se grafican. | Must |
| RF-09 | Ofrecer un range slider sobre todo el dataset limpio. | Must |
| RF-10 | Generar una gráfica interactiva tiempo vs variables. | Must |
| RF-11 | Mostrar resumen de filas y columnas descartadas. | Should |
| RF-12 | Permitir cargar otro archivo sin recargar la página. | Should |
| RF-13 | Exportar la gráfica como PNG desde la interfaz. | Should |
| RF-14 | Mostrar errores comprensibles ante archivos inválidos. | Must |

### 5.2 Requisitos no funcionales

| ID | Requisito |
|---|---|
| RNF-01 | Procesar los CSV de referencia en menos de 2 segundos en un equipo de desarrollo típico. |
| RNF-02 | Generar la figura de un subrango en menos de 1 segundo para los fixtures actuales. |
| RNF-03 | Funcionar sin conexión a internet una vez instaladas las dependencias y vendorizados los assets. |
| RNF-04 | Interfaz responsive para escritorio y tablet. |
| RNF-05 | Controles accesibles por teclado y con etiquetas asociadas. |
| RNF-06 | No modificar los archivos de entrada. |
| RNF-07 | Soportar los tres formatos sin intervención manual del usuario. |

### 5.3 Invariantes

| ID | Invariante |
|---|---|
| INV-01 | `test_csv/` y cualquier CSV subido se abren en modo lectura; nunca se escriben. |
| INV-02 | La limpieza se aplica solo al DataFrame en memoria. |
| INV-03 | La columna temporal se usa como índice y no aparece como variable graficable. |
| INV-04 | Los colores enviados y devueltos cumplen `^#[0-9A-Fa-f]{6}$`. |
| INV-05 | El rango es inclusivo, `0 <= start_index <= end_index < rows_clean`. |
| INV-06 | BlackBox usa exactamente `0.001 s` por muestra. |
| INV-07 | Todas las series comparten el mismo eje Y; una variable escalada se dibuja en ese mismo eje con sus valores transformados. |
| INV-08 | Se listan todas las variables numéricas, incluidas las constantes. |
| INV-09 | El número de trazas devueltas es igual al número de variables válidas solicitadas. |
| INV-10 | Los nombres de variables se muestran tal como aparecen en el CSV, sin reinterpretación. El usuario puede asignar un nombre de visualización y unidades en el panel de opciones; el nombre original sigue visible en ese panel y en el recuadro de la variable, y nunca se modifica el dataset. |

---

## 6. Formatos de entrada y adaptadores

### 6.1 Registro de adaptadores

| Adaptador | Detección | Tratamiento temporal | Variables |
|---|---|---|---|
| `RaTrendAdapter` | Encabezados `Date` y `Time` | Combina `dd/mm/yyyy` + `HH:MM:SS;fff` | Columnas numéricas posteriores a `Time` |
| `CcwTrendAdapter` | Preámbulo de metadatos y fila de encabezado que inicia con `Time` | Mantiene `mm:ss.s` como reloj de captura (`kind="clock"`); el archivo no trae fecha | Columnas numéricas posteriores a `Time` |
| `BlackBoxAdapter` | Sin columna temporal y muchas columnas numéricas/hex | `fila × 0.001 s` | Columnas numéricas; descarta hex string |
| `GenericAdapter` | Respaldo | Primera columna temporal detectable o índice | Columnas numéricas restantes |

### 6.2 Detección de codificación y delimitador

Orden de codificaciones:

1. `utf-8-sig`
2. `utf-16`
3. `cp1252`
4. `latin-1`

Detección de delimitador:

- Evaluar `,`, `;`, `\t` y `|` sobre las primeras 25 líneas.
- Elegir el delimitador que produzca un número de columnas estable y mayor.
- No confiar únicamente en `csv.Sniffer`: el `;` de los milisegundos de RA
  puede confundirse con separador.
- Soportar campos entre comillas.

### 6.3 Detección de encabezado

- Buscar en las primeras 25 filas.
- Priorizar la fila con más celdas no vacías cuyo siguiente bloque de filas
  contenga datos numéricos o temporales válidos.
- En CCW, ignorar las filas de metadatos (`Sample Rate`, `Capture Size`,
  `Trigger`).
- En RA y BlackBox, el encabezado suele ser la primera fila.

### 6.4 Particularidades por formato

#### RA

- Separador: coma.
- `Date`: `dd/mm/yyyy`.
- `Time`: `HH:MM:SS;fff`; el `;` separa milisegundos, no columnas.
- Eje X: datetime local.
- Se descartan `Date` y `Time` como variables tras construir el índice.

#### CCW

- Preámbulo de 5 filas de metadatos.
- Encabezado real en la fila 6 de los fixtures actuales.
- Tiempo `mm:ss.s`; soportar también `h:mm:ss.s` si aparece.
- Eje X: reloj de captura `mm:ss.s` (por ejemplo `16:42.3 → 22:29.1`). El
  archivo no contiene fecha; no se inventa una.
- Las 19 filas finales sin tiempo ni variables completas se descartan.

#### BlackBox

- Sin columna de tiempo.
- 14 columnas hex (`0x...`) se descartan por ser string.
- 49 columnas numéricas, de las cuales 19 son constantes y se conservan.
- Eje X: `índice_de_fila × 0.001 s`.
- Rango esperado para el fixture: `0.000 … 0.127 s`.

#### Genérico

- Si existe una columna llamada `Time`, `Timestamp`, `Date`, `Fecha` o similar,
  intentar parsearla.
- Si no, usar índice de fila con intervalo de 1 segundo y marcarlo como
  `origin: "row_index"`.
- Si no quedan columnas numéricas, devolver `NO_NUMERIC_COLUMNS`.

---

## 7. Limpieza del DataFrame

### 7.1 Orden de operaciones

1. Leer bytes y decodificar.
2. Detectar delimitador y encabezado.
3. Construir el índice temporal.
4. Eliminar filas y columnas totalmente vacías.
5. Normalizar valores nulos: `""`, `NA`, `N/A`, `NaN`, `-`.
6. Convertir columnas candidatas a numérico con `pd.to_numeric(errors="coerce")`.
7. Conservar como numérica una columna si al menos el **90 %** de sus valores no
   nulos son parseables; en caso contrario, clasificarla como string y
   descartarla.
8. Descartar columnas string que no sean el índice temporal.
9. Eliminar filas con cualquier valor nulo entre las variables numéricas
   restantes.
10. Ordenar por tiempo.
11. Calcular metadatos y métricas de limpieza.

### 7.2 Reglas explícitas

- **Filas nulas:** se elimina la fila completa si falta cualquier variable
  numérica. Es la regla pedida y no es configurable en v1.
- **Columnas string:** se eliminan del conjunto graficable. `Date` y `Time` se
  usan para el índice y luego se excluyen.
- **Decimales:** se acepta punto y coma decimal; internamente se usa punto.
- **Valores no parseables:** se convierten a `NaN` y la fila se elimina en el
  paso 9.
- **Columnas constantes:** se conservan y se marcan con `is_constant: true`.
- **Duplicados temporales:** se conservan; no se agrupan ni se eliminan.
- **Orden:** ascendente por tiempo; si hay empate, se conserva el orden de
  lectura.

### 7.3 Métricas devueltas

- `rows_raw`: filas de la sección de datos, después del encabezado y sin
  metadatos.
- `rows_clean`: filas después de toda la limpieza.
- `dropped_rows_empty`: filas totalmente vacías.
- `dropped_rows_invalid_time`: filas sin tiempo válido.
- `dropped_rows_null`: filas con algún nulo numérico.
- `dropped_columns_empty`: columnas totalmente vacías.
- `dropped_columns_string`: nombres de columnas string eliminadas.
- `variables`: variables numéricas conservadas.

Los tests deben validar `rows_clean` y el total de filas descartadas; no deben
depender de cómo se reparte el descarte entre categorías.

---

## 8. Contratos de datos

### 8.1 `DatasetMetadata`

```json
{
  "dataset_id": "3f1c2a9e-7b2d-4c1a-9f10-8d2e6b7a1c55",
  "filename": "CCW.csv",
  "format": "ccw",
  "rows_raw": 3488,
  "rows_clean": 3469,
  "dropped_rows_empty": 0,
  "dropped_rows_invalid_time": 19,
  "dropped_rows_null": 0,
  "dropped_columns_empty": 0,
  "dropped_columns_string": ["Time"],
  "time": {
    "kind": "clock",
    "origin": "csv_clock",
    "start": 1002.3,
    "end": 1349.1,
    "label": "Tiempo (mm:ss.s)",
    "sample_interval_s": 0.1,
    "values": [1002.3, 1002.4, 1002.5]
  },
  "variables": [
    {
      "id": "var_1",
      "name": "PowerFlex 755T_1 Port 10: 3-Output Current",
      "color": "#1f77b4",
      "min": 0.0,
      "max": 41.42,
      "is_constant": false
    }
  ]
}
```

Campos de `time`:

| Campo | Tipo | Valores |
|---|---|---|
| `kind` | string | `datetime`, `elapsed` o `clock` |
| `origin` | string | `csv_datetime`, `csv_time`, `csv_clock`, `fixed_1ms`, `row_index` |
| `start` | string o float | ISO 8601 si es datetime; segundos de reloj si es clock; segundos transcurridos si es elapsed |
| `end` | string o float | Igual que `start` |
| `label` | string | Texto para el eje X |
| `sample_interval_s` | float o null | Intervalo conocido, si aplica |
| `values` | array de string o float | Serie temporal limpia completa. Permite al range slider mostrar la fecha/hora o el segundo exacto de cada índice. En el ejemplo se trunca; en la respuesta real contiene una entrada por fila limpia. |

### 8.2 `PlotRequest`

```json
{
  "variables": [
    {"id": "var_1", "color": "#1f77b4", "name": "Tensión L1", "unit": "V",
     "scale": {"min": 0, "max": 100}},
    {"id": "var_2", "color": "#ff7f0e"}
  ],
  "range": {
    "start_index": 100,
    "end_index": 1200
  }
}
```

Reglas:

- `variables` no vacío, máximo 50, IDs únicos.
- `start_index` y `end_index` enteros inclusivos.
- `0 <= start_index <= end_index < rows_clean`.
- Los colores son obligatorios y válidos.
- `name` (opcional, máximo 80 caracteres) es el nombre de visualización; vacío
  o ausente = nombre original del CSV.
- `unit` (opcional, máximo 4 caracteres) se muestra en la leyenda como
  `Nombre [unidad]` y en el hover junto al valor. Si todas las trazas comparten
  la misma unidad, el eje Y se titula `Valor [unidad]`.
- Ambos se recortan (`strip`); un `name` o `unit` demasiado largo devuelve
  `VALIDATION_ERROR`.
- `scale` (opcional, `null` = sin escalar): `{min, max}` finitos con
  `min < max`; si no, `VALIDATION_ERROR`. El rango real de la variable en
  **todo** el dataset limpio (`VariableInfo.min … max`) se mapea linealmente a
  `min … max`: `y' = min + (y − real_min)·(max − min)/(real_max − real_min)`.
  Usar el dataset completo (no el subrango) mantiene la escala estable al
  mover el slider. Una variable constante se dibuja en `min`.
- Con escalado, la traza lleva los valores reales en `customdata` y el hover
  muestra “Real: …”; la leyenda añade `· esc. min…max` y `meta[2]` guarda ese
  sufijo. La unidad (`unit`) se refiere al valor escalado mostrado.

### 8.3 `PlotResponse`

```json
{
  "figure": {
    "data": [],
    "layout": {}
  },
  "rows_plotted": 1101,
  "variables": [
    {
      "id": "var_1",
      "name": "Tensión L1",
      "original_name": "Nombre original",
      "unit": "V",
      "scale": {"min": 0, "max": 100},
      "color": "#1f77b4",
      "range_min": 0.0,
      "range_max": 74.41
    }
  ]
}
```

- `figure` sigue el esquema de Plotly (`data`, `layout`), sin `frames`.
- `rows_plotted` es el número de filas del subrango solicitado.
- `range_min` / `range_max` son el mínimo y el máximo **reales** (sin escalar)
  de cada variable en el subrango graficado; alimentan el recuadro
  “Mínimos y máximos” de la gráfica.
- No se devuelven los datos completos del CSV.

### 8.4 Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/` | Interfaz web. |
| `GET` | `/health` | Estado del servicio. |
| `POST` | `/api/datasets` | Subir, detectar y limpiar un CSV. |
| `GET` | `/api/datasets/{id}` | Consultar metadatos. |
| `POST` | `/api/datasets/{id}/plot` | Generar figura Plotly. |
| `DELETE` | `/api/datasets/{id}` | Liberar dataset. |

---

## 9. Línea base de fixtures

### 9.1 Archivos de referencia

| Archivo | Líneas | SHA-256 |
|---|---:|---|
| `test_csv/test_RA_CSV.CSV` | 8095 | `3c3080ad9a0c6a14253687e17c017ba064cd93c285e9311e717b65158f1a1aa5` |
| `test_csv/CCW.csv` | 3494 | `0564489991583736eb57d7094d346f43ae91bab03ba03f4a0adf0c702f77e34d` |
| `test_csv/blackbox.csv` | 129 | `e046a2c8f4c8bdd375f8ee54d0d097f6b6225f7f4b873762d0eb79eb86554f9d` |

Si un hash cambia, actualizar este documento y revisar los adaptadores antes de
ajustar los tests.

### 9.2 Resultados esperados

| Archivo | Formato | `rows_raw` | `rows_clean` | Variables | Cols. string | Eje X |
|---|---|---:|---:|---:|---:|---|
| `test_RA_CSV.CSV` | `ra` | 8094 | 8094 | 5 | 2 (`Date`, `Time`) | `2026-07-17T17:06:14.499` → `2026-07-17T17:07:35.429` |
| `CCW.csv` | `ccw` | 3488 | 3469 | 7 | 1 (`Time`) | `16:42.3` → `22:29.1` |
| `blackbox.csv` | `blackbox` | 128 | 128 | 49 | 14 (hex) | `0.000` → `0.127 s` |

Notas:

- RA: 8094 filas, 5 variables numéricas, sin filas nulas.
- CCW: 19 filas finales descartadas; 7 variables; intervalo de 0.1 s; eje X con
  reloj de captura `mm:ss.s` (`16:42.3 → 22:29.1`), sin fecha porque el archivo
  no la incluye.
- BlackBox: 14 columnas hex descartadas; 49 variables numéricas, 19 constantes;
  intervalo fijo de 1 ms.

---

## 10. Pruebas y criterios de aceptación

### 10.1 Matriz de pruebas

| ID | Prueba | Entrada | Resultado esperado |
|---|---|---|---|
| T-01 | Detección RA | `test_RA_CSV.CSV` | `format="ra"`, 8094 filas, 5 variables. |
| T-02 | Detección CCW | `CCW.csv` | `format="ccw"`, 3469 filas, 7 variables, 19 descartadas. |
| T-03 | Detección BlackBox | `blackbox.csv` | `format="blackbox"`, 128 filas, 49 variables, 14 string descartadas. |
| T-04 | Tiempo RA | fixture RA | Inicio/fin exactos y `kind="datetime"`. |
| T-05 | Tiempo CCW | fixture CCW | `16:42.3 → 22:29.1`, `kind="clock"`. |
| T-06 | Tiempo BlackBox | fixture BlackBox | `0.000 → 0.127`, intervalo 0.001. |
| T-07 | Limpieza de nulos | CSV sintético | Fila con una celda vacía desaparece. |
| T-08 | Limpieza de strings | CSV sintético | Columna de texto no aparece en variables. |
| T-09 | Decimales con coma | CSV sintético | Valor `"1,5"` se interpreta como `1.5`. |
| T-10 | Rango válido | API + fixture | Número de puntos y trazas correctos. |
| T-11 | Rango inválido | `start > end` | HTTP 422 con `INVALID_RANGE`. |
| T-12 | Color inválido | API | HTTP 422 con `INVALID_COLOR`. |
| T-13 | Variable inexistente | API | HTTP 422 con `INVALID_VARIABLE`. |
| T-14 | Dataset expirado | API | HTTP 404 con `DATASET_NOT_FOUND`. |
| T-15 | Archivo no soportado | `.txt` o binario | HTTP 400 con `UNSUPPORTED_FORMAT`. |
| T-16 | Inmutabilidad | Fixtures | Los hashes no cambian después de las pruebas. |
| T-17 | Figura | 2 variables | 2 trazas con los colores solicitados. |
| T-18 | Slider | Rango parcial | Solo se grafican las filas seleccionadas. |

### 10.2 Criterios de aceptación

| ID | Criterio |
|---|---|
| AC-01 | Los 3 archivos se cargan y detectan sin intervención manual. |
| AC-02 | La limpieza ocurre en el DataFrame y los archivos originales no cambian. |
| AC-03 | Las columnas string y las filas con nulos no aparecen en el conjunto graficable. |
| AC-04 | Antes de graficar se ven nombre y color de cada variable. |
| AC-05 | El color de cada variable es editable y se respeta en la gráfica. |
| AC-06 | El slider cubre todo el CSV limpio y el rango elegido se respeta. |
| AC-07 | La gráfica permite zoom, paneo, hover, ocultar series y exportar imagen. |
| AC-08 | Los errores se muestran con un mensaje comprensible. |
| AC-09 | La interfaz funciona sin internet con los assets vendorizados. |
| AC-10 | `ruff check` y `pytest` pasan sin errores. |
| AC-11 | La documentación `/docs` refleja los endpoints y esquemas. |
| AC-12 | El README explica instalación, ejecución y pruebas. |

### 10.3 Definition of Done

- [ ] Código implementado y tipado.
- [ ] `ruff format` y `ruff check` sin errores.
- [ ] `pytest` verde en la matriz de pruebas.
- [ ] Los 3 fixtures cargan y grafican manualmente en navegador.
- [ ] No se modificó ningún archivo de `test_csv/`.
- [ ] README y `plan.md` actualizados.
- [ ] Versiones exactas registradas en `requirements.txt` y
      `requirements-dev.txt`.
- [ ] Assets vendorizados con sus hashes en `static/vendor/VERSIONS.md`.

---

## 11. Arquitectura y estructura

```text
Navegador
  ├── Sube CSV (multipart)
  ├── Recibe metadatos + variables + colores
  ├── Selecciona variables y rango
  └── Pide figura a FastAPI → Plotly.react

FastAPI
  ├── Detección de codificación, delimitador y formato
  ├── Limpieza en DataFrame
  ├── Asignación de colores
  ├── Almacén temporal en memoria
  └── Construcción de figura Plotly (JSON)
```

```text
Graficador Rockwell/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── api/
│   │   └── routes.py
│   ├── models/
│   │   └── schemas.py
│   ├── services/
│   │   ├── ingest.py
│   │   ├── cleaning.py
│   │   ├── palette.py
│   │   ├── plotting.py
│   │   ├── store.py
│   │   └── formats/
│   │       ├── base.py
│   │       ├── ra.py
│   │       ├── ccw.py
│   │       ├── blackbox.py
│   │       ├── generic.py
│   │       └── registry.py
│   ├── templates/
│   │   └── index.html
│   └── static/
│       ├── css/app.css
│       ├── js/app.js
│       └── vendor/
│           ├── plotly.min.js
│           ├── nouislider.min.js
│           ├── nouislider.min.css
│           └── VERSIONS.md
├── tests/
│   ├── test_formats.py
│   ├── test_cleaning.py
│   ├── test_plotting.py
│   └── test_api.py
├── test_csv/                 # Solo lectura, fixtures de referencia
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml            # Configuración de ruff y pytest
├── .python-version           # 3.11
├── run.sh
└── README.md
```

### 11.1 Flujo de datos

1. `POST /api/datasets` recibe el archivo.
2. `ingest.py` detecta codificación, delimitador y adaptador.
3. `cleaning.py` produce un `CleanedDataset` con índice temporal, DataFrame
   numérico y métricas.
4. `palette.py` asigna colores a las variables.
5. `store.py` guarda el dataset con UUID y TTL.
6. El frontend muestra el resumen y el selector.
7. `POST /api/datasets/{id}/plot` valida variables, colores e índices.
8. `plotting.py` construye la figura con el subrango.
9. El frontend renderiza con `Plotly.react`.

### 11.2 Almacén temporal

- Estructura: diccionario protegido por lock, clave UUID4.
- Valor: `CleanedDataset` + metadatos + timestamp de creación/último acceso.
- TTL: 30 minutos desde el último acceso.
- Capacidad: 5 datasets; al superar, eliminar el menos usado.
- `DELETE /api/datasets/{id}` elimina inmediatamente.
- En v1 no se comparte estado entre workers. Ejecutar con un solo worker.

---

## 12. Diseño de interfaz

### 12.1 Dos vistas

1. **Cabecera:** título “Graficador Rockwell”, estado del servicio y botón
   “Modo oscuro” / “Modo claro”.
2. **Pestañas:** “Datos y opciones” y “Gráfica”. Se muestran cuando hay un
   dataset cargado; la pestaña “Gráfica” se habilita al existir una figura.
3. **Vista “Datos y opciones”:**
   - zona de arrastrar/soltar + botón “Seleccionar archivo”;
   - resumen de limpieza: formato, filas originales/limpias, columnas
     eliminadas y rango temporal;
   - tabla responsive de variables con checkbox, color, nombre, mínimo/máximo
     y badge de constante; el área del nombre de cada recuadro es un botón que
     abre el panel “Opciones de variable” (`<dialog>` modal) con nombre en la
     gráfica, unidades (máximo 4 caracteres), color, interruptor “Escalar
     variable” con mínimo y máximo (deshabilitados si está apagado; el error de
     validación se muestra dentro del panel) y vista previa de la leyenda, más los botones “Aceptar” y “Cancelar” (Esc o clic fuera también
     cancelan). El checkbox y el color siguen en el recuadro para seleccionar
     rápido;
   - acciones “Seleccionar todas”, “Limpiar selección” y
     “Restablecer colores”;
   - range slider de doble asa;
   - botón “Generar gráfica”.
4. **Vista “Gráfica”:** figura Plotly a pantalla completa, con altura calculada
   respecto al viewport, botones “Abrir en ventana”, “Volver a opciones” y
   “Actualizar gráfica”. “Abrir en ventana” crea una ventana independiente con
   la última figura generada y sus controles de zoom/exportación.
5. **Navegación:** al generar una gráfica correctamente se cambia a la vista
   “Gráfica”; “Volver a opciones” conserva dataset, selección, colores y rango.
6. **Redimensionado:** al cambiar de vista o de tamaño de ventana se llama a
   `Plotly.Plots.resize` para que la figura ocupe el alto disponible.
7. **Estados:** spinner durante carga/procesamiento, mensajes de error tipo
   toast, estado vacío antes de subir.
8. **Tema claro/oscuro:** por defecto sigue `prefers-color-scheme`; el botón
   de la cabecera alterna el tema y la elección se guarda en `localStorage`
   (`gr-theme`). `app/static/js/theme.js` se carga sin `defer` en `<head>`
   para aplicar `data-theme` antes del primer pintado. Los colores de la
   interfaz son variables CSS redefinidas en `:root[data-theme="dark"]`.

### 12.2 Comportamiento del selector

- Se listan todas las variables numéricas, incluidas las constantes.
- Por defecto se seleccionan las 3 primeras variables.
- Cada variable tiene un color asignado desde la paleta antes de graficar.
- El color se puede cambiar con `input type="color"`.
- “Restablecer colores” vuelve a la asignación automática.
- Nombres y unidades personalizados se conservan mientras el dataset está
  cargado y se reinician al cargar otro archivo.
- Al pulsar “Aceptar”, si la variable ya está en la gráfica, nombre, unidad,
  color y escalado se aplican al instante (leyenda, hover, valores, título y
  autorango del eje Y) con `Plotly.update`, también en la ventana
  independiente, sin pedir la figura al backend. El frontend reescala con la
  misma fórmula que el backend, usando los valores reales (`customdata` si la
  traza ya estaba escalada; si no, `y`) y `VariableInfo.min/max`. Selección,
  rango y el color cambiado desde el recuadro siguen requiriendo “Actualizar
  gráfica”.
- La gráfica incluye un recuadro “Mínimos y máximos” fuera del área de
  trazado, en el margen derecho, debajo de la leyenda y alineado con ella
  (`x = 1.01`, anclado a la izquierda; abajo, `y = 0`). Tiene una línea por
  variable graficada, identificada solo por el color de la traza (sin nombre,
  que ya está en la leyenda): mínimo y máximo del subrango con su unidad.
  Si la variable está escalada se muestran los valores escalados (la
  transformación es lineal creciente, así que basta reescalar
  `range_min/range_max`). Lo construye el frontend como anotación de Plotly
  (`name: "stats"`), se reconstruye al aceptar el panel de opciones y al
  cambiar de tema, aparece en la ventana independiente y en el PNG exportado,
  y se puede arrastrar (`edits.annotationPosition`) si tapa datos; la posición
  arrastrada se conserva al actualizar la gráfica.
- Puntos fijados: un clic sobre la gráfica fija el instante más cercano
  (`plotly_click`; con `hovermode: "x unified"` vale para todas las trazas).
  Se dibuja una línea vertical punteada (`layout.shapes`) y una etiqueta
  (anotación `name: "pin-<índice>"`) con el tiempo y el valor de cada variable
  identificado por su color; si la variable está escalada muestra también
  `(real …)`. Clic en la etiqueta (o de nuevo en el mismo punto) lo quita;
  “Quitar puntos fijados” los quita todos. Máximo 20 (se descarta el más
  antiguo). Se recalculan al aceptar el panel de opciones y al cambiar de
  tema, se ven en la ventana independiente (donde también se pueden fijar) y
  en el PNG, y se borran al generar o actualizar la gráfica (puede cambiar el
  rango). Plotly puede emitir dos `plotly_clickannotation` por clic: quitar
  es idempotente.
- Al apagar el escalado se conservan el mínimo y el máximo escritos para
  volver a activarlo; el recuadro muestra la etiqueta `esc. min…max`.
- Cada traza lleva `meta = [nombre, unidad, sufijo de escala]` y su `hovertemplate` usa
  `%{meta[0]}`/`%{meta[1]}`; así el texto del usuario nunca se interpreta como
  marcador de plantilla.
- El botón “Generar gráfica” solo se habilita si hay al menos una variable
  seleccionada y el rango es válido.

### 12.3 Range slider

- Implementado con noUiSlider 15.8.1, modo doble asa.
- Rango: `0 … rows_clean - 1`.
- Etiquetas: fecha/hora o segundos de inicio y fin, más el número de filas
  seleccionadas.
- El rango es inclusivo.
- Al mover el slider no se regenera la gráfica automáticamente; se actualiza al
  pulsar “Generar gráfica” o “Actualizar gráfica”.

### 12.4 Gráfica

- Una traza `scatter` por variable, `mode="lines"`.
- Para más de 5000 puntos por traza, usar `scattergl`.
- Layout:
  - título con nombre del archivo y rango;
  - eje X con `time.label`;
  - eje Y “Valor”;
  - `hovermode="x unified"`;
  - leyenda interactiva;
  - plantilla clara (`plotly_white`) desde el backend; el frontend aplica el
    tema activo (fondos, texto, rejilla, hover, modebar) con
    `Plotly.relayout`, también en “Abrir en ventana”, sin pedir datos de
    nuevo. Los colores de las trazas no cambian con el tema y el PNG
    exportado usa los colores del tema visible;
  - responsive.
- Downsampling LTTB si una traza supera 50 000 puntos.
- Sin ejes secundarios ni normalización automática en v1; el escalado manual
  por variable (§8.2) usa el mismo eje Y.
- Layout con `autosize=True`; el frontend fija la altura al alto útil de la
  vista “Gráfica” y llama a `Plotly.Plots.resize` al redimensionar.
- Para `kind="clock"` se usa un eje de fecha sintético (epoch fijo) con
  `tickformat="%M:%S"` y `hoverformat="%M:%S.%L"`, de modo que se vea el reloj
  original `mm:ss.s` sin inventar una fecha.

### 12.5 Paleta de colores

- Paleta categórica inicial de 10 colores.
- A partir del color 11, generar tonos con ángulo áureo en HSL y convertir a
  hexadecimal.
- La asignación es determinista según el orden de las columnas.
- Los colores se pueden editar individualmente.

---

## 13. Fases de implementación

| Fase | Entregable |
|---|---|
| F1 | Esqueleto FastAPI, configuración, `/health`, plantilla base. |
| F2 | Ingesta: codificación, delimitador, detección de encabezado y adaptadores. |
| F3 | Limpieza, métricas y pruebas de los 3 formatos. |
| F4 | Paleta, almacén temporal, endpoints de dataset y figura. |
| F5 | Frontend: carga, resumen, selector de variables/colores y slider. |
| F6 | Gráfica Plotly, estados de error, responsive y accesibilidad. |
| F7 | Pruebas de API, README, vendorización y revisión manual. |

---

## 14. Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación |
|---|---|---|
| El `;` de milisegundos de RA se detecta como delimitador. | Alto | Heurística de columnas estables; test específico. |
| CCW cambia la cantidad de filas de metadatos. | Medio | Búsqueda de encabezado por contenido, no por número fijo. |
| BlackBox agrega columnas hex con otro prefijo. | Medio | Regla de parseabilidad numérica y test sintético. |
| Archivos futuros superan 50 000 puntos. | Medio | LTTB y límite de filas. |
| Escalas muy distintas aplastan señales pequeñas. | Medio | Eje compartido por decisión; el usuario selecciona grupos similares. |
| Pérdida de flags hex al aplicar la regla de strings. | Bajo | Documentado; tratamiento categórico queda fuera de v1. |
| Múltiples workers con almacén en memoria. | Medio | Ejecutar un worker en v1; persistencia queda fuera de alcance. |
| Dependencias futuras rompen compatibilidad. | Medio | Versiones exactas y matriz de pruebas antes de actualizar. |

---

## 15. Registro de cambios del plan

| Versión | Fecha | Tipo | Cambio |
|---|---|---|---|
| 1.0.0 | 2026-11-11 | Baseline | Línea base inicial con arquitectura, contratos, convenciones, versiones, fixtures y criterios de aceptación. |
| 1.0.1 | 2026-11-11 | Patch | Corrige el conteo de variables de CCW (7, no 8); documenta `time.values` en `DatasetMetadata`; agrega el código estable `VALIDATION_ERROR`. |
| 1.1.0 | 2026-11-11 | Minor | Separa la interfaz en dos vistas (“Datos y opciones” y “Gráfica”); la gráfica ocupa el alto disponible y se redimensiona con `Plotly.Plots.resize`. |
| 1.2.0 | 2026-11-11 | Minor | Agrega “Abrir en ventana” en la vista “Gráfica” para mostrar la última figura en una ventana independiente. |
| 1.3.0 | 2026-11-12 | Minor | CCW muestra el reloj original `mm:ss.s` (`kind="clock"`, `origin="csv_clock"`) en lugar de segundos desde 0; no se inventa fecha porque el archivo no la trae. |
| 1.4.0 | 2026-11-12 | Minor | Agrega modo oscuro: botón en la cabecera, preferencia del sistema por defecto, persistencia en `localStorage` y figura Plotly re-tematizada en el cliente (incluida la ventana independiente). |
| 1.5.0 | 2026-11-12 | Minor | Panel “Opciones de variable”: el recuadro de cada variable abre un diálogo para cambiar el nombre de visualización, agregar unidades (máx. 4) y color, con “Aceptar”/“Cancelar”. `PlotRequest.variables[]` acepta `name` y `unit` opcionales; `PlotResponse.variables[]` agrega `original_name` y `unit`. INV-10 aclarado. |
| 1.5.1 | 2026-11-12 | Patch | El nombre y la unidad editados se reflejan al instante en la gráfica ya generada (y en la ventana independiente) sin regenerarla; el hover lee las etiquetas desde `meta` de la traza. |
| 1.6.0 | 2026-11-12 | Minor | Escalado lineal opcional por variable en el panel “Opciones de variable” (interruptor on/off, mínimo y máximo del usuario). `PlotRequest.variables[].scale` y `PlotTraceInfo.scale`; hover con valor real en `customdata`. Aprobado por el usuario aunque §4.2 excluía la normalización; INV-07 aclarado. |
| 1.6.1 | 2026-11-12 | Patch | El escalado y el color aceptados en el panel se aplican al instante a la gráfica existente (antes solo la marcaban como pendiente). `Cache-Control: no-cache` en `/` y `/static/` para que el navegador no use un `app.js` obsoleto. |
| 1.6.2 | 2026-11-12 | Patch | URLs de recursos con huella de contenido (`asset_url`, `?v=`): un `app.js` cacheado de una versión anterior (sin `Cache-Control`) seguía ignorando el escalado aunque el HTML fuera nuevo. |
| 1.7.0 | 2026-11-12 | Minor | Recuadro “Mínimos y máximos” abajo a la derecha de la gráfica (anotación Plotly arrastrable, valores del subrango, escalados si aplica). `PlotTraceInfo.range_min/range_max`. |
| 1.7.1 | 2026-11-13 | Patch | El recuadro “Mínimos y máximos” sale del área de trazado: margen derecho, debajo de la leyenda; sin nombres, solo el color de cada variable. |
| 1.8.0 | 2026-11-13 | Minor | Puntos fijados: clic en la gráfica fija una línea y una etiqueta con los valores de todas las variables en ese instante; clic en la etiqueta o “Quitar puntos fijados” los elimina. |
| 1.8.0 | 2026-11-16 | Repo | Preparación para GitHub: `test_csv/` fuera del repositorio (`.gitignore`), tests omitidos si falta un fixture (`fixture_path`), rutas locales eliminadas del plan. Sin cambios en la aplicación. |

### 15.1 Procedimiento para futuras actualizaciones

1. Comparar la propuesta contra este archivo (`diff`).
2. Identificar requisitos, invariantes, contratos o versiones afectadas.
3. Actualizar las secciones correspondientes.
4. Agregar una fila al registro de cambios con versión, fecha, tipo y resumen.
5. Actualizar la matriz de pruebas si cambia el comportamiento esperado.
6. Ejecutar `ruff check` y `pytest`.
7. Si la implementación se desvía del plan, actualizar el plan en el mismo
   commit; no dejar documentación desactualizada.

### 15.2 Reglas de versionado

| Incremento | Cuándo |
|---|---|
| **MAJOR** | Cambio de alcance, arquitectura, contrato de API incompatible o formato de entrada que rompe compatibilidad. |
| **MINOR** | Nueva funcionalidad compatible, nuevo adaptador, nuevo control de interfaz o cambio de dependencia con impacto funcional. |
| **PATCH** | Corrección, aclaración, actualización de fixture o upgrade PATCH de dependencia sin cambio de comportamiento. |

---

## 16. Aprobación

- **Estado:** línea base propuesta.
- **Aprobador:** usuario / responsable del proyecto.
- **Fecha de aprobación:** pendiente.
- **Próximo paso:** implementar F1–F7 y actualizar este documento con los
  resultados reales de la matriz de pruebas.
