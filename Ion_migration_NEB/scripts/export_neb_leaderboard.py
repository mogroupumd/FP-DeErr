#!/usr/bin/env python3
"""Public, deterministic leaderboard-summary export for the Ion Migration by
NEB component.

Given a DFT-NEB reference file and an all-FP results file (each accepted as
plain .json or gzip-compressed .json.gz), this script:

  1. loads both through the public `neb_analysis.load_neb_datasets`;
  2. validates the active population (154 pathways, 1,078 finalized
     DFT-reference images, 109 unique active ICSD identifiers (these collapse
     to 106 structurally distinct materials once endpoints are matched with
     pymatgen StructureMatcher -- see the component README; this check counts
     source identifiers, not distinct materials), `113548|10` absent) before computing or writing anything;
  3. runs the same unmodified `neb_analysis.py` functions the analysis
     notebook itself uses (`build_neb_analysis_results`, and the
     `barrier_error_summary_by_protocol` / `profile_summary_by_protocol`
     attributes it already computes -- never recomputed a second time here);
  4. calls `compute_key_neb_metrics_summary` once and parses its "MAE / RMSE"
     barrier-error strings directly for the exported values (rather than
     re-deriving the forward/backward combination a second, independent way
     here), so the export always tracks whatever combination convention that
     function's own default (`barrier_combination="pooled"`) computes and
     cannot silently drift from what the analysis notebook itself displays;
  5. writes the compact per-FP summary to
     `<component-dir>/data/ion_migration_neb_leaderboard_summary.json` and an
     identical copy to `<repo-root>/docs/data/ion_migration_neb_leaderboard_summary.json`
     (the GitHub Pages copy), creating `docs/data/` if needed;
  6. refuses to silently overwrite either destination if it already exists
     with *different* content, unless `--force` is given (a no-op rewrite of
     byte-identical content is always allowed).

Also computes and adds endpoint-structure relaxation error fields (Table 9;
mirrors the presentation the Phase Stability component uses for its own
structural-relaxation RMSD table) to each FP's record: reuses
`neb_analysis.py`'s own `compute_endpoint_rmsd` output verbatim (StructureMatcher
ltol=0.5/stol=0.5/angle_tol=10.0, unchanged), restricted at this export layer
-- not inside `neb_analysis.py` -- to the converged full FP-NEB population
(the same `neb_converged` lookup and default-True-if-missing convention
`compute_barrier_error_summaries` already uses), pooling the initial (img0)
and final (img_last) endpoint comparisons into one distribution per FP since
the table is one row per FP. "Map success" mirrors the Phase Stability
component's own concept exactly: a successful StructureMatcher mapping
(non-NaN RMSD) versus a failed one (NaN) -- no new tolerance or matching
algorithm. The three RMSD-threshold-fraction columns (<0.05/<0.10/<0.20 A)
mirror Phase Stability's own thresholds and its own denominator convention
verbatim (`Phase_stability_ordering/scripts/convexhull_analysis_utils.py`,
`summarize_structure_rmsd`: fraction of *mapped* comparisons under each
cutoff, not a fraction of every attempt) -- `neb_analysis.py` itself still
computes no threshold fractions; this export script only counts what
fraction of its own already-real, already-computed RMSD values fall under
each cutoff, exactly as Phase Stability's own export layer does.

No scientific value is hardcoded anywhere in this script: every number in
the output comes from `neb_analysis.py`.

Usage (run from the `Ion_migration_NEB/` directory):

    python scripts/export_neb_leaderboard.py \\
        --reference data/ion_migration_neb_reference.json.gz \\
        --results /path/to/ion_migration_neb_results_standardized.json

Or from anywhere, with --component-dir pointing at Ion_migration_NEB/:

    python Ion_migration_NEB/scripts/export_neb_leaderboard.py \\
        --component-dir Ion_migration_NEB \\
        --reference Ion_migration_NEB/data/ion_migration_neb_reference.json.gz \\
        --results /path/to/ion_migration_neb_results_standardized.json
"""

import argparse
import datetime
import hashlib
import json
import sys
from pathlib import Path

