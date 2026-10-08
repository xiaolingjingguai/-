"""一次性生成作者密钥对（Ed25519）。

用法：
    python tools/make_keys.py

生成：
    tools/keys/author_private.pem   —— 作者私钥，务必自己离线保管，切勿上传仓库或分发！
    并在屏幕上打印公钥常量，请复制替换 app/license_verify.py 里的 PUBLIC_KEY_HEX，再重新打包程序。

说明：私钥用于签发许可证（license_issuer.py），公钥内置于被保护程序用于验证。
只要私钥不泄露，任何人都无法伪造能通过校验的授权文件。
"""
import os
import sys

from cryptography.hazmat.primitives import serialization as ser
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

HERE = os.path.dirname(os.path.abspath(__file__))
KEYDIR = os.path.join(HERE, "keys")
PRIV = os.path.join(KEYDIR, "author_private.pem")


def main():
    os.makedirs(KEYDIR, exist_ok=True)
    if os.path.exists(PRIV) and "--force" not in sys.argv:
        print("已存在私钥：%s" % PRIV)
        print("如确需覆盖（会使已签发的许可证全部失效），请加 --force 重新运行。")
        return 1
    sk = Ed25519PrivateKey.generate()
    pem = sk.private_bytes(ser.Encoding.PEM, ser.PrivateFormat.PKCS8,
                           ser.NoEncryption())
    with open(PRIV, "wb") as f:
        f.write(pem)
    try:
        os.chmod(PRIV, 0o600)
    except Exception:
        pass
    pub = sk.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw)
    print("已生成私钥：%s" % PRIV)
    print("请妥善离线保管该私钥，切勿上传仓库或随程序分发。\n")
    print("请将 app/license_verify.py 中的公钥常量替换为下面这一行，然后重新打包程序：\n")
    print('PUBLIC_KEY_HEX = "%s"' % pub.hex())
    return 0


if __name__ == "__main__":
    sys.exit(main())
