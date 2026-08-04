def test_rate_limiter_blocks_after_limit():
    from app.core.ratelimit import RateLimiter

    t = [0.0]
    rl = RateLimiter(3, 60, clock=lambda: t[0])
    assert all(rl.hit("1.2.3.4") for _ in range(3))
    assert not rl.hit("1.2.3.4")


def test_rate_limiter_window_expiry_frees():
    from app.core.ratelimit import RateLimiter

    t = [0.0]
    rl = RateLimiter(2, 60, clock=lambda: t[0])
    rl.hit("ip")
    rl.hit("ip")
    assert not rl.hit("ip")
    t[0] = 61.0
    assert rl.hit("ip")


def test_rate_limiter_keys_independent():
    from app.core.ratelimit import RateLimiter

    rl = RateLimiter(1, 60)
    assert rl.hit("a")
    assert rl.hit("b")
    assert not rl.hit("a")


def test_rate_limiter_reset():
    from app.core.ratelimit import RateLimiter

    rl = RateLimiter(1, 60)
    rl.hit("a")
    rl.reset("a")
    assert rl.hit("a")
