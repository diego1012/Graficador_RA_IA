"use strict";

const FORMAT_LABELS = {
  ra: "RA Trend",
  ccw: "CCW Trend",
  blackbox: "BlackBox",
  generic: "Genérico",
};

const state = {
  dataset: null,
  selected: new Set(),
  colors: new Map(),
  labels: new Map(),
  scales: new Map(),
  plottedIds: [],
  // Per plotted trace: real extremes of the plotted subrange and active scale.
  plottedStats: [],
  // Points fixed by clicking the chart: indexes into the plotted traces.
  pins: [],
  editingId: null,
  slider: null,
  range: [0, 0],
  chartReady: false,
  figure: null,
  plotting: false,
  uploading: false,
  view: "config",
  chartWindow: null,
};

const el = (id) => document.getElementById(id);

const dropZone = el("drop-zone");
const fileInput = el("file-input");
const uploadStatus = el("upload-status");
const summary = el("summary");
const configPanel = el("config-panel");
const variablesList = el("variables-list");
const plotButton = el("plot-button");
const updatePlotButton = el("update-plot");
const openWindowButton = el("open-window");
const backToConfig = el("back-to-config");
const viewTabs = el("view-tabs");
const viewConfig = el("view-config");
const viewChart = el("view-chart");
const tabConfig = el("tab-config");
const tabChart = el("tab-chart");
const chartElement = el("chart");
const chartWrap = el("chart-wrap");
const chartEmpty = el("chart-empty");
const chartLoading = el("chart-loading");
const chartMeta = el("chart-meta");
const clearPinsButton = el("clear-pins");
const toastContainer = el("toast-container");
const variableDialog = el("variable-dialog");
const variableForm = el("variable-form");
const variableDialogTitle = el("variable-dialog-title");
const variableOriginalName = el("variable-original-name");
const variableNameInput = el("variable-name-input");
const variableUnitInput = el("variable-unit-input");
const variableColorInput = el("variable-color-input");
const variablePreviewSwatch = el("variable-preview-swatch");
const variablePreviewText = el("variable-preview-text");
const variableScaleToggle = el("variable-scale-toggle");
const variableScaleMin = el("variable-scale-min");
const variableScaleMax = el("variable-scale-max");
const variableScaleReal = el("variable-scale-real");
const variableScaleError = el("variable-scale-error");
const MAX_UNIT_LENGTH = 4;
const themeToggle = el("theme-toggle");
const themeToggleLabel = el("theme-toggle-label");

const PLOT_THEMES = {
  light: {
    paper: "#ffffff",
    plot: "#ffffff",
    ink: "#2a3f5f",
    grid: "#ebf0f8",
    line: "#d8e2ee",
    hoverBg: "#ffffff",
    hoverBorder: "#d8e2ee",
    statsBg: "rgba(255, 255, 255, 0.88)",
  },
  dark: {
    paper: "#131e2e",
    plot: "#131e2e",
    ink: "#d6e1ee",
    grid: "#24344a",
    line: "#34485f",
    hoverBg: "#1a2738",
    hoverBorder: "#34485f",
    statsBg: "rgba(19, 30, 46, 0.88)",
  },
};

function currentTheme() {
  return window.GrTheme ? window.GrTheme.get() : "light";
}

/** Layout overrides (Plotly dotted keys) that recolor a figure for a theme. */
function plotThemeUpdate(theme) {
  const colors = PLOT_THEMES[theme] || PLOT_THEMES.light;
  const update = {
    paper_bgcolor: colors.paper,
    plot_bgcolor: colors.plot,
    "font.color": colors.ink,
    "title.font.color": colors.ink,
    "legend.bgcolor": "rgba(0,0,0,0)",
    "legend.font.color": colors.ink,
    "hoverlabel.bgcolor": colors.hoverBg,
    "hoverlabel.bordercolor": colors.hoverBorder,
    "hoverlabel.font.color": colors.ink,
    "modebar.bgcolor": "rgba(0,0,0,0)",
    "modebar.color": theme === "dark" ? "#8a9db3" : "#6b7f96",
    "modebar.activecolor": theme === "dark" ? "#2bb3a5" : "#0f766e",
  };
  for (const axis of ["xaxis", "yaxis"]) {
    update[`${axis}.gridcolor`] = colors.grid;
    update[`${axis}.linecolor`] = colors.line;
    update[`${axis}.zerolinecolor`] = colors.line;
    update[`${axis}.color`] = colors.ink;
  }
  return update;
}

/** Return a copy of a layout with the theme overrides applied. */
function themedLayout(layout, theme) {
  const result = structuredClone(layout || {});
  for (const [path, value] of Object.entries(plotThemeUpdate(theme))) {
    const keys = path.split(".");
    let target = result;
    for (const key of keys.slice(0, -1)) {
      if (typeof target[key] !== "object" || target[key] === null) {
        target[key] = {};
      }
      target = target[key];
    }
    target[keys[keys.length - 1]] = value;
  }
  return result;
}

function syncThemeToggle(theme) {
  const isDark = theme === "dark";
  themeToggle.setAttribute("aria-pressed", String(isDark));
  themeToggle.title = isDark ? "Cambiar a modo claro" : "Cambiar a modo oscuro";
  themeToggleLabel.textContent = isDark ? "Modo claro" : "Modo oscuro";
}

function applyThemeToCharts(theme) {
  syncThemeToggle(theme);
  if (state.chartReady && typeof Plotly !== "undefined") {
    Plotly.relayout(chartElement, plotThemeUpdate(theme));
  }
  const win = state.chartWindow;
  if (win && !win.closed) {
    win.document.documentElement.dataset.theme = theme;
    const chartDiv = win.document.getElementById("standalone-chart");
    if (win.Plotly && chartDiv && chartDiv.data) {
      win.Plotly.relayout(chartDiv, plotThemeUpdate(theme));
    }
  }
  refreshOverlays();
}

