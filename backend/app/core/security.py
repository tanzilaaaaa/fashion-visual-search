"""Session cookies: an HMAC-signed, expiring token carrying the user id (itsdangerous)."""

from __future__ import annotations

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

COOKIE_NAME = "fvs_session"


class SessionSigner:
    def __init__(self, secret: str, max_age_s: int) -> None:
        self._serializer = URLSafeTimedSerializer(secret, salt="fvs-session")
        self.max_age_s = max_age_s

    def issue(self, user_id: int) -> str:
        return self._serializer.dumps({"uid": int(user_id)})

    def verify(self, token: str | None) -> int | None:
        if not token:
            return None
        try:
            data = self._serializer.loads(token, max_age=self.max_age_s)
        except (BadSignature, SignatureExpired):
            return None
        uid = data.get("uid") if isinstance(data, dict) else None
        return uid if isinstance(uid, int) else None
