"""Tests for agora rate_limit module — extracted from SharedBrain D_Gateway."""

import time

from agora.rate_limit import RateLimitConfig, RateLimiter, TokenBucket


def test_config_defaults_to_minute():
    config = RateLimitConfig()
    limit, unit = config.get_primary_limit()
    assert unit == "minute"
    assert limit == 100


def test_config_prefers_per_second():
    config = RateLimitConfig(requests_per_second=50, requests_per_minute=100)
    limit, unit = config.get_primary_limit()
    assert unit == "second"
    assert limit == 50


def test_token_bucket_can_consume():
    bucket = TokenBucket(capacity=10, tokens=10.0, refill_rate=1.0)
    assert bucket.consume()
    assert bucket.get_available_tokens() == 9


def test_token_bucket_empty_denies():
    bucket = TokenBucket(capacity=1, tokens=0.0, refill_rate=0.1)
    assert not bucket.consume()


def test_token_bucket_refills_over_time():
    bucket = TokenBucket(capacity=10, tokens=0.0, refill_rate=100.0)
    time.sleep(0.05)  # refill ~5 tokens
    assert bucket.consume()


def test_token_bucket_wait_time():
    bucket = TokenBucket(capacity=10, tokens=0.0, refill_rate=10.0)
    wait = bucket.get_wait_time(tokens=5)
    assert wait > 0.0
    bucket2 = TokenBucket(capacity=10, tokens=10.0, refill_rate=1.0)
    assert bucket2.get_wait_time(tokens=1) == 0.0


def test_rate_limiter_allows_and_denies():
    limiter = RateLimiter()
    config = RateLimitConfig(requests_per_second=2, burst=0)
    key = "test-client:/api/test"

    assert limiter.is_allowed(key, config)
    limiter.clear_all()


def test_rate_limiter_per_key_isolation():
    limiter = RateLimiter()
    config = RateLimitConfig(requests_per_second=1, burst=0)

    assert limiter.is_allowed("client-a:/api", config)
    assert not limiter.is_allowed("client-a:/api", config)
    assert limiter.is_allowed("client-b:/api", config)
    limiter.clear_all()


def test_rate_limiter_bucket_info():
    limiter = RateLimiter()
    config = RateLimitConfig(requests_per_second=10, burst=10)
    limiter.is_allowed("test:/api", config)

    info = limiter.get_bucket_info("test:/api")
    assert info is not None
    assert info["capacity"] == 20  # 10 + 10 burst
    limiter.clear_all()


def test_rate_limiter_reset():
    limiter = RateLimiter()
    config = RateLimitConfig(requests_per_second=1, burst=0)
    limiter.is_allowed("r:/api", config)
    assert not limiter.is_allowed("r:/api", config)
    limiter.reset_bucket("r:/api")
    assert limiter.is_allowed("r:/api", config)
    limiter.clear_all()
