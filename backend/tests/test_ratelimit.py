from app.ratelimit import RateLimiter


def test_allows_up_to_limit_then_blocks_then_resets_after_window():
    now = [0.0]
    rl = RateLimiter(2, 60.0, clock=lambda: now[0])
    assert rl.allow("a") and rl.allow("a") and not rl.allow("a")
    assert rl.allow("b")                      # other clients are independent
    now[0] = 59.9
    assert not rl.allow("a")
    now[0] = 60.0
    assert rl.allow("a")                      # new window
