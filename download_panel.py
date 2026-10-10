# -*- coding: utf-8 -*-
"""标准下载窗口：检索生态环境部标准库、国家标准全文公开系统，下载 PDF 并另存到用户选择的位置"""
import datetime
import os

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QColor
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QInputDialog, QAbstractItemView,
)

import std_download as D
from cloud_panel import Worker, ORG, APP
from PySide6.QtCore import QSettings

HEAD = ["来源", "标准名称", "标准号", "状态", "实施日期", "栏目", "详情页"]


class DownloadDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("标准下载（官方渠道）")
        self.resize(1150, 640)
        self.idx, self.rows, self._w = None, [], None
        v = QVBoxLayout(self)
        tip = QLabel("在下框输入标准号、标准名称或关键词（多个关键词用空格分开），检索生态环境部标准库和国家标准全文公开系统。"
                     "选中结果点\"下载\"，选择保存位置后直接下载 PDF；文件名按\"名称 标准号-年份\"自动拟定，已废止的加\"（无效）\"。")
        tip.setWordWrap(True)
        tip.setStyleSheet("color:#555")
        v.addWidget(tip)

        hb = QHBoxLayout()
        self.q = QLineEdit()
        self.q.setPlaceholderText("如：GB 3095　或　海洋沉积物　或　大气 导则")
        self.q.returnPressed.connect(self.run_search)
        hb.addWidget(self.q, 1)
        self.cb_mee = QCheckBox("生态环境部标准库")
        self.cb_mee.setChecked(True)
        self.cb_gb = QCheckBox("国家标准全文公开系统")
        self.cb_gb.setChecked(True)
        hb.addWidget(self.cb_mee)
        hb.addWidget(self.cb_gb)
        self.btn_search = QPushButton("检索")
        self.btn_search.setStyleSheet("QPushButton{background:#2f5d8a;color:white;padding:6px 18px;}")
        self.btn_search.clicked.connect(self.run_search)
        hb.addWidget(self.btn_search)
        v.addLayout(hb)

        self.tbl = QTableWidget()
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tbl.cellDoubleClicked.connect(lambda i, j: self.download())
        v.addWidget(self.tbl, 1)

        hb = QHBoxLayout()
        self.idx_lab = QLabel()
        self.idx_lab.setStyleSheet("color:#555")
        hb.addWidget(self.idx_lab)
        b = QPushButton("更新官网目录")
        b.setToolTip("重新读取生态环境部标准库全部栏目（约需 1~3 分钟），官网发布新标准后使用")
        b.clicked.connect(lambda: self.update_index(then_search=False))
        hb.addWidget(b)
        hb.addStretch()
        b = QPushButton("打开网页")
        b.clicked.connect(self.open_page)
        hb.addWidget(b)
        self.btn_dl = QPushButton("下载（另存为）")
        self.btn_dl.setStyleSheet("QPushButton{background:#2f7a3d;color:white;padding:6px 18px;}")
        self.btn_dl.clicked.connect(self.download)
        hb.addWidget(self.btn_dl)
        v.addLayout(hb)

        links = QLabel('其他官方渠道（地方标准、行业标准、工程建设标准）：'
                       '<a href="https://std.samr.gov.cn/">全国标准信息公共服务平台</a>　'
                       '<a href="https://dbba.sacinfo.org.cn/">地方标准信息服务平台</a>　'
                       '<a href="https://www.mohurd.gov.cn/">住房和城乡建设部</a>')
        links.setOpenExternalLinks(True)
        v.addWidget(links)
        self.status = QLabel("")
        self.status.setStyleSheet("color:#8a6d00")
        self.status.setWordWrap(True)
        v.addWidget(self.status)

        c = D.load_cache()
        if c:
            self.idx = c["items"]
        self._show_idx(c["updated"] if c else "")

    # ------------------------------------------------------------ 目录
    def _show_idx(self, when):
        self.idx_lab.setText(f"生态环境部标准库目录：{len(self.idx)} 项（{when} 更新）" if self.idx
                             else "生态环境部标准库目录：尚未建立（首次检索时自动读取）")

    def _start(self, fn, done, busy):
        if self._w and self._w.isRunning():
            self._w.wait(3000)            # 上一步的完成回调里接着发起下一步时，等其线程收尾
            if self._w.isRunning():
                return False
        self.status.setText(busy)
        self._w = Worker(fn)
        self._w.progress.connect(self.status.setText)
        self._w.done.connect(done)
        self._w.start()
        return True

    def update_index(self, then_search=False):
        def done(idx, err):
            if err:
                self.status.setText("")
                QMessageBox.warning(self, "标准下载", f"读取生态环境部标准库失败：{err}")
                return
            when = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            self.idx = idx
            try:
                D.save_cache(idx, when)
            except OSError:
                pass
            self._show_idx(when)
            self.status.setText(f"目录已更新：{len(idx)} 项。")
            if then_search:
                self.run_search()
        self._start(lambda prog: D.build_mee_index(prog), done, "正在读取生态环境部标准库目录 …")

    # ------------------------------------------------------------ 检索
    def run_search(self):
        q = self.q.text().strip()
        if not q:
            return
        if self.cb_mee.isChecked() and not self.idx:
            self.update_index(then_search=True)
            return
        use_mee, use_gb, idx = self.cb_mee.isChecked(), self.cb_gb.isChecked(), self.idx or []

        def fn(prog):
            rows, warn = [], []
            if use_mee:
                for it in D.search_index(idx, q):
                    rows.append(dict(src="生态环境部", title=it["title"], code=it["code"],
                                     status="已废止" if "废止" in it["title"] else "",
                                     impl="", section=it.get("section", ""), url=it["url"], kind="mee"))
            if use_gb:
                prog("正在检索国家标准全文公开系统 …")
                try:
                    for it in D.search_openstd(q):
                        rows.append(dict(src="国标公开系统", title=it["title"], code=it["code"], status=it["status"],
                                         impl=it["impl"], section="", url=it["url"], kind="gb"))
                except D.DownloadError as e:
                    warn.append(f"国家标准全文公开系统：{e}")
            return rows, warn

        def done(res, err):
            self.btn_search.setEnabled(True)
            if err:
                self.status.setText("")
                QMessageBox.warning(self, "标准下载", err)
                return
            self.rows, warn = res
            self._fill()
            msg = f"检索到 {len(self.rows)} 项。" + ("；".join(warn) if warn else "")
            if not self.rows:
                msg += "未检索到。可换用关键词，或点\"更新官网目录\"后再试；地方标准请到下方官方平台查询（信息不足时请勿采用非官方来源）。"
            self.status.setText(msg)
        self.btn_search.setEnabled(False)
        self._start(fn, done, "正在检索 …")

    def _fill(self):
        t = self.tbl
        t.clear()
        t.setColumnCount(len(HEAD))
        t.setRowCount(len(self.rows))
        t.setHorizontalHeaderLabels(HEAD)
        for i, r in enumerate(self.rows):
            vals = [r["src"], r["title"], r["code"], r["status"], r["impl"], r["section"], r["url"]]
            bad = any(k in r["status"] for k in ("废止", "被代替"))
            for j, x in enumerate(vals):
                it = QTableWidgetItem(x)
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                it.setToolTip(x)
                if bad:
                    it.setBackground(QColor("#fde2e1"))
                t.setItem(i, j, it)
        t.resizeColumnsToContents()
        t.setColumnWidth(1, min(t.columnWidth(1), 460))
        t.horizontalHeader().setStretchLastSection(True)

    def _selected(self):
        return sorted({i.row() for i in self.tbl.selectedIndexes()})

    def open_page(self):
        for i in self._selected()[:5]:
            QDesktopServices.openUrl(QUrl(self.rows[i]["url"]))

    # ------------------------------------------------------------ 下载
    def download(self):
        sel = self._selected()
        if not sel:
            QMessageBox.information(self, "标准下载", "请先在结果中选中要下载的标准（可多选）。")
            return
        gb = [i for i in sel if self.rows[i]["kind"] == "gb"]
        if gb:
            QMessageBox.information(self, "标准下载", "国家标准全文公开系统下载须在网页上输入验证码，将在浏览器中打开详情页，"
                                                    "请点击页面上的\"下载标准\"。")
            for i in gb[:5]:
                QDesktopServices.openUrl(QUrl(self.rows[i]["url"]))
        mee = [self.rows[i] for i in sel if self.rows[i]["kind"] == "mee"]
        if not mee:
            return
        folder = None
        if len(mee) > 1:
            folder = QFileDialog.getExistingDirectory(self, "选择保存文件夹", self._last_dir())
            if not folder:
                return
            self._remember(folder)
        jobs = []

        def fn(prog):
            out = []
            for k, r in enumerate(mee, 1):
                prog(f"正在读取详情页 {k}/{len(mee)}：{r['title'][:30]}")
                try:
                    out.append((r, D.mee_pdfs(r["url"])))
                except D.DownloadError as e:
                    out.append((r, e))
            return out

        def got_links(res, err):
            if err:
                self.status.setText("")
                QMessageBox.warning(self, "标准下载", err)
                return
            for r, pdfs in res:
                if isinstance(pdfs, Exception) or not pdfs:
                    self.status.setText(f"{r['title'][:40]}：详情页未找到 PDF 附件，已在浏览器中打开详情页。")
                    QDesktopServices.openUrl(QUrl(r["url"]))
                    continue
                for n, (label, url) in enumerate(pdfs):
                    title = r["title"] if len(pdfs) == 1 else (label if D.CODE_RE.search(label) else f"{r['title']}_{label}")
                    name = D.safe_name(title)
                    if folder:
                        path = os.path.join(folder, name)
                    else:
                        path, _ = QFileDialog.getSaveFileName(self, "另存为", os.path.join(self._last_dir(), name),
                                                              "PDF 文件 (*.pdf)")
                        if not path:
                            continue
                        self._remember(os.path.dirname(path))
                    jobs.append((url, path))
            if jobs:
                self._start(do_download, finished, "正在下载 …")
            else:
                self.status.setText(self.status.text() or "已取消。")

        def do_download(prog):
            done_list = []
            for k, (url, path) in enumerate(jobs, 1):
                prog(f"正在下载 {k}/{len(jobs)}：{os.path.basename(path)}")
                try:
                    size = D.download(url, path)
                    done_list.append((path, size, ""))
                except (D.DownloadError, OSError) as e:
                    done_list.append((path, 0, str(e)))
            return done_list

        def finished(res, err):
            if err:
                self.status.setText("")
                QMessageBox.warning(self, "标准下载", err)
                return
            ok = [p for p, s, e in res if not e]
            bad = [f"{os.path.basename(p)}：{e}" for p, s, e in res if e]
            self.status.setText(f"已下载 {len(ok)} 个文件：" + "；".join(os.path.basename(p) for p in ok)
                                + ("。失败：" + "；".join(bad) if bad else "。")
                                + "下载后请打开核对标准号、名称和年份，并用环评云助手核查是否现行有效。")
            if ok and len(ok) == 1 and QMessageBox.question(self, "标准下载", "下载完成，是否打开所在文件夹？") == QMessageBox.Yes:
                QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(ok[0])))

        self._start(fn, got_links, "正在读取详情页 …")

    @staticmethod
    def _last_dir():
        return QSettings(ORG, APP).value("download_dir", os.path.expanduser("~/Downloads"), str)

    @staticmethod
    def _remember(d):
        QSettings(ORG, APP).setValue("download_dir", d)
