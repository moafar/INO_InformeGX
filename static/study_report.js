(function () {
  "use strict";

  const form = document.getElementById("study-report-form");
  if (!form) return;

  const page = document.querySelector(".study-report-page");
  const controls = Array.from(form.querySelectorAll("[data-report-control][id][name]"));
  const escapeHtml = (input) => String(input ?? "").replace(/[&<>\"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#039;",
  })[char]);
  const control = (id) => document.getElementById(id);
  const value = (id) => {
    const element = control(id);
    if (!element) return "";
    if (element.type === "checkbox") return element.checked ? "true" : "";
    return String(element.value ?? "").trim();
  };
  const has = (id) => Boolean(value(id));
  const text = (id) => escapeHtml(value(id));
  const datum = (id, suffix = "") => `<em>${text(id)}${suffix}</em>`;
  const strong = (id) => `<strong>${text(id)}</strong>`;
  const any = (ids) => ids.some(has);

  function narrative0() {
    const rows = [];
    if (has("motivo_remision")) rows.push(`<div class="clinical-summary-row"><strong>Motivo de la remisión:</strong>${datum("motivo_remision")}</div>`);
    if (has("diagnosis")) rows.push(`<div class="clinical-summary-row"><strong>Diagnóstico:</strong>${datum("diagnosis")}</div>`);
    if (has("disnea_mrc")) rows.push(`<div class="clinical-summary-row clinical-summary-row--indent"><strong>Disnea MRC:</strong>${datum("disnea_mrc")}</div>`);
    if (any(["tbco_prod", "pk_yrs", "biomasa", "oxigeno"])) {
      const parts = [];
      if (has("tbco_prod")) parts.push(`<span><strong>Tabaquismo:</strong>${datum("tbco_prod")}</span>`);
      if (has("pk_yrs")) parts.push(`<span><strong>IPA:</strong>${datum("pk_yrs")}</span>`);
      if (has("biomasa")) parts.push(`<span><strong>Exposición a biomasa:</strong>${datum("biomasa")}</span>`);
      if (has("oxigeno")) parts.push(`<span><strong>Oxígeno:</strong>${datum("oxigeno")}</span>`);
      rows.push(`<div class="clinical-summary-row clinical-summary-row--inline">${parts.join("")}</div>`);
    }
    if (has("medicamentos")) rows.push(`<div class="clinical-summary-row"><strong>Medicamentos:</strong>${datum("medicamentos")}</div>`);
    if (any(["weight", "height", "bmi"])) {
      const parts = ["<strong>Medidas antropométricas:</strong>"];
      if (has("weight")) parts.push(`<span>Peso: ${datum("weight", " kg")}</span>`);
      if (has("height")) parts.push(`<span>Estatura: ${datum("height", " cm")}</span>`);
      if (has("bmi")) parts.push(`<span>Índice de masa corporal: ${datum("bmi", " kg/m²")}</span>`);
      rows.push(`<div class="clinical-summary-row clinical-summary-row--inline">${parts.join("")}</div>`);
    }
    if (any(["hb", "hc"])) {
      const parts = [];
      if (has("hb")) parts.push(`<span><strong>Hb:</strong>${datum("hb", " g/dL")}</span>`);
      if (has("hc")) parts.push(`<span><strong>Hc:</strong>${datum("hc", " %")}</span>`);
      rows.push(`<div class="clinical-summary-row clinical-summary-row--inline">${parts.join("")}</div>`);
    }
    return rows.length ? `<aside class="section-narrative clinical-summary">${rows.join("")}</aside>` : "";
  }

  function narrative1() {
    const items = [
      "Se utilizó una bicicleta ergométrica, hiperbólica y medición de gases espirados respiración a respiración.",
    ];
    if (has("medicion_gases")) items.push("Se realizó medición de gases arteriales en reposo e inmediatamente al terminar el ejercicio.");
    items.push("Se realizó monitoreo con oximetría de pulso, frecuencia cardiaca y tensión arterial.");
    if (any(["gx_vo2_max_time_min", "cambio_watts_por_etapa", "gx_vo2_max_work_watts"])) {
      let line = has("gx_vo2_max_time_min") ? `La prueba tuvo una duración de ${datum("gx_vo2_max_time_min")} minutos. ` : "";
      line += "Inicia con 3 minutos de reposo, luego 3 minutos de ejercicio sin carga y continúa con pedaleo con carga";
      if (has("cambio_watts_por_etapa")) line += ` en incrementos progresivos de ${datum("cambio_watts_por_etapa")} vatios`;
      if (has("gx_vo2_max_work_watts")) line += `, llegando a ${datum("gx_vo2_max_work_watts")} vatios, carga máxima tolerada por el paciente`;
      line += ", y finaliza con 1 minuto de recuperación.";
      items.push(line);
    }
    if (any(["disnea_borg_inicial", "fatiga_borg_inicial", "disnea_borg_final", "fatiga_borg_final", "porc_fc_maxima", "porc_o2_predicho", "gx_vo2_max_rer", "sugerencia_rer"])) {
      let line = "";
      if (any(["disnea_borg_inicial", "fatiga_borg_inicial"])) {
        line += "Se inicia";
        if (has("disnea_borg_inicial")) line += ` con disnea ${datum("disnea_borg_inicial")}`;
        if (has("fatiga_borg_inicial")) line += `${has("disnea_borg_inicial") ? " y" : " con"} fatiga ${datum("fatiga_borg_inicial")}`;
        line += " por escala de Borg. ";
      }
      if (any(["disnea_borg_final", "fatiga_borg_final"])) {
        line += "Se suspendió la prueba";
        if (has("disnea_borg_final")) line += ` con disnea ${datum("disnea_borg_final")}`;
        if (has("fatiga_borg_final")) line += `${has("disnea_borg_final") ? " y" : " con"} fatiga ${datum("fatiga_borg_final")}`;
        line += " por escala de Borg. ";
      }
      if (any(["porc_fc_maxima", "porc_o2_predicho"])) {
        line += "Se alcanzó";
        if (has("porc_fc_maxima")) line += ` el ${datum("porc_fc_maxima", "%")} de la frecuencia cardiaca máxima`;
        if (has("porc_fc_maxima") && has("porc_o2_predicho")) line += " y";
        if (has("porc_o2_predicho")) line += ` un consumo de oxígeno pico del ${datum("porc_o2_predicho", "%")} del predicho`;
        line += ". ";
      }
      if (has("gx_vo2_max_rer")) line += `El RER en ejercicio pico fue ${datum("gx_vo2_max_rer")}. `;
      if (has("sugerencia_rer")) line += text("sugerencia_rer");
      items.push(line.trim());
    }
    return `<aside class="section-narrative protocol-summary"><ul class="protocol-summary-list">${items.map((item) => `<li>${item}</li>`).join("")}</ul></aside>`;
  }

  function narrative2() {
    const paragraphs = [];
    if (any(["gx_rest_vo2_ml_per_min", "gx_rest_vo2_ml_per_kg_per_min", "interpretacion_consumo_vo2"])) {
      let line = "";
      if (has("gx_rest_vo2_ml_per_min")) line += `Consumo de oxígeno en reposo: ${datum("gx_rest_vo2_ml_per_min")} ml/min`;
      if (has("gx_rest_vo2_ml_per_kg_per_min")) line += `${has("gx_rest_vo2_ml_per_min") ? ", equivalente a" : "Consumo de oxígeno relativo en reposo:"} ${datum("gx_rest_vo2_ml_per_kg_per_min")} ml/kg/min`;
      if (has("interpretacion_consumo_vo2")) line += `${any(["gx_rest_vo2_ml_per_min", "gx_rest_vo2_ml_per_kg_per_min"]) ? ". Se considera " : "Se considera "}${strong("interpretacion_consumo_vo2")}`;
      paragraphs.push(`${line}.`);
    }
    const assessment = ["interpretacion_prueba_cp", "gx_vo2_max_vo2_ml_per_min", "porc_vo2_predicho", "gx_vo2_max_vo2_ml_per_kg_per_min_1", "clase_funcional", "carga_max_w", "relacion_consumo_trabajo", "interpretacion_relacion_consumo_trabajo"];
    if (any(assessment)) {
      let line = `Prueba de ejercicio cardiopulmonar${has("interpretacion_prueba_cp") ? ` ${strong("interpretacion_prueba_cp")}` : ""}. `;
      if (has("gx_vo2_max_vo2_ml_per_min")) line += `Se alcanzó un consumo de oxígeno pico (VO₂ pico) de ${datum("gx_vo2_max_vo2_ml_per_min")} ml/min de O₂`;
      if (has("porc_vo2_predicho")) line += `${has("gx_vo2_max_vo2_ml_per_min") ? ", correspondiente al" : "El VO₂ pico correspondió al"} ${datum("porc_vo2_predicho", "%")} del predicho`;
      if (any(["gx_vo2_max_vo2_ml_per_min", "porc_vo2_predicho"])) line += ".";
      if (has("gx_vo2_max_vo2_ml_per_kg_per_min_1")) line += ` En relación con el peso, el VO₂ pico fue de ${datum("gx_vo2_max_vo2_ml_per_kg_per_min_1")} ml/kg/min.`;
      if (has("clase_funcional")) line += ` Clase funcional ${strong("clase_funcional")}.`;
      if (has("carga_max_w")) line += ` La carga máxima de trabajo correspondió al ${datum("carga_max_w", "%")} de lo esperado.`;
      if (has("relacion_consumo_trabajo")) line += ` La relación consumo-trabajo (VO₂/W) fue de ${datum("relacion_consumo_trabajo")} ml O₂/min/W`;
      if (has("interpretacion_relacion_consumo_trabajo")) line += `${has("relacion_consumo_trabajo") ? ". Se considera " : " Se considera "}${strong("interpretacion_relacion_consumo_trabajo")}`;
      line += ".";
      paragraphs.push(line);
    }
    if (!paragraphs.length) return "";
    return `<aside class="section-narrative functional-summary">${paragraphs.map((paragraph) => `<p>${paragraph}</p>`).join("")}<cite>(Weber KT, Janicki JS. Exercise Testing in the Evaluation of the Patient with Chronic Cardiac Failure. Am Rev Respir Dis. 1984; 129: S60–S62)</cite></aside>`;
  }

  function narrative3() {
    const paragraphs = [];
    if (any(["ritmo_cardio_inicial", "gx_rest_hr_bpm", "gx_vo2_max_hr_bpm", "calif_fc", "ritmo_ekg", "gx_rest_sysbp_mmhg", "gx_rest_diabp_mmhg", "gx_vo2_max_sysbp_mmhg", "gx_vo2_max_diabp_mmhg", "latidos_recuperados_minuto", "vo2_minuto"])) {
      let line = "";
      if (any(["ritmo_cardio_inicial", "gx_rest_hr_bpm"])) {
        line += "El paciente inició la prueba";
        if (has("ritmo_cardio_inicial")) line += ` en ritmo ${datum("ritmo_cardio_inicial")}`;
        if (has("gx_rest_hr_bpm")) line += ` con frecuencia cardíaca de ${datum("gx_rest_hr_bpm", "/min")}`;
        line += has("gx_vo2_max_hr_bpm") ? `, incrementando hasta el final del ejercicio a ${datum("gx_vo2_max_hr_bpm", "/min")}. ` : ". ";
      } else if (has("gx_vo2_max_hr_bpm")) line += `La frecuencia cardíaca al final del ejercicio fue de ${datum("gx_vo2_max_hr_bpm", "/min")}. `;
      if (has("calif_fc")) line += `Frecuencia cardíaca: ${strong("calif_fc")}. `;
      if (has("ritmo_ekg")) line += `EKG en ritmo ${datum("ritmo_ekg")} durante la prueba. `;
      if (any(["gx_rest_sysbp_mmhg", "gx_rest_diabp_mmhg"])) line += `T.A. inicial: <em>${has("gx_rest_sysbp_mmhg") ? text("gx_rest_sysbp_mmhg") : ""}${has("gx_rest_sysbp_mmhg") && has("gx_rest_diabp_mmhg") ? "/" : ""}${has("gx_rest_diabp_mmhg") ? text("gx_rest_diabp_mmhg") : ""}</em> mmHg. `;
      if (any(["gx_vo2_max_sysbp_mmhg", "gx_vo2_max_diabp_mmhg"])) line += `T.A. final: <em>${has("gx_vo2_max_sysbp_mmhg") ? text("gx_vo2_max_sysbp_mmhg") : ""}${has("gx_vo2_max_sysbp_mmhg") && has("gx_vo2_max_diabp_mmhg") ? "/" : ""}${has("gx_vo2_max_diabp_mmhg") ? text("gx_vo2_max_diabp_mmhg") : ""}</em> mmHg. `;
      if (has("latidos_recuperados_minuto")) line += `${datum("latidos_recuperados_minuto")} latidos recuperados al minuto de terminar. `;
      if (has("vo2_minuto")) line += `El VO₂ al minuto de finalizar el ejercicio fue de ${datum("vo2_minuto", " ml/min")}.`;
      paragraphs.push(line.trim());
    }
    if (any(["porc_pred_o2_latido_6", "interpretacion_o2_latido_6", "umbral_anaerobio_alcanzado"])) {
      let line = "";
      if (has("porc_pred_o2_latido_6")) line += `El oxígeno latido (ml O₂/lat) correspondió al ${datum("porc_pred_o2_latido_6", "%")} del predicho. `;
      if (has("interpretacion_o2_latido_6")) line += `Se considera ${strong("interpretacion_o2_latido_6")}. `;
      if (has("umbral_anaerobio_alcanzado")) line += `El umbral anaerobio ${strong("umbral_anaerobio_alcanzado")} fue alcanzado durante el ejercicio.`;
      paragraphs.push(line.trim());
    }
    return paragraphs.length ? `<aside class="section-narrative cardiovascular-summary">${paragraphs.map((paragraph) => `<p>${paragraph}</p>`).join("")}</aside>` : "";
  }

  function narrative4() {
    const threshold = value("umbral_anaerobio_alcanzado").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toUpperCase();
    const notReached = threshold === "NO";
    const reached = threshold === "SI";
    const paragraphs = [];
    const ventilation = ["interpretacion_curva_flujo_volumen", "pf_pre_mvv_l_per_min", "gx_rest_ve_btps_l_per_min", "gx_vo2_max_ve_btps_l_per_min", "reserva_respiratoria_pico_l", "interpretacion_reserva_pico_vvm", "gx_vo2_max_ve_per_mvv_pct", "gx_vo2_max_vt_per_ic_pct", "comportamiento_vvm"];
    if (any(ventilation)) {
      let line = "";
      if (has("interpretacion_curva_flujo_volumen")) line += `Curva flujo-volumen basal ${strong("interpretacion_curva_flujo_volumen")}. `;
      if (has("pf_pre_mvv_l_per_min")) line += `La VVM medida fue de ${datum("pf_pre_mvv_l_per_min", " L/min")}. `;
      if (any(["gx_rest_ve_btps_l_per_min", "gx_vo2_max_ve_btps_l_per_min"])) {
        line += "La ventilación minuto (VE)";
        if (has("gx_rest_ve_btps_l_per_min")) line += ` fue de ${datum("gx_rest_ve_btps_l_per_min", " L/min")} en reposo`;
        if (has("gx_vo2_max_ve_btps_l_per_min")) line += `${has("gx_rest_ve_btps_l_per_min") ? " y aumentó hasta " : " fue de "}${datum("gx_vo2_max_ve_btps_l_per_min", " L/min")} en ejercicio pico`;
        line += ". ";
      }
      if (has("reserva_respiratoria_pico_l")) line += `Esto determina una reserva respiratoria en el ejercicio pico de ${datum("reserva_respiratoria_pico_l", " L/min")}. `;
      if (has("interpretacion_reserva_pico_vvm")) line += `Se considera ${strong("interpretacion_reserva_pico_vvm")}. `;
      if (has("gx_vo2_max_ve_per_mvv_pct")) line += `La relación VE/VVM fue de ${datum("gx_vo2_max_ve_per_mvv_pct", "%")}`;
      if (has("gx_vo2_max_vt_per_ic_pct")) line += `${has("gx_vo2_max_ve_per_mvv_pct") ? " y la relación" : "La relación"} VT/CI fue de ${datum("gx_vo2_max_vt_per_ic_pct", "%")}`;
      if (any(["gx_vo2_max_ve_per_mvv_pct", "gx_vo2_max_vt_per_ic_pct"])) line += ". ";
      if (has("comportamiento_vvm")) line += `${text("comportamiento_vvm")}.`;
      paragraphs.push(line.trim());
    }
    const pattern = ["gx_rest_rr_br_per_min", "gx_vo2_max_rr_br_per_min_1", "observaciones_asa_volumen_corriente", "observaciones_volumen_minuto", "interpretacion_fr_maxima", "gx_rest_spo2_pct", "gx_vo2_max_spo2_pct"];
    if (any(pattern)) {
      let line = "";
      if (any(["gx_rest_rr_br_per_min", "gx_vo2_max_rr_br_per_min_1"])) {
        line += "La prueba inició";
        if (has("gx_rest_rr_br_per_min")) line += ` con una frecuencia respiratoria de ${datum("gx_rest_rr_br_per_min", " resp/min")}`;
        if (has("gx_vo2_max_rr_br_per_min_1")) line += `${has("gx_rest_rr_br_per_min") ? ", que aumentó hasta " : " con una frecuencia respiratoria máxima de "}${datum("gx_vo2_max_rr_br_per_min_1", " resp/min")}`;
        line += ". ";
      }
      if (has("observaciones_asa_volumen_corriente")) line += `Se observa que el asa de volumen corriente ${strong("observaciones_asa_volumen_corriente")}. `;
      if (has("observaciones_volumen_minuto")) line += `El volumen minuto ${strong("observaciones_volumen_minuto")}. `;
      if (has("interpretacion_fr_maxima")) line += `La frecuencia respiratoria máxima durante el ejercicio se considera ${strong("interpretacion_fr_maxima")}. `;
      if (any(["gx_rest_spo2_pct", "gx_vo2_max_spo2_pct"])) {
        line += "La SpO₂ por pulso-oximetría";
        if (has("gx_rest_spo2_pct")) line += ` en reposo fue de ${datum("gx_rest_spo2_pct", "%")}`;
        if (has("gx_vo2_max_spo2_pct")) line += `${has("gx_rest_spo2_pct") ? ", mientras que al final del ejercicio fue de " : " al final del ejercicio fue de "}${datum("gx_vo2_max_spo2_pct", "%")}`;
        line += ".";
      }
      paragraphs.push(line.trim());
    }
    const gas = ["gx_rest_vd_per_vt_meas", "gx_vo2_max_vd_per_vt_meas", "relacion_vdvt_reposo", "comportamiento_relacion_vdvt", "gx_rest_petco2_mmhg", "comportamiento_petco2_rest_ejercicio_total", "comportamiento_petco2_rest_ejercicio_maximo", "interpretacion_petco2_pico_reposo"];
    if (any(gas) || notReached || (reached && any(["gx_at_ve_per_vco2", "gx_at_ve_per_vo2"]))) {
      let line = "";
      if (any(["gx_rest_vd_per_vt_meas", "gx_vo2_max_vd_per_vt_meas"])) {
        line += "El espacio muerto (VD/VT) medido por gases arteriales";
        if (has("gx_rest_vd_per_vt_meas")) line += ` en reposo fue de ${datum("gx_rest_vd_per_vt_meas")}`;
        if (has("gx_vo2_max_vd_per_vt_meas")) line += `${has("gx_rest_vd_per_vt_meas") ? " y en el ejercicio máximo fue de " : " en el ejercicio máximo fue de "}${datum("gx_vo2_max_vd_per_vt_meas")}`;
        line += ". ";
      }
      if (has("relacion_vdvt_reposo")) line += `La relación VD/VT en reposo se considera ${strong("relacion_vdvt_reposo")}. `;
      if (has("comportamiento_relacion_vdvt")) line += `Entre el reposo y el ejercicio máximo, la relación VD/VT ${strong("comportamiento_relacion_vdvt")}. `;
      if (notReached) line += "El equivalente respiratorio para CO₂ (VE/VCO₂) en el umbral láctico no aplica. El equivalente respiratorio para O₂ (VE/VO₂) en el umbral láctico no aplica. ";
      if (reached) {
        if (has("gx_at_ve_per_vco2")) line += `El equivalente respiratorio para CO₂ (VE/VCO₂) en el umbral láctico fue de ${datum("gx_at_ve_per_vco2")}. `;
        if (has("gx_at_ve_per_vo2")) line += `El equivalente respiratorio para O₂ (VE/VO₂) en el umbral láctico fue de ${datum("gx_at_ve_per_vo2")}. `;
      }
      if (has("gx_rest_petco2_mmhg")) line += `La PETCO₂ en reposo fue de ${datum("gx_rest_petco2_mmhg", " mmHg")}. `;
      if (has("comportamiento_petco2_rest_ejercicio_total")) line += `Durante el ejercicio, la PETCO₂ ${strong("comportamiento_petco2_rest_ejercicio_total")}. `;
      if (has("comportamiento_petco2_rest_ejercicio_maximo")) line += `En el ejercicio máximo, la PETCO₂ ${strong("comportamiento_petco2_rest_ejercicio_maximo")}. `;
      if (has("interpretacion_petco2_pico_reposo")) line += `La PETCO₂ en ejercicio pico respecto al reposo se considera ${strong("interpretacion_petco2_pico_reposo")}.`;
      paragraphs.push(line.trim());
    }
    return paragraphs.length ? `<aside class="section-narrative ventilatory-summary">${paragraphs.map((paragraph) => `<p>${paragraph}</p>`).join("")}</aside>` : "";
  }

  function narrative5() {
    const parts = [];
    if (has("gx_vo2_max_vo2_ml_per_kg_per_min_2")) parts.push(`VO₂ pico relativo: ${datum("gx_vo2_max_vo2_ml_per_kg_per_min_2", " ml/kg/min")}. `);
    if (has("gx_vo2_max_vo2workslope_ml_per_min_per_watt")) parts.push(`Pendiente VO₂/trabajo: ${datum("gx_vo2_max_vo2workslope_ml_per_min_per_watt", " ml/min/W")}. `);
    if (has("gx_vo2_max_rr_br_per_min_2")) parts.push(`Frecuencia respiratoria máxima: ${datum("gx_vo2_max_rr_br_per_min_2", " rpm")}.`);
    if (!parts.length && !has("conclusiones_definitivas")) return "";
    return `<aside class="section-narrative conclusions-summary">${parts.length ? `<p>${parts.join("")}</p>` : ""}${has("conclusiones_definitivas") ? `<p class="final-conclusions">${text("conclusiones_definitivas")}</p>` : ""}</aside>`;
  }

  const narrativeBuilders = [narrative0, narrative1, narrative2, narrative3, narrative4, narrative5];

  function update() {
    narrativeBuilders.forEach((builder, index) => {
      const html = builder();
      document.querySelectorAll(`[data-section-narrative="${index}"], [data-report-narrative="${index}"]`)
        .forEach((slot) => { slot.innerHTML = html; });
    });
    const name = [value("patient_first_name"), value("patient_middle_name"), value("patient_last_name")].filter(Boolean).join(" ").replace(/\s+/g, " ").trim();
    const setText = (id, content) => { const element = document.getElementById(id); if (element) element.textContent = content; };
    setText("sticky-patient-name", name || "Paciente sin identificar");
    setText("sticky-sex", value("sex") || "—");
    setText("sticky-age", value("age") || "—");
    setText("sticky-id", value("patient_id_num") || "—");
    setText("sticky-date", value("visit_date") || "—");
    setText("report-patient-name", name || "Paciente sin identificar");
    setText("report-patient-id", value("patient_id_num") || "—");
    setText("report-age", value("age") ? `${value("age")} años` : "—");
    setText("report-sex", value("sex") || "—");
    setText("report-date", value("visit_date") || "—");
    setText("filled-count", String(controls.filter((element) => element.type === "checkbox" ? element.checked : String(element.value ?? "").trim()).length));
    setText("total-count", String(controls.length));
    controls.forEach((element) => {
      const current = element.type === "checkbox" ? String(element.checked) : String(element.value ?? "");
      const original = String(element.dataset.originalValue ?? "");
      const field = element.closest("[data-origin]");
      if (field && field.dataset.origin === "GX") field.dataset.edited = String(current !== original);
    });
  }

  controls.forEach((element) => {
    element.addEventListener("input", update);
    element.addEventListener("change", update);
  });
  document.querySelectorAll(".section-head").forEach((button) => {
    button.addEventListener("click", () => {
      const body = button.nextElementSibling;
      if (!body) return;
      const expanded = button.getAttribute("aria-expanded") === "true";
      button.setAttribute("aria-expanded", String(!expanded));
      body.hidden = expanded;
      button.querySelector(".chevron")?.classList.toggle("up", !expanded);
    });
  });
  document.getElementById("toggle-detail")?.addEventListener("click", (event) => {
    const button = event.currentTarget;
    const visible = button.getAttribute("aria-pressed") !== "true";
    button.setAttribute("aria-pressed", String(visible));
    button.textContent = visible ? "Ocultar detalle" : "Mostrar detalle";
    page?.classList.toggle("detail-visible", visible);
    const identity = document.getElementById("identity-grid");
    if (identity) identity.hidden = !visible;
  });
  document.getElementById("view-report")?.addEventListener("click", () => document.getElementById("preview")?.scrollIntoView({ behavior: "smooth" }));
  document.getElementById("back-to-form")?.addEventListener("click", () => window.scrollTo({ top: 0, behavior: "smooth" }));

  const pdfButton = document.getElementById("generate-pdf");
  const pdfDialog = document.getElementById("pdf-confirm-dialog");
  const cancelPdf = document.getElementById("cancel-pdf");
  const confirmPdf = document.getElementById("confirm-pdf");
  const pdfError = document.getElementById("pdf-dialog-error");
  let generatingPdf = false;

  const setPdfError = (message) => {
    if (!pdfError) return;
    pdfError.textContent = message;
    pdfError.hidden = !message;
  };
  pdfButton?.addEventListener("click", () => {
    if (pdfButton.disabled || generatingPdf) return;
    setPdfError("");
    pdfDialog?.showModal();
  });
  cancelPdf?.addEventListener("click", () => {
    if (!generatingPdf) pdfDialog?.close();
  });
  confirmPdf?.addEventListener("click", async () => {
    if (generatingPdf || !form.dataset.pdfUrl) return;
    generatingPdf = true;
    pdfButton.disabled = true;
    confirmPdf.disabled = true;
    cancelPdf.disabled = true;
    pdfDialog?.setAttribute("aria-busy", "true");
    setPdfError("");
    try {
      const response = await fetch(form.dataset.pdfUrl, {
        method: "POST",
        body: new FormData(form),
        credentials: "same-origin",
        headers: { Accept: "application/pdf" },
      });
      if (!response.ok) {
        const serverMessage = (await response.text()).trim();
        throw new Error(serverMessage || "No fue posible generar el PDF.");
      }
      const blob = await response.blob();
      if (blob.type !== "application/pdf") throw new Error("La respuesta PDF no es válida.");
      const disposition = response.headers.get("Content-Disposition") || "";
      const filenameMatch = disposition.match(/filename="?([^";]+)"?/i);
      const filename = filenameMatch ? filenameMatch[1] : "informe_gx.pdf";
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(objectUrl);
      pdfDialog?.close();
    } catch (error) {
      setPdfError(error instanceof Error ? error.message : "No fue posible generar el PDF.");
    } finally {
      generatingPdf = false;
      pdfButton.disabled = false;
      confirmPdf.disabled = false;
      cancelPdf.disabled = false;
      pdfDialog?.removeAttribute("aria-busy");
    }
  });
  update();
})();