function formatCount(value) {
  return new Intl.NumberFormat("es-ES").format(Number(value));
}

function formatNumber(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "—";
  }
  if (number !== 0 && (Math.abs(number) < 0.001 || Math.abs(number) >= 1000000)) {
    return number.toExponential(3);
  }
  return new Intl.NumberFormat("es-ES", {
    maximumFractionDigits: 4,
  }).format(number);
}

function formatClock(value) {
  const total = Number(value);
  if (!Number.isFinite(total)) {
    return "—";
  }
  const sign = total < 0 ? "-" : "";
  const absolute = Math.abs(total);
  const minutes = Math.floor(absolute / 60);
  const seconds = absolute - minutes * 60;
  return `${sign}${String(minutes).padStart(2, "0")}:${seconds
    .toFixed(1)
    .padStart(4, "0")}`;
}

function formatTime(value, kind) {
  if (value === null || value === undefined) {
    return "—";
  }
  if (kind === "datetime") {
    return String(value).replace("T", " ");
  }
  if (kind === "clock") {
    return formatClock(value);
  }
  return `${Number(value).toFixed(3)} s`;
}

async function readResponse(response) {
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  if (!response.ok) {
    const detail = payload && payload.detail;
    const message =
      typeof detail === "string"
        ? detail
        : detail && detail.message
          ? detail.message
          : `Error HTTP ${response.status}`;
    throw new Error(message);
  }
  return payload;
}

function showToast(message) {
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = message;
  toastContainer.append(toast);
  window.setTimeout(() => {
    toast.classList.add("out");
    window.setTimeout(() => toast.remove(), 320);
  }, 6500);
}

function setUploadStatus(message, isError = false) {
  uploadStatus.textContent = message;
  uploadStatus.classList.toggle("error", isError);
}

function setHealth(status, message) {
  const dot = el("health-dot");
  dot.classList.remove("ok", "error");
  if (status) {
    dot.classList.add(status);
  }
  el("health-text").textContent = message;
}

async function checkHealth() {
  try {
    const response = await fetch("/health", { cache: "no-store" });
    const payload = await readResponse(response);
    setHealth("ok", `Servicio listo · v${payload.version}`);
  } catch {
    setHealth("error", "Servicio no disponible");
  }
}

function syncTabs() {
  viewTabs.classList.toggle("hidden", !state.dataset);
  tabChart.disabled = !state.chartReady;
  updatePlotButton.disabled =
    !state.chartReady || state.plotting || state.selected.size === 0;
  openWindowButton.disabled = !state.chartReady || !state.figure;
}

function setView(view) {
  state.view = view;
  const showConfig = view === "config";
  viewConfig.classList.toggle("hidden", !showConfig);
  viewChart.classList.toggle("hidden", showConfig);
  tabConfig.classList.toggle("is-active", showConfig);
  tabChart.classList.toggle("is-active", !showConfig);
  tabConfig.setAttribute("aria-selected", String(showConfig));
  tabChart.setAttribute("aria-selected", String(!showConfig));

  if (!showConfig) {
    window.requestAnimationFrame(() => {
      if (state.chartReady && typeof Plotly !== "undefined") {
        Plotly.Plots.resize(chartElement);
      }
    });
  }
}

function renderSummary() {
  const dataset = state.dataset;
  const droppedRows = dataset.rows_raw - dataset.rows_clean;
  el("format-badge").textContent =
    FORMAT_LABELS[dataset.format] || dataset.format.toUpperCase();
  el("sum-file").textContent = dataset.filename;
  el("sum-rows-raw").textContent = formatCount(dataset.rows_raw);
  el("sum-rows-clean").textContent = `${formatCount(dataset.rows_clean)} (${formatCount(
    droppedRows,
  )} descartadas)`;
  el("sum-vars").textContent = formatCount(dataset.variables.length);
  el("sum-time").textContent = `${formatTime(
    dataset.time.start,
    dataset.time.kind,
  )} → ${formatTime(dataset.time.end, dataset.time.kind)}`;

  const droppedColumns = dataset.dropped_columns_string || [];
  if (droppedColumns.length) {
    const preview = droppedColumns.slice(0, 5).join(", ");
    const extra =
      droppedColumns.length > 5
        ? ` y ${droppedColumns.length - 5} más`
        : "";
    el("dropped-columns").textContent = `Columnas string eliminadas (${droppedColumns.length}): ${preview}${extra}`;
  } else {
    el("dropped-columns").textContent = "No se eliminaron columnas string.";
  }
}

function updateSelectionUi() {
  const total = state.dataset ? state.dataset.variables.length : 0;
  el("var-count").textContent = `${formatCount(state.selected.size)} de ${formatCount(
    total,
  )} seleccionadas`;
  plotButton.disabled =
    !state.dataset || state.selected.size === 0 || state.plotting;
  if (state.plotting) {
    plotButton.textContent = "Generando…";
  } else if (state.chartReady) {
    plotButton.textContent = "Actualizar gráfica";
  } else {
    plotButton.textContent = "Generar gráfica";
  }
  syncTabs();
}

function markChartStale() {
  if (state.chartReady) {
    chartMeta.textContent = "Cambios pendientes · pulsa Actualizar gráfica";
  }
}

function variableLabel(variable) {
  const label = state.labels.get(variable.id) || {};
  return {
    name: label.name || variable.name,
    unit: label.unit || "",
    renamed: Boolean(label.name) && label.name !== variable.name,
  };
}

function formatBound(value) {
  return Number(value).toString();
}