FP_ORDER = [
    "MACE-MP0_medium", "CHGNET", "M3GNET_pes", "UMA_s1_p1",
    "M3GNET_matpes_PBE", "TensorNET_matpes_PBE", "MACE_matpes_pbe",
    "Orb_v3_conservative_inf_omat", "SevenNet_mf_ompa", "MatterSim_v1_5M",
    "Nequix_oam_1", "GPTFF_v2", "NEP89", "DPA4_Plus_OMat24",
    "GRACE_3L_OMAT_large_ft_AM", "MACE_OMAT_0_medium",
]
# GPTFF_v2 ran under ASE 3.28.0 while every other second-wave FP ran 3.29.0
# (all fifteen otherwise share matcalc 0.4.3, neb_method "aseneb" and the same
# BFGS-through-MatCalc optimizer). It is also the barrier outlier of the set,
# so the two had to be disentangled before including it. They were, via the
# fp_static_on_dft_neb protocol, which evaluates the FP on the DFT NEB images
# and therefore never invokes ASE's NEB tangent construction or BFGS: GPTFF's
# static barrier MAE (0.2066 eV) is already worse than every other FP in either
# wave, and its full/static ratio (1.07) sits inside the 0.88-1.29 band spanned
# by all fifteen. The anomaly is in the potential energy surface, not the ASE
# version. See NEB_matcalc_ase_provenance.md.
# MACE_OMAT_0_medium (added after the manuscript) ran in the MACE-MatPES
# environment: ASE 3.24.0, matcalc 0.4.0, the same neb_method "aseneb" and
# BFGS-through-MatCalc optimizer.
FP_DISPLAY_NAMES = {
    "MACE-MP0_medium":      "MACE",
    "CHGNET":               "CHGNet",
    "M3GNET_pes":           "M3GNet",
    "UMA_s1_p1":            "UMA",
    "M3GNET_matpes_PBE":    "M3GNet-MatPES",
    "TensorNET_matpes_PBE": "TensorNet-MatPES",
    "MACE_matpes_pbe":      "MACE-MatPES",
    "Orb_v3_conservative_inf_omat": "Orb",
    "SevenNet_mf_ompa":             "SevenNet",
    "MatterSim_v1_5M":              "MatterSim",
    "Nequix_oam_1":                 "Nequix",
    "GPTFF_v2":                     "GPTFF",
    "NEP89":                        "NEP89",
    "DPA4_Plus_OMat24":             "DPA4",
    "GRACE_3L_OMAT_large_ft_AM":    "GRACE",
    "MACE_OMAT_0_medium":           "MACE-OMAT",
}
OUTLIER_THRESHOLD = 1.0
ROUND_DECIMALS = 4

EXPECTED_ACTIVE_PATHWAYS = 154
EXPECTED_ACTIVE_IMAGES = 1078
EXPECTED_UNIQUE_ICSD = 109
EXCLUDED_PATHWAY_KEY = "113548|10"


# r(x, na) rounds a final, about-to-be-exported value to ROUND_DECIMALS
# using neb_analysis.py's house rule for display/formatting-time rounding
# (round_half_away_from_zero: ties away from zero, not to even -- see that
# function's docstring). Takes `na` explicitly (rather than a bare
# module-level helper) since this script only imports neb_analysis lazily,
# inside main(), after --component-dir is known.
def r(x, na):
    return na.round_half_away_from_zero(float(x), ROUND_DECIMALS)


def sha256_of_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_active_population(reference_data):
    """Hard population checks, run before anything is computed or written.
    Raises AssertionError (refusing to proceed) if the shipped/regenerated
    reference does not match the approved active population."""
    pathways = reference_data["pathways"]
    common = reference_data["common_pathway_keys"]
    n_images = sum(len(p["dft_neb_images"]) for p in pathways.values())
    unique_icsd = {p["identifiers"]["icsd_id"] for p in pathways.values()}

    assert len(pathways) == EXPECTED_ACTIVE_PATHWAYS, (
        f"active pathway count is {len(pathways)}, expected {EXPECTED_ACTIVE_PATHWAYS} -- refusing to export")
    assert len(common) == EXPECTED_ACTIVE_PATHWAYS, (
        f"common_pathway_keys count is {len(common)}, expected {EXPECTED_ACTIVE_PATHWAYS} -- refusing to export")
    assert n_images == EXPECTED_ACTIVE_IMAGES, (
        f"total DFT-reference image count is {n_images}, expected {EXPECTED_ACTIVE_IMAGES} -- refusing to export")
    assert all(len(p["dft_neb_images"]) == 7 for p in pathways.values()), (
        "not every active pathway has exactly 7 DFT-reference images -- refusing to export")
    assert len(unique_icsd) == EXPECTED_UNIQUE_ICSD, (
        f"unique active ICSD count is {len(unique_icsd)}, expected {EXPECTED_UNIQUE_ICSD} -- refusing to export")
    assert EXCLUDED_PATHWAY_KEY not in pathways and EXCLUDED_PATHWAY_KEY not in common, (
        f"{EXCLUDED_PATHWAY_KEY} is present in the active population -- refusing to export")


