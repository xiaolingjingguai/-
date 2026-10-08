"""许可机制自测：运行 python tests/test_license.py

覆盖：机器码稳定性、Ed25519 签名互通、有效/到期/换机/篡改四种校验结果。
使用演示私钥（tools/keys_demo/private_demo.pem），与 app/license_verify.py 内置的演示公钥配对。
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


def run():
    out, bad = [], 0

    def check(name, cond):
        nonlocal bad
        bad += 0 if cond else 1
        out.append("%s：%s" % (name, "通过" if cond else "失败"))

    code1 = LV.machine_code()
    code2 = LV.machine_code()
    check("机器码稳定", code1 == code2 and "-" in code1)

    text, _ = LI.make_license(code1, "测试单位", None, DEMO_KEY)
    ok, info, reason = LV.verify_license_bytes(text, code1)
    check("有效许可证通过", ok and info and info.get("name") == "测试单位")

    text, _ = LI.make_license(code1, "", "2020-01-01", DEMO_KEY)
    ok, _, reason = LV.verify_license_bytes(text, code1)
    check("过期许可证拒绝", (not ok) and "到期" in reason)

    text, _ = LI.make_license("AAAA-BBBB-CCCC-DDDD", "", None, DEMO_KEY)
    ok, _, reason = LV.verify_license_bytes(text, code1)
    check("换机许可证拒绝", (not ok) and "机器码" in reason)

    text, _ = LI.make_license(code1, "原名", None, DEMO_KEY)
    d = json.loads(text)
    d["name"] = "篡改后的名字"
    ok, _, reason = LV.verify_license_bytes(json.dumps(d, ensure_ascii=False), code1)
    check("篡改内容拒绝", (not ok) and "签名" in reason)

    out.append("LICENSE %s" % ("PASS" if not bad else "FAIL"))
    return bad, out


if __name__ == "__main__":
    bad, lines = run()
    print("\n".join(lines))
    sys.exit(1 if bad else 0)
