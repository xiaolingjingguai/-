# -*- coding: utf-8 -*-
"""环评云助手窗口：① 标准时效核查  ② 联网检索（法规、标准、问答、排放限值）  ③ 问答对话"""
import html

from PySide6.QtCore import Qt, QThread, Signal, QSettings, QUrl
from PySide6.QtGui import QDesktopServices, QColor, QGuiApplication
from PySide6.QtCore import QMimeData
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QTabWidget, QTextBrowser, QVBoxLayout, QWidget,
)

import hpyzs_client as H

ORG, APP = "EnvQualityWorkbench", "Workbench"


def load_token():
    return H.token_from_env() or QSettings(ORG, APP).value("hpyzs_token", "", str)


def save_token(t):
    QSettings(ORG, APP).setValue("hpyzs_token", H.clean_token(t))


class Worker(QThread):
    done = Signal(object, str)          # (结果, 错误信息)
    progress = Signal(str)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        try:
            self.done.emit(self.fn(self.progress.emit), "")
        except H.HpyzsError as e:
            self.done.emit(None, str(e))
        except Exception as e:          # 网络、解析等未预期错误
            self.done.emit(None, f"{type(e).__name__}：{e}")


def _fill(tw, head, rows, url_col=None, color=None):
    tw.clear()
    tw.setColumnCount(len(head))
    tw.setRowCount(len(rows))
    tw.setHorizontalHeaderLabels(head)
    for i, r in enumerate(rows):
        bg = color(r) if color else None
        for j, v in enumerate(r):
            it = QTableWidgetItem(str(v))
            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            it.setToolTip(str(v))
            if bg is not None:
                it.setBackground(bg)
            if j == url_col and v:
                it.setForeground(QColor("#1a5fb4"))
            tw.setItem(i, j, it)
    tw.resizeColumnsToContents()
    for j in range(tw.columnCount()):
        tw.setColumnWidth(j, min(tw.columnWidth(j), 320))
    tw.horizontalHeader().setStretchLastSection(True)


