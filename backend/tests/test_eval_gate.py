"""CI eval gate: the committed evaluation results must still meet the claims the README and website make.

This does NOT retrain or re-run anything (CI has no GPU, no datasets, no model files). It checks the recorded
results in evals/*.json, so a change that regresses a headline number, or a result file edited by hand to look
better than the code produced, has to be noticed and explained in a commit.

Thresholds are set with a little room below today's numbers. Loosening one is a visible, reviewable decision.
"""

import json
from pathlib import Path

import pytest

EVALS = Path(__file__).resolve().parents[2] / "evals"


def load(name: str) -> dict:
    path = EVALS / name
    if not path.exists():
        pytest.skip(f"{name} is not in this checkout")
    return json.loads(path.read_text())


def test_crop_gate_accepts_leaves_rejects_objects_and_beats_the_confidence_shortcut():
    g = load("crop_gate.json")
    assert g["clip_gate"]["true_positive_rate"] >= 0.98
    assert g["clip_gate"]["false_positive_rate"] <= 0.03
    assert g["clip_gate"]["auroc"] >= 0.99
    assert g["clip_gate"]["auroc"] > g["baseline_classifier_confidence"]["auroc"] + 0.2


def test_the_deployed_onnx_models_still_agree_with_pytorch():
    p = load("onnx_parity.json")
    assert p["classifier"]["top1_label_agreement"] >= 0.99
    assert p["severity"]["grade_agreement"] >= 0.98
    assert p["gate"]["decision_agreement_at_0.5"] >= 0.99
    assert p["gate"]["onnx_int8"]["true_positive_rate"] >= 0.97
    assert p["gate"]["onnx_int8"]["false_positive_rate"] <= 0.03


def test_severity_model_beats_both_baselines():
    s = load("severity.json")
    learned, naive, colour = s["learned_segmentation"], s["naive_mean_baseline"], s["colour_threshold_baseline"]
    assert learned["grade_accuracy"] >= naive["grade_accuracy"] + 0.25
    assert learned["grade_accuracy"] > colour["grade_accuracy"]
    assert learned["severity_mae_points"] < naive["severity_mae_points"]


def test_adding_field_photos_still_helps_a_lot_on_held_out_field_photos():
    f = load("field_tuned.json")
    lab_only = f["held_out_field_lab_only_baseline"]["accuracy"]
    tuned = f["held_out_field_field_tuned"]
    assert tuned["accuracy"] >= lab_only + 0.20
    assert tuned["accuracy"] > tuned["majority_baseline_accuracy"] * 3


def test_the_lab_to_field_gap_is_still_reported_honestly():
    b = load("baseline_lab_vs_field.json")
    assert b["lab_test"]["accuracy"] - b["field_test"]["accuracy"] >= 0.5   # the gap is the point; do not hide it


def test_market_agent_is_not_worse_than_naive_and_its_ranges_are_roughly_calibrated():
    m = load("market_forecast.json")
    assert m["mean_error_pct"]["agent"] <= m["mean_error_pct"]["naive_baseline"] * 1.05
    cov = m["range_coverage"]["observed_all_horizons"]
    assert 0.70 <= cov <= 0.95, f"80% ranges contained the outcome {cov:.0%} of the time"


def test_every_result_file_that_the_website_shows_is_present_and_nonempty():
    for name in ("baseline_lab_vs_field.json", "field_tuned.json", "cotton_cross_source.json", "severity.json", "crop_gate.json", "corn_field.json", "market_forecast.json"):
        assert load(name), name
