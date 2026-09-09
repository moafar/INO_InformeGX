"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

function fakeControl(id, value, type = "text", checked = false, origin = "MANUAL") {
  const listeners = {};
  const field = { dataset: { origin, edited: "false" } };
  return {
    id,
    name: id,
    value,
    type,
    checked,
    dataset: { originalValue: type === "checkbox" ? String(checked) : value },
    listeners,
    addEventListener(event, listener) { listeners[event] = listener; },
    closest() { return field; },
    field,
  };
}

const restVdvt = fakeControl("gx_rest_vd_per_vt_meas", "25", "text", false, "GX");
restVdvt.dataset.vdvtMeasuredValue = "25";
restVdvt.dataset.vdvtEstimatedValue = "30";
const peakVdvt = fakeControl("gx_vo2_max_vd_per_vt_meas", "18", "text", false, "GX");
peakVdvt.dataset.vdvtMeasuredValue = "18";
peakVdvt.dataset.vdvtEstimatedValue = "22";

const controls = [
  fakeControl("patient_first_name", "Ana", "text", false, "GX"),
  fakeControl("patient_middle_name", "", "text", false, "GX"),
  fakeControl("patient_last_name", "Prueba", "text", false, "GX"),
  fakeControl("conclusiones_definitivas", "<img src=x onerror=alert(1)>", "textarea"),
  fakeControl("gx_vo2_max_time_min", ""),
  fakeControl("reposo_inicial_min", "3"),
  fakeControl("tiempo_sin_carga_min", "3"),
  fakeControl("medicion_gases", "", "checkbox", true, "GX"),
  restVdvt,
  peakVdvt,
  fakeControl("gx_vo2_max_vo2_per_hr_ml_per_beat", "11.2", "text", false, "GX"),
  fakeControl("umbral_anaerobio_alcanzado", "NO"),
  fakeControl("gx_at_ex_time_min", "", "text", false, "GX"),
  fakeControl("porc_vo2_at_predicho", "", "text", false, "GX"),
  fakeControl("gx_at_ve_per_vco2", "99", "text", false, "GX"),
  fakeControl("gx_at_ve_per_vo2", "88", "text", false, "GX"),
  fakeControl("gx_rest_ve_btps_l_per_min", "18", "text", false, "GX"),
  fakeControl("gx_vo2_max_ve_btps_l_per_min", "55", "text", false, "GX"),
  fakeControl("gx_vo2_max_ve_per_mvv_pct", "58", "text", false, "GX"),
  fakeControl("comentario_petco2", "", "textarea"),
];
const byId = Object.fromEntries(controls.map((control) => [control.id, control]));
const textTargets = [
  "sticky-patient-name", "sticky-sex", "sticky-age", "sticky-id", "sticky-date",
  "report-patient-name", "report-patient-id", "report-age", "report-sex", "report-date",
  "filled-count", "total-count",
];
textTargets.forEach((id) => { byId[id] = { id, textContent: "" }; });
byId["vdvt-source-mode"] = { textContent: "medido por gases arteriales" };

const narrativeSlots = Array.from({ length: 6 }, () => [{ innerHTML: "" }, { innerHTML: "" }]);
const pageClasses = new Set();
const page = {
  classList: {
    toggle(name, enabled) {
      if (enabled) pageClasses.add(name);
      else pageClasses.delete(name);
    },
  },
};
const identity = { hidden: true };
byId["identity-grid"] = identity;

function fakeButton(id) {
  const listeners = {};
  const attributes = { "aria-pressed": "false" };
  return {
    id,
    disabled: false,
    listeners,
    textContent: "",
    addEventListener(event, listener) { listeners[event] = listener; },
    getAttribute(name) { return attributes[name]; },
    setAttribute(name, value) { attributes[name] = value; },
  };
}
const detailButton = fakeButton("toggle-detail");
byId["toggle-detail"] = detailButton;

const signButton = fakeButton("sign-report");
const cancelPdf = fakeButton("cancel-pdf");
const confirmPdf = fakeButton("confirm-pdf");
const pdfError = { textContent: "", hidden: true };
const pdfDialog = {
  open: false,
  attributes: {},
  showModal() { this.open = true; },
  close() { this.open = false; },
  setAttribute(name, value) { this.attributes[name] = value; },
  removeAttribute(name) { delete this.attributes[name]; },
};
byId["sign-report"] = signButton;
byId["cancel-pdf"] = cancelPdf;
byId["confirm-pdf"] = confirmPdf;
byId["pdf-dialog-error"] = pdfError;
byId["pdf-confirm-dialog"] = pdfDialog;

