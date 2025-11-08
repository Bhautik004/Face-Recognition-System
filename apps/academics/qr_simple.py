import base64, hmac, hashlib, json, time

def _b64url_decode(s: str) -> bytes:
    # add '=' padding if needed
    pad = (-len(s)) % 4
    return base64.urlsafe_b64decode(s + ("=" * pad))

def _b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")

def verify_qr_token(token: str, secret: str):
    """
    Verifies "<b64url(json)>.<b64url(hmac_sha256(json, secret))>"
    Returns (payload_dict) if valid, else raises ValueError.
    """
    if not token or "." not in token:
        raise ValueError("Malformed token")

    left, right = token.split(".", 1)
    raw = _b64url_decode(left)
    sig = _b64url_decode(right)

    expect = hmac.new(secret.encode(), raw, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expect):
        raise ValueError("Bad signature")

    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        raise ValueError("Bad JSON")

    # Basic required fields
    for k in ("sid", "rid", "iat", "exp"):
        if k not in payload:
            raise ValueError(f"Missing {k}")

    now = int(time.time())
    if int(payload["exp"]) < now:
        raise ValueError("Expired")

    return payload  # {sid, rid, iat, exp, nonce?}
