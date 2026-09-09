"""Explicit allowlist of the clinical columns consumed by InformeGX."""

CLINICAL_STUDY_COLUMN_KEYS = (
    "patient_id_num", "patient_first_name", "patient_middle_name", "patient_last_name",
    "visit_datetime", "age", "sex", "diagnosis", "dyspnea", "cough", "wheez",
    "tbco_prod", "pk_yrs", "weight", "height", "bmi", "gx_vo2_max_time_sec",
    "gx_at_ex_time_sec", "gx_at_vo2_ml_per_min", "gx_vo2_max_work_watts",
    "gx_vo2_max_rer", "gx_rest_vo2_ml_per_min", "gx_rest_vo2_ml_per_kg_per_min",
    "gx_vo2_max_vo2_ml_per_min", "gx_vo2_max_vo2_ml_per_kg_per_min",
    "gx_vo2_max_vo2workslope_ml_per_min_per_watt", "gx_predicted_vo2_ml_per_min",
    "gx_predicted_vo2_ml_per_kg_per_min", "gx_predicted_work_watts",
    "gx_predicted_vo2workslope_ml_per_min_per_watt", "gx_rest_hr_bpm",
    "gx_vo2_max_hr_bpm", "gx_predicted_hr_bpm", "gx_rest_sysbp_mmhg",
    "gx_rest_diabp_mmhg", "gx_vo2_max_sysbp_mmhg", "gx_vo2_max_diabp_mmhg",
    "gx_rest_vo2_per_hr_ml_per_beat", "gx_vo2_max_vo2_per_hr_ml_per_beat",
    "gx_predicted_vo2_per_hr_ml_per_beat", "pf_pre_mvv_l_per_min",
    "gx_rest_ve_btps_l_per_min", "gx_vo2_max_ve_btps_l_per_min",
    "gx_vo2_max_ve_per_mvv_pct", "gx_vo2_max_vt_per_ic_pct", "gx_rest_rr_br_per_min",
    "gx_vo2_max_rr_br_per_min", "gx_rest_spo2_pct", "gx_vo2_max_spo2_pct",
    "gx_rest_vd_per_vt_meas", "gx_vo2_max_vd_per_vt_meas", "gx_rest_vd_per_vt_est",
    "gx_vo2_max_vd_per_vt_est", "gx_rest_petco2_mmhg", "gx_vo2_max_petco2_mmhg",
    "gx_rest_ph", "gx_vo2_max_ph", "gx_at_ve_per_vco2", "gx_at_ve_per_vo2",
)
