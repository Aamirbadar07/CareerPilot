"""The per-IP limit is the only cost control on routes that spend model calls, so the IP it
counts must be one the caller cannot choose."""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.rate_limit import rate_limit


@pytest.fixture
def limited():
    app = FastAPI()

    @app.get("/x", dependencies=[Depends(rate_limit(2, 3600))])
    def x():
        return {"ok": True}

    return TestClient(app)


def codes(client, calls, **headers):
    return [client.get("/x", headers=headers).status_code for _ in range(calls)]


def test_a_forged_left_hand_entry_cannot_reset_the_limit(limited, monkeypatch):
    """Cloud Run and Render append to X-Forwarded-For, so with one hop in front the caller's
    address is the last entry and anything to its left is whatever the caller typed."""
    monkeypatch.setattr(settings, "trusted_proxy_hops", 1)
    real = "198.51.100.7"
    assert codes(limited, 3, **{"X-Forwarded-For": real}) == [200, 200, 429]
    # a new forged value in front of the appended one: still the same caller
    assert codes(limited, 1, **{"X-Forwarded-For": f"203.0.113.9, {real}"}) == [429]
    # and a different caller still gets its own budget
    assert codes(limited, 1, **{"X-Forwarded-For": "203.0.113.9"}) == [200]


def test_two_hops_skip_the_load_balancer(limited, monkeypatch):
    monkeypatch.setattr(settings, "trusted_proxy_hops", 2)
    real, lb = "198.51.100.7", "203.0.113.1"
    assert codes(limited, 3, **{"X-Forwarded-For": f"forged, {real}, {lb}"}) == [200, 200, 429]


def test_a_header_too_short_for_the_configured_hops_is_ignored(limited, monkeypatch):
    """Rather than fall back to an entry the caller wrote, key on the socket address: one
    shared bucket is a blunt limit, but it cannot be bypassed."""
    monkeypatch.setattr(settings, "trusted_proxy_hops", 2)
    assert codes(limited, 3, **{"X-Forwarded-For": "203.0.113.9"}) == [200, 200, 429]
    assert codes(limited, 1, **{"X-Forwarded-For": "198.51.100.7"}) == [429]


def test_every_x_forwarded_for_line_is_read(limited, monkeypatch):
    """A proxy may add its own X-Forwarded-For line instead of appending to the caller's.
    Reading only the first line means reading only what the caller wrote."""
    monkeypatch.setattr(settings, "trusted_proxy_hops", 1)
    real = "198.51.100.7"
    # starlette joins repeated headers in order, so two lines look like one chain
    sent = [("x-forwarded-for", "forged-by-the-caller"), ("x-forwarded-for", real)]
    codes = [limited.get("/x", headers=sent).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    # a different forgery in front of the same appended address is the same caller
    other = [("x-forwarded-for", "another-forgery"), ("x-forwarded-for", real)]
    assert limited.get("/x", headers=other).status_code == 429
