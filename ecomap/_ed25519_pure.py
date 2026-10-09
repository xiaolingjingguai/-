"""纯 Python 实现的 Ed25519 签名验证（仅验证，不含私钥运算）。

依据 RFC 8032（Edwards-Curve Digital Signature Algorithm）。本模块不依赖任何
第三方库，便于随被保护程序一起用 PyInstaller 打包，且不改变现有打包依赖。

作者端签发许可证时使用 cryptography 库生成签名（见 tools/license_issuer.py），
本模块负责在被保护程序内离线验证该签名。两者均遵循 RFC 8032，可互操作。
"""
import hashlib

_P = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493  # 群阶
_D = (-121665 * pow(121666, _P - 2, _P)) % _P
_I = pow(2, (_P - 1) // 4, _P)  # sqrt(-1) mod p


def _inv(x):
    return pow(x, _P - 2, _P)


def _xrecover(y):
    xx = (y * y - 1) * _inv(_D * y * y + 1) % _P
    x = pow(xx, (_P + 3) // 8, _P)
    if (x * x - xx) % _P != 0:
        x = (x * _I) % _P
    if x % 2 != 0:
        x = _P - x
    return x


_By = 4 * _inv(5) % _P
_Bx = _xrecover(_By)
_B = (_Bx % _P, _By % _P)


def _edwards(P, Q):
    x1, y1 = P
    x2, y2 = Q
    denom = _D * x1 * x2 * y1 * y2
    x3 = (x1 * y2 + x2 * y1) * _inv(1 + denom) % _P
    y3 = (y1 * y2 + x1 * x2) * _inv(1 - denom) % _P
    return (x3 % _P, y3 % _P)


def _scalarmult(P, e):
    """常数无关的朴素倍点（迭代，避免递归深度问题）。"""
    result = (0, 1)
    addend = P
    while e > 0:
        if e & 1:
            result = _edwards(result, addend)
        addend = _edwards(addend, addend)
        e >>= 1
    return result


def _bit(h, i):
    return (h[i // 8] >> (i % 8)) & 1


def _isoncurve(P):
    x, y = P
    return (-x * x + y * y - 1 - _D * x * x * y * y) % _P == 0


def _decodepoint(s):
    y = int.from_bytes(s, "little") & ((1 << 255) - 1)
    x = _xrecover(y)
    if (x & 1) != _bit(s, 255):
        x = _P - x
    P = (x, y)
    if not _isoncurve(P):
        raise ValueError("点不在曲线上")
    return P


def verify(public_key, signature, message):
    """验证 Ed25519 签名。public_key 32 字节，signature 64 字节，message 为 bytes。

    返回 True/False；任何格式错误均返回 False，不抛异常。
    """
    try:
        if len(public_key) != 32 or len(signature) != 64:
            return False
        R = _decodepoint(signature[:32])
        A = _decodepoint(public_key)
        S = int.from_bytes(signature[32:], "little")
        if S >= _L:
            return False
        h = int.from_bytes(hashlib.sha512(signature[:32] + public_key + message).digest(), "little") % _L
        left = _scalarmult(_B, S)
        right = _edwards(R, _scalarmult(A, h))
        return left == right
    except Exception:
        return False
