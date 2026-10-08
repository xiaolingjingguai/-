"""被保护程序内置的许可校验模块（离线、机器绑定）。

职责：
1. machine_code()  计算本机机器码（指纹），供用户发给作者申请授权。
2. check_license() 读取程序目录下的 license.key，用内置公钥验证签名、核对机器码与
   有效期，返回是否放行。
3. gate()         供主程序在启动时调用：无有效许可证时弹窗显示机器码与申请说明并拒绝运行。

设计说明
--------
- 采用非对称签名（Ed25519）：私钥只在作者手上，公钥内置于本程序。用户无法伪造许可证。
- 仅做验证，使用纯 Python 实现（app/_ed25519_pure.py），不引入新的打包依赖。
- 完全离线：机器码对拷即可，不联网激活。
- 许可证绑定机器码，可选到期日。

安全边界（务必知晓）：Python/PyInstaller 打包的程序可被逆向，本机制能有效阻止
“普通用户私自传播、换机使用”，但无法抵御专业逆向（删除校验、改公钥后重打包）。
如需更强保护，请配合代码混淆（如 PyArmor），见 packaging/软件授权说明.md。
"""
import base64
import datetime
import hashlib
import json
import os
import sys

import _ed25519_pure as _ed

# ====================================================================== 内置公钥
# 作者公钥（32 字节，hex）。下方为【演示密钥】，正式分发前请务必用你自己的公钥替换：
#   运行  python tools/make_keys.py  生成你的密钥对，按提示替换此常量，重新打包。
# 私钥务必离线自存，切勿上传仓库或随程序分发。
PUBLIC_KEY_HEX = "9c4215f9cca756438bb2110b0de6bfe5cee4b7a5ac8adf22ebc354cc1e31ba1e"

LICENSE_FILENAME = "license.key"
APP_TAG = "HJ169"  # 签名域分隔，避免跨程序重放


# ====================================================================== 机器码
def _win_machine_guid():
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                           r"SOFTWARE\Microsoft\Cryptography", 0,
                           winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
        val, _ = winreg.QueryValueEx(k, "MachineGuid")
        winreg.CloseKey(k)
        return str(val)
    except Exception:
        return ""


def _win_volume_serial():
    try:
        import ctypes
        serial = ctypes.c_ulong(0)
        root = os.environ.get("SystemDrive", "C:") + "\\"
        ctypes.windll.kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(root), None, 0, ctypes.byref(serial),
            None, None, None, 0)
        return str(serial.value)
    except Exception:
        return ""


def _linux_machine_id():
    for p in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            with open(p, "r") as f:
                v = f.read().strip()
            if v:
                return v
        except Exception:
            pass
    return ""


def _mac_platform_uuid():
    try:
        import subprocess
        out = subprocess.check_output(
            ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
            stderr=subprocess.DEVNULL, timeout=5).decode("utf-8", "ignore")
        for line in out.splitlines():
            if "IOPlatformUUID" in line:
                return line.split('"')[-2]
    except Exception:
        pass
    return ""


def _real_mac():
    """仅在 uuid.getnode() 返回真实网卡地址（而非随机回退值）时返回它。"""
    try:
        import uuid
        n = uuid.getnode()
        # 组播位（第一字节最低位）置 1 表示这是随机生成的回退值，不稳定，弃用
        if (n >> 40) & 1:
            return ""
        return "mac:%012x" % n
    except Exception:
        return ""


def _raw_fingerprint():
    """采集稳定的本机标识。Windows 优先用 MachineGuid + 系统盘卷序列号；
    Linux 用 /etc/machine-id，macOS 用 IOPlatformUUID；再回退到真实网卡 MAC。"""
    parts = []
    if sys.platform == "win32":
        g = _win_machine_guid()
        v = _win_volume_serial()
        if g:
            parts.append("guid:" + g)
        if v:
            parts.append("vol:" + v)
    else:
        mid = _linux_machine_id() if sys.platform.startswith("linux") else ""
        if mid:
            parts.append("mid:" + mid)
        if not parts and sys.platform == "darwin":
            u = _mac_platform_uuid()
            if u:
                parts.append("uuid:" + u)
    if not parts:
        m = _real_mac()
        if m:
            parts.append(m)
    if not parts:
        parts.append("host:" + str(os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or "unknown"))
    return "|".join(parts)


def machine_code():
    """返回本机机器码，形如 A1B2-C3D4-E5F6-7890（16 位 hex，分 4 组）。
    同一台机器稳定不变；换机后不同。"""
    digest = hashlib.sha256(_raw_fingerprint().encode("utf-8")).hexdigest().upper()
    s = digest[:16]
    return "-".join(s[i:i + 4] for i in range(0, 16, 4))


# ====================================================================== 许可证
def _canonical(fields):
    """许可证被签名的规范字节：去除 sig 后按键排序、紧凑序列化，并加程序标签。"""
    body = {k: fields[k] for k in fields if k != "sig"}
    payload = json.dumps(body, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False)
    return (APP_TAG + "\n" + payload).encode("utf-8")


