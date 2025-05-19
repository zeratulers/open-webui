import io, os, time, random, string
import base64
from captcha.image import ImageCaptcha
from typing import Dict, Tuple

_CAPTCHA_STORE: Dict[str, Tuple[str, float]] = {}
_EXPIRE_SEC = int(os.getenv("CAPTCHA_EXPIRE", 300))

def _gen_code(n: int = 4) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))

def create_captcha() -> Tuple[str, str]:
    code = _gen_code()
    token = _gen_code(10)
    _CAPTCHA_STORE[token] = (code.lower(), time.time() + _EXPIRE_SEC)

    img = ImageCaptcha(width=200, height=60)
    buf = io.BytesIO()
    img.write(code, buf)
    b64_bytes = base64.b64encode(buf.getvalue())
    b64_string = b64_bytes.decode('utf-8')
    b64 = "data:image/png;base64," + b64_string
    return token, b64

def verify_captcha(token: str, user_code: str) -> bool:
    record = _CAPTCHA_STORE.get(token)
    if not record:
        return False
    code, expire = record
    if time.time() > expire:
        _CAPTCHA_STORE.pop(token, None)
        return False
    ok = code == user_code.lower()
    if ok:
        _CAPTCHA_STORE.pop(token, None)
    return ok