def compute_endpoint_rmsd_leaderboard_fields(analysis, na, fp_order):
    """Per-FP endpoint-structure relaxation error (Table 9), full_fp_neb
    protocol only, restricted to the converged full FP-NEB population.
    Reuses `analysis.endpoint_rmsd_by_fp_protocol_path` verbatim -- the raw
    output of `neb_analysis.compute_endpoint_rmsd`, already computed once
    inside `build_neb_analysis_results` -- and `analysis.full_fp_neb_status_by_fp_path`
    for the exact same `neb_converged` lookup (default True if a pathway is
    missing from the status map) that `compute_barrier_error_summaries` uses
    internally. No new StructureMatcher call, tolerance, or matching logic.

    Returns {fp_key: {field_name: value_or_None}}."""
    fields_by_fp = {}
    for fp_key in fp_order:
        status_lookup = analysis.full_fp_neb_status_by_fp_path.get(fp_key, {})
        rmsd_lookup = analysis.endpoint_rmsd_by_fp_protocol_path.get(fp_key, {}).get(
            na.PROTOCOL_FULL_FP_NEB, {})

        attempted = []
        n_converged_paths = 0
        for pkey, rd in rmsd_lookup.items():
            icsd_str, path_str = pkey.split("|")
            status_key = (str(int(icsd_str)), str(int(path_str)))
            converged = status_lookup.get(status_key, {}).get("neb_converged", True)
            if not converged:
                continue
            n_converged_paths += 1
            attempted.append(rd.get("rmsd_img0", float("nan")))
            attempted.append(rd.get("rmsd_img_last", float("nan")))

        matched = [v for v in attempted if not na.np.isnan(v)]
        n_attempted = len(attempted)
        n_matched = len(matched)

        def pct_under(threshold, matched=matched, n_matched=n_matched):
            # Same convention as Phase Stability's summarize_structure_rmsd
            # (convexhull_analysis_utils.py): denominator is n_matched (the
            # successfully-mapped comparisons), not n_attempted -- a failed
            # mapping is excluded from every threshold fraction, not counted
            # as a failure against it.
            if not n_matched:
                return None
            return r(100.0 * sum(1 for v in matched if v < threshold) / n_matched, na)

        fields_by_fp[fp_key] = {
            "endpoint_rmsd_n_converged_paths": n_converged_paths,
            "endpoint_rmsd_n_endpoint_attempts": n_attempted,
            "endpoint_rmsd_map_success_pct": r(100.0 * n_matched / n_attempted, na) if n_attempted else None,
            "endpoint_rmsd_mean_angstrom": r(float(na.np.mean(matched)), na) if matched else None,
            "endpoint_rmsd_max_angstrom": r(float(na.np.max(matched)), na) if matched else None,
            "endpoint_rmsd_lt_0_05_pct": pct_under(0.05),
            "endpoint_rmsd_lt_0_10_pct": pct_under(0.10),
            "endpoint_rmsd_lt_0_20_pct": pct_under(0.20),
        }
    return fields_by_fp


