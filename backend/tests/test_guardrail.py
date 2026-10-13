from rag.guardrail import Citation, Recommendation, Status, check

# Fake fixtures: these tests supply their OWN lists and sources; they make no claim about real registrations.
REGISTERED = {"alphamethrin", "Tebuconazole"}
BANNED = {"oldpoison"}
SOURCES = {
    "advisory-1": "For yellow rust, spray Tebuconazole at 200 ml per acre.\nWear gloves and a face mask while mixing.",
}
GOOD = Citation("advisory-1", "spray tebuconazole at 200 ml per acre")


def rec(**kw):
    base = dict(active_ingredient="Tebuconazole", dose="200 ml per acre", citations=(GOOD,))
    return Recommendation(**{**base, **kw})


def test_registered_dose_cited_is_approved():
    assert check(rec(), REGISTERED, BANNED, SOURCES).status is Status.APPROVED


def test_matching_ignores_case_and_whitespace():
    r = rec(active_ingredient="  TEBUCONAZOLE ", citations=(Citation("advisory-1", "Spray   Tebuconazole\nat 200 ML per acre"),))
    assert check(r, REGISTERED, BANNED, SOURCES).status is Status.APPROVED


def test_banned_is_rejected_even_if_also_registered_and_well_cited():
    v = check(rec(active_ingredient="oldpoison"), REGISTERED | {"oldpoison"}, BANNED, SOURCES)
    assert v.status is Status.REJECTED and "banned" in v.reasons[0]


def test_unregistered_is_rejected():
    v = check(rec(active_ingredient="mysterychem"), REGISTERED, BANNED, SOURCES)
    assert v.status is Status.REJECTED and "not on the registered list" in v.reasons[0]


def test_dose_without_any_citation_is_rejected():
    v = check(rec(citations=()), REGISTERED, BANNED, SOURCES)
    assert v.status is Status.REJECTED and "dose" in v.reasons[0]


def test_invented_quote_not_in_source_is_rejected():
    fake = Citation("advisory-1", "spray tebuconazole at 500 ml per acre")
    assert check(rec(citations=(fake,)), REGISTERED, BANNED, SOURCES).status is Status.REJECTED


def test_unknown_source_id_is_rejected():
    assert check(rec(citations=(Citation("ghost", GOOD.quote),)), REGISTERED, BANNED, SOURCES).status is Status.REJECTED


def test_real_quote_that_does_not_contain_the_dose_is_rejected():
    other = Citation("advisory-1", "wear gloves and a face mask while mixing")
    assert check(rec(citations=(other,)), REGISTERED, BANNED, SOURCES).status is Status.REJECTED


def test_empty_quote_never_counts():
    assert check(rec(citations=(Citation("advisory-1", "  "),)), REGISTERED, BANNED, SOURCES).status is Status.REJECTED


def test_ppe_must_also_be_cited():
    mask = Citation("advisory-1", "wear gloves and a face mask while mixing")
    ok = rec(ppe=("gloves and a face mask",), citations=(GOOD, mask))
    assert check(ok, REGISTERED, BANNED, SOURCES).status is Status.APPROVED
    bad = rec(ppe=("full chemical suit",), citations=(GOOD, mask))
    v = check(bad, REGISTERED, BANNED, SOURCES)
    assert v.status is Status.REJECTED and "PPE" in v.reasons[0]


def test_no_dose_given_is_allowed_but_flagged():
    v = check(Recommendation(active_ingredient="Tebuconazole"), REGISTERED, BANNED, SOURCES)
    assert v.status is Status.NO_DOSE and "extension office" in v.reasons[0]


def _approved(dose, quote, source):
    r = Recommendation(active_ingredient="Tebuconazole", dose=dose, citations=(Citation("s", quote),))
    return check(r, REGISTERED, BANNED, {"s": source}).status


def test_dose_is_not_accepted_as_the_tail_of_a_bigger_number():
    # "20 ml" appears inside "120 ml": a different, 6x larger dose. Must not match.
    assert _approved("20 ml per acre", "use 120 ml per acre", "use 120 ml per acre") is Status.REJECTED
    assert _approved("5 ml per litre", "use 0.5 ml per litre", "use 0.5 ml per litre") is Status.REJECTED


def test_quote_is_not_accepted_when_it_is_only_the_tail_of_a_bigger_number_in_the_source():
    assert _approved("200 ml per acre", "200 ml per acre", "use 1200 ml per acre") is Status.REJECTED
    assert _approved("200 ml per acre", "200 ml per acre", "use 200 ml per acre today") is Status.APPROVED


def test_decimal_continuation_is_not_a_match():
    assert _approved("2 g per litre", "2 g per litre", "use 2 g per litre.") is Status.APPROVED  # sentence end is fine
    assert _approved("20", "use 20", "use 20.5 g") is Status.REJECTED
