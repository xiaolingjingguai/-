"""授权码生成器（作者端）——为指定用户的机器签发 license.key。

两种用法：

一、图形界面（推荐，双击或命令行直接运行）：
        python tools/license_issuer.py
    填入：用户机器码、授权给（名称/单位，可选）、到期日（可空=永久），
    选择私钥文件，点“签发”，即生成 license.key 发给该用户。

二、命令行（便于批量/自动化）：
        python tools/license_issuer.py sign \
            --machine A1B2-C3D4-E5F6-7890 \
            --name "某某环保公司" \
            --expiry 2027-12-31 \
            --key tools/keys/author_private.pem \
            --out license.key
    --expiry 省略即默认一年有效期（自签发日起）；加 --permanent 则为永久授权；
    也可用 --expiry YYYY-MM-DD 指定任意到期日。

签发使用私钥对 (程序标签 + 机器码 + 名称 + 签发日 + 到期日) 做 Ed25519 签名，
被保护程序用内置公钥验证。私钥务必自存，勿上传仓库或分发。
"""
import argparse
import base64
import datetime
import json
import os
import sys

from cryptography.hazmat.primitives import serialization as ser

# 复用程序内置模块里的规范化与标签，确保签名与验证完全一致
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "app"))
import license_verify as LV  # noqa: E402

# 打包成 EXE 后，私钥默认到 EXE 所在目录的 keys/ 下找；脚本运行时用 tools/keys/
BASE = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else HERE
DEFAULT_KEY = os.path.join(BASE, "keys", "author_private.pem")
DEMO_KEY = os.path.join(HERE, "keys_demo", "private_demo.pem")

DEFAULT_YEARS = 1  # 不指定到期日时的默认有效期（年）
_PERMANENT_WORDS = {"永久", "none", "never", "0", "permanent"}

# 可签发的软件清单：(显示名, 签名标签)。每个软件用各自的标签（签名域），
# 因此为某软件签出的 license.key 只能解锁那个软件，彼此独立、不通用。
# 新增软件时在此登记其标签（须与该软件内置 license_verify.APP_TAG 一致）。
APPS = [
    ("HJ169 风险计算器", "HJ169"),
    ("环境质量判定工作台（EnvQualityWorkbench）", "ENVQ"),
]
_TAGS = {name: tag for name, tag in APPS}
_VALID_TAGS = {tag for _, tag in APPS}
DEFAULT_APP_TAG = APPS[0][1]


def _plus_years(d, years):
    try:
        return d.replace(year=d.year + years)
    except ValueError:  # 2月29日等边界，顺延到下一天
        return d.replace(year=d.year + years, day=28) + datetime.timedelta(days=1)


def resolve_expiry(raw, permanent=False):
    """把用户输入的到期日解析成最终值（供 make_license 使用）。
    - permanent=True 或输入“永久/none/never/0”→ None（永久）
    - 留空（None/""）→ 默认 DEFAULT_YEARS 年后的日期
    - 其它 → 按 YYYY-MM-DD 校验后原样返回
    """
    if permanent:
        return None
    s = (raw or "").strip()
    if s == "":
        return _plus_years(datetime.date.today(), DEFAULT_YEARS).isoformat()
    if s.lower() in _PERMANENT_WORDS or s in _PERMANENT_WORDS:
        return None
    datetime.date.fromisoformat(s)  # 校验格式，错误即抛出
    return s


def _load_private(path):
    with open(path, "rb") as f:
        return ser.load_pem_private_key(f.read(), password=None)


def public_hex_of_private(key_path):
    """返回私钥对应公钥的 hex（Raw 32 字节）。"""
    sk = _load_private(key_path)
    return sk.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw).hex()


def key_matches_app(key_path):
    """判断该私钥是否与被保护程序内置的作者公钥（LV.PUBLIC_KEY_HEX）配套。
    只有配套的私钥签出来的 license.key 才能在该程序上通过校验。"""
    try:
        return public_hex_of_private(key_path).lower() == LV.PUBLIC_KEY_HEX.lower()
    except Exception:
        return False


def _auto_default_key():
    """按优先级自动寻找作者私钥：EXE/脚本旁的 author_private.pem、其 keys 子目录、
    最后才是演示私钥（仅脚本源码环境存在）。找不到返回 ""。"""
    for p in (os.path.join(BASE, "author_private.pem"), DEFAULT_KEY, DEMO_KEY):
        if os.path.exists(p):
            return p
    return ""