/** Legend suffix for a rescaled variable; mirrors plotting.scale_label. */
function scaleText(scale) {
  return scale ? `esc. ${formatBound(scale.min)}…${formatBound(scale.max)}` : "";
}

/** Active scale ({min, max}) of a variable, or null when scaling is off. */
function activeScale(id) {
  const scale = state.scales.get(id);
  return scale && scale.enabled ? { min: scale.min, max: scale.max } : null;
}

function legendText(name, unit, suffix = "") {
  const text = unit ? `${name} [${unit}]` : name;
  return suffix ? `${text} · ${suffix}` : text;
}

function renderVariables() {
  const fragment = document.createDocumentFragment();

  state.dataset.variables.forEach((variable) => {
    const label = variableLabel(variable);
    const row = document.createElement("div");
    row.className = "variable-row";

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.id = `check-${variable.id}`;
    checkbox.checked = state.selected.has(variable.id);
    checkbox.setAttribute("aria-label", `Graficar ${label.name}`);
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) {
        state.selected.add(variable.id);
      } else {
        state.selected.delete(variable.id);
      }
      updateSelectionUi();
      markChartStale();
    });

    const colorInput = document.createElement("input");
    colorInput.type = "color";
    colorInput.value = state.colors.get(variable.id) || "#1f77b4";
    colorInput.setAttribute("aria-label", `Color de ${label.name}`);
    colorInput.addEventListener("input", () => {
      state.colors.set(variable.id, colorInput.value);
      markChartStale();
    });

    const open = document.createElement("button");
    open.type = "button";
    open.className = "variable-open";
    open.setAttribute("aria-haspopup", "dialog");
    open.title = `Opciones de ${label.name}`;
    open.addEventListener("click", () => openVariableDialog(variable.id));

    const info = document.createElement("span");
    info.className = "variable-info";

    const nameLine = document.createElement("span");
    nameLine.className = "variable-name-line";
    const name = document.createElement("span");
    name.className = "variable-name";
    name.textContent = label.name;
    nameLine.append(name);
    if (label.unit) {
      const unit = document.createElement("span");
      unit.className = "unit-badge";
      unit.textContent = label.unit;
      nameLine.append(unit);
    }
    const scale = activeScale(variable.id);
    if (scale) {
      const badge = document.createElement("span");
      badge.className = "scale-badge";
      badge.textContent = scaleText(scale);
      badge.title = "Variable escalada";
      nameLine.append(badge);
    }

    const meta = document.createElement("span");
    meta.className = "variable-meta";
    if (label.renamed) {
      const original = document.createElement("span");
      original.className = "variable-original";
      original.textContent = `CSV: ${variable.name}`;
      meta.append(original);
    }
    const range = document.createElement("span");
    range.textContent = `${formatNumber(variable.min)} … ${formatNumber(
      variable.max,
    )}`;
    meta.append(range);
    if (variable.is_constant) {
      const constant = document.createElement("span");
      constant.className = "constant-badge";
      constant.textContent = "constante";
      meta.append(constant);
    }

    const editIcon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    editIcon.setAttribute("viewBox", "0 0 24 24");
    editIcon.setAttribute("aria-hidden", "true");
    editIcon.classList.add("edit-icon");
    const editPath = document.createElementNS("http://www.w3.org/2000/svg", "path");
    editPath.setAttribute("d", "M4 20h4L19 9l-4-4L4 16v4Zm9-13 4 4");
    editIcon.append(editPath);

    info.append(nameLine, meta);
    open.append(info, editIcon);
    row.append(checkbox, colorInput, open);
    fragment.append(row);
  });

  variablesList.replaceChildren(fragment);
  updateSelectionUi();
}

function findVariable(id) {
  return state.dataset?.variables.find((variable) => variable.id === id) || null;
}

function updateVariablePreview() {
  const variable = findVariable(state.editingId);
  if (!variable) {
    return;
  }
  const name = variableNameInput.value.trim() || variable.name;
  const unit = variableUnitInput.value.trim();
  const draft = readScaleInputs();
  const suffix = draft.enabled && !draft.error ? scaleText(draft) : "";
  variablePreviewText.textContent = legendText(name, unit, suffix);
  variablePreviewSwatch.style.backgroundColor = variableColorInput.value;
}

function openVariableDialog(id) {
  const variable = findVariable(id);
  if (!variable) {
    return;
  }
  const label = variableLabel(variable);
  state.editingId = id;
  variableDialogTitle.textContent = label.name;
  variableOriginalName.textContent = variable.name;
  variableNameInput.value = label.name;
  variableNameInput.placeholder = variable.name;
  variableUnitInput.value = label.unit;
  variableColorInput.value = state.colors.get(id) || variable.color;
  const scale = state.scales.get(id);
  variableScaleToggle.checked = Boolean(scale && scale.enabled);
  variableScaleMin.value = String(scale ? scale.min : variable.min);
  variableScaleMax.value = String(scale ? scale.max : variable.max);
  variableScaleReal.textContent = variable.is_constant
    ? `Variable constante (${formatNumber(variable.min)}): se dibuja en el mínimo.`
    : `Rango real ${formatNumber(variable.min)} … ${formatNumber(
        variable.max,
      )} → mínimo … máximo.`;
  showScaleError("");
  syncScaleInputs();
  updateVariablePreview();
  variableDialog.showModal();
  variableNameInput.focus();
  variableNameInput.select();
}

function syncScaleInputs() {
  const enabled = variableScaleToggle.checked;
  variableScaleMin.disabled = !enabled;
  variableScaleMax.disabled = !enabled;
  if (!enabled) {
    showScaleError("");
  }
}

function showScaleError(message) {
  variableScaleError.textContent = message;
  variableScaleError.hidden = !message;
}

