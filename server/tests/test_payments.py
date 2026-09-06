"""payments 验签单元测试（C3）

用本地构造的 channel secret + body 自洽验证 HMAC 验签管线，
不依赖真实 LINE 凭据；凭据就位后此测试可直接作为回归基线。
"""

import asyncio
import base64
import hashlib
import hmac
import json

import pytest

from app.services.payments import LinePayProvider, PaymentVerificationError, NotConfigured
from config import get_settings

SECRET = "unit-test-channel-secret-0123456789"
CHANNEL_ID = "test-channel-id"


def _sign(body: str) -> str:
    sig = base64.b64encode(
        hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).digest()
    ).decode("ascii")
    return f"{body} {sig}"


@pytest.fixture
def provider_env(monkeypatch):
    settings = get_settings()
    old = (settings.LINE_PAY_CHANNEL_ID, settings.LINE_PAY_CHANNEL_SECRET)
    settings.LINE_PAY_CHANNEL_ID = CHANNEL_ID
    settings.LINE_PAY_CHANNEL_SECRET = SECRET
    yield LinePayProvider()
    settings.LINE_PAY_CHANNEL_ID, settings.LINE_PAY_CHANNEL_SECRET = old


def run(coro):
    return asyncio.run(coro)


def test_verify_ok(provider_env):
    body = json.dumps({"transactionId": "TX-1", "amount": 330})
    info = run(
        provider_env.verify(
            body.encode(),
            {"x-line-channelid": CHANNEL_ID, "x-line-authorization": _sign(body)},
        )
    )
    assert info["transaction_id"] == "TX-1"


def test_verify_rejects_forged_signature(provider_env):
    body = json.dumps({"transactionId": "TX-1", "amount": 330})
    forged = _sign(body)[:-4] + "AAAA"  # 篡改签名值
    with pytest.raises(PaymentVerificationError):
        run(
            provider_env.verify(
                body.encode(),
                {"x-line-channelid": CHANNEL_ID, "x-line-authorization": forged},
            )
        )


def test_verify_rejects_wrong_channel(provider_env):
    body = json.dumps({"transactionId": "TX-1"})
    with pytest.raises(PaymentVerificationError):
        run(
            provider_env.verify(
                body.encode(),
                {"x-line-channelid": "other", "x-line-authorization": _sign(body)},
            )
        )


def test_verify_missing_auth_header(provider_env):
    body = json.dumps({"transactionId": "TX-1"})
    with pytest.raises(PaymentVerificationError):
        run(provider_env.verify(body.encode(), {"x-line-channelid": CHANNEL_ID}))


def test_verify_not_configured(monkeypatch):
    settings = get_settings()
    old = (settings.LINE_PAY_CHANNEL_ID, settings.LINE_PAY_CHANNEL_SECRET)
    settings.LINE_PAY_CHANNEL_ID = ""
    settings.LINE_PAY_CHANNEL_SECRET = ""
    try:
        with pytest.raises(NotConfigured):
            run(LinePayProvider().verify(b"{}", {}))
    finally:
        settings.LINE_PAY_CHANNEL_ID, settings.LINE_PAY_CHANNEL_SECRET = old