def _app_fingerprint():
    """内置授权公钥的短指纹（末 8 位），供用户核对私钥/公钥是否配套。"""
    k = LV.PUBLIC_KEY_HEX
    return k[-8:].upper() if k else "(无)"


def _norm_machine(code):
    return str(code).strip().upper()


def make_license(machine, name="", expiry=None, key_path=None, app_tag=None):
    """返回 license.key 的文本内容（str）。expiry 为 'YYYY-MM-DD' 或 None/''。
    app_tag 指定给哪个软件签发（签名域）；默认为清单首个软件。"""
    key_path = key_path or (DEFAULT_KEY if os.path.exists(DEFAULT_KEY) else DEMO_KEY)
    sk = _load_private(key_path)
    if expiry:
        datetime.date.fromisoformat(expiry)  # 校验格式，错误即抛出
    fields = {
        "v": 1,
        "machine": _norm_machine(machine),
        "name": name or "",
        "issued": datetime.date.today().isoformat(),
        "expiry": expiry or None,
    }
    sig = sk.sign(LV._canonical(fields, app_tag or DEFAULT_APP_TAG))
    fields["sig"] = base64.b64encode(sig).decode("ascii")
    return json.dumps(fields, ensure_ascii=False, indent=2), key_path


def _cli(argv):
    ap = argparse.ArgumentParser(description="HJ169 授权码生成器（作者端）")
    ap.add_argument("--machine", required=True, help="用户机器码，如 A1B2-C3D4-E5F6-7890")
    ap.add_argument("--app", default=DEFAULT_APP_TAG,
                    help="给哪个软件签发（签名标签），可选 %s；默认 %s"
                         % ("/".join(sorted(_VALID_TAGS)), DEFAULT_APP_TAG))
    ap.add_argument("--name", default="", help="授权给（名称/单位，可选）")
    ap.add_argument("--expiry", default="", help="到期日 YYYY-MM-DD，省略为默认一年")
    ap.add_argument("--permanent", action="store_true", help="签发永久授权（无到期日）")
    ap.add_argument("--key", default="", help="私钥 PEM 路径，默认 tools/keys/author_private.pem")
    ap.add_argument("--out", default="license.key", help="输出文件，默认 license.key")
    ap.add_argument("--allow-mismatch", action="store_true",
                    help="允许用与内置公钥不配套的私钥签发（仅 CI/演示用，正式签发勿用）")
    a = ap.parse_args(argv)
    app_tag = _TAGS.get(a.app, a.app)  # 允许传显示名或标签
    if app_tag not in _VALID_TAGS:
        print("错误：未知软件标签 %r，可选：%s" % (a.app, "、".join(sorted(_VALID_TAGS))))
        return 2
    expiry = resolve_expiry(a.expiry, a.permanent)
    kp = a.key or _auto_default_key() or DEMO_KEY
    if not os.path.exists(kp):
        print("错误：找不到私钥文件：%s" % kp)
        return 2
    if not a.allow_mismatch and not key_matches_app(kp):
        print("错误：这把私钥与程序内置的授权公钥（指纹 …%s）不配套，签出来的 license.key 无法使用。"
              % _app_fingerprint())
        print("请改用与当前这版程序配套的 author_private.pem（即生成当前程序公钥时产生的那把私钥）。")
        return 2
    text, used = make_license(a.machine, a.name, expiry, kp, app_tag)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    demo = os.path.abspath(used) == os.path.abspath(DEMO_KEY)
    print("已签发：%s" % a.out)
    print("  软件  ：%s（标签 %s）" % (next((n for n, t in APPS if t == app_tag), app_tag), app_tag))
    print("  机器码：%s" % _norm_machine(a.machine))
    print("  授权给：%s" % (a.name or "(未填)"))
    print("  到期  ：%s" % (expiry or "永久"))
    print("  私钥  ：%s%s" % (used, "  ← 演示密钥！正式分发前请换成你自己的私钥" if demo else ""))
    return 0