/** Read and validate the scale inputs of the dialog. */
function readScaleInputs() {
  const enabled = variableScaleToggle.checked;
  const rawMin = variableScaleMin.value.trim();
  const rawMax = variableScaleMax.value.trim();
  const min = Number(rawMin);
  const max = Number(rawMax);
  let error = "";
  if (enabled) {
    if (rawMin === "" || rawMax === "" || !Number.isFinite(min) || !Number.isFinite(max)) {
      error = "Escribe un mínimo y un máximo numéricos.";
    } else if (min >= max) {
      error = "El mínimo debe ser menor que el máximo.";
    }
  }
  return { enabled, min, max, error };
}

function sameScale(a, b) {
  if (!a || !b) {
    return a === b;
  }
  return a.min === b.min && a.max === b.max;
}

function closeVariableDialog() {
  state.editingId = null;
  if (variableDialog.open) {
    variableDialog.close();
  }
}

function acceptVariableDialog() {
  const variable = findVariable(state.editingId);
  if (!variable) {
    closeVariableDialog();
    return;
  }
  const name = variableNameInput.value.trim();
  const unit = variableUnitInput.value.trim();
  if (unit.length > MAX_UNIT_LENGTH) {
    showToast("Las unidades admiten un máximo de 4 caracteres.");
    variableUnitInput.focus();
    return;
  }

  const draftScale = readScaleInputs();
  if (draftScale.error) {
    showScaleError(draftScale.error);
    const minIsValid = Number.isFinite(draftScale.min) && variableScaleMin.value !== "";
    (minIsValid ? variableScaleMax : variableScaleMin).focus();
    return;
  }

  const previous = variableLabel(variable);
  const previousColor = state.colors.get(variable.id);
  const previousScale = activeScale(variable.id);
  const next = {
    name: name && name !== variable.name ? name : "",
    unit,
  };
  if (next.name || next.unit) {
    state.labels.set(variable.id, next);
  } else {
    state.labels.delete(variable.id);
  }
  state.colors.set(variable.id, variableColorInput.value);
  if (draftScale.enabled) {
    state.scales.set(variable.id, {
      enabled: true,
      min: draftScale.min,
      max: draftScale.max,
    });
  } else if (state.scales.has(variable.id)) {
    // Keep the typed bounds so turning the switch back on restores them.
    state.scales.get(variable.id).enabled = false;
  }
  const scaleChanged = !sameScale(previousScale, activeScale(variable.id));

  const current = variableLabel(variable);
  const labelChanged =
    current.name !== previous.name || current.unit !== previous.unit;
  const colorChanged = previousColor !== variableColorInput.value;
  closeVariableDialog();
  if (labelChanged || colorChanged || scaleChanged) {
    renderVariables();
    applyVariableToCharts(variable);
  }
}

/** Shared Y axis title: "Valor [u]" only when every trace uses the same unit. */
function yAxisTitle(traces) {
  const units = new Set(traces.map((trace) => (trace.meta && trace.meta[1]) || ""));
  if (units.size === 1) {
    const [unit] = units;
    if (unit) {
      return `Valor [${unit}]`;
    }
  }
  return "Valor";
}

const TYPED_ARRAYS = {
  f8: Float64Array,
  f4: Float32Array,
  i1: Int8Array,
  u1: Uint8Array,
  i2: Int16Array,
  u2: Uint16Array,
  i4: Int32Array,
  u4: Uint32Array,
};

/** Plotly arrays may arrive as base64 typed arrays ({dtype, bdata}). */
function decodeArray(value) {
  if (value && typeof value === "object" && "bdata" in value) {
    const binary = atob(value.bdata);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) {
      bytes[i] = binary.charCodeAt(i);
    }
    const ArrayType = TYPED_ARRAYS[value.dtype] || Float64Array;
    return Array.from(new ArrayType(bytes.buffer));
  }
  return Array.from(value || []);
}

/** Same linear mapping as plotting.rescale in the backend. */
function rescaleValues(values, realMin, realMax, scale) {
  const span = realMax - realMin;
  if (span === 0) {
    return values.map(() => scale.min);
  }
  const factor = (scale.max - scale.min) / span;
  return values.map((value) => scale.min + (value - realMin) * factor);
}

const REAL_HOVER = "<br>Real: %{customdata:.6g}";

