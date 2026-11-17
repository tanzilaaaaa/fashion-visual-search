"""Optional demo session login (PRD §11.1): a signed, expiring cookie — no user table."""

from __future__ import annotations

import hmac

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

COOKIE_NAME = "fvs_session"


class SessionSigner:
    def __init__(self, secret: str, max_age_s: int) -> None:
        self._serializer = URLSafeTimedSerializer(secret, salt="fvs-session")
        self.max_age_s = max_age_s

    def issue(self, username: str) -> str:
        return self._serializer.dumps({"u": username})

    def verify(self, token: str | None) -> str | None:
        if not token:
            return None
        try:
            data = self._serializer.loads(token, max_age=self.max_age_s)
        except (BadSignature, SignatureExpired):
            return None
        return data.get("u") if isinstance(data, dict) else None


def credentials_match(username: str, password: str, expected_user: str, expected_password: str) -> bool:
    if not expected_password:
        return False  # login disabled until a password is configured
    user_ok = hmac.compare_digest(username.encode(), expected_user.encode())
    pass_ok = hmac.compare_digest(password.encode(), expected_password.encode())
    return user_ok and pass_ok