def build_leaderboard(reference_path, results_path, na, area_between_curves, simplify_class,
                       barrier_combination="pooled", fp_keys=None):
    """barrier_combination: forwarded verbatim to compute_key_neb_metrics_summary
    (see that function's docstring). "pooled" (default) is the only value
    that should ever be used for a real published/leaderboard export;
    "round_then_average_legacy" exists solely to regenerate historical
    reproductions (e.g. the legacy-reproduction supplement in backups/) and
    must never be passed by anything that writes to the live leaderboard
    JSON files without an explicit, deliberate override at the call site."""
    if barrier_combination not in ("pooled", "round_then_average_legacy"):
        raise ValueError(
            f"barrier_combination must be 'pooled' or 'round_then_average_legacy', "
            f"got {barrier_combination!r}"
        )
    with open(reference_path, "rb") as f:
        ref_sha256 = hashlib.sha256(f.read()).hexdigest() if Path(reference_path).suffix != ".gz" else None
    # For .gz inputs, record the compressed-file hash directly (what a user
    # actually downloads/verifies); load_neb_datasets decompresses internally.
    if ref_sha256 is None:
        ref_sha256 = sha256_of_file(reference_path)
    res_sha256 = sha256_of_file(results_path)

    reference_data, fp_results = na.load_neb_datasets(str(reference_path), str(results_path))
    validate_active_population(reference_data)

    requested = list(fp_keys) if fp_keys else list(FP_ORDER)
    unknown = [k for k in requested if k not in FP_DISPLAY_NAMES]
    if unknown:
        raise ValueError(f"no display name registered for FP keys {unknown}; add them to FP_DISPLAY_NAMES")

    models = fp_results.get("models", {})
    fp_order = [k for k in requested if k in models]
    missing = [k for k in requested if k not in models]
    if missing:
        print(f"WARNING: results file is missing FPs {missing}; exporting only {fp_order}", file=sys.stderr)

    # A results file may declare a model key with no data behind it (an empty
    # placeholder reserved for a run that has not finished yet). Key presence
    # alone therefore cannot scope an export: such an entry would otherwise be
    # carried into the analysis as a real FP with zero pathways. Fail loudly
    # and name them rather than exporting a silently meaningless row.
    empty = [k for k in fp_order if not models[k].get("full_fp_neb", {}).get("pathways")]
    if empty:
        raise ValueError(
            f"FP keys present in the results file but carrying no full_fp_neb pathways: {empty}. "
            f"Scope this run with --fp-keys, or point --results at a file that has their data."
        )

    analysis = na.build_neb_analysis_results(
        reference_data, fp_results, expected_pathways=EXPECTED_ACTIVE_PATHWAYS,
        fp_order=fp_order, outlier_threshold=OUTLIER_THRESHOLD, validate=True,
    )
    assert analysis.validation_report.ok, "validation failed -- refusing to export"

    # Only full_barrier_df's mean_RMSD_img0/mean_RMSD_img_last columns are
    # still needed directly (the RMSD cross-check below) -- barrier MAE/RMSE
    # itself now comes from key_df (see below), not from these DataFrames.
    full_barrier_df = analysis.barrier_error_summary_by_protocol[na.PROTOCOL_FULL_FP_NEB]
    full_profile_df = analysis.profile_summary_by_protocol[na.PROTOCOL_FULL_FP_NEB].set_index("FP")

    # Single source of truth for the combined barrier-error MAE/RMSE: calls
    # compute_key_neb_metrics_summary with its own default
    # (barrier_combination="pooled" -- this script does not override it, so
    # it always tracks whatever that function's real default is) and parses
    # its "MAE / RMSE" strings directly, rather than re-deriving the
    # combination with a second, independent implementation here. A second
    # implementation is exactly how this script silently fell out of sync
    # with a real defect fix once before (it used to hardcode compute_key_
    # neb_metrics_summary's OLD round-then-combine math directly, which
    # would have kept exporting stale/wrong values -- or hit its own
    # cross-check assertion -- the moment the library's default changed).
    key_df = na.compute_key_neb_metrics_summary(
        analysis.dft_valid_path_metrics_df, analysis.fp_path_metrics_by_protocol,
        analysis.dft_path_metrics_df, analysis.full_fp_neb_status_by_fp_path,
        analysis.endpoint_rmsd_by_fp_protocol_path,
        na.pd.DataFrame([{"ICSD": int(k.split("|")[0]), "Path": int(k.split("|")[1])}
                          for k in reference_data["common_pathway_keys"]]),
        analysis.dft_neb_images_by_path, analysis.full_fp_neb_images_by_fp_path,
        analysis.fp_static_on_dft_neb_images_by_fp_path, fp_order, OUTLIER_THRESHOLD,
        area_between_curves, simplify_class, barrier_combination=barrier_combination,
    )

    endpoint_rmsd_fields_by_fp = compute_endpoint_rmsd_leaderboard_fields(analysis, na, fp_order)

    records = []
    for fp_key in fp_order:
        conv = analysis.full_fp_neb_convergence_summary[fp_key][na.PROTOCOL_FULL_FP_NEB]
        n_total = int(conv["n_total"])
        n_not_conv = int(conv["n_neb_not_conv"])

        barrier_mae_full, barrier_rmse_full = (
            float(v) for v in key_df.loc[fp_key, "Barrier error (eV) (full)"].split(" / "))
        barrier_mae_static, barrier_rmse_static = (
            float(v) for v in key_df.loc[fp_key, "Barrier error (eV) (static)"].split(" / "))

        ep_dE_mae = float(full_profile_df.loc[fp_key, "Endpoint ΔE MAE (eV)"])
        ep_dE_rmse = float(full_profile_df.loc[fp_key, "Endpoint ΔE RMSE (eV)"])
        ep_rank_pct = float(full_profile_df.loc[fp_key, "Endpoint Energy Ranking Accuracy (%)"])
        shape_pct = float(full_profile_df.loc[fp_key, "Pathway Topology Accuracy (%)"])

        expected_nonconv = key_df.loc[fp_key, "Non-conv. paths (n/total)"]
        assert expected_nonconv == f"{n_not_conv}/{n_total}", (fp_key, expected_nonconv, n_not_conv, n_total)

        # Cross-check the pooled (img0 + img_last) endpoint-RMSD mean against
        # compute_barrier_error_summaries's own already-computed, separately
        # tracked mean_RMSD_img0/mean_RMSD_img_last (same converged
        # population, same underlying compute_endpoint_rmsd data) -- this
        # export's own aggregation must reproduce the real function's numbers,
        # never silently diverge from them.
        rmsd_mean_exported = endpoint_rmsd_fields_by_fp[fp_key]["endpoint_rmsd_mean_angstrom"]
        m0 = full_barrier_df.loc[fp_key, "mean_RMSD_img0"] if "mean_RMSD_img0" in full_barrier_df.columns else float("nan")
        ml = full_barrier_df.loc[fp_key, "mean_RMSD_img_last"] if "mean_RMSD_img_last" in full_barrier_df.columns else float("nan")
        if rmsd_mean_exported is not None and not (na.np.isnan(m0) or na.np.isnan(ml)):
            expected_pooled_mean = (float(m0) + float(ml)) / 2
            assert abs(rmsd_mean_exported - expected_pooled_mean) < 5e-4, (
                fp_key, "endpoint_rmsd_mean_angstrom cross-check failed",
                rmsd_mean_exported, expected_pooled_mean)

        record = {
            "fp_key": fp_key,
            "display_name": FP_DISPLAY_NAMES[fp_key],
            "n_nonconverged": n_not_conv,
            "n_total": n_total,
            "barrier_mae_full_eV": r(barrier_mae_full, na),
            "barrier_rmse_full_eV": r(barrier_rmse_full, na),
            "barrier_mae_static_eV": r(barrier_mae_static, na),
            "barrier_rmse_static_eV": r(barrier_rmse_static, na),
            "endpoint_energy_diff_mae_eV": r(ep_dE_mae, na),
            "endpoint_energy_diff_rmse_eV": r(ep_dE_rmse, na),
            "endpoint_ranking_agreement_pct": r(ep_rank_pct, na),
            "energy_profile_shape_agreement_pct": r(shape_pct, na),
        }
        record.update(endpoint_rmsd_fields_by_fp[fp_key])
        records.append(record)

    leaderboard = {
        "schema_version": "1.0.0",
        "component": "ion_migration_neb",
        "dataset_name": "FP-DeErr ion-migration NEB leaderboard summary",
        "active_pathway_count": len(reference_data["pathways"]),
        "active_dft_reference_image_count": sum(
            len(p["dft_neb_images"]) for p in reference_data["pathways"].values()),
        "units": {"energy": "eV", "angle": "degree"},
        "metric_columns": {
            "n_nonconverged": "Number of full FP-NEB paths (of n_total) that did not satisfy the NEB force-convergence criterion within the maximum optimization steps.",
            "n_total": "Total number of eligible full FP-NEB calculations entering the barrier-error analysis for this FP (common active pathways with a valid DFT-NEB classification and a full_fp_neb result).",
            "barrier_mae_full_eV": ("MAE of forward/backward migration-barrier errors (eV), full FP-NEB workflow over the converged full FP-NEB population: the true pooled MAE over the concatenated forward+backward per-path error array (compute_key_neb_metrics_summary's barrier_combination=\"pooled\", the default)."
                                     if barrier_combination == "pooled" else
                                     "MAE of forward/backward migration-barrier errors (eV), full FP-NEB workflow over the converged full FP-NEB population, reproduced under barrier_combination=\"round_then_average_legacy\" -- forward/backward MAE rounded to 2dp before averaging, matching the originally published (pre-fix) values, NOT the approved pooled convention. This export is a historical reproduction, not the live leaderboard."),
            "barrier_rmse_full_eV": "RMSE of forward/backward migration-barrier errors (eV), full FP-NEB workflow over the converged full FP-NEB population, same pooled combination convention.",
            "barrier_mae_static_eV": "MAE of forward/backward migration-barrier errors (eV), static FP evaluations on the finalized DFT-NEB image structures (not filtered by full FP-NEB convergence).",
            "barrier_rmse_static_eV": "RMSE of forward/backward migration-barrier errors (eV), static FP evaluations on the finalized DFT-NEB image structures (not filtered by full FP-NEB convergence).",
            "endpoint_energy_diff_mae_eV": "MAE of the endpoint energy-difference error (eV, not per atom), full FP-NEB workflow, over the converged full FP-NEB population.",
            "endpoint_energy_diff_rmse_eV": "RMSE of the endpoint energy-difference error (eV, not per atom), full FP-NEB workflow, over the converged full FP-NEB population.",
            "endpoint_ranking_agreement_pct": "Endpoint energy-ranking agreement (%): fraction of the converged full FP-NEB population where the FP identifies the same lower-energy endpoint as DFT (or both classify the endpoints as equal in energy).",
            "energy_profile_shape_agreement_pct": "Energy-profile shape agreement (%): fraction of the converged full FP-NEB population for which the FP reproduces the DFT Normal-Hill energy profile.",
        },
        "endpoint_rmsd_metric_columns": {
            "endpoint_rmsd_n_converged_paths": "Number of full FP-NEB paths with neb_status.neb_converged == true (same convergence source as the barrier-error/endpoint-energy metrics above) and a computable endpoint-RMSD record.",
            "endpoint_rmsd_n_endpoint_attempts": "Number of individual endpoint-structure comparisons attempted (2 per converged path: the initial and final endpoint), the population map_success_pct/mean/max are computed or filtered from.",
            "endpoint_rmsd_map_success_pct": "Map success (%): fraction of endpoint-structure comparisons, over the converged full FP-NEB population, for which pymatgen's StructureMatcher.get_rms_dist found a valid structural mapping between the FP-relaxed and DFT-relaxed endpoint structure (ltol=0.5, stol=0.5, angle_tol=10.0, unchanged from neb_analysis.py). A failed mapping is excluded from the mean/max RMSD below, not counted as RMSD=0.",
            "endpoint_rmsd_mean_angstrom": "Mean RMSD (angstrom) between FP-relaxed and DFT-relaxed endpoint structures, pooling the initial and final endpoints, over the converged full FP-NEB population, restricted to endpoint-structure comparisons with a successful StructureMatcher mapping.",
            "endpoint_rmsd_max_angstrom": "Maximum RMSD (angstrom) over the same population as endpoint_rmsd_mean_angstrom.",
            "endpoint_rmsd_lt_0_05_pct": "Fraction (%) of successfully-mapped endpoint-structure comparisons with RMSD < 0.05 angstrom, over the same population as endpoint_rmsd_mean_angstrom. Same threshold and denominator convention as Phase Stability's own RMSD < 0.05 A column.",
            "endpoint_rmsd_lt_0_10_pct": "Fraction (%) of successfully-mapped endpoint-structure comparisons with RMSD < 0.10 angstrom, over the same population as endpoint_rmsd_mean_angstrom. Same threshold and denominator convention as Phase Stability's own RMSD < 0.10 A column.",
            "endpoint_rmsd_lt_0_20_pct": "Fraction (%) of successfully-mapped endpoint-structure comparisons with RMSD < 0.20 angstrom, over the same population as endpoint_rmsd_mean_angstrom. Same threshold and denominator convention as Phase Stability's own RMSD < 0.20 A column.",
        },
        "fp_order": fp_order,
        "models": records,
        "generation_metadata": {
            "generated_by": "Ion_migration_NEB/scripts/export_neb_leaderboard.py, from neb_analysis.py's build_neb_analysis_results/compute_key_neb_metrics_summary (same functions and rounding order as the analysis notebook)",
            "generation_timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "source_reference_file": str(Path(reference_path).name),
            "source_reference_sha256": ref_sha256,
            "source_results_file": str(Path(results_path).name),
            "source_results_sha256": res_sha256,
        },
    }
    return leaderboard


