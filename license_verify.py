"""被保护程序内置的许可校验模块（离线、机器绑定）。

职责：
1. machine_code()  计算本机机器码（指纹），供用户发给作者申请授权。
2. check_license() 读取程序目录下的 license.key，用内置公钥验证签名、核对机器码与
   有效期，返回是否放行。
3. license_state()/show_gate()  供主程序启动时调用：已授权直接运行；未授权则给予首次
   TRIAL_MINUTES 分钟试用，到时弹窗显示机器码与申请说明并锁定；试用用完后启动即要求授权。

设计说明
--------
- 采用非对称签名（Ed25519）：私钥只在作者手上，公钥内置于本程序。用户无法伪造许可证。
- 仅做验证，使用纯 Python 实现（_ed25519_pure.py），不引入新的打包依赖。
- 完全离线：机器码对拷即可，不联网激活。
- 许可证绑定机器码，可选到期日。
- 本程序与作者的其它软件（如 HJ169 风险计算器）共用同一把作者公钥/私钥，但各自使用
  不同的签名域（APP_TAG），因此为本程序签发的 license.key 只能解锁本程序、不与其它软件通用；
  作者用同一套“授权码生成器”选择“本软件”即可签发。
- 门禁弹窗用 PySide6（Qt）实现，与本程序界面一致。

安全边界（务必知晓）：Python/PyInstaller 打包的程序可被逆向，本机制能有效阻止
“普通用户私自传播、换机使用”，但无法抵御专业逆向（删除校验、改公钥后重打包）。
如需更强保护，请配合代码混淆（如 PyArmor）。
"""
import base64
import datetime
import hashlib
import json
import os
import sys
import time

import _ed25519_pure as _ed

# ====================================================================== 内置公钥
# 作者公钥（32 字节，hex）。对应私钥只在作者手上。与 HJ169 风险计算器共用同一把公钥，
# 便于作者用同一套授权工具管理两个软件。如需更换作者，运行密钥生成器生成新密钥对，
# 用新公钥替换此常量后重新打包。
PUBLIC_KEY_HEX = "34890c731b85832e8f3e5d106767b7954128e1f7280208c1f0a9c4ad1ab3a16c"

LICENSE_FILENAME = "license.key"
# 签名域标签。本程序专用标签，与 HJ169 等其它软件不同，使本程序的授权与其它软件相互独立、不通用。
# 作者端的授权码生成器须选择“环境质量判定工作台（ENVQ）”才能签出本程序可用的 license.key。
APP_TAG = "ENVQ"


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
        if (n >> 40) & 1:  # 组播位置 1 表示随机回退值，不稳定，弃用
            return ""
        return "mac:%012x" % n
    except Exception:
        return ""


def _raw_fingerprint():
    """采集稳定的本机标识。Windows 优先用 MachineGuid + 系统盘卷序列号；
    Linux 用 /etc/machine-id，macOS 用 IOPlatformUUID；再回退到真实网卡 MAC。

    注意：此算法与 HJ169 计算器完全一致，故两软件在同一台机器上得到相同的机器码，
    同一份 license.key 可通用。"""
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
def _canonical(fields, app_tag=None):
    """许可证被签名的规范字节：去除 sig 后按键排序、紧凑序列化，并加程序标签。
    app_tag 默认用本程序内置标签（APP_TAG=ENVQ）。"""
    if app_tag is None:
        app_tag = APP_TAG
    body = {k: fields[k] for k in fields if k != "sig"}
    payload = json.dumps(body, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False)
    return (app_tag + "\n" + payload).encode("utf-8")


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


def verify_license_bytes(raw, this_machine=None, public_key_hex=None):
    """验证许可证内容（bytes 或 str）。返回 (ok: bool, info: dict|None, reason: str)。

    public_key_hex 默认用内置作者公钥；测试时可传入其它公钥。"""
    if this_machine is None:
        this_machine = machine_code()
    if public_key_hex is None:
        public_key_hex = PUBLIC_KEY_HEX
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
    pub = bytes.fromhex(public_key_hex)
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


# ====================================================================== 试用期
# 未授权时允许首次试用一段时间（自首次运行起累计），到时弹窗要求授权。
# 首次运行时刻记录在用户目录文件与注册表（HKCU）两处，互为备份、取最早值。
# 本软件的试用计时与 HJ169 计算器相互独立（使用各自的存储位置）。
TRIAL_MINUTES = 30
_TRIAL_REG_PATH = r"Software\EnvQWorkbench"
_TRIAL_REG_NAME = "T1"
_TRIAL_DIR = "EnvQWorkbench"


def _trial_file():
    base = (os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
            or os.path.expanduser("~"))
    d = os.path.join(base, _TRIAL_DIR)
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return os.path.join(d, "trial.dat")


def _read_file_start():
    try:
        with open(_trial_file(), "r") as f:
            return float(f.read().strip())
    except Exception:
        return None