def _copy(tw):
    rows = [[tw.horizontalHeaderItem(j).text() for j in range(tw.columnCount())]]
    for i in range(tw.rowCount()):
        rows.append([(tw.item(i, j).text() if tw.item(i, j) else "") for j in range(tw.columnCount())])
    md = QMimeData()
    md.setText("\n".join("\t".join(r) for r in rows))
    md.setHtml('<table border="1" style="border-collapse:collapse">' + "".join(
        "<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in r) + "</tr>" for r in rows) + "</table>")
    QGuiApplication.clipboard().setMimeData(md)


class CloudDialog(QDialog):
    def __init__(self, parent=None, cited=None):
        super().__init__(parent)
        self.setWindowTitle("环评云助手 · 标准时效核查与联网检索")
        self.resize(1180, 680)
        self.cited = cited or (lambda: [])
        self._w = None
        v = QVBoxLayout(self)

        top = QHBoxLayout()
        self.tok_lab = QLabel()
        top.addWidget(self.tok_lab)
        b = QPushButton("设置令牌")
        b.clicked.connect(self.set_token)
        top.addWidget(b)
        b = QPushButton("连接测试")
        b.clicked.connect(self.test)
        top.addWidget(b)
        top.addStretch()
        v.addLayout(top)

        tabs = QTabWidget()
        v.addWidget(tabs, 1)

        # ---- ① 标准时效核查
        p1 = QWidget()
        l1 = QVBoxLayout(p1)
        tip = QLabel("核查对象：本软件判定所依据的标准 + 已导入报告中引用的标准。可在下框增删（每行一个标准号）。"
                     "结论取自环评云助手标准库，作为线索使用，正式引用前请对照官方发布文件复核。")
        tip.setWordWrap(True)
        tip.setStyleSheet("color:#555")
        l1.addWidget(tip)
        self.codes = QPlainTextEdit()
        self.codes.setMaximumHeight(90)
        l1.addWidget(self.codes)
        hb = QHBoxLayout()
        b = QPushButton("重新载入标准清单")
        b.clicked.connect(self.reload_codes)
        hb.addWidget(b)
        hb.addStretch()
        self.btn_check = QPushButton("开始核查")
        self.btn_check.setStyleSheet("QPushButton{background:#2f5d8a;color:white;padding:6px 18px;}")
        self.btn_check.clicked.connect(self.run_check)
        hb.addWidget(self.btn_check)
        l1.addLayout(hb)
        self.tbl_check = QTableWidget()
        self.tbl_check.cellDoubleClicked.connect(lambda i, j: self._open(self.tbl_check, i, 5))
        l1.addWidget(self.tbl_check, 1)
        hb = QHBoxLayout()
        hb.addWidget(QLabel("双击行打开详情页。红底：已废止或有新版本；黄底：未检索到（信息不足）"))
        hb.addStretch()
        b = QPushButton("复制表格")
        b.clicked.connect(lambda: _copy(self.tbl_check))
        hb.addWidget(b)
        l1.addLayout(hb)
        tabs.addTab(p1, "① 标准时效核查")

        # ---- ② 联网检索
        p2 = QWidget()
        l2 = QVBoxLayout(p2)
        hb = QHBoxLayout()
        self.tool = QComboBox()
        for t, s, n in H.SEARCH_TOOLS:
            self.tool.addItem(t, (s, n))
        hb.addWidget(self.tool)
        self.query = QLineEdit()
        self.query.setPlaceholderText("输入标准号、法规名称、关键词，或用一句话描述问题")
        self.query.returnPressed.connect(self.run_search)
        hb.addWidget(self.query, 1)
        self.area = QLineEdit("福建省")
        self.area.setFixedWidth(90)
        self.area.setToolTip("地方类检索使用的地区")
        hb.addWidget(QLabel("地区："))
        hb.addWidget(self.area)
        self.only_valid = QCheckBox("仅现行有效")
        hb.addWidget(self.only_valid)
        self.btn_search = QPushButton("检索")
        self.btn_search.setStyleSheet("QPushButton{background:#2f5d8a;color:white;padding:6px 18px;}")
        self.btn_search.clicked.connect(self.run_search)
        hb.addWidget(self.btn_search)
        l2.addLayout(hb)
        self.tbl_search = QTableWidget()
        self.tbl_search.cellDoubleClicked.connect(lambda i, j: self._open(self.tbl_search, i, 7))
        self.tbl_search.cellClicked.connect(self._show_text)
        l2.addWidget(self.tbl_search, 1)
        self.detail = QPlainTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setMaximumHeight(120)
        self.detail.setPlaceholderText("单击结果行查看内容摘要；双击打开详情页")
        l2.addWidget(self.detail)
        hb = QHBoxLayout()
        hb.addStretch()
        b = QPushButton("复制表格")
        b.clicked.connect(lambda: _copy(self.tbl_search))
        hb.addWidget(b)
        l2.addLayout(hb)
        tabs.addTab(p2, "② 联网检索")

        # ---- ③ 问答对话
        p3 = QWidget()
        l3 = QVBoxLayout(p3)
        tip = QLabel("直接提问，由环评云助手的实务问答库和法规标准库给出最相关的回答及出处。"
                     "回答为检索所得的已有问答和条文，不是针对本问题新生成的答复，引用前请核对原文。")
        tip.setWordWrap(True)
        tip.setStyleSheet("color:#555")
        l3.addWidget(tip)
        self.chat = QTextBrowser()
        self.chat.setOpenExternalLinks(True)
        self.chat.setStyleSheet("QTextBrowser{background:#fbfcfe;}")
        l3.addWidget(self.chat, 1)
        hb = QHBoxLayout()
        hb.addWidget(QLabel("同时检索："))
        self.ask_law = QCheckBox("相关标准、法规")
        self.ask_law.setChecked(True)
        hb.addWidget(self.ask_law)
        self.ask_local = QCheckBox("地方标准与政策")
        hb.addWidget(self.ask_local)
        hb.addStretch()
        b = QPushButton("清空对话")
        b.clicked.connect(self.chat.clear)
        hb.addWidget(b)
        l3.addLayout(hb)
        hb = QHBoxLayout()
        self.ask_box = QLineEdit()
        self.ask_box.setPlaceholderText("请输入问题，如：地表水Ⅱ类COD标准限值是多少？按回车发送")
        self.ask_box.returnPressed.connect(self.run_ask)
        hb.addWidget(self.ask_box, 1)
        self.btn_ask = QPushButton("发送")
        self.btn_ask.setStyleSheet("QPushButton{background:#2f5d8a;color:white;padding:6px 18px;}")
        self.btn_ask.clicked.connect(self.run_ask)
        hb.addWidget(self.btn_ask)
        l3.addLayout(hb)
        tabs.addTab(p3, "③ 问答对话")

        self.status = QLabel("")
        self.status.setStyleSheet("color:#8a6d00")
        v.addWidget(self.status)
        self._texts = []
        self.reload_codes()
        self._show_token()

    # ---------------------------------------------------------------- 令牌
    def _show_token(self):
        t = load_token()
        t = H.clean_token(t)
        self.tok_lab.setText("令牌：已设置（" + t[:4] + "…" + t[-4:] + "）" if len(t) > 8 else
                             "令牌：未设置（请点击\"设置令牌\"，填入您本人的环评云助手令牌）")

    def set_token(self):
        t, ok = QInputDialog.getText(self, "设置令牌", "环评云助手令牌（Bearer Token），仅保存在本机：",
                                     QLineEdit.Password, load_token())
        if ok:
            save_token(t)
            self._show_token()

    def _client(self):
        t = load_token()
        if not t:
            QMessageBox.information(self, "环评云助手", "请先点击\"设置令牌\"，填入您本人的环评云助手令牌。")
            return None
        return H.Client(t)

    def _start(self, fn, on_done, busy):
        if self._w and self._w.isRunning():
            return
        self.status.setText(busy)
        self._w = Worker(fn)
        self._w.progress.connect(self.status.setText)
        self._w.done.connect(on_done)
        self._w.start()

    def test(self):
        c = self._client()
        if not c:
            return

        def fn(prog):
            out = []
            for s in H.SERVERS:
                prog(f"正在连接 {s} …")
                out.append(f"{s}：" + "；".join(c.describe(s)))
            prog("正在用令牌试检索一次 …")
            try:                         # 握手和工具清单不校验令牌，需实际调用一次
                c.search("law-keyword", "search_keyword_standard", "GB 3096")
                out.append("令牌校验：通过")
            except H.HpyzsError as e:
                out.append(f"令牌校验：未通过（{e}）。请核对令牌是否完整、是否过期")
            return out

        def done(res, err):
            self.status.setText("")
            if err:
                QMessageBox.warning(self, "连接测试", err)
            else:
                QMessageBox.information(self, "连接测试", "连接成功：\n" + "\n".join(res))
        self._start(fn, done, "正在连接环评云助手 …")

    # ---------------------------------------------------------------- 核查
    def reload_codes(self):
        codes = list(dict.fromkeys(H.canon(c) for c in H.BUILTIN_STANDARDS + [c for c in self.cited() if H.split_code(c)]))
        self.codes.setPlainText("\n".join(codes))

    def run_check(self):
        c = self._client()
        if not c:
            return
        codes = [x.strip() for x in self.codes.toPlainText().splitlines() if x.strip()]

        def fn(prog):
            out = []
            for k, code in enumerate(codes, 1):
                prog(f"正在核查 {code}（{k}/{len(codes)}）…")
                try:
                    out.append(H.check_standard(c, code))
                except H.HpyzsError as e:
                    if k == 1:
                        raise
                    out.append(dict(code=code, name="", conclusion=f"查询失败：{e}", latest="", impl="", url=""))
            return out

        def done(res, err):
            self.btn_check.setEnabled(True)
            if err:
                self.status.setText("")
                QMessageBox.warning(self, "标准时效核查", err)
                return
            rows = [[r["code"], r["name"], r["conclusion"], r["latest"], r["impl"], r["url"]] for r in res]

            def color(r):
                if "废止" in r[2] or "新版本" in r[2] or "失效" in r[2]:
                    return QColor("#fde2e1")
                if "信息不足" in r[2] or "失败" in r[2]:
                    return QColor("#fff6d5")
                return None
            _fill(self.tbl_check, ["标准号", "标准名称", "核查结论", "检索到的新版本", "实施日期", "详情链接"], rows, 5, color)
            self.status.setText(f"核查完成：{len(res)} 项。结论取自环评云助手，正式引用前请对照官方文件复核。")
        self.btn_check.setEnabled(False)
        self._start(fn, done, "正在核查 …")

    # ---------------------------------------------------------------- 检索
    def run_search(self):
        q = self.query.text().strip()
        if not q:
            return
        c = self._client()
        if not c:
            return
        server, tool = self.tool.currentData()
        area, only = self.area.text().strip(), self.only_valid.isChecked()

        def fn(prog):
            return [H.norm_item(x) for x in c.search(server, tool, q, area, only)]

        def done(res, err):
            self.btn_search.setEnabled(True)
            if err:
                self.status.setText("")
                QMessageBox.warning(self, "联网检索", err)
                return
            self._texts = [r["text"] for r in res]
            rows = [[r["name"], r["num"], r["status"], r["pub"], r["impl"], r["area"] or r["dept"], r["text"][:60], r["url"]]
                    for r in res]
            _fill(self.tbl_search, ["名称", "文号/标准号", "状态", "发布日期", "实施日期", "地区/发布部门", "内容摘要", "详情链接"],
                  rows, 7, lambda r: QColor("#fde2e1") if ("废止" in r[2] or "失效" in r[2]) else None)
            self.detail.clear()
            self.status.setText(f"检索到 {len(res)} 条。检索结果作为线索使用，引用前请核对原文。")
        self.btn_search.setEnabled(False)
        self._start(fn, done, "正在检索 …")

    # ---------------------------------------------------------------- 问答对话
    def run_ask(self):
        q = self.ask_box.text().strip()
        if not q or (self._w and self._w.isRunning()):
            return
        c = self._client()
        if not c:
            return
        law, local, area = self.ask_law.isChecked(), self.ask_local.isChecked(), self.area.text().strip() or "福建省"
        self.chat.append(f'<p style="margin:10px 0 2px 0;color:#2f5d8a"><b>我：</b>{html.escape(q)}</p>')
        self.ask_box.clear()

        def fn(prog):
            out = {}
            jobs = [("qa", "qa", "search_semantic_qa", "")]
            if law:
                jobs.append(("std", "law-semantic", "search_nationwide_semantic_standard", ""))
                jobs.append(("pol", "law-semantic", "search_nationwide_semantic_policy", ""))
            if local:
                jobs.append(("loc", "law-semantic", "search_semantic_province_sta_pol", area))
            for key, server, tool, ar in jobs:
                prog("正在检索 …")
                try:
                    out[key] = [H.norm_item(x) for x in c.search(server, tool, q, ar)]
                except H.HpyzsError as e:
                    out[key] = e
            return out

        def done(res, err):
            self.btn_ask.setEnabled(True)
            self.status.setText("")
            if err:
                self.chat.append(f'<p style="color:#b00000"><b>环评云助手：</b>{html.escape(err)}</p>')
                return
            self.chat.append(self._answer_html(res, area))
            self.chat.verticalScrollBar().setValue(self.chat.verticalScrollBar().maximum())
        self.btn_ask.setEnabled(False)
        self._start(fn, done, "正在向环评云助手提问 …")

    @staticmethod
    def _answer_html(res, area):
        def link(it):
            return f' <a href="{html.escape(it["url"])}">详情</a>' if it["url"] else ""

        def para(t, n=1200):
            t = html.escape(t[:n] + ("…" if len(t) > n else ""))
            return t.replace("\n", "<br>")

        parts = ['<div style="margin:2px 0 8px 0"><b>环评云助手：</b>']
        qa = res.get("qa")
        if isinstance(qa, Exception):
            parts.append(f'<p style="color:#b00000">问答库检索失败：{html.escape(str(qa))}</p>')
        elif qa:
            top = qa[0]
            parts.append(f'<p style="margin:4px 0"><span style="color:#555">最相关问答：</span>{html.escape(top["name"])}{link(top)}</p>')
            parts.append(f'<p style="margin:4px 0 6px 12px">{para(top["text"]) or "（该条无答复正文，请打开详情）"}</p>')
            if len(qa) > 1:
                parts.append('<p style="margin:2px 0;color:#555">其他相关问答：</p><ul style="margin-top:0">')
                parts += [f'<li>{html.escape(x["name"])}{link(x)}</li>' for x in qa[1:5]]
                parts.append("</ul>")
        else:
            parts.append('<p style="margin:4px 0">问答库中未检索到相关问答（信息不足）。</p>')
        for key, label in (("std", "相关标准"), ("pol", "相关法规"), ("loc", f"{area}地方标准与政策")):
            if key not in res:
                continue
            v = res[key]
            if isinstance(v, Exception):
                parts.append(f'<p style="color:#b00000">{label}检索失败：{html.escape(str(v))}</p>')
                continue
            if not v:
                continue
            parts.append(f'<p style="margin:6px 0 2px 0;color:#555">{label}：</p><ul style="margin-top:0">')
            for x in v[:3]:
                meta = "，".join(y for y in (x["num"], x["status"], x["area"]) if y)
                snip = f'<br><span style="color:#666">{para(x["text"], 200)}</span>' if x["text"] else ""
                parts.append(f'<li>{html.escape(x["name"])}{"（" + html.escape(meta) + "）" if meta else ""}{link(x)}{snip}</li>')
            parts.append("</ul>")
        parts.append('<p style="color:#8a6d00;font-size:9pt">以上为环评云助手库内检索结果，正式引用前请核对原文。</p></div>')
        return "".join(parts)

    def _show_text(self, i, j):
        if i < len(self._texts):
            self.detail.setPlainText(self._texts[i])

    def _open(self, tw, i, col):
        it = tw.item(i, col)
        if it and it.text().startswith("http"):
            QDesktopServices.openUrl(QUrl(it.text()))
