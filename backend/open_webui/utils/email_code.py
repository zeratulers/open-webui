import os, random, string, time
import logging
from typing import Dict, Tuple

log = logging.getLogger(__name__)

# 存储邮箱验证码和过期时间
_EMAIL_CODE_STORE: Dict[str, Tuple[str, float]] = {}
# 存储邮箱上次发送验证码的时间
_EMAIL_LAST_SENT: Dict[str, float] = {}
# 验证码有效期（秒）
_EXPIRE_SEC = int(os.getenv("EMAIL_CODE_EXPIRE", 600))

def _gen_code(n: int = 6) -> str:
    return "".join(random.choices(string.digits, k=n))

def store_email_code(email: str) -> str:
    """生成并存储邮箱验证码"""
    code = _gen_code()
    _EMAIL_CODE_STORE[email.lower()] = (code, time.time() + _EXPIRE_SEC)
    _EMAIL_LAST_SENT[email.lower()] = time.time()
    log.info(f"[DEBUG] Stored email code '{code}' for email '{email}'")
    return code

def verify_email_code(email: str, code: str) -> bool:
    """验证邮箱验证码"""
    record = _EMAIL_CODE_STORE.get(email.lower())
    if not record:
        return False
    stored_code, expire = record
    if time.time() > expire:
        _EMAIL_CODE_STORE.pop(email.lower(), None)
        return False
    ok = stored_code == code
    if ok:
        _EMAIL_CODE_STORE.pop(email.lower(), None)
    return ok

def need_captcha_for_email(email: str) -> bool:
    """判断是否需要图形验证码才能发送邮箱验证码
    如果在5分钟内重复发送，则需要图形验证码
    """
    last_sent = _EMAIL_LAST_SENT.get(email.lower())
    if last_sent is None:
        return False
    return (time.time() - last_sent) < _EXPIRE_SEC
