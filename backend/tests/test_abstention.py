from vision.abstention import best_coverage_at_accuracy, coverage_accuracy_curve, operating_point

CONF = [0.95, 0.90, 0.80, 0.60, 0.55]
OK = [True, True, True, False, False]


def test_operating_point_counts_only_confident_answers():
    p = operating_point(CONF, OK, 0.7)
    assert p.coverage == 0.6 and p.selective_accuracy == 1.0


def test_threshold_above_everything_answers_nothing():
    p = operating_point(CONF, OK, 0.99)
    assert p.coverage == 0.0 and p.selective_accuracy is None


def test_zero_threshold_answers_everything_with_overall_accuracy():
    p = operating_point(CONF, OK, 0.0)
    assert p.coverage == 1.0 and p.selective_accuracy == 0.6


def test_curve_coverage_never_increases_as_threshold_rises():
    coverages = [p.coverage for p in coverage_accuracy_curve(CONF, OK)]
    assert coverages == sorted(coverages, reverse=True)


def test_best_coverage_at_accuracy_picks_largest_coverage_meeting_target():
    p = best_coverage_at_accuracy(CONF, OK, 0.99)
    assert p is not None and p.threshold == 0.80 and p.coverage == 0.6


def test_best_coverage_returns_none_when_target_unreachable():
    assert best_coverage_at_accuracy([0.9, 0.8], [False, False], 0.5) is None