def _write_file_start(ts):
    try:
        with open(_trial_file(), "w") as f:
            f.write(repr(float(ts)))
    except Exception:
        pass


def _read_reg_start():
    if sys.platform != "win32":
        return None
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _TRIAL_REG_PATH)
        val, _ = winreg.QueryValueEx(k, _TRIAL_REG_NAME)
        winreg.CloseKey(k)
        return float(val)
    except Exception:
        return None


def _write_reg_start(ts):
    if sys.platform != "win32":
        return
    try:
        import winreg
        k = winreg.CreateKey(winreg.HKEY_CURRENT_USER, _TRIAL_REG_PATH)
        winreg.SetValueEx(k, _TRIAL_REG_NAME, 0, winreg.REG_SZ, repr(float(ts)))
        winreg.CloseKey(k)
    except Exception:
        pass


def trial_remaining_seconds(_now=None):
    """返回未授权状态下的试用剩余秒数（0 表示试用已用完）。
    首次调用会记录首次运行时刻。_now 仅供测试注入当前时间。"""
    now = time.time() if _now is None else _now
    starts = [s for s in (_read_file_start(), _read_reg_start()) if s is not None]
    if starts:
        start = min(starts)
    else:
        start = now  # 首次运行：以当前时刻为试用起点
    _write_file_start(start)
    _write_reg_start(start)
    if start > now:  # 时钟被回拨到首次运行之前：按已到期处理
        return 0
    remaining = TRIAL_MINUTES * 60 - (now - start)
    return max(0, int(remaining))


def license_state():
    """返回 (state, payload, reason)：
    - ("licensed", info, "ok")      已授权
    - ("trial", 剩余秒数, reason)    未授权但仍在试用期内
    - ("expired", None, reason)      未授权且试用已用完
    """
    ok, info, reason = check_license()
    if ok:
        return "licensed", info, reason
    rem = trial_remaining_seconds()
    if rem > 0:
        return "trial", rem, reason
    return "expired", None, reason


# ====================================================================== 启动门禁（Qt）
def show_gate(reason=None, parent=None):
    """显示授权窗口（PySide6 模态对话框），阻塞至用户关闭。
    显示本机机器码与申请说明，供用户复制机器码发给作者申请授权。"""
    try:
        from PySide6.QtWidgets import (QApplication, QDialog, QLabel, QLineEdit,
                                       QPushButton, QVBoxLayout, QHBoxLayout)
        from PySide6.QtCore import Qt, QTimer
        from PySide6.QtGui import QFont
    except Exception:
        # 没有 Qt 环境（极少见）时退化为控制台输出，不至于静默失败
        print("本软件需授权后使用：", reason or "")
        print("您的机器码：", machine_code())
        return

    app = QApplication.instance()
    owned = app is None
    if owned:
        app = QApplication(sys.argv)

    code = machine_code()
    dlg = QDialog(parent)
    dlg.setWindowTitle("环境质量判定工作台 — 软件授权")
    dlg.setModal(True)
    lay = QVBoxLayout(dlg)

    title = QLabel("本软件需授权后使用")
    f = QFont("Microsoft YaHei", 12)
    f.setBold(True)
    title.setFont(f)
    lay.addWidget(title)

    st = QLabel("当前状态：" + (reason or "本软件需授权后使用"))
    st.setStyleSheet("color:#b00020;")
    st.setWordWrap(True)
    lay.addWidget(st)

    lay.addWidget(QLabel("您的机器码（请复制后发给软件作者申请授权）："))
    ed = QLineEdit(code)
    ed.setReadOnly(True)
    ed.setAlignment(Qt.AlignCenter)
    ed.setFont(QFont("Consolas", 13))
    lay.addWidget(ed)

    row = QHBoxLayout()
    btn = QPushButton("复制机器码")

    def _copy():
        try:
            QApplication.clipboard().setText(code)
            btn.setText("已复制 ✓")
            QTimer.singleShot(1500, lambda: btn.setText("复制机器码"))
        except Exception:
            pass

    btn.clicked.connect(_copy)
    row.addWidget(btn)
    row.addStretch(1)
    lay.addLayout(row)

    tip = QLabel("使用步骤：\n"
                 "1. 把上面的机器码发给软件作者；\n"
                 "2. 作者签发与本机绑定的 license.key 授权文件发回给您；\n"
                 "3. 将 license.key 与本程序放在同一目录，重新启动即可使用。\n"
                 "（本授权仅对本软件有效，与作者的其它软件各自独立。）")
    tip.setStyleSheet("color:#444;")
    tip.setWordWrap(True)
    lay.addWidget(tip)

    quit_row = QHBoxLayout()
    quit_row.addStretch(1)
    qb = QPushButton("退出")
    qb.clicked.connect(dlg.accept)
    quit_row.addWidget(qb)
    lay.addLayout(quit_row)

    dlg.exec()


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
