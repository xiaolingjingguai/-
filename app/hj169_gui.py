"""HJ 169 风险计算器（桌面版）

依据《建设项目环境风险评价技术导则》（HJ 169-2018）附录C、D、F、G，进行环境风险潜势判定、
事故源强核算与大气预测模型筛选。物质库可按中文名、英文名、CAS 号检索，选中后参数自动带入。
本程序不做扩散浓度预测。
"""
import json
import math
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import hj169calc as H
import selfcheck

APP_NAME = "HJ 169 风险计算器"
APP_VER = "1.0（2026-10-07）"
STD = "《建设项目环境风险评价技术导则》（HJ 169-2018）"
fmt = H.fmt


def resource(*parts):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


def load_db():
    with open(resource("data", "substances.json"), encoding="utf-8") as f:
        return json.load(f)


def parse(v):
    s = str(v).strip().replace("×10^", "e").replace("，", ".")
    if not s:
        raise ValueError("空值")
    return float(s)


# ====================================================================== 通用控件
class ScrollFrame(ttk.Frame):
    """可纵向滚动的容器，内部放表单。"""

    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas, padding=(4, 4, 12, 4))
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.win, width=e.width))
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.vsb.pack(side="right", fill="y")
        self.inner.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._wheel))
        self.inner.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _wheel(self, e):
        self.canvas.yview_scroll(int(-e.delta / 120), "units")


class Form:
    """参数表单：每行 标签 | 输入框 | 单位 | 来源。用户手改后来源变为“用户输入”。"""

    def __init__(self, parent, on_change):
        self.parent = parent
        self.on_change = on_change
        self.vars, self.src, self.srclbl, self.rows, self.labels = {}, {}, {}, {}, {}
        self.r = 0
        parent.columnconfigure(1, weight=0)
        parent.columnconfigure(3, weight=1)

    def head(self, text, ref=""):
        f = ttk.Frame(self.parent)
        f.grid(row=self.r, column=0, columnspan=4, sticky="w", pady=(12, 4))
        ttk.Label(f, text=text, style="H.TLabel").pack(side="left")
        if ref:
            ttk.Label(f, text="  " + ref, style="Ref.TLabel").pack(side="left")
        self.r += 1

    def add(self, key, label, unit="", default="", src=""):
        lab = ttk.Label(self.parent, text=label, wraplength=230, justify="left")
        lab.grid(row=self.r, column=0, sticky="w", pady=2, padx=(0, 8))
        v = tk.StringVar(value=str(default))
        e = ttk.Entry(self.parent, textvariable=v, width=16, font=("Consolas", 10))
        e.grid(row=self.r, column=1, sticky="w", pady=2)
        u = ttk.Label(self.parent, text=unit, style="Unit.TLabel")
        u.grid(row=self.r, column=2, sticky="w", padx=4)
        s = ttk.Label(self.parent, text="", style="Src.TLabel", wraplength=330, justify="left")
        s.grid(row=self.r, column=3, sticky="w", padx=(6, 0))
        e.bind("<KeyRelease>", lambda ev, k=key: self._user(k))
        self.vars[key], self.srclbl[key], self.rows[key], self.labels[key] = v, s, (lab, e, u, s), label
        self.set(key, default, src)
        self.r += 1
        return e

    def combo(self, key, label, options, default=0):
        """options: [(值, 显示文字)]"""
        lab = ttk.Label(self.parent, text=label, wraplength=230, justify="left")
        lab.grid(row=self.r, column=0, sticky="w", pady=2, padx=(0, 8))
        cb = ttk.Combobox(self.parent, values=[o[1] for o in options], state="readonly", width=44)
        cb.current(default)
        cb.grid(row=self.r, column=1, columnspan=3, sticky="w", pady=2)
        cb.bind("<<ComboboxSelected>>", lambda e: self.on_change())
        cb.options = options
        self.vars[key], self.rows[key], self.labels[key] = cb, (lab, cb), label
        self.r += 1
        return cb

    def _user(self, k):
        if self.src.get(k) != "用户输入":
            self.src[k] = "用户输入"
            self.srclbl[k].configure(text="用户输入（请在报告中注明来源）", style="SrcUser.TLabel")
        self.on_change()

    def set(self, key, val, src=""):
        self.vars[key].set(str(val))
        self.src[key] = src or ""
        if key in self.srclbl:
            self.srclbl[key].configure(text=("来源：" + src) if src else "", style="Src.TLabel")

    def get(self, key):
        w = self.vars[key]
        if isinstance(w, ttk.Combobox):
            return w.options[w.current()][0]
        return parse(w.get())

    def text(self, key):
        w = self.vars[key]
        return w.get()

    def source(self, key, dflt="用户输入"):
        return self.src.get(key) or dflt

    def show(self, key, visible):
        for w in self.rows[key]:
            if visible:
                w.grid()
            else:
                w.grid_remove()


class ResultPane(ttk.Frame):
    """结果区：摘要 + 提示 + 计算过程，附“复制计算书”“导出”按钮。"""

    def __init__(self, master, app, key):
        super().__init__(master, padding=6)
        self.app, self.key = app, key
        bar = ttk.Frame(self)
        bar.pack(fill="x")
        ttk.Label(bar, text="计算结果", style="H.TLabel").pack(side="left")
        ttk.Button(bar, text="导出计算书…", command=self.export).pack(side="right")
        ttk.Button(bar, text="复制计算书", command=self.copy).pack(side="right", padx=6)
        self.txt = tk.Text(self, wrap="word", font=("Microsoft YaHei UI", 10), relief="flat", padx=10, pady=8,
                           background="#f6f8f7", borderwidth=1, highlightthickness=1, highlightbackground="#d3dcd9")
        sb = ttk.Scrollbar(self, command=self.txt.yview)
        self.txt.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", pady=(6, 0))
        self.txt.pack(fill="both", expand=True, pady=(6, 0))
        self.txt.tag_configure("big", font=("Microsoft YaHei UI", 13, "bold"), foreground="#0d6b66", spacing3=4)
        self.txt.tag_configure("h", font=("Microsoft YaHei UI", 10, "bold"), spacing1=8, spacing3=2)
        self.txt.tag_configure("warn", foreground="#8a4b00", background="#fff3dc", lmargin1=6, lmargin2=6, spacing1=2, spacing3=2)
        self.txt.tag_configure("f", foreground="#5a6a70")
        self.txt.tag_configure("mono", font=("Consolas", 10))
        self.txt.tag_configure("res", font=("Consolas", 10, "bold"))
        self.sheet = ""

    def show(self, summary, warn, steps, sheet, extra=""):
        t = self.txt
        t.configure(state="normal")
        t.delete("1.0", "end")
        for line in summary:
            t.insert("end", line + "\n", "big")
        if extra:
            t.insert("end", extra + "\n")
        for w in warn:
            t.insert("end", "⚠ " + w + "\n", "warn")
        t.insert("end", "计算过程\n", "h")
        for i, (lab, f, s, r) in enumerate(steps, 1):
            t.insert("end", "（%d）%s\n" % (i, lab), "h")
            t.insert("end", "    " + f + "\n", "f")
            t.insert("end", "    代入：" + s + "\n", "mono")
            t.insert("end", "    结果：" + r + "\n", "res")
        t.configure(state="disabled")
        self.sheet = sheet
        self.app.sheets[self.key] = sheet

    def error(self, msg):
        t = self.txt
        t.configure(state="normal")
        t.delete("1.0", "end")
        t.insert("end", msg + "\n", "warn")
        t.configure(state="disabled")
        self.app.sheets.pop(self.key, None)

    def copy(self):
        self.app.clip(self.sheet)

    def export(self):
        self.app.export_text(self.sheet, self.key)


def sheet_text(title, basis, params, steps, results, warn):
    t = "%s\n依据：%s%s。\n1. 参数取值\n" % (title, STD, basis)
    for i, p in enumerate(params, 1):
        t += "（%d）%s：%s%s（%s）\n" % (i, p[0], p[1], " " + p[2] if p[2] else "", p[3])
    t += "2. 计算过程\n"
    for i, s in enumerate(steps, 1):
        t += "（%d）%s：%s；代入 %s；得 %s\n" % (i, s[0], s[1], s[2], s[3])
    t += "3. 计算结果\n" + "".join(r + "\n" for r in results)
    if warn:
        t += "4. 提示\n" + "".join("（%d）%s\n" % (i, w) for i, w in enumerate(warn, 1))
    return t


