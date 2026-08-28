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

const controls = [
  fakeControl("patient_first_name", "Ana", "text", false, "GX"),
  fakeControl("patient_middle_name", "", "text", false, "GX"),
  fakeControl("patient_last_name", "Prueba", "text", false, "GX"),
  fakeControl("conclusiones_definitivas", "<img src=x onerror=alert(1)>", "textarea"),
  fakeControl("umbral_anaerobio_alcanzado", "NO"),
  fakeControl("gx_at_ve_per_vco2", "99", "text", false, "GX"),
  fakeControl("gx_at_ve_per_vo2", "88", "text", false, "GX"),
  fakeControl("gx_vo2_max_ve_per_mvv_pct", "58", "text", false, "GX"),
];
const byId = Object.fromEntries(controls.map((control) => [control.id, control]));
const textTargets = [
  "sticky-patient-name", "sticky-sex", "sticky-age", "sticky-id", "sticky-date",
  "report-patient-name", "report-patient-id", "report-age", "report-sex", "report-date",
  "filled-count", "total-count",
];
textTargets.forEach((id) => { byId[id] = { id, textContent: "" }; });

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

const pdfButton = fakeButton("generate-pdf");
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
byId["generate-pdf"] = pdfButton;
byId["cancel-pdf"] = cancelPdf;
byId["confirm-pdf"] = confirmPdf;
byId["pdf-dialog-error"] = pdfError;
byId["pdf-confirm-dialog"] = pdfDialog;

const form = {
  dataset: { pdfUrl: "/studies/report.pdf" },
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
  window: { scrollTo() {} },
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
assert.ok(!narrativeSlots[4][0].innerHTML.includes("0.58"));
assert.strictEqual(byId["report-patient-name"].textContent, "Ana Prueba");
assert.strictEqual(byId["total-count"].textContent, String(controls.length));

byId["conclusiones_definitivas"].value = "Conclusión actualizada";
byId["umbral_anaerobio_alcanzado"].value = "SÍ";
byId["conclusiones_definitivas"].listeners.input();
assert.ok(narrativeSlots[5][0].innerHTML.includes("Conclusión actualizada"));
assert.strictEqual(narrativeSlots[5][0].innerHTML, narrativeSlots[5][1].innerHTML);
assert.ok(narrativeSlots[4][0].innerHTML.includes("99"));
assert.ok(!narrativeSlots[4][0].innerHTML.includes("no aplica"));

detailButton.listeners.click({ currentTarget: detailButton });
assert.strictEqual(detailButton.textContent, "Ocultar detalle");
assert.strictEqual(identity.hidden, false);
assert.ok(pageClasses.has("detail-visible"));

async function testPdfConfirmation() {
  pdfButton.listeners.click();
  assert.strictEqual(pdfDialog.open, true);
  cancelPdf.listeners.click();
  assert.strictEqual(pdfDialog.open, false);
  assert.strictEqual(fetchCalls, 0);

  pdfButton.listeners.click();
  const pendingDownload = confirmPdf.listeners.click();
  assert.strictEqual(fetchCalls, 1);
  assert.strictEqual(pdfButton.disabled, true);
  assert.strictEqual(confirmPdf.disabled, true);
  assert.strictEqual(cancelPdf.disabled, true);
  confirmPdf.listeners.click();
  assert.strictEqual(fetchCalls, 1);
  resolveFetch({
    ok: true,
    blob: async () => ({ type: "application/pdf" }),
    headers: {
      get(name) {
        return name === "Content-Disposition"
          ? 'attachment; filename="informe_gx_12345678_2026-08-20.pdf"'
          : null;
      },
    },
  });
  await pendingDownload;
  assert.strictEqual(pdfDialog.open, false);
  assert.strictEqual(pdfButton.disabled, false);
  assert.strictEqual(confirmPdf.disabled, false);
  assert.strictEqual(cancelPdf.disabled, false);
  assert.strictEqual(downloads.length, 1);
  assert.strictEqual(downloads[0].download, "informe_gx_12345678_2026-08-20.pdf");
  assert.strictEqual(downloads[0].clicked, true);
  assert.strictEqual(pdfError.hidden, true);
}

testPdfConfirmation()
  .then(() => console.log("study_report.js: OK"))
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  });
