# -*- coding: utf-8 -*-
"""许可机制自测：机器码稳定性、签名互通、默认/永久/到期/换机/篡改校验、试用计时。
用随机测试密钥签发并验证（与程序内置作者公钥无关），故无需作者私钥即可在 CI 跑通。
"""
import base64
import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import license_verify as LV
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def _sign(sk, machine, name="测试", expiry=None):
    fields = {"machine": machine, "name": name}
    if expiry:
        fields["expiry"] = expiry
    fields["sig"] = base64.b64encode(sk.sign(LV._canonical(fields))).decode()
    return json.dumps(fields, ensure_ascii=False)


def main():
    sk = Ed25519PrivateKey.generate()
    pub = sk.public_key().public_bytes_raw().hex()
    ok_all = True

    def check(name, cond):
        nonlocal ok_all
        ok_all = ok_all and bool(cond)
        print("%s：%s" % (name, "通过" if cond else "失败"))

    # 内置公钥格式
    check("内置公钥格式正确", len(bytes.fromhex(LV.PUBLIC_KEY_HEX)) == 32)

    # 机器码稳定、格式正确
    mc = LV.machine_code()
    check("机器码稳定", mc == LV.machine_code())
    check("机器码格式", bool(re.fullmatch(r"[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}", mc)))

    # 有效许可证通过
    ok, info, r = LV.verify_license_bytes(_sign(sk, mc), this_machine=mc, public_key_hex=pub)
    check("有效许可证通过", ok)

    # 永久（无 expiry）当前有效
    ok, _, _ = LV.verify_license_bytes(_sign(sk, mc), this_machine=mc, public_key_hex=pub)
    check("永久授权有效", ok)

    # 过期拒绝
    ok, _, r = LV.verify_license_bytes(_sign(sk, mc, expiry="2000-01-01"), this_machine=mc, public_key_hex=pub)
    check("过期许可证拒绝", (not ok) and "到期" in r)

    # 换机拒绝
    ok, _, r = LV.verify_license_bytes(_sign(sk, mc), this_machine="FFFF-FFFF-FFFF-FFFF", public_key_hex=pub)
    check("换机许可证拒绝", (not ok) and "机器码" in r)

    # 篡改拒绝
    ok, _, r = LV.verify_license_bytes(_sign(sk, mc).replace("测试", "黑客"), this_machine=mc, public_key_hex=pub)
    check("篡改内容拒绝", (not ok) and "签名" in r)

    # 用错公钥拒绝
    other = Ed25519PrivateKey.generate().public_key().public_bytes_raw().hex()
    ok, _, r = LV.verify_license_bytes(_sign(sk, mc), this_machine=mc, public_key_hex=other)
    check("错误公钥拒绝", (not ok) and "签名" in r)

    # 试用计时（注入时间 + 临时目录）
    os.environ["LOCALAPPDATA"] = tempfile.mkdtemp()
    rem0 = LV.trial_remaining_seconds(_now=1000.0)
    check("试用首次约30分钟", 29 * 60 <= rem0 <= 30 * 60)
    rem1 = LV.trial_remaining_seconds(_now=1000.0 + 31 * 60)
    check("试用到期后为0", rem1 == 0)

    print("LICENSE PASS" if ok_all else "LICENSE FAIL")
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
