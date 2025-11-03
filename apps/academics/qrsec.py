import base64, hmac, hashlib, json, time

def make_qr_token(session_id: int, room_id: int, step_seconds: int, secret: str, now=None):
    """
    Rolling token valid for current 10s (or step) window.
    """
    now = int(now or time.time())
    issued_slot = now - (now % step_seconds)         # 10s slot start
    exp = issued_slot + step_seconds

    payload = {
        "sid": session_id,
        "rid": room_id,
        "iat": issued_slot,
        "exp": exp,
        "nonce": issued_slot,  # slot-based nonce
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    sig = hmac.new(secret.encode(), raw, hashlib.sha256).digest()
    tok = base64.urlsafe_b64encode(raw).rstrip(b"=") + b"." + base64.urlsafe_b64encode(sig).rstrip(b"=")
    return tok.decode(), payload