const form = {
  dataset: { signUrl: "/studies/drafts/sign", canSign: "true" },
  querySelectorAll(selector) {
    assert.strictEqual(selector, "[data-report-control][id][name]");
    return controls;
  },
};

const downloads = [];
const documentBody = {
  appendChild(element) { downloads.push(element); },
};

const document = {
  body: documentBody,
  createElement(tag) {
    assert.strictEqual(tag, "a");
    return {
      href: "",
      download: "",
      clicked: false,
      click() { this.clicked = true; },
      remove() {},
    };
  },
  getElementById(id) {
    if (id === "study-report-form") return form;
    return byId[id] || null;
  },
  querySelector(selector) {
    return selector === ".study-report-page" ? page : null;
  },
  querySelectorAll(selector) {
    if (selector === ".section-head") return [];
    const match = selector.match(/narrative=\"(\d)\"/);
    return match ? narrativeSlots[Number(match[1])] : [];
  },
};

const script = fs.readFileSync(
  path.join(__dirname, "..", "static", "study_report.js"),
  "utf8",
);
let fetchCalls = 0;
let resolveFetch;
const fakeFetch = () => {
  fetchCalls += 1;
  return new Promise((resolve) => { resolveFetch = resolve; });
};
class FakeFormData {
  constructor(receivedForm) { assert.strictEqual(receivedForm, form); }
}
const fakeUrl = {
  createObjectURL() { return "blob:synthetic-pdf"; },
  revokeObjectURL() {},
};
vm.runInNewContext(script, {
  document,
  window: { scrollTo() {}, location: { assign() {} } },
  fetch: fakeFetch,
  FormData: FakeFormData,
  URL: fakeUrl,
  console,
  String,
  Boolean,
  Array,
  Number,
});

assert.strictEqual(narrativeSlots[5][0].innerHTML, narrativeSlots[5][1].innerHTML);
assert.ok(narrativeSlots[5][0].innerHTML.includes("&lt;img src=x onerror=alert(1)&gt;"));
assert.ok(!narrativeSlots[5][0].innerHTML.includes("<img src=x"));
assert.ok(narrativeSlots[4][0].innerHTML.includes("no aplica"));
assert.ok(!narrativeSlots[4][0].innerHTML.includes("99"));
assert.ok(narrativeSlots[4][0].innerHTML.includes("58%"));
assert.ok(narrativeSlots[4][0].innerHTML.includes("La ventilación minuto (VE) fue de <em>18 L/min</em> en reposo y alcanzó <em>55 L/min (BTPS)</em> en ejercicio pico."));
assert.ok(narrativeSlots[4][0].innerHTML.includes("VD/VT) medido por gases arteriales en reposo fue de <em>25</em>"));
assert.ok(!narrativeSlots[4][0].innerHTML.includes("0.58"));
assert.ok(narrativeSlots[1][0].innerHTML.includes("Inicia con <em>3</em> minutos de reposo, luego <em>3</em> minutos de ejercicio sin carga y continúa con pedaleo con carga"));
assert.ok(!narrativeSlots[1][0].innerHTML.includes("La prueba tuvo una duración"));
assert.ok(narrativeSlots[3][0].innerHTML.includes("El oxígeno latido <em>11.2</em> (ml O₂/lat)"));
assert.strictEqual(byId["report-patient-name"].textContent, "Ana Prueba");
assert.strictEqual(byId["total-count"].textContent, String(controls.length));

byId["conclusiones_definitivas"].value = "Conclusión actualizada";
byId["umbral_anaerobio_alcanzado"].value = "SÍ";
byId["conclusiones_definitivas"].listeners.input();
assert.ok(narrativeSlots[5][0].innerHTML.includes("Conclusión actualizada"));
assert.strictEqual(narrativeSlots[5][0].innerHTML, narrativeSlots[5][1].innerHTML);
assert.ok(narrativeSlots[4][0].innerHTML.includes("99"));
assert.ok(!narrativeSlots[4][0].innerHTML.includes("no aplica"));

byId["reposo_inicial_min"].value = "4";
byId["reposo_inicial_min"].listeners.input();
assert.ok(narrativeSlots[1][0].innerHTML.includes("Inicia con <em>4</em> minutos de reposo"));

byId["gx_vo2_max_time_min"].value = "12";
byId["gx_vo2_max_time_min"].listeners.input();
assert.ok(narrativeSlots[1][0].innerHTML.includes("La prueba tuvo una duración de <em>12</em> minutos."));

byId["medicion_gases"].checked = false;
byId["medicion_gases"].listeners.input();
assert.strictEqual(restVdvt.value, "30");
assert.strictEqual(peakVdvt.value, "22");
assert.strictEqual(byId["vdvt-source-mode"].textContent, "estimado");
assert.ok(narrativeSlots[4][0].innerHTML.includes("VD/VT) estimado en reposo fue de <em>30</em>"));

byId["comentario_petco2"].value = "Comentario manual sobre PETCO₂.";
byId["comentario_petco2"].listeners.input();
assert.ok(narrativeSlots[4][0].innerHTML.includes("Comentario manual sobre PETCO₂."));

byId["gx_at_ex_time_min"].value = "06:26";
byId["porc_vo2_at_predicho"].value = "36";
byId["umbral_anaerobio_alcanzado"].value = "SÍ";
byId["gx_at_ex_time_min"].listeners.input();
assert.ok(narrativeSlots[3][0].innerHTML.includes("El umbral anaerobio fue alcanzado durante el ejercicio. Fue a los <em>06:26</em> min de inicio del ejercicio, <em>36%</em> de consumo de oxígeno máximo predicho."));

byId["umbral_anaerobio_alcanzado"].value = "Probable, no claramente definido";
byId["umbral_anaerobio_alcanzado"].listeners.input();
assert.ok(narrativeSlots[3][0].innerHTML.includes("El umbral anaerobio no se definió con claridad; se estima de forma probable a los <em>06:26</em> min de inicio del ejercicio, <em>36%</em> de consumo de oxígeno máximo predicho."));

byId["umbral_anaerobio_alcanzado"].value = "No alcanzado";
byId["umbral_anaerobio_alcanzado"].listeners.input();
assert.ok(narrativeSlots[3][0].innerHTML.includes("No se alcanzó el umbral anaerobio durante el ejercicio."));
assert.ok(!narrativeSlots[3][0].innerHTML.includes("06:26"));

byId["umbral_anaerobio_alcanzado"].value = "No evaluable";
byId["umbral_anaerobio_alcanzado"].listeners.input();
assert.ok(narrativeSlots[3][0].innerHTML.includes("El umbral anaerobio no fue evaluable."));
assert.ok(!narrativeSlots[3][0].innerHTML.includes("06:26"));

detailButton.listeners.click({ currentTarget: detailButton });
assert.strictEqual(detailButton.textContent, "Ocultar detalle");
assert.strictEqual(identity.hidden, false);
assert.ok(pageClasses.has("detail-visible"));

async function testSigningConfirmation() {
  signButton.listeners.click();
  assert.strictEqual(pdfDialog.open, true);
  cancelPdf.listeners.click();
  assert.strictEqual(pdfDialog.open, false);
  assert.strictEqual(fetchCalls, 0);

  signButton.listeners.click();
  const pendingDownload = confirmPdf.listeners.click();
  assert.strictEqual(fetchCalls, 1);
  assert.strictEqual(signButton.disabled, true);
  assert.strictEqual(confirmPdf.disabled, true);
  assert.strictEqual(cancelPdf.disabled, true);
  confirmPdf.listeners.click();
  assert.strictEqual(fetchCalls, 1);
  resolveFetch({
    ok: true,
    json: async () => ({ next_url: "" }),
  });
  await pendingDownload;
  assert.strictEqual(pdfDialog.open, false);
  assert.strictEqual(signButton.disabled, true);
  assert.strictEqual(confirmPdf.disabled, false);
  assert.strictEqual(cancelPdf.disabled, false);
  assert.strictEqual(downloads.length, 0);
  assert.strictEqual(pdfError.hidden, true);
}

testSigningConfirmation()
  .then(() => console.log("study_report.js: OK"))
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  });
