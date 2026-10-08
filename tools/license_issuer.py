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


def _norm_machine(code):
    return str(code).strip().upper()


def make_license(machine, name="", expiry=None, key_path=None):
    """返回 license.key 的文本内容（str）。expiry 为 'YYYY-MM-DD' 或 None/''。"""
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
    sig = sk.sign(LV._canonical(fields))
    fields["sig"] = base64.b64encode(sig).decode("ascii")
    return json.dumps(fields, ensure_ascii=False, indent=2), key_path


def _cli(argv):
    ap = argparse.ArgumentParser(description="HJ169 授权码生成器（作者端）")
    ap.add_argument("--machine", required=True, help="用户机器码，如 A1B2-C3D4-E5F6-7890")
    ap.add_argument("--name", default="", help="授权给（名称/单位，可选）")
    ap.add_argument("--expiry", default="", help="到期日 YYYY-MM-DD，省略为默认一年")
    ap.add_argument("--permanent", action="store_true", help="签发永久授权（无到期日）")
    ap.add_argument("--key", default="", help="私钥 PEM 路径，默认 tools/keys/author_private.pem")
    ap.add_argument("--out", default="license.key", help="输出文件，默认 license.key")
    a = ap.parse_args(argv)
    expiry = resolve_expiry(a.expiry, a.permanent)
    text, used = make_license(a.machine, a.name, expiry, a.key or None)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    demo = os.path.abspath(used) == os.path.abspath(DEMO_KEY)
    print("已签发：%s" % a.out)
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
              font=("Microsoft YaHei", 12, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

    def row(r, label):
        ttk.Label(frm, text=label).grid(row=r, column=0, sticky="e", padx=(0, 8), pady=4)
        v = tk.StringVar()
        e = ttk.Entry(frm, textvariable=v, width=40)
        e.grid(row=r, column=1, columnspan=2, sticky="we", pady=4)
        return v

    m_var = row(1, "用户机器码：")
    n_var = row(2, "授权给（可选）：")
    x_var = row(3, "到期日(YYYY-MM-DD，空=默认一年，填“永久”=永久)：")

    if os.path.exists(DEFAULT_KEY):
        key_default = DEFAULT_KEY
    elif os.path.exists(DEMO_KEY):
        key_default = DEMO_KEY
    else:
        key_default = ""  # 打包后首次使用：留空，由用户“浏览…”选私钥
    k_var = tk.StringVar(value=key_default)
    ttk.Label(frm, text="私钥文件：").grid(row=4, column=0, sticky="e", padx=(0, 8), pady=4)
    ttk.Entry(frm, textvariable=k_var, width=32).grid(row=4, column=1, sticky="we", pady=4)

    def pick_key():
        p = filedialog.askopenfilename(title="选择私钥 PEM", filetypes=[("PEM", "*.pem"), ("全部", "*.*")])
        if p:
            k_var.set(p)

    ttk.Button(frm, text="浏览…", command=pick_key).grid(row=4, column=2, sticky="w", pady=4)

    if os.path.abspath(key_default) == os.path.abspath(DEMO_KEY):
        ttk.Label(frm, text="注意：当前为演示密钥，正式分发前请先运行 make_keys.py 生成自己的密钥。",
                  foreground="#b00020", wraplength=420, justify="left").grid(
            row=5, column=0, columnspan=3, sticky="w", pady=(2, 6))

    def do_issue():
        m = m_var.get().strip()
        if not m:
            messagebox.showwarning("提示", "请填写用户机器码")
            return
        try:
            expiry = resolve_expiry(x_var.get().strip())
            text, used = make_license(m, n_var.get().strip(), expiry, k_var.get().strip())
        except Exception as ex:
            messagebox.showerror("签发失败", str(ex))
            return
        out = filedialog.asksaveasfilename(title="保存授权文件", initialfile="license.key",
                                           defaultextension=".key")
        if not out:
            return
        with open(out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        messagebox.showinfo("已签发", "已生成：\n%s\n到期：%s\n\n把它发给该用户，放在程序同一目录即可。"
                            % (out, expiry or "永久"))

    ttk.Button(frm, text="签发 license.key", command=do_issue).grid(
        row=6, column=0, columnspan=3, pady=(10, 0), sticky="we")
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
