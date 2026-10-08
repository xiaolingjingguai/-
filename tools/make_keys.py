"""一次性生成作者密钥对（Ed25519）。

两种形态：
- 脚本：  python tools/make_keys.py
- Windows EXE：双击 HJ169_密钥生成器.exe（无需安装 Python）

生成（均写到本工具所在目录下）：
    keys/author_private.pem         —— 作者私钥，务必自己离线保管，切勿上传仓库或分发！
    公钥_PUBLIC_KEY.txt             —— 公钥常量，把其中一行发给开发者/贴进 app/license_verify.py，再重新打包程序。

说明：私钥用于签发许可证（license_issuer），公钥内置于被保护程序用于验证。
只要私钥不泄露，任何人都无法伪造能通过校验的授权文件。
"""
import os
import sys

from cryptography.hazmat.primitives import serialization as ser
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def _base_dir():
    # 打包成 EXE 后写到 EXE 所在目录；脚本运行时写到 tools 目录
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _pause_if_frozen():
    if getattr(sys, "frozen", False):
        try:
            input("\n按回车键关闭本窗口……")
        except Exception:
            pass


def main():
    base = _base_dir()
    keydir = os.path.join(base, "keys")
    priv = os.path.join(keydir, "author_private.pem")
    pubtxt = os.path.join(base, "公钥_PUBLIC_KEY.txt")
    os.makedirs(keydir, exist_ok=True)
    if os.path.exists(priv) and "--force" not in sys.argv:
        print("已存在私钥：%s" % priv)
        print("如确需覆盖（会使已签发的许可证全部失效），请加 --force 重新运行。")
        _pause_if_frozen()
        return 1
    sk = Ed25519PrivateKey.generate()
    pem = sk.private_bytes(ser.Encoding.PEM, ser.PrivateFormat.PKCS8,
                           ser.NoEncryption())
    with open(priv, "wb") as f:
        f.write(pem)
    try:
        os.chmod(priv, 0o600)
    except Exception:
        pass
    pub = sk.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw)
    line = 'PUBLIC_KEY_HEX = "%s"' % pub.hex()
    with open(pubtxt, "w", encoding="utf-8") as f:
        f.write("把下面这一行贴进 app/license_verify.py（替换原 PUBLIC_KEY_HEX），然后重新打包程序：\n\n")
        f.write(line + "\n")
    print("已生成私钥：%s" % priv)
    print("请妥善离线保管该私钥，切勿上传仓库或随程序分发。\n")
    print("公钥已写入：%s" % pubtxt)
    print("请将 app/license_verify.py 中的公钥常量替换为下面这一行，然后重新打包程序：\n")
    print(line)
    _pause_if_frozen()
    return 0


if __name__ == "__main__":
    sys.exit(main())