# ====================================================================== 主程序
class App:
    def __init__(self, root):
        self.root = root
        self.db = load_db()
        self.subs = self.db["subs"]
        self.sheets = {}
        self.current = None
        self.last_leak = None
        self.last_evap = None
        root.title("%s  %s" % (APP_NAME, APP_VER))
        root.geometry("1320x860")
        root.minsize(1000, 640)
        self._style()

        top = ttk.Frame(root, padding=(12, 10, 12, 6))
        top.pack(fill="x")
        ttk.Label(top, text=APP_NAME, style="Title.TLabel").pack(side="left")
        ttk.Label(top, text="  HJ 169-2018 附录C／D／F／G", style="Ref.TLabel").pack(side="left")
        ttk.Button(top, text="导出全部计算书…", command=self.export_all).pack(side="right")
        ttk.Button(top, text="复制全部计算书", command=lambda: self.clip(self.all_sheets())).pack(side="right", padx=6)

        cur = ttk.Frame(root, padding=(12, 0, 12, 6))
        cur.pack(fill="x")
        ttk.Label(cur, text="当前物质：").pack(side="left")
        self.cur_lbl = ttk.Label(cur, text="未选择（在“物质库”页搜索并选择）", style="Cur.TLabel")
        self.cur_lbl.pack(side="left")
        ttk.Label(cur, text="    本程序不做扩散浓度预测；大气风险预测须采用 SLAB、AFTOX 等推荐模型及经认可的软件。",
                  style="Warn.TLabel").pack(side="left")

        self.nb = ttk.Notebook(root)
        self.nb.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        self.tab_db()
        self.tab_risk()
        self.tab_leak()
        self.tab_evap()
        self.tab_fire()
        self.tab_model()
        self.tab_notes()
        self.recalc_all()

    # -------------------------------------------------------------- 样式
    def _style(self):
        st = ttk.Style()
        try:
            st.theme_use("vista" if sys.platform == "win32" else "clam")
        except tk.TclError:
            pass
        base = ("Microsoft YaHei UI", 10)
        self.root.option_add("*Font", base)
        st.configure(".", font=base)
        st.configure("Title.TLabel", font=("Microsoft YaHei UI", 15, "bold"), foreground="#15242b")
        st.configure("H.TLabel", font=("Microsoft YaHei UI", 10, "bold"), foreground="#15242b")
        st.configure("Ref.TLabel", font=("Consolas", 9), foreground="#0d6b66")
        st.configure("Unit.TLabel", font=("Consolas", 9), foreground="#5a6a70")
        st.configure("Src.TLabel", font=("Microsoft YaHei UI", 8), foreground="#0d6b66")
        st.configure("SrcUser.TLabel", font=("Microsoft YaHei UI", 8), foreground="#8a4b00")
        st.configure("Cur.TLabel", font=("Microsoft YaHei UI", 10, "bold"), foreground="#0d6b66")
        st.configure("Warn.TLabel", foreground="#8a4b00")
        st.configure("Treeview", rowheight=24)
        st.configure("TNotebook.Tab", padding=(14, 5))

    def split(self, tab_title):
        """左表单右结果的页面骨架。"""
        f = ttk.Frame(self.nb)
        self.nb.add(f, text=tab_title)
        pw = ttk.PanedWindow(f, orient="horizontal")
        pw.pack(fill="both", expand=True)
        left = ScrollFrame(pw)
        pw.add(left, weight=3)
        return pw, left.inner

    # -------------------------------------------------------------- 物质库
    def tab_db(self):
        f = ttk.Frame(self.nb, padding=8)
        self.nb.add(f, text="物质库")
        bar = ttk.Frame(f)
        bar.pack(fill="x")
        ttk.Label(bar, text="搜索（中文名／英文名／CAS 号）：").pack(side="left")
        self.q = tk.StringVar()
        e = ttk.Entry(bar, textvariable=self.q, width=36)
        e.pack(side="left")
        e.bind("<KeyRelease>", lambda ev: self.filter_db())
        self.flt = tk.StringVar(value="all")
        for v, t in (("all", "全部"), ("b1", "表B.1 有临界量"), ("h1", "表H.1 有终点浓度"), ("ep", "有终点浓度（含 3146 种）")):
            ttk.Radiobutton(bar, text=t, value=v, variable=self.flt, command=self.filter_db).pack(side="left", padx=6)
        self.db_count = ttk.Label(bar, text="", style="Unit.TLabel")
        self.db_count.pack(side="right")

        pw = ttk.PanedWindow(f, orient="horizontal")
        pw.pack(fill="both", expand=True, pady=(8, 0))
        lf = ttk.Frame(pw)
        cols = ("cas", "cn", "en", "qc", "ep1", "ep2")
        self.tree = ttk.Treeview(lf, columns=cols, show="headings", selectmode="browse")
        for c, t, w in zip(cols, ("CAS 号", "中文名", "英文名", "临界量/t", "终点-1 mg/m³", "终点-2 mg/m³"), (110, 210, 220, 80, 95, 95)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="e" if c in ("qc", "ep1", "ep2") else "w", stretch=c in ("cn", "en"))
        vsb = ttk.Scrollbar(lf, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.show_detail())
        self.tree.bind("<Double-1>", lambda e: self.use_current())
        pw.add(lf, weight=3)

        rf = ttk.Frame(pw, padding=(8, 0, 0, 0))
        btns = ttk.Frame(rf)
        btns.pack(fill="x")
        ttk.Button(btns, text="设为当前物质并带入参数", command=self.use_current).pack(side="left")
        ttk.Button(btns, text="加入 Q 计算", command=self.add_q_from_db).pack(side="left", padx=6)
        ttk.Button(btns, text="复制详情", command=lambda: self.clip(self.detail.get("1.0", "end"))).pack(side="left")
        self.detail = tk.Text(rf, wrap="word", font=("Microsoft YaHei UI", 10), relief="flat", padx=10, pady=8,
                              background="#f6f8f7", highlightthickness=1, highlightbackground="#d3dcd9")
        self.detail.tag_configure("h", font=("Microsoft YaHei UI", 12, "bold"), foreground="#0d6b66", spacing3=4)
        self.detail.tag_configure("k", font=("Microsoft YaHei UI", 10, "bold"))
        self.detail.tag_configure("s", foreground="#5a6a70", font=("Microsoft YaHei UI", 8))
        self.detail.tag_configure("na", foreground="#a0a8aa")
        self.detail.pack(fill="both", expand=True, pady=(6, 0))
        pw.add(rf, weight=2)
        self.filter_db()

    def sub_by_iid(self, iid):
        return self.subs[int(iid)]

    def filter_db(self):
        q = self.q.get().strip().lower()
        mode = self.flt.get()
        self.tree.delete(*self.tree.get_children())
        n = 0
        for i, s in enumerate(self.subs):
            if mode == "b1" and not s["b1"]:
                continue
            if mode == "h1" and not s["h1"]:
                continue
            if mode == "ep" and not (s["h1"] or s["lem"]):
                continue
            if q and q not in s["cas"].lower() and q not in (s["cn"] or "").lower() and q not in (s["en"] or "").lower() \
                    and not any(q in b[0].lower() for b in s["b1"]):
                continue
            qc = "／".join(fmt(b[1]) for b in s["b1"]) if s["b1"] else ""
            ep1, ep2 = (s["h1"] if s["h1"] else ([fmt(s["lem"][0]), fmt(s["lem"][1])] if s["lem"] else ["", ""]))
            cas = "" if s["cas"].startswith("无CAS") else s["cas"]
            self.tree.insert("", "end", iid=str(i), values=(cas, s["cn"], s["en"], qc, ep1, ep2))
            n += 1
            if n >= 1500:
                break
        self.db_count.configure(text="显示 %d 条%s（库内共 %d 条）" % (n, "，结果过多仅显示前 1500 条" if n >= 1500 else "", len(self.subs)))

    def show_detail(self):
        sel = self.tree.selection()
        if not sel:
            return
        s = self.sub_by_iid(sel[0])
        t = self.detail
        t.configure(state="normal")
        t.delete("1.0", "end")
        cas = "无 CAS 号" if s["cas"].startswith("无CAS") else "CAS " + s["cas"]
        t.insert("end", "%s　%s\n" % (s["cn"] or s["en"], cas), "h")
        if s["en"]:
            t.insert("end", s["en"] + "\n")
        if s["cn_src"]:
            t.insert("end", "中文名来源：%s\n" % s["cn_src"], "s")
        t.insert("end", "\n临界量（HJ 169-2018 附录B 表B.1）\n", "k")
        if s["b1"]:
            for b in s["b1"]:
                t.insert("end", "  %s：%s t%s\n" % (b[0], fmt(b[1]), "（%s）" % b[2] if b[2] else ""))
        else:
            t.insert("end", "  表B.1 未列入。可按 GHS 分类对照表B.2 取推荐临界量，或注明依据。\n", "na")
        t.insert("end", "\n大气毒性终点浓度\n", "k")
        if s["h1"]:
            t.insert("end", "  表H.1：终点浓度-1 %s mg/m³，终点浓度-2 %s mg/m³（HJ 169-2018 附录H，法定引用值）\n" % tuple(s["h1"]))
        if s["lem"]:
            l = s["lem"]
            t.insert("end", "  3146 种补充表（PAC-3／PAC-2）：%s／%s mg/m³\n" % (fmt(l[0]), fmt(l[1])))
            t.insert("end", "  DOE PacTeel 2026-09-17 现行值：%s／%s mg/m³（%s）\n" % (fmt(l[2]), fmt(l[3]), l[4] or "—"), "s")
        if not s["h1"] and not s["lem"]:
            t.insert("end", "  信息不足\n", "na")
        p = s["p"]
        rows = [("分子式", "formula", ""), ("分子量", "mw", "g/mol"), ("熔点", "mp", "℃"), ("沸点", "tb", "℃"), ("闪点", "fp", "℃"),
                ("自燃点", "ait", "℃"), ("爆炸下限", "lel", "%(V/V)"), ("爆炸上限", "uel", "%(V/V)"), ("20 ℃ 饱和蒸气压", "pv20", "kPa"),
                ("液体密度", "rhoL", "g/cm³"), ("20 ℃ 饱和液体密度", "rhoL20", "kg/m³"), ("气体密度", "rhoG", "g/L"), ("相对蒸气密度（空气=1）", "vd", ""),
                ("正常沸点汽化热", "hvTb", "J/kg"), ("液体定压比热容", "cpL", "J/(kg·K)"), ("绝热指数 γ（298.15 K）", "gamma", ""),
                ("LD50 经口（大鼠）", "ld50o", ""), ("LD50 经皮", "ld50d", ""), ("LC50 吸入（大鼠）", "lc50", ""), ("水溶性", "sol", ""), ("IARC 致癌分类", "iarc", "")]
        t.insert("end", "\n理化、燃爆与毒理参数\n", "k")
        for lab, k, u in rows:
            if k in p:
                v, src = p[k]
                t.insert("end", "  %s：%s %s\n" % (lab, fmt(v) if isinstance(v, float) else v, u))
                if src:
                    t.insert("end", "      来源：%s\n" % src, "s")
            else:
                t.insert("end", "  %s：信息不足\n" % lab, "na")
        t.insert("end", "\n理化参数取自 CalebBell/chemicals（提交 e79047588b30）原始数据与 PubChem（HSDB/ICSC），使用前请以 MSDS 或手册核对。\n", "s")
        t.configure(state="disabled")

    def selected_sub(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo(APP_NAME, "请先在列表中选择一种物质。")
            return None
        return self.sub_by_iid(sel[0])

    def use_current(self):
        s = self.selected_sub()
        if not s:
            return
        self.current = s
        cas = "" if s["cas"].startswith("无CAS") else "（CAS %s）" % s["cas"]
        self.cur_lbl.configure(text="%s%s" % (s["cn"] or s["en"], cas))
        filled = self.fill_from(s)
        self.recalc_all()
        messagebox.showinfo(APP_NAME, "已设为当前物质：%s%s\n\n已带入参数：%s\n\n库中缺少的参数保持原值，请手工核对填写。"
                            % (s["cn"] or s["en"], cas, "、".join(filled) if filled else "无（库中缺少可带入的理化参数）"))

    def fill_from(self, s):
        p, nm, done = s["p"], s["cn"] or s["en"] or s["cas"], []

        def g(k):
            return p.get(k)

        L, E, Mf = self.leak, self.evap, self.model
        rho = None
        if g("rhoL20"):
            rho = (g("rhoL20")[0], g("rhoL20")[1])
        elif g("rhoL"):
            rho = (round(g("rhoL")[0] * 1000, 1), g("rhoL")[1] + "（g/cm³×1000）")
        if rho:
            L.set("rho", rho[0], "%s：%s" % (nm, rho[1]))
            L.set("rho2", rho[0], "%s：%s" % (nm, rho[1]))
            done.append("液体密度")
        if g("mw"):
            M = round(g("mw")[0] / 1000, 7)
            src = "%s：%s（g/mol÷1000）" % (nm, g("mw")[1])
            L.set("M", M, src)
            E.set("M", M, src)
            Mf.set("igM", M, src)
            done.append("摩尔质量")
        if g("gamma"):
            L.set("k", g("gamma")[0], "%s：%s" % (nm, g("gamma")[1]))
            done.append("绝热指数")
        if g("tb"):
            T = round(g("tb")[0] + 273.15, 2)
            src = "%s：%s" % (nm, g("tb")[1])
            L.set("Tb", T, src)
            L.set("TC", T, "%s：常压沸点（%s），作为 T_C 近似值，请复核" % (nm, g("tb")[1]))
            E.set("Tb", T, src)
            done.append("沸点")
        if g("cpL"):
            L.set("cp", g("cpL")[0], "%s：%s（液体值，两相混合物 Cp 请复核）" % (nm, g("cpL")[1]))
            E.set("Cp", g("cpL")[0], "%s：%s" % (nm, g("cpL")[1]))
            done.append("液体比热容")
        if g("hvTb"):
            src = "%s：%s" % (nm, g("hvTb")[1])
            L.set("H", g("hvTb")[0], src)
            E.set("Hv", g("hvTb")[0], src)
            E.set("H", g("hvTb")[0], src)
            done.append("汽化热")
        if g("tb") and g("tb")[0] < 20 and g("pv20"):
            L.set("P", round(g("pv20")[0] * 1000), "%s：20 ℃ 饱和蒸气压，%s（按常温全压力储存的液化气体取，请按设计压力复核）" % (nm, g("pv20")[1]))
            done.append("储罐压力")
        elif g("tb") and g("tb")[0] >= 20:
            L.set("P", 101325, "%s：常压沸点高于 20 ℃，按常压储罐取环境压力，请按设计压力复核" % nm)
        try:
            T0 = E.get("T0")
        except ValueError:
            T0 = 298.15
        if g("tb") and g("tb")[0] + 273.15 < T0:
            E.set("p", 101325, "%s：常压沸点低于环境温度，沸腾液池表面蒸气压按环境压力取，请复核" % nm)
            done.append("液面蒸气压")
        elif g("pv20"):
            E.set("p", round(g("pv20")[0] * 1000), "%s：20 ℃ 饱和蒸气压，%s" % (nm, g("pv20")[1]))
            done.append("液面蒸气压")
        if g("mw") and g("tb"):
            Tr = min(g("tb")[0] + 273.15, T0)
            rr = H.ideal_rho(H.P_ATM, g("mw")[0] / 1000, g("tb")[0] + 273.15)
            L.set("rho1", round(rr, 4), "%s：按理想气体 ρ=PM/(RT)，101325 Pa、常压沸点估算" % nm)
            Mf.set("igT", round(Tr, 2), "%s：取常压沸点与环境温度中较低者" % nm)
            done.append("蒸汽密度")
        lc = g("lc50")
        self.fire_lc_ref.configure(text=("%s LC50 参考：%s" % (nm, lc[0])) if lc else "%s：库中无 LC50 吸入数据（信息不足）" % nm)
        return done

    # -------------------------------------------------------------- 风险潜势
    def tab_risk(self):
        pw, f = self.split("风险潜势判定")
        self.risk_items = []  # [name, cas, qc, q, src]
        self.m_units = [(2, 1)]
        ttk.Label(f, text="一、危险物质数量与临界量比值 Q", style="H.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(f, text="附录C.1.1 式(C.1)；临界量取附录B 表B.1、表B.2", style="Ref.TLabel").grid(row=1, column=0, sticky="w")
        tf = ttk.Frame(f)
        tf.grid(row=2, column=0, sticky="nsew", pady=4)
        f.columnconfigure(0, weight=1)
        self.qtree = ttk.Treeview(tf, columns=("n", "cas", "qc", "q", "r", "src"), show="headings", height=6)
        for c, t, w in zip(("n", "cas", "qc", "q", "r", "src"), ("物质", "CAS 号", "临界量 Qᵢ/t", "最大存在总量 qᵢ/t", "qᵢ/Qᵢ", "临界量来源"), (170, 90, 80, 110, 70, 160)):
            self.qtree.heading(c, text=t)
            self.qtree.column(c, width=w, anchor="e" if c in ("qc", "q", "r") else "w")
        self.qtree.pack(fill="x")
        self.qtree.bind("<Double-1>", lambda e: self.edit_q())
        b = ttk.Frame(f)
        b.grid(row=3, column=0, sticky="w")
        ttk.Button(b, text="从物质库添加", command=lambda: self.nb.select(0)).pack(side="left")
        ttk.Button(b, text="添加表B.2 类别", command=self.add_b2).pack(side="left", padx=4)
        ttk.Button(b, text="手工添加", command=lambda: self.edit_q(new=True)).pack(side="left")
        ttk.Button(b, text="修改所选（双击）", command=self.edit_q).pack(side="left", padx=4)
        ttk.Button(b, text="删除所选", command=self.del_q).pack(side="left")

        ttk.Label(f, text="二、行业及生产工艺 M", style="H.TLabel").grid(row=4, column=0, sticky="w", pady=(14, 0))
        ttk.Label(f, text="附录C.1.2 表C.1；多套工艺单元分别评分求和", style="Ref.TLabel").grid(row=5, column=0, sticky="w")
        self.mtree = ttk.Treeview(f, columns=("o", "n", "s"), show="headings", height=4)
        for c, t, w in zip(("o", "n", "s"), ("评估依据", "套数", "分值"), (520, 60, 90)):
            self.mtree.heading(c, text=t)
            self.mtree.column(c, width=w, anchor="w" if c == "o" else "e")
        self.mtree.grid(row=6, column=0, sticky="ew", pady=4)
        mb = ttk.Frame(f)
        mb.grid(row=7, column=0, sticky="w")
        self.m_opt = ttk.Combobox(mb, values=[c[0] for c in H.C1], state="readonly", width=60)
        self.m_opt.current(2)
        self.m_opt.pack(side="left")
        ttk.Label(mb, text=" 套数").pack(side="left")
        self.m_cnt = tk.StringVar(value="1")
        ttk.Entry(mb, textvariable=self.m_cnt, width=5).pack(side="left")
        ttk.Button(mb, text="添加", command=self.add_m).pack(side="left", padx=4)
        ttk.Button(mb, text="删除所选", command=self.del_m).pack(side="left")

        ef = ttk.Frame(f)
        ef.grid(row=8, column=0, sticky="ew")
        self.E = Form(ef, self.calc_risk)
        self.E.head("三、环境敏感程度 E", "附录D 表D.1～D.7")
        self.E.combo("mode", "大气：项目形式", [("site", "厂区类项目"), ("pipe", "油气、化学品输送管线")])
        self.E.add("pop5", "周边 5 km 范围人口（居住区、医疗、文教、科研、行政机构）", "人", 30000)
        self.E.add("pop05", "周边 500 m 范围人口", "人", 300)
        self.E.combo("special", "其他需要特殊保护区域", [(False, "无"), (True, "有")])
        self.E.add("perkm", "管段周边 200 m 每千米人口", "人/km", 80)
        self.E.combo("F", "地表水：功能敏感性（表D.3）", [("F1", "F1 敏感：Ⅱ类及以上／海水第一类／24 h 流经范围涉跨国界"),
                                                   ("F2", "F2 较敏感：Ⅲ类／海水第二类／24 h 流经范围涉跨省界"), ("F3", "F3 低敏感：上述以外")], 2)
        self.E.combo("S", "地表水：环境敏感目标（表D.4）", [("S1", "S1 下游 10 km 内有饮用水水源保护区、自然保护区等"),
                                                   ("S2", "S2 有水产养殖区、天然渔场、森林公园等"), ("S3", "S3 无上述类型敏感目标")], 2)
        self.E.combo("G", "地下水：功能敏感性（表D.6）", [("G1", "G1 敏感：集中式饮用水水源准保护区等"),
                                                 ("G2", "G2 较敏感：准保护区以外补给径流区、分散式饮用水源地等"), ("G3", "G3 不敏感：上述以外")], 2)
        self.E.combo("D", "地下水：包气带防污性能（表D.7）", [("auto", "按下方 Mb、K 自动判定"), ("D1", "D1"), ("D2", "D2"), ("D3", "D3")], 0)
        self.E.add("Mb", "岩土层单层厚度 Mb", "m", 1.2)
        self.E.add("K", "渗透系数 K", "cm/s", "5e-5")
        self.E.combo("cont", "岩土层分布连续、稳定", [(True, "是"), (False, "否")])

        self.risk_res = ResultPane(pw, self, "risk")
        pw.add(self.risk_res, weight=2)
        nh3 = next((s for s in self.subs if s["cas"] == "7664-41-7"), None)
        if nh3:
            self.risk_items.append([nh3["cn"], nh3["cas"], nh3["b1"][0][1], 20.0, "表B.1（示例数据）"])
        hcl = next((s for s in self.subs if s["cas"] == "7647-01-0"), None)
        if hcl and len(hcl["b1"]) > 1:
            self.risk_items.append([hcl["b1"][1][0], hcl["cas"], hcl["b1"][1][1], 10.0, "表B.1（示例数据）"])
        self.draw_q()
        self.draw_m()

    def draw_q(self):
        self.qtree.delete(*self.qtree.get_children())
        for i, (n, cas, qc, q, src) in enumerate(self.risk_items):
            r = fmt(q / qc) if qc else "—"
            self.qtree.insert("", "end", iid=str(i), values=(n, cas or "—", fmt(qc) if qc else "信息不足", fmt(q), r, src))

    def draw_m(self):
        self.mtree.delete(*self.mtree.get_children())
        for i, (o, c) in enumerate(self.m_units):
            self.mtree.insert("", "end", iid=str(i), values=(H.C1[o][0], fmt(c), H.C1[o][2]))

    def add_m(self):
        try:
            c = parse(self.m_cnt.get())
        except ValueError:
            messagebox.showwarning(APP_NAME, "套数请输入数字。")
            return
        self.m_units.append((self.m_opt.current(), c))
        self.draw_m()
        self.calc_risk()

    def del_m(self):
        for iid in sorted(self.mtree.selection(), key=int, reverse=True):
            self.m_units.pop(int(iid))
        self.draw_m()
        self.calc_risk()

    def del_q(self):
        for iid in sorted(self.qtree.selection(), key=int, reverse=True):
            self.risk_items.pop(int(iid))
        self.draw_q()
        self.calc_risk()

    def add_q_from_db(self):
        s = self.selected_sub()
        if not s:
            return
        cas = "" if s["cas"].startswith("无CAS") else s["cas"]
        opts = [(b[0], b[1], "表B.1") for b in s["b1"]]
        if not opts:
            opts = [(s["cn"] or s["en"], None, "表B.1 未列入，请填写临界量并注明依据（可对照表B.2）")]
        name, qc, src = self.choose(opts) if len(opts) > 1 else opts[0]
        if name is None:
            return
        self.edit_q(new=True, preset=[name, cas, qc, 0.0, src])

    def choose(self, opts):
        d = tk.Toplevel(self.root)
        d.title("选择临界量条目")
        d.transient(self.root)
        d.grab_set()
        ttk.Label(d, text="该物质在表B.1 中有多条记录，请按物料实际形态选择：", padding=10).pack()
        res = [None, None, None]
        for o in opts:
            ttk.Button(d, text="%s　%s t" % (o[0], fmt(o[1])), command=lambda o=o: (res.__setitem__(slice(0, 3), o), d.destroy())).pack(fill="x", padx=10, pady=2)
        ttk.Button(d, text="取消", command=d.destroy).pack(pady=8)
        self.root.wait_window(d)
        return tuple(res)

    def add_b2(self):
        opts = [(b[0], b[1], "表B.2（%s）" % b[2]) for b in self.db["b2"]]
        d = tk.Toplevel(self.root)
        d.title("表B.2 其他危险物质临界量推荐值")
        d.transient(self.root)
        d.grab_set()
        ttk.Label(d, text="表B.1 未列入的物质可按 GHS 分类选择推荐临界量：", padding=10).pack()
        for o in opts:
            ttk.Button(d, text="%s　%s t" % (o[0], fmt(o[1])),
                       command=lambda o=o: (d.destroy(), self.edit_q(new=True, preset=[o[0], "", o[1], 0.0, o[2]]))).pack(fill="x", padx=10, pady=2)
        ttk.Button(d, text="取消", command=d.destroy).pack(pady=8)

    def edit_q(self, new=False, preset=None):
        if new:
            item = preset or ["", "", None, 0.0, "用户填写（请注明依据）"]
            idx = None
        else:
            sel = self.qtree.selection()
            if not sel:
                return
            idx = int(sel[0])
            item = list(self.risk_items[idx])
        d = tk.Toplevel(self.root)
        d.title("危险物质")
        d.transient(self.root)
        d.grab_set()
        fr = ttk.Frame(d, padding=12)
        fr.pack()
        vs = []
        for r, (lab, val) in enumerate((("物质名称", item[0]), ("CAS 号", item[1]), ("临界量 Qᵢ/t", "" if item[2] is None else item[2]),
                                        ("最大存在总量 qᵢ/t（厂界内）", item[3]), ("临界量来源", item[4]))):
            ttk.Label(fr, text=lab).grid(row=r, column=0, sticky="w", pady=3)
            v = tk.StringVar(value=str(val))
            ttk.Entry(fr, textvariable=v, width=44).grid(row=r, column=1, pady=3)
            vs.append(v)

        def ok():
            try:
                qc = parse(vs[2].get()) if vs[2].get().strip() else None
                q = parse(vs[3].get())
            except ValueError:
                messagebox.showwarning(APP_NAME, "临界量与存在量请输入数字。", parent=d)
                return
            src = vs[4].get()
            if idx is not None and qc != self.risk_items[idx][2]:
                src = "用户修改（请注明依据）"
            rec = [vs[0].get().strip() or "未命名物质", vs[1].get().strip(), qc, q, src]
            if idx is None:
                self.risk_items.append(rec)
            else:
                self.risk_items[idx] = rec
            d.destroy()
            self.draw_q()
            self.calc_risk()
            self.nb.select(1)

        ttk.Button(fr, text="确定", command=ok).grid(row=6, column=1, sticky="e", pady=(8, 0))
        d.bind("<Return>", lambda e: ok())

    def calc_risk(self):
        E = self.E
        site = E.get("mode") == "site"
        for k in ("pop5", "pop05", "special"):
            E.show(k, site)
        E.show("perkm", not site)
        auto = E.get("D") == "auto"
        for k in ("Mb", "K", "cont"):
            E.show(k, auto)
        try:
            items = [{"name": n, "cas": c, "qc": qc, "q": q} for n, c, qc, q, _ in self.risk_items]
            Q = H.q_value(items)
            M = H.m_value(self.m_units)
            P = H.p_level(Q["cls"], M["cls"])
            air = H.e_air(E.get("mode"), E.get("pop5") if site else 0, E.get("pop05") if site else 0,
                          E.get("special") if site else False, 0 if site else E.get("perkm"))
            D = H.d_class(E.get("Mb"), E.get("K"), E.get("cont")) if auto else E.get("D")
        except (ValueError, ZeroDivisionError) as ex:
            self.risk_res.error("参数不完整或格式有误：%s" % ex)
            return
        self.draw_q()
        F, S, G = E.get("F"), E.get("S"), E.get("G")
        eW, eG = H.TABLE_D2[S][F], H.TABLE_D5[D][G]
        els = []
        for k, e in (("大气", air["v"]), ("地表水", eW), ("地下水", eG)):
            pot = H.potential(P, e)
            els.append((k, e, pot, H.GRADE[pot]))
        overall = H.max_pot([x[2] for x in els])
        warn = Q["warn"] + M["warn"] + air["warn"]
        if Q["cls"] == "Q<1":
            warn.append("Q＜1，按附录C.1.1 环境风险潜势直接判为Ⅰ，开展简单分析（附录A）。")
        steps = Q["steps"] + ([] if Q["cls"] == "Q<1" else M["steps"])
        if P:
            steps.append(("危险物质及工艺系统危险性 P", "表C.2", "%s，%s" % (Q["cls"], M["cls"]), P))
        steps += air["steps"]
        if auto:
            steps.append(("包气带防污性能", "表D.7", "Mb=%s m，K=%s cm/s，%s" % (fmt(E.get("Mb")), fmt(E.get("K")), "连续稳定" if E.get("cont") else "不连续"), D))
        steps.append(("地表水环境敏感程度", "表D.2", "%s，%s" % (F, S), eW))
        steps.append(("地下水环境敏感程度", "表D.5", "%s，%s" % (G, D), eG))
        for k, e, pot, g in els:
            steps.append(("%s环境风险潜势" % k, "表2" if P else "附录C.1.1（Q＜1）", "%s，%s" % (P, e) if P else "Q＜1", "%s，评价工作等级：%s" % (pot, g)))
        steps.append(("建设项目环境风险潜势", "6.4 取各要素等级的相对高值；评价工作等级按表1", "、".join(x[2] for x in els), "%s，%s" % (overall, H.GRADE[overall])))
        summary = ["Q = %s（%s）　M = %s（%s）　P = %s" % (fmt(Q["v"]), Q["cls"], fmt(M["v"]), M["cls"], P or "—"),
                   "建设项目环境风险潜势：%s　评价工作等级：%s" % (overall, H.GRADE[overall])]
        extra = "\n".join("　%s：敏感程度 %s，风险潜势 %s，评价工作等级 %s" % x for x in els)
        params = [["%s%s 最大存在总量 q／临界量 Q" % (n, "（CAS %s）" % c if c else ""), "%s t／%s t" % (fmt(q), fmt(qc) if qc else "信息不足"), "", "临界量来源：HJ 169-2018 附录B %s" % src]
                  for n, c, qc, q, src in self.risk_items]
        params += [["工艺单元", "%s，%s 套" % (H.C1[o][0], fmt(c)), "", "表C.1"] for o, c in self.m_units]
        if site:
            params.append(["大气敏感目标人口", "5 km 范围 %s 人，500 m 范围 %s 人，特殊保护区域：%s" % (fmt(E.get("pop5")), fmt(E.get("pop05")), "有" if E.get("special") else "无"), "", "现场调查／统计资料，请注明"])
        else:
            params.append(["管段周边 200 m 每千米人口", fmt(E.get("perkm")), "人/km", "现场调查，请注明"])
        params.append(["地表水", "%s；%s" % (E.vars["F"].get(), E.vars["S"].get()), "", "表D.3、表D.4"])
        params.append(["地下水", "%s；包气带 %s" % (E.vars["G"].get(), D), "", "表D.6、表D.7"])
        sheet = sheet_text("（一）环境风险潜势初判", " 6.1～6.4、附录C、附录D", params, steps,
                           ["Q = %s（%s）；M = %s（%s）；P = %s" % (fmt(Q["v"]), Q["cls"], fmt(M["v"]), M["cls"], P or "—")]
                           + ["%s：%s，环境风险潜势 %s，评价工作等级 %s" % x for x in els]
                           + ["建设项目环境风险潜势综合等级为 %s，评价工作等级为%s（审批类别与评价等级请工程师复核）。" % (overall, H.GRADE[overall])], warn)
        self.risk_res.show(summary, warn, steps, sheet, extra)

    # -------------------------------------------------------------- 泄漏速率
    def tab_leak(self):
        pw, f = self.split("泄漏速率")
        L = self.leak = Form(f, self.calc_leak)
        L.head("泄漏形式与裂口", "附录F.1；示例：液氨储罐，圆形裂口 10 mm")
        L.combo("type", "泄漏形式", [("liq", "液体泄漏 式(F.1)"), ("gas", "气体泄漏 式(F.2)～(F.5)"), ("two", "两相流泄漏 式(F.6)～(F.8)")])
        L.combo("shape", "裂口形状", [("circle", "圆形（多边形）"), ("triangle", "三角形"), ("rect", "长方形")])
        L.combo("re", "雷诺数 Re（表F.1）", [("gt", "＞100"), ("le", "≤100")])
        L.combo("cdmode", "泄漏系数 C_d", [("auto", "按导则表F.1／式(F.4)注／式(F.6)注自动取值"), ("manual", "手工输入")])
        L.add("cd", "泄漏系数 C_d（手工）", "", 0.65)
        L.add("d", "裂口当量直径 d（面积按 πd²/4）", "mm", 10)
        L.head("工况与物性")
        L.add("P", "容器内压力 P（绝对压力）", "Pa", 854500, "氨 20 ℃ 饱和蒸气压 854.5 kPa（Perry 手册 8 版表2-8 计算）")
        L.add("P0", "环境压力 P₀", "Pa", 101325, "标准大气压")
        L.add("rho", "液体密度 ρ", "kg/m³", 609.4, "氨 20 ℃ 饱和液体密度（Perry 手册 8 版表2-32）")
        L.add("h", "裂口之上液位高度 h", "m", 2)
        L.add("TT", "储存温度（校核急骤蒸发，选填）", "K", 293.15)
        L.add("Tb", "常压沸点（校核用）", "K", 239.85, "氨常压沸点 −33.3 ℃（CRC 手册 95 版）")
        L.add("M", "摩尔质量 M", "kg/mol", 0.0170305, "氨分子量 17.0305 g/mol（PubChem）")
        L.add("k", "绝热指数 γ", "", 1.31, "氨，CRC 298.15 K 理想气体 Cp=35.1 J/(mol·K) 计算")
        L.add("TG", "气体温度 T_G", "K", 293.15)
        L.combo("pc", "两相流临界压力 P_C 取值", [("ratio", "0.55P（量纲推断，常用）"), ("literal", "0.55 Pa（导则原文字面）")])
        L.add("cp", "两相混合物定压比热容 C_p", "J/(kg·K)", 4651, "氨 20 ℃ 液体（Perry 手册 8 版表2-153）")
        L.add("TLG", "两相混合物温度 T_LG", "K", 293.15)
        L.add("TC", "临界压力下沸点 T_C", "K", 239.85, "氨常压沸点，作为 T_C 近似值，请复核")
        L.add("H", "汽化热 H", "J/kg", 1369895, "氨正常沸点汽化热 23330 J/mol（CRC 手册）")
        L.add("rho1", "蒸汽密度 ρ₁", "kg/m³", 0.8654, "氨按理想气体 101325 Pa、239.85 K 估算")
        L.add("rho2", "液体密度 ρ₂", "kg/m³", 609.4, "氨 20 ℃ 饱和液体密度（Perry 手册 8 版表2-32）")
        L.add("t", "泄漏时间 t（8.2.2.1：有紧急隔离 10 min，无 30 min）", "s", 600)
        self.leak_res = ResultPane(pw, self, "leak")
        pw.add(self.leak_res, weight=2)

    def calc_leak(self):
        L = self.leak
        t = L.get("type")
        vis = {"liq": {"re", "rho", "h", "TT", "Tb", "P0"}, "gas": {"M", "k", "TG", "P0"},
               "two": {"pc", "cp", "TLG", "TC", "H", "rho1", "rho2"}}
        for k in ("re", "rho", "h", "TT", "Tb", "P0", "M", "k", "TG", "pc", "cp", "TLG", "TC", "H", "rho1", "rho2"):
            L.show(k, k in vis[t])
        manual = L.get("cdmode") == "manual"
        L.show("cd", manual)
        try:
            sh = L.get("shape")
            if manual:
                Cd, cdsrc = L.get("cd"), "用户输入（请注明依据）"
            elif t == "liq":
                Cd = H.CD_LIQ[L.get("re")][sh]
                cdsrc = "表F.1（Re%s100，%s）" % ("＞" if L.get("re") == "gt" else "≤", H.SHAPE_CN[sh])
            elif t == "gas":
                Cd, cdsrc = H.CD_GAS[sh], "式(F.4)注（%s）" % H.SHAPE_CN[sh]
            else:
                Cd, cdsrc = 0.8, "式(F.6)注，两相流泄漏系数取 0.8"
            d = L.get("d")
            A = math.pi * (d / 1000) ** 2 / 4
            P = L.get("P")
            pA = [["泄漏系数 C_d", fmt(Cd), "", cdsrc], ["裂口面积 A", fmt(A), "m²", "A = πd²/4，d = %s mm" % fmt(d)], ["容器压力 P（绝对压力）", fmt(P), "Pa", L.source("P")]]
            if t == "liq":
                r = H.liquid_leak(Cd, A, L.get("rho"), P, L.get("P0"), L.get("h"))
                title, basis, label = "（二）液体泄漏速率计算", " 附录F.1.1 式(F.1)、表F.1", "Q_L"
                params = pA + [["环境压力 P₀", fmt(L.get("P0")), "Pa", L.source("P0")], ["液体密度 ρ", fmt(L.get("rho")), "kg/m³", L.source("rho")],
                               ["裂口之上液位高度 h", fmt(L.get("h")), "m", L.source("h", "设计资料")], ["重力加速度 g", "9.81", "m/s²", "式(F.1)注"]]
                try:
                    TT, Tb = L.get("TT"), L.get("Tb")
                    if TT > Tb:
                        r["warn"].append("储存温度 %s K 高于常压沸点 %s K，泄漏时喷口内可能发生急骤蒸发，式(F.1) 的限制条件可能不满足，宜同时按两相流式(F.6)～(F.8) 校核，取对后果更不利者并在报告中说明。" % (fmt(TT), fmt(Tb)))
                except ValueError:
                    pass
            elif t == "gas":
                r = H.gas_leak(Cd, A, P, L.get("P0"), L.get("M"), L.get("k"), L.get("TG"))
                title, basis, label = "（二）气体泄漏速率计算", " 附录F.1.2 式(F.2)～(F.5)", "Q_G"
                params = pA + [["环境压力 P₀", fmt(L.get("P0")), "Pa", L.source("P0")], ["摩尔质量 M", fmt(L.get("M"), 6), "kg/mol", L.source("M")],
                               ["绝热指数 γ", fmt(L.get("k")), "", L.source("k")], ["气体温度 T_G", fmt(L.get("TG")), "K", L.source("TG", "设计工况")],
                               ["气体常数 R", "8.314", "J/(mol·K)", "通用值，导则未给数值"]]
            else:
                r = H.two_phase_leak(Cd, A, P, L.get("cp"), L.get("TLG"), L.get("TC"), L.get("H"), L.get("rho1"), L.get("rho2"), L.get("pc"))
                title, basis, label = "（二）两相流泄漏速率计算", " 附录F.1.3 式(F.6)～(F.8)", "Q_LG"
                params = pA + [["临界压力 P_C 取值方式", L.vars["pc"].get(), "", "见“说明与校验”"], ["定压比热容 C_p", fmt(L.get("cp")), "J/(kg·K)", L.source("cp")],
                               ["两相混合物温度 T_LG", fmt(L.get("TLG")), "K", L.source("TLG", "设计工况")], ["临界压力下沸点 T_C", fmt(L.get("TC")), "K", L.source("TC")],
                               ["汽化热 H", fmt(L.get("H")), "J/kg", L.source("H")], ["蒸汽密度 ρ₁", fmt(L.get("rho1")), "kg/m³", L.source("rho1")],
                               ["液体密度 ρ₂", fmt(L.get("rho2")), "kg/m³", L.source("rho2")]]
                if L.get("pc") == "literal":
                    r["warn"].append("按导则原文“P_C 取 0.55 Pa”字面计算；该取值与量纲不符，结果请慎用，见“说明与校验”。")
            tt = L.get("t")
        except (ValueError, ZeroDivisionError) as ex:
            self.leak_res.error("参数不完整或格式有误：%s" % ex)
            return
        mass = r["v"] * tt
        r["steps"].append(("泄漏量", "泄漏速率 × 泄漏时间（8.2.2.1）", "%s kg/s × %s s" % (fmt(r["v"]), fmt(tt)), "%s kg" % fmt(mass)))
        params.append(["泄漏时间 t", fmt(tt), "s", "8.2.2.1（有紧急隔离系统 10 min，无 30 min）"])
        self.last_leak = r["v"]
        summary = ["泄漏速率 %s = %s kg/s　泄漏量 = %s kg" % (label, fmt(r["v"]), fmt(mass))]
        if t == "gas":
            summary.append("流态：%s" % ("临界流" if r["critical"] else "次临界流"))
        if t == "two":
            summary.append("蒸发比例 F_V = %s" % fmt(r["Fv"]))
        sheet = sheet_text(title, basis, params, r["steps"], ["泄漏速率 %s = %s kg/s，泄漏时间 %s s 内泄漏量 %s kg。" % (label, fmt(r["v"]), fmt(tt), fmt(mass))], r["warn"])
        self.leak_res.show(summary, r["warn"], r["steps"], sheet)

    # -------------------------------------------------------------- 液池蒸发
    def tab_evap(self):
        pw, f = self.split("液池蒸发")
        E = self.evap = Form(f, self.calc_evap)
        E.head("闪蒸", "F.1.4.1 式(F.9)(F.10)；示例：液氨泄漏，水泥地面围堰 100 m²")
        E.combo("qlmode", "物质泄漏速率 Q_L 来源", [("leak", "取“泄漏速率”页计算结果"), ("manual", "手工输入")])
        E.add("QL", "物质泄漏速率 Q_L（手工）", "kg/s", 1.559)
        E.add("TT", "储存温度 T_T", "K", 293.15)
        E.add("Tb", "泄漏液体沸点 T_b", "K", 239.85, "氨常压沸点（CRC 手册 95 版）")
        E.add("Cp", "液体定压比热容 C_p", "J/(kg·K)", 4651, "氨 20 ℃ 液体（Perry 手册 8 版表2-153）")
        E.add("Hv", "蒸发热 H_v", "J/kg", 1369895, "氨正常沸点汽化热（CRC 手册）")
        E.add("t1", "闪蒸蒸发时间 t₁", "s", 600)
        E.head("热量蒸发", "F.1.4.2 式(F.11) 表F.2")
        E.add("T0", "环境温度 T₀（最不利气象 25 ℃，9.1.1.4）", "K", 298.15)
        E.add("H", "液体汽化热 H", "J/kg", 1369895, "氨正常沸点汽化热（CRC 手册）")
        E.combo("surf", "地面情况（表F.2）", [(k, "%s　λ=%s W/(m·K)，α=%s m²/s" % (v[0], v[1], fmt(v[2], 3))) for k, v in H.SURF.items()])
        E.add("S", "液池面积 S（以围堰内面积为上限，8.2.2.1）", "m²", 100)
        E.add("t2", "热量蒸发时间 t₂（式中 t）", "s", 600)
        E.head("质量蒸发", "F.1.4.3 式(F.12) 表F.3")
        E.combo("stab", "大气稳定度（表F.3）", [(k, "%s　n=%s，α=%s" % (v[0], v[1], fmt(v[2]))) for k, v in H.STAB.items()], 2)
        E.add("u", "风速 u", "m/s", 1.5)
        E.combo("rmode", "液池半径 r", [("auto", "按围堰等效半径 r = √(S/π)"), ("manual", "手工输入")])
        E.add("r", "液池半径 r（手工）", "m", 5.6419)
        E.add("p", "液体表面蒸气压 p", "Pa", 101325, "氨常压沸点低于环境温度，沸腾液池表面蒸气压按环境压力取，请复核")
        E.add("M", "摩尔质量 M", "kg/mol", 0.0170305, "氨分子量（PubChem）")
        E.add("t3", "从泄漏到全部清理完毕的时间 t₃", "s", 1800)
        self.evap_res = ResultPane(pw, self, "evap")
        pw.add(self.evap_res, weight=2)

    def calc_evap(self):
        E = self.evap
        E.show("QL", E.get("qlmode") == "manual")
        E.show("r", E.get("rmode") == "manual")
        try:
            if E.get("qlmode") == "leak":
                if self.last_leak is None:
                    raise ValueError("“泄漏速率”页尚无有效结果")
                QL, qlsrc = self.last_leak, "“泄漏速率”页计算结果"
            else:
                QL, qlsrc = E.get("QL"), E.source("QL")
            S = E.get("S")
            if E.get("rmode") == "auto":
                r, rsrc = math.sqrt(S / math.pi), "r = √(S/π)，S = %s m²（围堰等效半径，F.1.4.3）" % fmt(S)
            else:
                r, rsrc = E.get("r"), E.source("r")
            o = dict(QL=QL, Cp=E.get("Cp"), TT=E.get("TT"), Tb=E.get("Tb"), Hv=E.get("Hv"), H=E.get("H"), T0=E.get("T0"), S=S,
                     surface=E.get("surf"), t1=E.get("t1"), t2=E.get("t2"), t3=E.get("t3"), stab=E.get("stab"), p=E.get("p"),
                     M=E.get("M"), u=E.get("u"), r=r)
            res = H.evaporation(**o)
        except (ValueError, ZeroDivisionError) as ex:
            self.evap_res.error("参数不完整或格式有误：%s" % ex)
            return
        self.last_evap = (res, r)
        if o["t2"] < 900 or o["t3"] < 900:
            res["warn"].append("8.2.2.1：蒸发时间一般可按 15～30 min 计，请核对 t₂、t₃ 取值依据。")
        res["warn"].append("式(F.11) 中热量蒸发速率随时间 t 递减，本程序按导则式(F.13) 以 t = t₂ 时的 Q₂ 乘以 t₂ 计算，与导则写法一致。")
        params = [["物质泄漏速率 Q_L", fmt(QL), "kg/s", qlsrc], ["储存温度 T_T", fmt(o["TT"]), "K", E.source("TT", "设计工况")], ["沸点 T_b", fmt(o["Tb"]), "K", E.source("Tb")],
                  ["液体定压比热容 C_p", fmt(o["Cp"]), "J/(kg·K)", E.source("Cp")], ["蒸发热 H_v", fmt(o["Hv"]), "J/kg", E.source("Hv")], ["汽化热 H", fmt(o["H"]), "J/kg", E.source("H")],
                  ["环境温度 T₀", fmt(o["T0"]), "K", E.source("T0", "9.1.1.4 最不利气象 25 ℃ 或当地常见气象")], ["地面情况", H.SURF[o["surface"]][0], "", "表F.2"],
                  ["液池面积 S", fmt(S), "m²", E.source("S", "围堰内面积（8.2.2.1）")], ["大气稳定度", H.STAB[o["stab"]][0], "", "表F.3"], ["风速 u", fmt(o["u"]), "m/s", E.source("u", "9.1.1.4")],
                  ["液池半径 r", fmt(r), "m", rsrc], ["液体表面蒸气压 p", fmt(o["p"]), "Pa", E.source("p")], ["摩尔质量 M", fmt(o["M"], 6), "kg/mol", E.source("M")],
                  ["时间 t₁／t₂／t₃", "%s／%s／%s" % (fmt(o["t1"]), fmt(o["t2"]), fmt(o["t3"])), "s", "8.2.2.1"]]
        summary = ["Q₁ = %s　Q₂ = %s　Q₃ = %s kg/s" % (fmt(res["Q1"]), fmt(res["Q2"]), fmt(res["Q3"])),
                   "闪蒸比例 F_v = %s　蒸发总量 W_p = %s kg" % (fmt(res["Fv"]), fmt(res["v"]))]
        sheet = sheet_text("（三）泄漏液体蒸发量计算", " 附录F.1.4 式(F.9)～(F.13)、表F.2、表F.3", params, res["steps"],
                           ["闪蒸蒸发速率 Q₁ = %s kg/s，热量蒸发速率 Q₂ = %s kg/s，质量蒸发速率 Q₃ = %s kg/s；液体蒸发总量 W_p = %s kg。"
                            % (fmt(res["Q1"]), fmt(res["Q2"]), fmt(res["Q3"]), fmt(res["v"]))], res["warn"])
        self.evap_res.show(summary, res["warn"], res["steps"], sheet)

    # -------------------------------------------------------------- 火灾伴生
    def tab_fire(self):
        pw, f = self.split("火灾伴生")
        F = self.fire = Form(f, self.calc_fire)
        F.head("火灾爆炸未燃烧有毒有害物质释放比例", "F.2 表F.4（示例数值）")
        F.add("Q", "有毒有害物质在线量 Q", "t", 300)
        F.add("lc", "半致死浓度 LC₅₀", "mg/m³", 500)
        self.fire_lc_ref = ttk.Label(f, text="选择当前物质后，此处显示库中 LC50 吸入数据（原文单位不一，须换算为 mg/m³）", style="Src.TLabel", wraplength=600)
        self.fire_lc_ref.grid(row=F.r, column=0, columnspan=4, sticky="w")
        F.r += 1
        F.head("油品火灾伴生二氧化硫", "F.3.1 式(F.14)")
        F.add("B", "物质燃烧量 B", "kg/h", 1000)
        F.add("S", "物质中硫含量 S", "%", 0.5)
        F.head("油品火灾伴生一氧化碳", "F.3.2 式(F.15)")
        F.add("q", "化学不完全燃烧值 q（1.5%～6.0%）", "%", 3)
        F.add("C", "物质中碳含量 C（导则取 85%）", "%", 85)
        F.add("Qb", "参与燃烧的物质量 Q", "t/s", 0.01)
        self.fire_res = ResultPane(pw, self, "fire")
        pw.add(self.fire_res, weight=2)

    def calc_fire(self):
        F = self.fire
        try:
            a = H.release_ratio(F.get("Q"), F.get("lc"))
            b = H.so2(F.get("B"), F.get("S"))
            c = H.co(F.get("q"), F.get("C"), F.get("Qb"))
        except ValueError as ex:
            self.fire_res.error("参数不完整或格式有误：%s" % ex)
            return
        steps, warn = a["steps"] + b["steps"] + c["steps"], a["warn"] + b["warn"] + c["warn"]
        ratio = "信息不足" if a["v"] is None else "%s%%" % fmt(a["v"])
        params = [["有毒有害物质在线量 Q", fmt(F.get("Q")), "t", F.source("Q", "工程分析")], ["LC₅₀", fmt(F.get("lc")), "mg/m³", F.source("lc", "MSDS 或毒理资料，请注明")],
                  ["物质燃烧量 B", fmt(F.get("B")), "kg/h", "请注明"], ["硫含量 S", fmt(F.get("S")), "%", "油品质量标准或检测，请注明"],
                  ["化学不完全燃烧值 q", fmt(F.get("q")), "%", "式(F.15)注 1.5%～6.0%"], ["碳含量 C", fmt(F.get("C")), "%", "式(F.15)注 85%"],
                  ["参与燃烧的物质量 Q", fmt(F.get("Qb")), "t/s", "请注明"]]
        summary = ["释放比例 %s　SO₂ %s kg/h　CO %s kg/s" % (ratio, fmt(b["v"]), fmt(c["v"]))]
        sheet = sheet_text("（四）火灾爆炸伴生／次生污染物估算", " 附录F.2 表F.4、F.3 式(F.14)(F.15)", params, steps,
                           ["未燃烧有毒有害物质释放比例 %s；SO₂ 排放速率 %s kg/h；CO 产生量 %s kg/s。" % (ratio, fmt(b["v"]), fmt(c["v"]))], warn)
        self.fire_res.show(summary, warn, steps, sheet)

    # -------------------------------------------------------------- 模型筛选
    def tab_model(self):
        pw, f = self.split("模型筛选")
        M = self.model = Form(f, self.calc_model)
        M.head("排放类型判定", "G.2.1 式(G.4)；示例：液氨液池蒸发")
        M.add("Td", "排放时间 T_d", "s", 1800)
        M.add("X", "事故点至最近受体（网格点或敏感点）距离 X", "m", 500)
        M.add("Ur", "10 m 高处风速 U_r", "m/s", 1.5)
        M.head("密度参数")
        M.combo("rhomode", "密度取值方式", [("ideal", "按理想气体 ρ = PM/(RT) 估算"), ("manual", "手工输入（两相、气溶胶等情形）")])
        M.add("igP", "排放压力", "Pa", 101325)
        M.add("igM", "排放物摩尔质量", "kg/mol", 0.0170305, "氨分子量（PubChem）")
        M.add("igT", "排放物温度", "K", 239.85, "氨常压沸点")
        M.add("igTa", "环境温度（干空气 M=0.028965 kg/mol）", "K", 298.15)
        M.add("rr", "排放物初始密度 ρ_rel（手工）", "kg/m³", 0.8654)
        M.add("ra", "环境空气密度 ρ_a（手工）", "kg/m³", 1.184)
        M.head("源参数", "式(G.2) 连续／式(G.3) 瞬时")
        M.combo("qmode", "连续排放速率 Q", [("evap", "取“液池蒸发”页 Q₁+Q₂+Q₃"), ("leak", "取“泄漏速率”页结果"), ("manual", "手工输入")])
        M.add("Q", "连续排放速率 Q（手工）", "kg/s", 0.7084)
        M.combo("dmode", "初始烟团宽度 D_rel", [("pool", "取液池等效直径 2r"), ("manual", "手工输入")])
        M.add("D", "源直径 D_rel（手工）", "m", 11.28)
        M.add("Qt", "瞬时排放物质质量 Q_t", "kg", 1000)
        self.model_res = ResultPane(pw, self, "model")
        pw.add(self.model_res, weight=2)

    def calc_model(self):
        M = self.model
        ideal = M.get("rhomode") == "ideal"
        for k in ("igP", "igM", "igT", "igTa"):
            M.show(k, ideal)
        for k in ("rr", "ra"):
            M.show(k, not ideal)
        M.show("Q", M.get("qmode") == "manual")
        M.show("D", M.get("dmode") == "manual")
        try:
            if ideal:
                rr = H.ideal_rho(M.get("igP"), M.get("igM"), M.get("igT"))
                ra = H.ideal_rho(M.get("igP"), H.M_AIR, M.get("igTa"))
                rrsrc = "理想气体 ρ=PM/(RT)：P=%s Pa，M=%s kg/mol（%s），T=%s K（%s）" % (fmt(M.get("igP")), fmt(M.get("igM"), 6), M.source("igM"), fmt(M.get("igT")), M.source("igT"))
                rasrc = "理想气体 ρ=PM/(RT)：干空气 M=0.028965 kg/mol，T=%s K" % fmt(M.get("igTa"))
            else:
                rr, ra, rrsrc, rasrc = M.get("rr"), M.get("ra"), M.source("rr"), M.source("ra")
            qm = M.get("qmode")
            if qm == "evap":
                if not self.last_evap:
                    raise ValueError("“液池蒸发”页尚无有效结果")
                e = self.last_evap[0]
                Q, qsrc = e["Q1"] + e["Q2"] + e["Q3"], "“液池蒸发”页 Q₁+Q₂+Q₃（Q₂ 为 t₂ 时刻值），请结合事故情形复核"
            elif qm == "leak":
                if self.last_leak is None:
                    raise ValueError("“泄漏速率”页尚无有效结果")
                Q, qsrc = self.last_leak, "“泄漏速率”页计算结果"
            else:
                Q, qsrc = M.get("Q"), M.source("Q")
            if M.get("dmode") == "pool":
                if not self.last_evap:
                    raise ValueError("“液池蒸发”页尚无有效结果")
                D, dsrc = 2 * self.last_evap[1], "液池等效直径 2r"
            else:
                D, dsrc = M.get("D"), M.source("D")
            o = dict(X=M.get("X"), Ur=M.get("Ur"), Td=M.get("Td"), rho_rel=rr, rho_a=ra, Q=Q, Drel=D, Qt=M.get("Qt"))
            r = H.richardson(**o)
        except (ValueError, ZeroDivisionError) as ex:
            self.model_res.error("参数不完整或格式有误：%s" % ex)
            return
        r["warn"].append("G.2.2：事故发生在丘陵、山地等复杂地形时，应考虑地形对扩散的影响，另行选择适用模型并说明理由。")
        params = [["排放时间 T_d", fmt(o["Td"]), "s", "源强计算"], ["事故点至计算点距离 X", fmt(o["X"]), "m", "平面布置／敏感目标"],
                  ["10 m 高处风速 U_r", fmt(o["Ur"]), "m/s", "9.1.1.4"], ["初始密度 ρ_rel", fmt(rr), "kg/m³", rrsrc], ["环境空气密度 ρ_a", fmt(ra), "kg/m³", rasrc]]
        if r["cont"]:
            params += [["连续排放速率 Q", fmt(Q), "kg/s", qsrc], ["源直径 D_rel", fmt(D), "m", dsrc]]
        else:
            params.append(["瞬时排放质量 Q_t", fmt(o["Qt"]), "kg", "源强计算"])
        params.append(["重力加速度 g", "9.81", "m/s²", "通用值"])
        summary = ["%s排放　R_i = %s　%s" % ("连续" if r["cont"] else "瞬时", fmt(r["v"]), "重质气体" if r["heavy"] else "轻质气体"),
                   "推荐模型：%s" % r["model"]]
        extra = "浓度预测须使用该模型及经认可的软件另行完成（附录G.4）。"
        sheet = sheet_text("（五）大气风险预测模型筛选", " 附录G.2 式(G.2)～(G.4)", params, r["steps"],
                           ["理查德森数 R_i = %s，判定为%s气体，推荐采用 %s 进行预测。" % (fmt(r["v"]), "重质" if r["heavy"] else "轻质", r["model"])], r["warn"])
        self.model_res.show(summary, r["warn"], r["steps"], sheet, extra)

    # -------------------------------------------------------------- 说明
    def tab_notes(self):
        f = ttk.Frame(self.nb, padding=8)
        self.nb.add(f, text="说明与校验")
        t = tk.Text(f, wrap="word", font=("Microsoft YaHei UI", 10), relief="flat", padx=14, pady=10, background="#f6f8f7")
        sb = ttk.Scrollbar(f, command=t.yview)
        t.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        t.pack(fill="both", expand=True)
        t.tag_configure("h", font=("Microsoft YaHei UI", 12, "bold"), spacing1=10, spacing3=4)
        t.tag_configure("m", font=("Consolas", 9))
        n = sum(1 for s in self.subs)
        txt = [
            ("h", "一、适用范围与边界\n"),
            ("", "1. 本程序覆盖 HJ 169-2018 第 4.3 节、第 6 章、附录C（P 分级）、附录D（E 分级）、附录F（源强）与附录G.2（模型筛选）。\n"
                 "2. 不做扩散浓度预测。一级、二级评价的大气风险预测须按 9.1.1 采用附录G 推荐的 SLAB、AFTOX 模型或其他技术成熟且说明理由的模型完成；推荐模型可在 www.lem.org.cn 下载（附录G.4）。\n"
                 "3. 泄漏频率（附录E）、伤害概率（附录I）、地表水与地下水风险预测不在本程序范围内。\n"
                 "4. 审批类别与评价等级结论请工程师对照现行名录与目录复核后使用。\n"),
            ("h", "二、计算约定与需要说明的取值\n"),
            ("", "1. 气体常数 R：导则式(F.4)(F.12) 未给数值，本程序取 8.314 J/(mol·K)。\n"
                 "2. 两相流临界压力 P_C：导则式(F.6) 注写“P_C——临界压力，Pa，取 0.55 Pa”。按 0.55 Pa 代入，P − P_C 与 P 几乎无差别，与“临界压力”的物理含义不符；按量纲推断应为 0.55P（此为推断，导则无勘误可查，信息不足）。程序默认按 0.55P 计算，可切换为原文字面值，报告中请说明所取方式。\n"
                 "3. 热量蒸发时间 t：式(F.11) 的 Q₂ 随 t 递减，式(F.13) 以 Q₂t₂ 计热量蒸发量。本程序按导则写法以 t = t₂ 代入，未做时间积分。\n"
                 "4. 式(F.14)(F.15)：S、q、C 以百分数输入，代入时换算为小数。\n"
                 "5. 表D.1 临界值：人口恰等于 5 万、1 万、1000、500 人（或每千米 200、100 人）时导则未明确归属，程序按较高敏感级判定并提示复核。\n"
                 "6. 表F.4 空白格：导则未给取值，程序显示“信息不足”。\n"
                 "7. 环境压力 P₀ 默认 101325 Pa（标准大气压）。\n"),
            ("h", "三、物质库与数据来源（共 %d 条）\n" % n),
            ("", "1. 临界量：HJ 169-2018 附录B 表B.1（385 条，其中 15 条无 CAS 号）、表B.2（3 条）。CAS 7647-01-0 在表B.1 中有两条（氯化氢 2.5 t、盐酸≥37% 7.5 t），加入 Q 计算时请按物料形态选择。\n"
                 "2. 大气毒性终点浓度：HJ 169-2018 附录H 表H.1（307 条，法定引用值）；其余物质取“大气毒性终点浓度数据库 3146 种”（用户提供，据称取自 www.lem.org.cn，终点-1 对应 PAC-3、终点-2 对应 PAC-2），并列出 DOE PacTeel 2026-09-17 现行值供复核。3146 种中多数中文名为参考译名，已对照《危险化学品目录（2015版）》核验 895 种，其余请自行核对。\n"
                 "3. 理化、燃爆参数：CalebBell/chemicals（提交 e79047588b30）原始数据。分子量 PubChem；熔沸点 CRC 手册 95 版等；闪点、自燃点、爆炸极限 IEC 60079-20-1:2010、NFPA 497:2008；20 ℃ 蒸气压 Perry 手册 8 版表2-8；汽化热 CRC 手册；液体比热容 CRC 标准热力学性质表或 Perry 手册 8 版表2-153；20 ℃ 饱和液体密度 Perry 手册 8 版表2-32；γ 按 CRC 298.15 K 理想气体 Cp 计算。\n"
                 "4. 毒理与水溶性：PubChem（主要为 HSDB、ICSC），保留原文与原始文献。\n"
                 "5. 库中缺少的参数显示“信息不足”，须查 MSDS 或手册后手工填写并注明来源。带入的参数也请以 MSDS 核对。\n"),
            ("h", "四、自校验（程序启动时实时运行）\n"),
            ("", "以下算例由独立脚本按导则原式手算，与本程序计算核心逐项比对（相对偏差小于 1×10⁻⁹ 判为一致）。\n"),
        ]
        for tag, s in txt:
            t.insert("end", s, tag)
        bad, lines = selfcheck.run()
        t.insert("end", "\n".join(lines) + "\n", "m")
        t.insert("end", "\n%s %s\n" % (APP_NAME, APP_VER))
        t.configure(state="disabled")
        self.selfcheck_bad = bad

    # -------------------------------------------------------------- 杂项
    def recalc_all(self):
        self.calc_risk()
        self.calc_leak()
        self.calc_evap()
        self.calc_fire()
        self.calc_model()

    def all_sheets(self):
        return "\n".join(self.sheets[k] for k in ("risk", "leak", "evap", "fire", "model") if k in self.sheets)

    def clip(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        messagebox.showinfo(APP_NAME, "已复制到剪贴板。")

    def export_text(self, text, name):
        if not text:
            messagebox.showwarning(APP_NAME, "当前没有可导出的计算书。")
            return
        p = filedialog.asksaveasfilename(defaultextension=".txt", initialfile="HJ169计算书_%s.txt" % name, filetypes=[("文本文件", "*.txt")])
        if p:
            with open(p, "w", encoding="utf-8-sig") as f:
                f.write(text.replace("\n", "\r\n") if sys.platform == "win32" else text)
            messagebox.showinfo(APP_NAME, "已导出：%s" % p)

    def export_all(self):
        self.export_text(self.all_sheets(), "全部")


def selftest(path):
    """无人值守自检：计算核心比对、物质库载入、界面构建与各模块计算。结果写入 path。"""
    out = []
    bad, lines = selfcheck.run()
    out += lines
    root = tk.Tk()
    app = App(root)
    root.update()
    out.append("物质库条目：%d" % len(app.subs))
    nh3 = next(i for i, s in enumerate(app.subs) if s["cas"] == "7664-41-7")
    app.tree.selection_set(str(nh3)) if app.tree.exists(str(nh3)) else None
    app.current = app.subs[nh3]
    filled = app.fill_from(app.subs[nh3])
    app.recalc_all()
    out.append("带入参数：" + "、".join(filled))
    for k in ("risk", "leak", "evap", "fire", "model"):
        ok = k in app.sheets
        bad += not ok
        out.append("计算书 %s：%s" % (k, "已生成" if ok else "缺失"))
    out.append("风险潜势计算书首行：" + app.sheets.get("risk", "").splitlines()[0] if "risk" in app.sheets else "")
    app.q.set("甲苯")
    app.filter_db()
    out.append("搜索“甲苯”命中：%d 条" % len(app.tree.get_children()))
    root.destroy()
    out.append("SELFTEST %s" % ("PASS" if not bad else "FAIL"))
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    return 0 if not bad else 1


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--selftest":
        sys.exit(selftest(sys.argv[2]))
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