def _license_path():
    """许可证文件位置：优先 EXE/脚本所在目录，其次当前工作目录。"""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    cand = os.path.join(base, LICENSE_FILENAME)
    if os.path.exists(cand):
        return cand
    return os.path.join(os.getcwd(), LICENSE_FILENAME)


def verify_license_bytes(raw, this_machine=None):
    """验证许可证内容（bytes 或 str）。返回 (ok: bool, info: dict|None, reason: str)。"""
    if this_machine is None:
        this_machine = machine_code()
    try:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        fields = json.loads(raw)
    except Exception:
        return False, None, "许可证文件格式无法解析"
    for key in ("machine", "sig"):
        if key not in fields:
            return False, None, "许可证缺少必要字段：%s" % key
    try:
        sig = base64.b64decode(fields["sig"])
    except Exception:
        return False, None, "许可证签名字段无效"
    pub = bytes.fromhex(PUBLIC_KEY_HEX)
    if not _ed.verify(pub, sig, _canonical(fields)):
        return False, None, "许可证签名无效（可能被篡改，或并非本程序作者签发）"
    if str(fields.get("machine", "")).strip().upper() != this_machine.upper():
        return False, None, "许可证与本机机器码不匹配（此证是为其它机器签发的）"
    expiry = fields.get("expiry")
    if expiry:
        try:
            exp = datetime.date.fromisoformat(str(expiry))
        except Exception:
            return False, None, "许可证到期日格式无效"
        if datetime.date.today() > exp:
            return False, fields, "许可证已于 %s 到期" % expiry
    return True, fields, "ok"


def check_license(this_machine=None):
    """读取并验证本机许可证。返回 (ok, info, reason)。"""
    path = _license_path()
    if not os.path.exists(path):
        return False, None, "未找到许可证文件 %s（请将作者签发的 license.key 放在程序同一目录）" % LICENSE_FILENAME
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
    except Exception as ex:
        return False, None, "许可证文件无法读取：%r" % ex
    return verify_license_bytes(raw, this_machine)


# ====================================================================== 启动门禁
def gate(parent=None):
    """主程序启动时调用。有效则返回 info（dict）；无效则弹窗显示机器码与申请说明后返回 None。"""
    ok, info, reason = check_license()
    if ok:
        return info
    _show_dialog(reason, parent)
    return None


def _show_dialog(reason, parent=None):
    import tkinter as tk
    from tkinter import ttk
    owned = parent is None
    root = tk.Tk() if owned else tk.Toplevel(parent)
    root.title("HJ 169 风险计算器 — 软件授权")
    try:
        root.resizable(False, False)
    except Exception:
        pass
    code = machine_code()
    frm = ttk.Frame(root, padding=16)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text="本软件需授权后使用", font=("Microsoft YaHei", 12, "bold")).pack(anchor="w")
    ttk.Label(frm, text="当前状态：" + reason, foreground="#b00020",
              wraplength=440, justify="left").pack(anchor="w", pady=(6, 10))
    ttk.Label(frm, text="您的机器码（请复制后发给软件作者申请授权）：",
              justify="left").pack(anchor="w")
    ev = tk.StringVar(value=code)
    ent = ttk.Entry(frm, textvariable=ev, width=28, font=("Consolas", 13),
                    justify="center")
    ent.pack(fill="x", pady=(4, 6))
    ent.configure(state="readonly")

    def copy():
        try:
            root.clipboard_clear()
            root.clipboard_append(code)
            btn.configure(text="已复制 ✓")
            root.after(1500, lambda: btn.configure(text="复制机器码"))
        except Exception:
            pass

    btn = ttk.Button(frm, text="复制机器码", command=copy)
    btn.pack(anchor="w")
    tip = ("使用步骤：\n"
           "1. 把上面的机器码发给软件作者；\n"
           "2. 作者签发与本机绑定的 license.key 授权文件发回给您；\n"
           "3. 将 license.key 与本程序放在同一目录，重新启动即可使用。")
    ttk.Label(frm, text=tip, justify="left", foreground="#444",
              wraplength=440).pack(anchor="w", pady=(10, 10))
    ttk.Button(frm, text="退出", command=root.destroy).pack(anchor="e")
    try:
        ent.focus_set()
        ent.selection_range(0, "end")
    except Exception:
        pass
    if owned:
        root.mainloop()


# 命令行辅助：打印机器码（供打包流水线/用户快速获取），或本地校验
if __name__ == "__main__":
    if "--print-machine" in sys.argv:
        print(machine_code())
        sys.exit(0)
    ok, info, reason = check_license()
    print("机器码：", machine_code())
    print("校验：", "通过" if ok else "未通过", "—", reason)
    if info:
        print("授权给：", info.get("name", ""), " 到期：", info.get("expiry") or "永久")
    sys.exit(0 if ok else 1)
