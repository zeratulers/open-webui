import os, random, string, time
from typing import Dict, Tuple

_EMAIL_CODE_STORE: Dict[str, Tuple[str, float]] = {}
_EXPIRE_SEC = int(os.getenv("EMAIL_CODE_EXPIRE", 600))

def _gen_code(n: int = 6) -> str:
    return "".join(random.choices(string.digits, k=n))

def store_email_code(email: str) -> str:
    code = _gen_code()
    _EMAIL_CODE_STORE[email] = (code, time.time() + _EXPIRE_SEC)
    return code

def verify_email_code(email: str, code: str) -> bool:
    record = _EMAIL_CODE_STORE.get(email)
    if not record:
        return False
    real, expire = record
    if time.time() > expire:
        _EMAIL_CODE_STORE.pop(email, None)
        return False
    ok = real == code
    if ok:
        _EMAIL_CODE_STORE.pop(email, None)
    return ok