/** Escape text for Plotly's pseudo-HTML (annotation text is parsed). */
function plotlyText(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

/**
 * Min/max box in the right margin, under the legend and aligned with it,
 * at the bottom of the plot. Each line is identified only by the trace color
 * (the legend above already names it). Values follow what the chart shows:
 * scaled when the variable is scaled (the mapping is linear and increasing,
 * so the extremes are the rescaled real extremes).
 */
function statsAnnotation(
  theme,
  position,
  figure = state.figure,
  plottedStats = state.plottedStats,
) {
  const colors = PLOT_THEMES[theme] || PLOT_THEMES.light;
  const lines = ["<b>Mínimos y máximos</b>"];
  plottedStats.forEach((stats, index) => {
    const trace = figure.data[index];
    const variable = findVariable(stats.id);
    if (!trace || !variable) {
      return;
    }
    let [low, high] = [stats.rangeMin, stats.rangeMax];
    if (stats.scale) {
      [low, high] = rescaleValues([low, high], variable.min, variable.max, stats.scale);
    }
    const meta = trace.meta || [];
    const unit = meta[1] ? ` ${meta[1]}` : "";
    const color = (trace.line && trace.line.color) || variable.color;
    lines.push(
      `<span style="color:${color}">━━</span> ` +
        `mín ${plotlyText(formatNumber(low) + unit)} · ` +
        `máx ${plotlyText(formatNumber(high) + unit)}`,
    );
  });
  return {
    name: "stats",
    text: lines.join("<br>"),
    xref: "paper",
    yref: "paper",
    // Same x as the legend (layout.legend.x = 1.01, anchored left).
    x: position ? position.x : 1.01,
    y: position ? position.y : 0,
    xanchor: "left",
    yanchor: "bottom",
    align: "left",
    showarrow: false,
    font: { size: 10, color: colors.ink },
    bgcolor: colors.statsBg,
    bordercolor: colors.line,
    borderwidth: 1,
    borderpad: 6,
  };
}

/** Where the user dragged the box on a chart, if anywhere. */
function statsPosition(chartDiv) {
  const current = chartDiv && chartDiv.layout && chartDiv.layout.annotations;
  const box = current && current.find((item) => item.name === "stats");
  return box ? { x: box.x, y: box.y } : null;
}

const MAX_PINS = 20;

/** Time of a pinned point, formatted like the chart hover. */
function pinTimeText(x) {
  const kind = state.dataset && state.dataset.time.kind;
  if (kind === "elapsed") {
    return `${Number(x).toFixed(3)} s`;
  }
  const text = String(x);
  if (kind === "clock") {
    // Clock values are plotted as dates on 1970-01-01 (see plotting._x_values).
    const millis = Date.parse(`${text.replace(" ", "T")}Z`);
    if (Number.isFinite(millis)) {
      const total = millis / 1000;
      const minutes = Math.floor(total / 60);
      const seconds = (total - minutes * 60).toFixed(3).padStart(6, "0");
      return `${String(minutes).padStart(2, "0")}:${seconds}`;
    }
  }
  return text;
}

/**
 * Overlays for the pinned points: a dotted vertical line at each one and a
 * label with the time and every variable's value (scaled and real when the
 * variable is scaled), identified by its color like the min/max box.
 */
function pinOverlays(theme, figure = state.figure) {
  const colors = PLOT_THEMES[theme] || PLOT_THEMES.light;
  const annotations = [];
  const shapes = [];
  if (!state.pins.length || !figure.data.length) {
    return { annotations, shapes };
  }
  const xs = decodeArray(figure.data[0].x);
  const series = figure.data.map((trace) => ({
    y: decodeArray(trace.y),
    real: trace.customdata ? decodeArray(trace.customdata) : null,
    unit: trace.meta && trace.meta[1] ? ` ${trace.meta[1]}` : "",
    color: (trace.line && trace.line.color) || colors.ink,
  }));
  state.pins.forEach((pointIndex) => {
    if (pointIndex >= xs.length) {
      return;
    }
    const x = xs[pointIndex];
    const lines = [`<b>${plotlyText(pinTimeText(x))}</b>`];
    for (const item of series) {
      let line =
        `<span style="color:${item.color}">━━</span> ` +
        plotlyText(formatNumber(item.y[pointIndex]) + item.unit);
      if (item.real) {
        line += ` (real ${plotlyText(formatNumber(item.real[pointIndex]))})`;
      }
      lines.push(line);
    }
    // Labels in the right third open to the left so they stay in the plot.
    const onRight = xs.length > 1 && pointIndex / (xs.length - 1) > 0.66;
    annotations.push({
      name: `pin-${pointIndex}`,
      text: lines.join("<br>"),
      xref: "x",
      yref: "paper",
      x,
      y: 1,
      xanchor: onRight ? "right" : "left",
      yanchor: "top",
      xshift: onRight ? -6 : 6,
      align: "left",
      showarrow: false,
      captureevents: true,
      font: { size: 10, color: colors.ink },
      bgcolor: colors.statsBg,
      bordercolor: colors.line,
      borderwidth: 1,
      borderpad: 5,
    });
    shapes.push({
      type: "line",
      xref: "x",
      yref: "paper",
      x0: x,
      x1: x,
      y0: 0,
      y1: 1,
      opacity: 0.7,
      line: { color: colors.ink, width: 1, dash: "dot" },
    });
  });
  return { annotations, shapes };
}

/** Layout keys for the min/max box and the pinned points of one chart. */
function overlayLayout(theme, chartDiv) {
  const pins = pinOverlays(theme);
  return {
    annotations: [statsAnnotation(theme, statsPosition(chartDiv)), ...pins.annotations],
    shapes: pins.shapes,
  };
}

/** Rebuild the min/max box and pinned points on every open chart. */
function refreshOverlays() {
  syncPinButton();
  if (!state.chartReady || !state.figure || typeof Plotly === "undefined") {
    return;
  }
  const theme = currentTheme();
  const update = overlayLayout(theme, chartElement);
  Object.assign(state.figure.layout, update);
  Plotly.relayout(chartElement, update);
  const win = state.chartWindow;
  if (win && !win.closed && win.Plotly) {
    const chartDiv = win.document.getElementById("standalone-chart");
    if (chartDiv && chartDiv.data) {
      win.Plotly.relayout(chartDiv, overlayLayout(theme, chartDiv));
    }
  }
}

function syncPinButton() {
  clearPinsButton.classList.toggle("hidden", state.pins.length === 0);
}

/** Click on a point: pin it, or unpin it if it was already pinned. */
function togglePin(pointIndex) {
  if (!Number.isInteger(pointIndex) || !state.chartReady) {
    return;
  }
  const existing = state.pins.indexOf(pointIndex);
  if (existing >= 0) {
    state.pins.splice(existing, 1);
  } else {
    state.pins.push(pointIndex);
    if (state.pins.length > MAX_PINS) {
      state.pins.shift();
    }
  }
  refreshOverlays();
}

/** Plotly click handlers: pin on a point, unpin by clicking its label. */
function bindPinEvents(chartDiv) {
  if (typeof chartDiv.removeAllListeners === "function") {
    chartDiv.removeAllListeners("plotly_click");
    chartDiv.removeAllListeners("plotly_clickannotation");
  }
  chartDiv.on("plotly_click", (event) => {
    const point = event && event.points && event.points[0];
    if (point) {
      togglePin(point.pointIndex ?? point.pointNumber);
    }
  });
  chartDiv.on("plotly_clickannotation", (event) => {
    const name = (event && event.annotation && event.annotation.name) || "";
    // Plotly may report one click on an editable annotation twice, so
    // remove by point (idempotent) rather than by position in the list.
    if (name.startsWith("pin-")) {
      const pointIndex = Number(name.slice(4));
      if (state.pins.includes(pointIndex)) {
        state.pins = state.pins.filter((pin) => pin !== pointIndex);
        refreshOverlays();
      }
    }
  });
}

/**
 * Apply the accepted dialog options (name, unit, color and scale) to an
 * already plotted trace in place, without asking the backend for the figure
 * again. Real values come from `customdata` (scaled trace) or `y`.
 */
function applyVariableToCharts(variable) {
  const index = state.plottedIds.indexOf(variable.id);
  if (!state.chartReady || !state.figure || index < 0) {
    return;
  }
  const trace = state.figure.data[index];
  const label = variableLabel(variable);
  const scale = activeScale(variable.id);
  const suffix = scaleText(scale);
  const color = state.colors.get(variable.id) || variable.color;

  const wasScaled = trace.customdata !== undefined && trace.customdata !== null;
  const realValues = decodeArray(wasScaled ? trace.customdata : trace.y);
  const yValues = scale
    ? rescaleValues(realValues, variable.min, variable.max, scale)
    : realValues;
  const baseHover = String(trace.hovertemplate || "")
    .replace("<extra></extra>", "")
    .replace(REAL_HOVER, "");
  const hovertemplate = `${baseHover}${scale ? REAL_HOVER : ""}<extra></extra>`;
  const legend = legendText(label.name, label.unit, suffix);

  Object.assign(trace, {
    name: legend,
    meta: [label.name, label.unit, suffix],
    y: yValues,
    customdata: scale ? realValues : null,
    hovertemplate,
  });
  trace.line = { ...(trace.line || {}), color };
  const title = yAxisTitle(state.figure.data);
  const layout = state.figure.layout;
  layout.yaxis = layout.yaxis || {};
  layout.yaxis.title = { ...(layout.yaxis.title || {}), text: title };

  const traceUpdate = {
    name: [legend],
    meta: [[label.name, label.unit, suffix]],
    y: [yValues],
    customdata: [scale ? realValues : null],
    hovertemplate: [hovertemplate],
    "line.color": [color],
  };
  // Autorange so the Y axis follows the new (scaled or real) values.
  const layoutUpdate = { "yaxis.title.text": title, "yaxis.autorange": true };
  if (typeof Plotly !== "undefined") {
    Plotly.update(chartElement, traceUpdate, layoutUpdate, [index]);
  }
  const win = state.chartWindow;
  if (win && !win.closed && win.Plotly) {
    const chartDiv = win.document.getElementById("standalone-chart");
    if (chartDiv && chartDiv.data) {
      win.Plotly.update(chartDiv, traceUpdate, layoutUpdate, [index]);
    }
  }
  state.plottedStats[index].scale = scale;
  refreshOverlays();
}

function updateRangeLabels() {
  const dataset = state.dataset;
  if (!dataset) {
    return;
  }
  const [start, end] = state.range;
  const values = dataset.time.values || [];
  const startValue = values[start] ?? dataset.time.start;
  const endValue = values[end] ?? dataset.time.end;
  el("range-start").textContent = formatTime(startValue, dataset.time.kind);
  el("range-end").textContent = formatTime(endValue, dataset.time.kind);
  el("range-count").textContent = `${formatCount(
    end - start + 1,
  )} de ${formatCount(dataset.rows_clean)} filas`;
}

function createRangeSlider() {
  const container = el("range-slider");
  if (state.slider) {
    state.slider.destroy();
    state.slider = null;
  }
  container.replaceChildren();

  const total = state.dataset.rows_clean;
  if (total <= 1) {
    state.range = [0, 0];
    container.textContent = "El dataset tiene una sola fila.";
    updateRangeLabels();
    return;
  }

  if (typeof noUiSlider === "undefined") {
    showToast("No se pudo cargar el control de rango.");
    return;
  }

  noUiSlider.create(container, {
    start: [0, total - 1],
    connect: true,
    step: 1,
    range: { min: 0, max: total - 1 },
    tooltips: false,
    behaviour: "drag-tap",
  });

  state.slider = container.noUiSlider;
  state.range = [0, total - 1];

  state.slider.on("update", (values) => {
    state.range = [
      Math.round(Number(values[0])),
      Math.round(Number(values[1])),
    ];
    updateRangeLabels();
    markChartStale();
  });

  updateRangeLabels();
}

function resetChart() {
  state.chartReady = false;
  state.figure = null;
  state.plottedIds = [];
  state.plottedStats = [];
  state.pins = [];
  syncPinButton();
  if (typeof Plotly !== "undefined") {
    Plotly.purge(chartElement);
  }
  chartWrap.classList.add("hidden");
  chartEmpty.classList.remove("hidden");
  chartLoading.classList.add("hidden");
  chartMeta.textContent = "";
  setView("config");
  updateSelectionUi();
}

function applyDataset(dataset) {
  state.dataset = dataset;
  state.selected = new Set(
    dataset.variables.slice(0, 3).map((variable) => variable.id),
  );
  state.colors = new Map(
    dataset.variables.map((variable) => [variable.id, variable.color]),
  );
  state.labels = new Map();
  state.scales = new Map();
  closeVariableDialog();

  renderSummary();
  renderVariables();
  createRangeSlider();
  resetChart();

  summary.classList.remove("hidden");
  configPanel.classList.remove("hidden");
  setUploadStatus(
    `Archivo cargado y limpio: ${dataset.filename} · ${formatCount(
      dataset.rows_clean,
    )} filas listas.`,
  );
  viewTabs.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function uploadFile(file) {
  if (!file) {
    return;
  }
  if (!file.name.toLowerCase().endsWith(".csv")) {
    setUploadStatus("Solo se aceptan archivos .csv.", true);
    showToast("Selecciona un archivo con extensión .csv.");
    return;
  }
  if (state.uploading) {
    return;
  }

  state.uploading = true;
  dropZone.classList.add("busy");
  setUploadStatus("Cargando, detectando formato y limpiando datos…");

  try {
    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch("/api/datasets", {
      method: "POST",
      body: formData,
    });
    const dataset = await readResponse(response);
    applyDataset(dataset);
  } catch (error) {
    setUploadStatus(error.message, true);
    showToast(error.message);
  } finally {
    state.uploading = false;
    dropZone.classList.remove("busy");
    fileInput.value = "";
  }
}

function nextFrame() {
  return new Promise((resolve) => {
    window.requestAnimationFrame(() => window.requestAnimationFrame(resolve));
  });
}

async function generatePlot() {
  if (!state.dataset || state.selected.size === 0 || state.plotting) {
    return;
  }

  const hadChart = state.chartReady;
  const dataset = state.dataset;
  const payload = {
    variables: [...state.selected].map((id) => {
      const label = state.labels.get(id) || {};
      return {
        id,
        color: state.colors.get(id),
        name: label.name || null,
        unit: label.unit || null,
        scale: activeScale(id),
      };
    }),
    range: {
      start_index: state.range[0],
      end_index: state.range[1],
    },
  };

  state.plotting = true;
  updateSelectionUi();
  chartLoading.classList.remove("hidden");
  chartWrap.classList.remove("hidden");
  chartEmpty.classList.add("hidden");
  setView("chart");

  try {
    const response = await fetch(
      `/api/datasets/${encodeURIComponent(dataset.dataset_id)}/plot`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
    );
    const result = await readResponse(response);

    if (typeof Plotly === "undefined") {
      throw new Error("No se pudo cargar Plotly.");
    }

    await nextFrame();
    result.figure.layout = result.figure.layout || {};
    result.figure.layout.height = Math.max(400, Math.round(chartElement.clientHeight));
    delete result.figure.layout.width;

    const plottedStats = result.variables.map((variable) => ({
      id: variable.id,
      rangeMin: variable.range_min,
      rangeMax: variable.range_max,
      scale: variable.scale || null,
    }));
    // A new figure may cover another range: pinned points no longer apply.
    state.pins = [];
    result.figure.layout.annotations = [
      statsAnnotation(
        currentTheme(),
        statsPosition(chartElement),
        result.figure,
        plottedStats,
      ),
    ];
    result.figure.layout.shapes = [];

    const safeFilename = dataset.filename.replace(/[^\w.-]+/g, "_");
    await Plotly.react(
      chartElement,
      result.figure.data,
      themedLayout(result.figure.layout, currentTheme()),
      {
        responsive: true,
        displaylogo: false,
        // The min/max box and pin labels can be dragged if they hide data.
        edits: { annotationPosition: true },
        modeBarButtonsToRemove: ["lasso2d", "select2d"],
        toImageButtonOptions: {
          format: "png",
          filename: `grafica_${safeFilename}`,
          height: 900,
          width: 1600,
          scale: 1,
        },
      },
    );

    state.chartReady = true;
    state.figure = result.figure;
    state.plottedIds = result.variables.map((variable) => variable.id);
    state.plottedStats = plottedStats;
    bindPinEvents(chartElement);
    syncPinButton();
    chartMeta.textContent = `${formatCount(
      result.rows_plotted,
    )} filas · ${formatCount(result.variables.length)} variables`;
    updateSelectionUi();
  } catch (error) {
    showToast(error.message);
    if (!hadChart) {
      chartWrap.classList.add("hidden");
      chartEmpty.classList.remove("hidden");
      chartMeta.textContent = "";
      setView("config");
    }
  } finally {
    state.plotting = false;
    chartLoading.classList.add("hidden");
    updateSelectionUi();
  }
}

function openChartWindow() {
  if (!state.chartReady || !state.figure || !state.dataset) {
    showToast("Genera una gráfica antes de abrirla en otra ventana.");
    return;
  }

  const win = window.open(
    "",
    "graficador_rockwell_chart",
    "popup=yes,width=1440,height=920",
  );
  if (!win) {
    showToast(
      "El navegador bloqueó la ventana emergente. Permite las ventanas para este sitio.",
    );
    return;
  }

  state.chartWindow = win;
  const doc = win.document;
  doc.documentElement.dataset.theme = currentTheme();
  doc.head.replaceChildren();
  doc.body.replaceChildren();
  doc.body.className = "chart-window";

  const charset = doc.createElement("meta");
  charset.setAttribute("charset", "utf-8");
  const viewport = doc.createElement("meta");
  viewport.setAttribute("name", "viewport");
  viewport.setAttribute("content", "width=device-width, initial-scale=1");
  const docTitle = doc.createElement("title");
  docTitle.textContent = `Gráfica · ${state.dataset.filename}`;
  const styles = doc.createElement("link");
  styles.rel = "stylesheet";
  styles.href = "/static/css/chart-window.css";
  doc.head.append(charset, viewport, docTitle, styles);

  const header = doc.createElement("header");
  header.className = "chart-window-header";
  const titleWrap = doc.createElement("div");
  const eyebrow = doc.createElement("p");
  eyebrow.className = "eyebrow";
  eyebrow.textContent = "Graficador Rockwell";
  const title = doc.createElement("h1");
  title.textContent = state.dataset.filename;
  const subtitle = doc.createElement("p");
  subtitle.className = "chart-window-meta";
  subtitle.textContent = chartMeta.textContent;
  titleWrap.append(eyebrow, title, subtitle);
  const closeButton = doc.createElement("button");
  closeButton.type = "button";
  closeButton.className = "ghost";
  closeButton.textContent = "Cerrar ventana";
  closeButton.addEventListener("click", () => win.close());
  header.append(titleWrap, closeButton);

  const chartDiv = doc.createElement("div");
  chartDiv.id = "standalone-chart";
  chartDiv.className = "standalone-chart";
  doc.body.append(header, chartDiv);

  const render = () => {
    if (!state.figure || !win.Plotly) {
      chartDiv.textContent = "No se pudo cargar Plotly en la ventana.";
      return;
    }
    const safeFilename = state.dataset.filename.replace(/[^\w.-]+/g, "_");
    const layout = {
      ...themedLayout(state.figure.layout, currentTheme()),
      height: Math.max(400, win.innerHeight - 110),
      autosize: true,
      uirevision: "standalone",
    };
    win.Plotly.newPlot(chartDiv, state.figure.data, layout, {
      responsive: true,
      displaylogo: false,
      // The min/max box and pin labels can be dragged if they hide data.
      edits: { annotationPosition: true },
      modeBarButtonsToRemove: ["lasso2d", "select2d"],
      toImageButtonOptions: {
        format: "png",
        filename: `grafica_${safeFilename}`,
        height: 900,
        width: 1600,
        scale: 1,
      },
    });
    bindPinEvents(chartDiv);
    win.addEventListener("resize", () => {
      win.Plotly.Plots.resize(chartDiv);
    });
  };

  const script = doc.createElement("script");
  script.src = "/static/vendor/plotly.min.js";
  script.addEventListener("load", render);
  script.addEventListener("error", () => {
    chartDiv.textContent = "No se pudo cargar Plotly en la ventana.";
  });
  doc.head.append(script);
  win.focus();
}

dropZone.addEventListener("click", () => fileInput.click());
dropZone.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    fileInput.click();
  }
});
dropZone.addEventListener("dragover", (event) => {
  event.preventDefault();
  dropZone.classList.add("dragover");
});
dropZone.addEventListener("dragleave", () => {
  dropZone.classList.remove("dragover");
});
dropZone.addEventListener("drop", (event) => {
  event.preventDefault();
  dropZone.classList.remove("dragover");
  const file = event.dataTransfer.files[0];
  uploadFile(file);
});
fileInput.addEventListener("change", () => {
  uploadFile(fileInput.files[0]);
});

