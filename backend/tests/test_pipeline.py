from app.pipeline import ABSTAIN_THRESHOLD, DiagnosisResult, Prediction, diagnose, is_healthy_label
from vision.severity import grade


def run(gate=0.9, label="Tomato___Late_blight", conf=0.95, sev=0.2, **kw):
    calls = []

    def g(img):
        calls.append("gate"); return gate

    def c(img):
        calls.append("classifier"); return Prediction(label, conf)

    def s(img):
        calls.append("severity"); return sev

    return diagnose("img", g, c, s, grade, **kw), calls


def test_not_a_crop_stops_before_the_classifier():
    result, calls = run(gate=0.1)
    assert result.status == "not_a_crop" and calls == ["gate"] and result.label is None


def test_low_confidence_abstains_and_refers_to_extension_office():
    result, calls = run(conf=0.5)
    assert result.status == "uncertain" and result.label is None
    assert "extension office" in result.message and calls == ["gate", "classifier"]


def test_confident_disease_gets_label_severity_grade_and_limitations():
    result, calls = run(conf=0.97, sev=0.35)
    assert result.status == "diagnosis" and result.label == "Tomato___Late_blight"
    assert result.severity == 0.35 and result.severity_grade == "severe"
    assert calls == ["gate", "classifier", "severity"]
    assert any("Wheat and cotton are NOT covered" in x for x in result.limitations)
    assert any("Severity was trained" in x for x in result.limitations)
    assert "preliminary" in result.message.lower()


def test_healthy_leaf_skips_severity():
    result, calls = run(label="Apple___healthy", conf=0.99)
    assert result.is_healthy is True and result.severity is None and "severity" not in calls


def test_boundary_values_are_inclusive_for_answering():
    assert run(conf=ABSTAIN_THRESHOLD)[0].status == "diagnosis"
    assert run(conf=ABSTAIN_THRESHOLD - 1e-6)[0].status == "uncertain"
    assert run(gate=0.5)[0].status == "diagnosis" and run(gate=0.4999)[0].status == "not_a_crop"


def test_every_answered_result_says_no_treatment_advice_yet():
    result, _ = run()
    assert any("Treatment advice exists only for cotton" in x for x in result.limitations)


def test_is_healthy_label():
    assert is_healthy_label("Apple___healthy") and not is_healthy_label("Apple___Black_rot")


def test_result_is_a_plain_dataclass():
    assert isinstance(run()[0], DiagnosisResult)


# ---------- crop hint: only used when the classifier abstains ----------
def test_abstain_names_an_uncovered_crop_when_the_hint_is_confident():
    result, _ = run(conf=0.5, crop_hint=lambda img: ("wheat ears", 0.8))
    assert result.status == "uncertain" and result.detected_crop == "wheat ears" and result.label is None
    assert "might be wheat ears" in result.message and "will not guess" in result.message and "extension office" in result.message


def test_hint_is_ignored_when_unsure_other_or_a_covered_crop():
    for hint in [("wheat ears", 0.5), ("other", 0.9), ("vegetable or fruit plant", 0.9), ("maize", 0.9)]:
        result, _ = run(conf=0.5, crop_hint=lambda img, h=hint: h)
        assert result.detected_crop is None and result.message.startswith("I am not sure what this is")


def test_hint_never_runs_when_the_classifier_is_confident_or_the_photo_is_not_a_crop():
    boom = lambda img: (_ for _ in ()).throw(AssertionError("hint must not run"))
    assert run(conf=0.95, crop_hint=boom)[0].status == "diagnosis"
    assert run(gate=0.1, crop_hint=boom)[0].status == "not_a_crop"