def _gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title("HJ169 授权码生成器（作者端）")
    frm = ttk.Frame(root, padding=16)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text="为指定用户签发授权文件 license.key",
              font=("Microsoft YaHei", 12, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 2))
    ttk.Label(frm, text="本程序配套的授权公钥指纹：…%s（请用对应的私钥签发）" % _app_fingerprint(),
              foreground="#555").grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 10))

    def row(r, label):
        ttk.Label(frm, text=label).grid(row=r, column=0, sticky="e", padx=(0, 8), pady=4)
        v = tk.StringVar()
        e = ttk.Entry(frm, textvariable=v, width=40)
        e.grid(row=r, column=1, columnspan=2, sticky="we", pady=4)
        return v

    # 授权软件选择：不同软件用各自签名域，签出的 license.key 相互独立、不通用
    ttk.Label(frm, text="授权软件：").grid(row=2, column=0, sticky="e", padx=(0, 8), pady=4)
    app_var = tk.StringVar(value=APPS[0][0])
    app_box = ttk.Combobox(frm, textvariable=app_var, state="readonly",
                           values=[n for n, _ in APPS], width=38)
    app_box.grid(row=2, column=1, columnspan=2, sticky="we", pady=4)

    m_var = row(3, "用户机器码：")
    n_var = row(4, "授权给（可选）：")
    x_var = row(5, "到期日(YYYY-MM-DD，空=默认一年，填“永久”=永久)：")

    k_var = tk.StringVar(value=_auto_default_key())
    ttk.Label(frm, text="私钥文件：").grid(row=6, column=0, sticky="e", padx=(0, 8), pady=4)
    ttk.Entry(frm, textvariable=k_var, width=32).grid(row=6, column=1, sticky="we", pady=4)

    def pick_key():
        p = filedialog.askopenfilename(title="选择私钥 PEM", filetypes=[("PEM", "*.pem"), ("全部", "*.*")])
        if p:
            k_var.set(p)

    ttk.Button(frm, text="浏览…", command=pick_key).grid(row=6, column=2, sticky="w", pady=4)

    status = ttk.Label(frm, text="", wraplength=460, justify="left")
    status.grid(row=7, column=0, columnspan=3, sticky="w", pady=(2, 6))

    def refresh_status(*_):
        p = k_var.get().strip()
        if not p:
            status.configure(text="请选择你的私钥 author_private.pem（“浏览…”）。", foreground="#b00020")
        elif not os.path.exists(p):
            status.configure(text="私钥文件不存在：%s" % p, foreground="#b00020")
        elif key_matches_app(p):
            status.configure(text="✓ 私钥与本程序配套，签出的授权可用。", foreground="#1a7f37")
        elif os.path.abspath(p) == os.path.abspath(DEMO_KEY):
            status.configure(text="✗ 这是演示私钥，与本程序公钥不配套，签出的授权无法使用。", foreground="#b00020")
        else:
            status.configure(text="✗ 这把私钥与本程序公钥（指纹 …%s）不配套，签出的授权无法使用。"
                                   "请改用生成本程序公钥时产生的 author_private.pem。" % _app_fingerprint(),
                             foreground="#b00020")

    k_var.trace_add("write", refresh_status)
    refresh_status()

    def do_issue():
        m = m_var.get().strip()
        if not m:
            messagebox.showwarning("提示", "请填写用户机器码")
            return
        kp = k_var.get().strip()
        if not kp or not os.path.exists(kp):
            messagebox.showwarning("提示", "请先选择你的私钥 author_private.pem")
            return
        if not key_matches_app(kp):
            messagebox.showerror("私钥不配套",
                                 "这把私钥与本程序内置的授权公钥（指纹 …%s）不配套，\n"
                                 "签出来的 license.key 在计算器上会提示“签名无效”。\n\n"
                                 "请改用生成本程序这版公钥时产生的 author_private.pem 再签。" % _app_fingerprint())
            return
        app_name = app_var.get()
        app_tag = _TAGS.get(app_name, DEFAULT_APP_TAG)
        try:
            expiry = resolve_expiry(x_var.get().strip())
            text, used = make_license(m, n_var.get().strip(), expiry, kp, app_tag)
        except Exception as ex:
            messagebox.showerror("签发失败", str(ex))
            return
        out = filedialog.asksaveasfilename(title="保存授权文件", initialfile="license.key",
                                           defaultextension=".key")
        if not out:
            return
        with open(out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        messagebox.showinfo("已签发",
                            "已为【%s】生成：\n%s\n到期：%s\n\n"
                            "把它发给该用户，放在【%s】程序的同一目录即可。\n"
                            "注意：该授权只对这一个软件有效，其它软件需单独签发。"
                            % (app_name, out, expiry or "永久", app_name))

    ttk.Button(frm, text="签发 license.key", command=do_issue).grid(
        row=8, column=0, columnspan=3, pady=(10, 0), sticky="we")
    frm.columnconfigure(1, weight=1)
    root.mainloop()


def main():
    argv = sys.argv[1:]
    if argv and argv[0] == "sign":
        return _cli(argv[1:])
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    _gui()
    return 0


if __name__ == "__main__":
    sys.exit(main())