document.addEventListener("dragover", (event) => event.preventDefault());
document.addEventListener("drop", (event) => {
  if (!dropZone.contains(event.target)) {
    event.preventDefault();
  }
});

el("select-all").addEventListener("click", () => {
  if (!state.dataset) {
    return;
  }
  state.selected = new Set(
    state.dataset.variables.map((variable) => variable.id),
  );
  renderVariables();
  markChartStale();
});

el("select-none").addEventListener("click", () => {
  state.selected.clear();
  renderVariables();
  markChartStale();
});

el("reset-colors").addEventListener("click", () => {
  if (!state.dataset) {
    return;
  }
  state.colors = new Map(
    state.dataset.variables.map((variable) => [variable.id, variable.color]),
  );
  renderVariables();
  markChartStale();
});

tabConfig.addEventListener("click", () => setView("config"));
tabChart.addEventListener("click", () => {
  if (state.chartReady) {
    setView("chart");
  }
});
backToConfig.addEventListener("click", () => setView("config"));
openWindowButton.addEventListener("click", openChartWindow);
themeToggle.addEventListener("click", () => window.GrTheme?.toggle());
variableForm.addEventListener("submit", (event) => {
  event.preventDefault();
  acceptVariableDialog();
});
el("variable-cancel").addEventListener("click", closeVariableDialog);
el("variable-name-reset").addEventListener("click", () => {
  const variable = findVariable(state.editingId);
  if (variable) {
    variableNameInput.value = variable.name;
    updateVariablePreview();
    variableNameInput.focus();
  }
});
variableDialog.addEventListener("cancel", () => {
  state.editingId = null;
});
variableDialog.addEventListener("click", (event) => {
  // Click on the backdrop (outside the form) behaves like "Cancelar".
  if (event.target === variableDialog) {
    closeVariableDialog();
  }
});
variableScaleToggle.addEventListener("change", () => {
  syncScaleInputs();
  updateVariablePreview();
  if (variableScaleToggle.checked) {
    variableScaleMin.focus();
  }
});
for (const input of [
  variableNameInput,
  variableUnitInput,
  variableColorInput,
  variableScaleMin,
  variableScaleMax,
]) {
  input.addEventListener("input", () => {
    if (input === variableScaleMin || input === variableScaleMax) {
      showScaleError("");
    }
    updateVariablePreview();
  });
}
window.GrTheme?.onChange(applyThemeToCharts);
syncThemeToggle(currentTheme());
updatePlotButton.addEventListener("click", generatePlot);
clearPinsButton.addEventListener("click", () => {
  state.pins = [];
  refreshOverlays();
});
plotButton.addEventListener("click", generatePlot);

let resizeTimer = null;
window.addEventListener("resize", () => {
  if (
    !state.chartReady ||
    state.view !== "chart" ||
    typeof Plotly === "undefined"
  ) {
    return;
  }
  window.clearTimeout(resizeTimer);
  resizeTimer = window.setTimeout(() => {
    Plotly.Plots.resize(chartElement);
  }, 120);
});

checkHealth();
