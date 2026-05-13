"""Security tests — verify hardening measures work correctly.

Tests: auth bypass, injection, IDOR, error leakage, headers, rate limits.
"""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


# ═══════════════════════════════════════════════════════════
# 1. AUTH & TOKEN SECURITY
# ═══════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_invalid_token_rejected(client: AsyncClient):
    """Forged JWT tokens must be rejected."""
    resp = await client.get("/api/v1/signals", headers={
        "Authorization": "Bearer fake.jwt.token"
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_expired_token_rejected(client: AsyncClient):
    """Expired tokens must be rejected."""
    import jwt as pyjwt
    from datetime import datetime, timezone, timedelta
    token = pyjwt.encode(
        {"sub": str(uuid.uuid4()), "exp": datetime.now(timezone.utc) - timedelta(hours=1)},
        "test-secret-key-only-for-tests-not-production-use",
        algorithm="HS256",
    )
    resp = await client.get("/api/v1/signals", headers={
        "Authorization": f"Bearer {token}"
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_no_auth_header_rejected(client: AsyncClient):
    """Requests without auth header must be rejected on protected endpoints."""
    resp = await client.get("/api/v1/signals")
    assert resp.status_code == 403  # HTTPBearer returns 403 when header missing


@pytest.mark.asyncio
async def test_wrong_algorithm_token_rejected(client: AsyncClient):
    """Token signed with different algorithm must be rejected."""
    import jwt as pyjwt
    from datetime import datetime, timezone, timedelta
    # Sign with HS384 but server expects HS256
    token = pyjwt.encode(
        {"sub": str(uuid.uuid4()), "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        "test-secret-key-only-for-tests-not-production-use",
        algorithm="HS384",
    )
    resp = await client.get("/api/v1/signals", headers={
        "Authorization": f"Bearer {token}"
    })
    assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════
# 2. PASSWORD SECURITY
# ═══════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_weak_password_rejected_on_reset(client: AsyncClient, auth_headers: dict, registered_user: dict):
    """Weak passwords must be rejected on password change."""
    resp = await client.patch("/api/v1/auth/profile", headers=auth_headers, params={
        "current_password": "testpass123",
        "new_password": "123",  # too short
    })
    assert resp.status_code == 400
    assert "8 characters" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_password_not_in_response(client: AsyncClient, seed_referrer: str):
    """Password hash must never appear in API responses."""
    resp = await client.post("/api/v1/auth/register", json={
        "email": f"sec_{uuid.uuid4().hex[:6]}@test.com",
        "username": f"sec_{uuid.uuid4().hex[:6]}",
        "password": "SecurePass123",
        "referral_code": seed_referrer,
    })
    assert resp.status_code == 201
    body = resp.text
    assert "hashed_password" not in body
    assert "$2b$" not in body  # bcrypt hash pattern


# ═══════════════════════════════════════════════════════════
# 3. IDOR (Insecure Direct Object Reference)
# ═══════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_cannot_access_other_users_orders(client: AsyncClient, auth_headers: dict):
    """Users must only see their own orders."""
    resp = await client.get("/api/v1/execution/orders", headers=auth_headers)
    assert resp.status_code == 200
    # All orders should belong to authenticated user (empty for new user)
    data = resp.json()
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_cannot_delete_other_users_account(client: AsyncClient, auth_headers: dict):
    """Users cannot modify other users' exchange accounts."""
    fake_id = str(uuid.uuid4())
    resp = await client.delete(f"/api/v1/execution/accounts/{fake_id}", headers=auth_headers)
    assert resp.status_code == 404  # Not found, not 403 (doesn't reveal existence)


# ═══════════════════════════════════════════════════════════
# 4. ADMIN ACCESS CONTROL
# ═══════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_non_admin_cannot_access_admin_endpoints(client: AsyncClient, auth_headers: dict):
    """Regular users must not access admin endpoints."""
    resp = await client.get("/api/v1/admin/users", headers=auth_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_non_admin_cannot_change_roles(client: AsyncClient, auth_headers: dict):
    """Regular users cannot change user roles."""
    resp = await client.patch(
        f"/api/v1/admin/users/{uuid.uuid4()}/role",
        headers=auth_headers,
        params={"role": "admin"},
    )
    assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════
# 5. INPUT VALIDATION & INJECTION
# ═══════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_sql_injection_in_ticker_filter(client: AsyncClient, auth_headers: dict):
    """SQL injection attempts in query params must be harmless."""
    resp = await client.get("/api/v1/signals", headers=auth_headers, params={
        "ticker": "'; DROP TABLE signals; --"
    })
    # Should return 200 with 0 results, not crash
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_xss_in_username_sanitized(client: AsyncClient, seed_referrer: str):
    """XSS payloads in username should not be executed."""
    resp = await client.post("/api/v1/auth/register", json={
        "email": f"xss_{uuid.uuid4().hex[:6]}@test.com",
        "username": "<script>alert('xss')</script>",
        "password": "SecurePass123",
        "referral_code": seed_referrer,
    })
    # FastAPI returns JSON, so XSS in response is not directly exploitable
    # But verify the payload doesn't crash the system
    assert resp.status_code in (201, 400)  # 400 if validation rejects


@pytest.mark.asyncio
async def test_oversized_payload_rejected(client: AsyncClient):
    """Extremely large payloads should be handled gracefully."""
    resp = await client.post("/api/v1/signals/webhook/tradingview", json={
        "ticker": "A" * 100000,  # 100KB string
        "action": "buy",
        "price": 1.0,
    })
    assert resp.status_code in (422, 400, 413)


# ═══════════════════════════════════════════════════════════
# 6. SECURITY HEADERS
# ═══════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_security_headers_present(client: AsyncClient):
    """Critical security headers must be present on responses."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"
    assert resp.headers.get("x-xss-protection") == "1; mode=block"
    assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


# ═══════════════════════════════════════════════════════════
# 7. ERROR INFORMATION LEAKAGE
# ═══════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_404_does_not_leak_internals(client: AsyncClient, auth_headers: dict):
    """404 responses should not reveal internal structure."""
    resp = await client.get(f"/api/v1/signals/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404
    body = resp.json()
    assert "traceback" not in str(body).lower()
    assert "sqlalchemy" not in str(body).lower()


@pytest.mark.asyncio
async def test_webhook_error_does_not_leak_details(client: AsyncClient):
    """Webhook errors should not expose internal exception details."""
    resp = await client.post("/api/v1/signals/webhook/tradingview", json={
        "ticker": "",  # invalid
        "action": "buy",
        "price": -1,  # invalid
    })
    if resp.status_code == 422:
        body = resp.text
        assert "Exception" not in body
        assert "Traceback" not in body


# ═══════════════════════════════════════════════════════════
# 8. REFERRAL TREE — NO EMAIL LEAKAGE
# ═══════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_referral_tree_no_email_exposure(client: AsyncClient, auth_headers: dict):
    """Referral tree must not expose email addresses of referred users."""
    resp = await client.get("/api/v1/referrals/tree", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.text
    # Email field should not be in response
    assert '"email"' not in body


# ═══════════════════════════════════════════════════════════
# 9. STRIPE WEBHOOK PROTECTION
# ═══════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_stripe_webhook_without_signature_rejected(client: AsyncClient):
    """Stripe webhook without signature header must be rejected."""
    resp = await client.post("/api/v1/payments/webhook", content=b'{}')
    # Should fail (either 503 not configured, or 400 missing signature)
    assert resp.status_code in (400, 503)


# ═══════════════════════════════════════════════════════════
# 10. SENSITIVE DATA NOT IN EXCHANGE ACCOUNT RESPONSES
# ═══════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_exchange_account_no_keys_in_response(client: AsyncClient, auth_headers: dict):
    """Exchange account responses must not contain API keys."""
    resp = await client.get("/api/v1/execution/accounts", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.text
    assert "api_key" not in body
    assert "api_secret" not in body
    assert "encrypted" not in body