def write_output(leaderboard, dest_path, force):
    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    new_text = json.dumps(leaderboard, indent=2)
    if dest_path.exists():
        old_text = dest_path.read_text()
        # A regeneration_timestamp_utc-only difference is expected on every
        # run; compare everything else before deciding this is a real change.
        old_obj = json.loads(old_text)
        new_obj = json.loads(new_text)
        old_obj.get("generation_metadata", {}).pop("generation_timestamp_utc", None)
        new_obj_cmp = json.loads(new_text)
        new_obj_cmp.get("generation_metadata", {}).pop("generation_timestamp_utc", None)
        if old_obj != new_obj_cmp and not force:
            raise RuntimeError(
                f"{dest_path} already exists with different content. Refusing to overwrite "
                f"without --force (pass --force to confirm this is an intentional update)."
            )
    dest_path.write_text(new_text)
    print(f"Wrote {dest_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reference", required=True, help="Path to ion_migration_neb_reference.json[.gz]")
    parser.add_argument("--results", required=True, help="Path to the all-FP results file (.json or .json.gz)")
    parser.add_argument("--component-dir", default=".", help="Path to the Ion_migration_NEB/ directory (default: current directory)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing output files even if their content differs")
    parser.add_argument("--fp-keys", default=None,
                         help="Comma-separated subset of FP keys to export in this run, in the order "
                              "given (default: all of FP_ORDER). Needed when a results file declares "
                              "model keys it holds no data for, since an empty placeholder entry is "
                              "still a present key and cannot be scoped out by presence alone.")
    parser.add_argument("--legacy", action="store_true",
                         help="Export under barrier_combination='round_then_average_legacy' instead of the "
                              "default 'pooled'. NEVER pass this for a real leaderboard update -- it exists "
                              "only to regenerate historical reproductions of the pre-fix published values.")
    args = parser.parse_args()

    component_dir = Path(args.component_dir).resolve()
    scripts_dir = component_dir / "scripts"
    sys.path.insert(0, str(scripts_dir))
    import neb_analysis as na
    from neb_plots import area_between_curves, simplify_class

    barrier_combination = "round_then_average_legacy" if args.legacy else "pooled"
    fp_keys = [k.strip() for k in args.fp_keys.split(",") if k.strip()] if args.fp_keys else None
    leaderboard = build_leaderboard(args.reference, args.results, na, area_between_curves, simplify_class,
                                     barrier_combination=barrier_combination, fp_keys=fp_keys)

    component_dest = component_dir / "data" / "ion_migration_neb_leaderboard_summary.json"
    docs_dest = component_dir.parent / "docs" / "data" / "ion_migration_neb_leaderboard_summary.json"

    write_output(leaderboard, component_dest, args.force)
    write_output(leaderboard, docs_dest, args.force)

    print("CROSS-CHECK AGAINST key_neb_metrics_summary_df: ALL PASSED")
    print("CROSS-CHECK endpoint_rmsd_mean_angstrom AGAINST mean_RMSD_img0/mean_RMSD_img_last: ALL PASSED")


if __name__ == "__main__":
    main()
