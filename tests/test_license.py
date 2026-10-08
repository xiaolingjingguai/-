"""许可机制自测：运行 python tests/test_license.py

覆盖：机器码稳定性、Ed25519 签名互通、默认一年有效期、永久、有效/到期/换机/篡改。
测试用演示私钥（tools/keys_demo/private_demo.pem）签发，并用其对应的演示公钥校验，
因此与 app/license_verify.py 内置的作者公钥无关（内置公钥另做格式校验）。
"""
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "app"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import license_verify as LV  # noqa: E402
import license_issuer as LI  # noqa: E402

DEMO_KEY = os.path.join(ROOT, "tools", "keys_demo", "private_demo.pem")


def _demo_public_hex():
    from cryptography.hazmat.primitives import serialization as ser
    with open(DEMO_KEY, "rb") as f:
        sk = ser.load_pem_private_key(f.read(), password=None)
    pub = sk.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw)
    return pub.hex()


def run():
    out, bad = [], 0
    demo_pub = _demo_public_hex()

    def check(name, cond):
        nonlocal bad
        bad += 0 if cond else 1
        out.append("%s：%s" % (name, "通过" if cond else "失败"))

    def verify(text, machine):
        return LV.verify_license_bytes(text, machine, public_key_hex=demo_pub)

    # 内置作者公钥应为 64 位十六进制（32 字节）
    k = LV.PUBLIC_KEY_HEX
    check("内置公钥格式正确", isinstance(k, str) and len(k) == 64 and all(c in "0123456789abcdefABCDEF" for c in k))

    # 私钥—内置公钥配套校验：演示私钥与正式内置公钥不配套，应被判为不匹配
    check("配套校验识别不匹配私钥", LI.public_hex_of_private(DEMO_KEY) == demo_pub
          and (LI.key_matches_app(DEMO_KEY) == (demo_pub.lower() == k.lower())))

    code1 = LV.machine_code()
    code2 = LV.machine_code()
    check("机器码稳定", code1 == code2 and "-" in code1)

    text, _ = LI.make_license(code1, "测试单位", None, DEMO_KEY)
    ok, info, reason = verify(text, code1)
    check("有效许可证通过", ok and info and info.get("name") == "测试单位")

    import datetime
    exp = LI.resolve_expiry("")  # 留空 → 默认一年
    one_year = LI._plus_years(datetime.date.today(), 1).isoformat()
    check("默认有效期一年", exp == one_year)
    check("显式永久", LI.resolve_expiry("", permanent=True) is None and LI.resolve_expiry("永久") is None)
    text, _ = LI.make_license(code1, "一年用户", exp, DEMO_KEY)
    ok, info, _ = verify(text, code1)
    check("一年期许可证当前有效", ok and info.get("expiry") == one_year)

    text, _ = LI.make_license(code1, "", "2020-01-01", DEMO_KEY)
    ok, _, reason = verify(text, code1)
    check("过期许可证拒绝", (not ok) and "到期" in reason)

    text, _ = LI.make_license("AAAA-BBBB-CCCC-DDDD", "", None, DEMO_KEY)
    ok, _, reason = verify(text, code1)
    check("换机许可证拒绝", (not ok) and "机器码" in reason)

    text, _ = LI.make_license(code1, "原名", None, DEMO_KEY)
    d = json.loads(text)
    d["name"] = "篡改后的名字"
    ok, _, reason = verify(json.dumps(d, ensure_ascii=False), code1)
    check("篡改内容拒绝", (not ok) and "签名" in reason)

    out.append("LICENSE %s" % ("PASS" if not bad else "FAIL"))
    return bad, out


if __name__ == "__main__":
    bad, lines = run()
    print("\n".join(lines))
    sys.exit(1 if bad else 0)
