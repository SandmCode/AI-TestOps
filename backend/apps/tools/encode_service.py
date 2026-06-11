"""编码、解码与摘要哈希工具。"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import html
import re
from urllib.parse import quote, unquote

ENCODE_ACTIONS: list[dict[str, str]] = [
    {"value": "base64_encode", "label": "Base64 编码", "group": "编解码", "desc": "文本 → Base64"},
    {"value": "base64_decode", "label": "Base64 解码", "group": "编解码", "desc": "Base64 → 文本"},
    {"value": "url_encode", "label": "URL 编码", "group": "编解码", "desc": "百分号编码，用于 Query 参数"},
    {"value": "url_decode", "label": "URL 解码", "group": "编解码", "desc": "解码 %XX 序列"},
    {"value": "unicode_encode", "label": "Unicode 编码", "group": "编解码", "desc": "转为 \\uXXXX 形式"},
    {"value": "unicode_decode", "label": "Unicode 解码", "group": "编解码", "desc": "解析 \\uXXXX"},
    {"value": "hex_encode", "label": "Hex 编码", "group": "编解码", "desc": "字节 → 十六进制"},
    {"value": "hex_decode", "label": "Hex 解码", "group": "编解码", "desc": "十六进制 → 文本"},
    {"value": "html_encode", "label": "HTML 实体编码", "group": "编解码", "desc": "<>& 等转义"},
    {"value": "html_decode", "label": "HTML 实体解码", "group": "编解码", "desc": "还原 HTML 实体"},
    {"value": "md5", "label": "MD5", "group": "摘要哈希", "desc": "32 位十六进制，不可逆"},
    {"value": "sha1", "label": "SHA-1", "group": "摘要哈希", "desc": "40 位十六进制，不可逆"},
    {"value": "sha256", "label": "SHA-256", "group": "摘要哈希", "desc": "64 位十六进制，不可逆"},
    {"value": "sha512", "label": "SHA-512", "group": "摘要哈希", "desc": "128 位十六进制，不可逆"},
    {"value": "hmac_sha256", "label": "HMAC-SHA256", "group": "摘要哈希", "desc": "带密钥的签名摘要"},
]

HASH_ACTIONS = frozenset({"md5", "sha1", "sha256", "sha512", "hmac_sha256"})


def get_encode_meta() -> dict:
    return {"actions": ENCODE_ACTIONS}


def _digest(text: str, algorithm: str, salt: str = "") -> str:
    payload = f"{salt}{text}" if salt else text
    return hashlib.new(algorithm, payload.encode("utf-8")).hexdigest()


def encode_convert(action: str, text: str, extra: dict | None = None) -> str:
    extra = extra or {}
    salt = str(extra.get("salt") or "")
    secret = str(extra.get("secret") or "")

    if action == "base64_encode":
        return base64.b64encode(text.encode("utf-8")).decode("ascii")
    if action == "base64_decode":
        raw = text.strip()
        padding = (-len(raw)) % 4
        if padding:
            raw += "=" * padding
        return base64.b64decode(raw.encode("ascii")).decode("utf-8")
    if action == "url_encode":
        return quote(text, safe="")
    if action == "url_decode":
        return unquote(text)
    if action == "unicode_encode":
        return text.encode("unicode_escape").decode("ascii")
    if action == "unicode_decode":
        return text.encode("utf-8").decode("unicode_escape")
    if action == "hex_encode":
        return text.encode("utf-8").hex()
    if action == "hex_decode":
        cleaned = re.sub(r"\s+", "", text.strip())
        if cleaned.startswith("0x"):
            cleaned = cleaned[2:]
        return bytes.fromhex(cleaned).decode("utf-8")
    if action == "html_encode":
        return html.escape(text)
    if action == "html_decode":
        return html.unescape(text)
    if action == "md5":
        return _digest(text, "md5", salt)
    if action == "sha1":
        return _digest(text, "sha1", salt)
    if action == "sha256":
        return _digest(text, "sha256", salt)
    if action == "sha512":
        return _digest(text, "sha512", salt)
    if action == "hmac_sha256":
        key = secret or salt
        if not key:
            raise ValueError("HMAC-SHA256 需要填写密钥（salt/secret）")
        return hmac.new(key.encode("utf-8"), text.encode("utf-8"), hashlib.sha256).hexdigest()

    raise ValueError(f"未知操作: {action}")
