# -*- coding: utf-8 -*-
"""
环境质量判定工作台（桌面界面）

运行：python app.py
操作：① 左侧选评价参数 → ② 拖入监测报告 → ③ 核对识别数据（可直接修改）→ ④ 判定并复制/导出
"""
import html
import os
import re
import sys
import shutil

from PySide6.QtCore import Qt, QMimeData, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QGuiApplication
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QFileDialog, QFormLayout, QFrame,
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPlainTextEdit, QPushButton, QRadioButton, QSplitter, QTableWidget, QTableWidgetItem,
    QTabWidget, QVBoxLayout, QWidget, QListWidget, QListWidgetItem, QStackedWidget, QScrollArea,
)

import pipeline
from pipeline import SURFACE, GROUNDWATER, AIR, NOISE, SOIL, SEDIMENT, BIOTA, MORE
from export_more import AIR_HEAD, AIR_KEYS, NOISE_HEAD, NOISE_KEYS, SOIL_HEAD, SOIL_KEYS, MARINE_HEAD, MARINE_KEYS
import cloud_panel
import lib_limit
import download_panel
import emission_params
from emission_judge import WASTEWATER, STACK, FUGITIVE, BOILER, ODOR_STACK, ODOR_FENCE, BNOISE, EMISSION, GAS, metric_of
from export_emission import heads as em_heads
from air_judge import PERIOD_CN
from export import red_keys, _mark_overall
from export import (SUMMARY_HEAD, SUMMARY_KEYS, GW_SUMMARY_HEAD, GW_OVERALL_HEAD, GW_OVERALL_KEYS,
                    GW_STAT_HEAD, GW_STAT_KEYS, sup_unicode)

APP_TITLE = "环境质量判定工作台"
CLASS_ITEMS = [("Ⅰ类", "I"), ("Ⅱ类", "II"), ("Ⅲ类", "III"), ("Ⅳ类", "IV"), ("Ⅴ类", "V")]
REC_HEAD = ["监测点位", "采样日期", "监测项目（报告原名）", "监测值", "单位", "报告标准值", "识别附注"]
REC_KEYS = ["station", "date", "item", "value", "unit", "report_limit", "src_note"]
# 环境空气核对表多一列"平均时间"（可填：1小时平均 / 日平均 / 日最大8小时平均 / 年平均）
AIR_REC_HEAD = ["监测点位", "采样日期", "污染物（报告原名）", "平均时间", "监测值", "单位", "报告标准值", "识别附注"]
AIR_REC_KEYS = ["station", "date", "item", "period_cn", "value", "unit", "report_limit", "src_note"]
NOISE_REC_HEAD = ["监测点位", "监测日期", "时段（昼间/夜间）", "测量时间", "测量值 dB(A)", "单位", "报告标准值", "识别附注"]
NOISE_REC_KEYS = ["station", "date", "item", "time", "value", "unit", "report_limit", "src_note"]
KIND_FILE = {SURFACE: "_地表水", GROUNDWATER: "_地下水", AIR: "_环境空气", NOISE: "_声环境", SOIL: "_土壤", SEDIMENT: "_海洋沉积物", BIOTA: "_海洋生物质量",
             WASTEWATER: "_GB8978废水", STACK: "_GB16297有组织废气", FUGITIVE: "_GB16297无组织废气",
             BOILER: "_GB13271锅炉废气", ODOR_STACK: "_GB14554恶臭有组织", ODOR_FENCE: "_GB14554恶臭厂界",
             BNOISE: "_GB12348厂界噪声"}
# 排放标准各页核对表
EM_REC_HEAD = ["监测点位", "采样日期/频次", "监测项目（报告原名）", "监测值", "单位", "报告标准值", "识别附注"]
STACK_REC_HEAD = ["排气筒/点位", "采样日期/频次", "污染物（报告原名）", "指标", "监测值", "单位", "排气筒高度(m)",
                  "实测含氧量(%)", "报告标准值", "识别附注"]
STACK_REC_KEYS = ["station", "date", "item", "metric_cn", "value", "unit", "height", "o2", "report_limit", "src_note"]
ODOR_REC_HEAD = [h for h in STACK_REC_HEAD if "含氧" not in h]
ODOR_REC_KEYS = [k for k in STACK_REC_KEYS if k != "o2"]
LAND_ITEMS = [("建设用地 第一类用地", "build1"), ("建设用地 第二类用地", "build2"),
              ("农用地 水田", "paddy"), ("农用地 其他", "other"), ("农用地 果园", "orchard")]
RED, YELLOW = QColor("#fde2e1"), QColor("#fff6d5")
LIB_BG, DIFF_BG = QColor("#eef3f8"), QColor("#ffd8a8")     # 目标类别标准值列底色 / 与报告标准值不一致
LIB_COLS = {SURFACE: "目标类别标准值", GROUNDWATER: "目标类别标准值", SEDIMENT: "目标类别标准值",
            BIOTA: "目标类别标准值", AIR: "功能区标准限值", NOISE: "功能区标准限值", SOIL: "用地类型筛选值/管制值",
            WASTEWATER: "所选标准限值", STACK: "所选标准限值", FUGITIVE: "所选标准限值", BOILER: "所选标准限值",
            ODOR_STACK: "所选标准限值", ODOR_FENCE: "所选标准限值",
            BNOISE: "所选标准限值"}
SUPPORTED = (".docx", ".xlsx", ".xlsm", ".pdf")


# ------------------------------------------------------------------ 拖入区
class DropZone(QLabel):
    def __init__(self, on_file):
        super().__init__("将 Word / PDF / Excel 监测报告拖到这里\n（或点击\"打开文件\"）")
        self.on_file = on_file
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(70)
        self._style(False)

    def _style(self, hover):
        self.setStyleSheet(
            "QLabel{border:2px dashed %s;border-radius:8px;color:#2f5d8a;font-size:14px;"
            "background:%s;}" % (("#2f5d8a", "#eaf1f8") if hover else ("#8fadc8", "#f8fafc")))

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._style(True)

    def dragLeaveEvent(self, e):
        self._style(False)

    def dropEvent(self, e):
        self._style(False)
        urls = e.mimeData().urls()
        if urls:
            self.on_file(urls[0].toLocalFile())


# ------------------------------------------------------------------ 表格工具
def fill_table(tw, head, keys, rows, editable=False, color_fn=None):
    tw.clear()
    tw.setColumnCount(len(head))
    tw.setRowCount(len(rows))
    tw.setHorizontalHeaderLabels(head)
    for i, r in enumerate(rows):
        bg = color_fn(r) if color_fn else None
        reds = set() if editable else red_keys(r)
        for j, k in enumerate(keys):
            it = QTableWidgetItem(sup_unicode(str(r.get(k, "") if r.get(k) is not None else "")))
            it.setTextAlignment(Qt.AlignCenter)
            if not editable:
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            if bg is not None:
                it.setBackground(bg)
            if k in reds:                    # 超标数据红字，复制到 Word/Excel 时保留
                it.setForeground(QColor("#d00000"))
                it.setData(Qt.UserRole, "red")
            tw.setItem(i, j, it)
    tw.resizeColumnsToContents()
    tw.horizontalHeader().setStretchLastSection(True)


def table_to_clipboard(tw, title=""):
    """复制为 HTML 三线表 + 制表符文本：粘贴到 Word 为表格，粘贴到 Excel 为单元格。"""
    rows = [[tw.horizontalHeaderItem(j).text() for j in range(tw.columnCount())]]
    red = [[False] * tw.columnCount()]
    for i in range(tw.rowCount()):
        rows.append([(tw.item(i, j).text() if tw.item(i, j) else "") for j in range(tw.columnCount())])
        red.append([bool(tw.item(i, j) and tw.item(i, j).data(Qt.UserRole) == "red") for j in range(tw.columnCount())])
    tsv = "\n".join("\t".join(r) for r in rows)
    cell = "padding:2px 6px;text-align:center;font-family:宋体;font-size:9pt;"
    trs = []
    for i, r in enumerate(rows):
        b = ("border-top:1.5pt solid #000;border-bottom:0.75pt solid #000;font-weight:bold;" if i == 0
             else ("border-bottom:1.5pt solid #000;" if i == len(rows) - 1 else ""))
        tag = "th" if i == 0 else "td"
        trs.append("<tr>" + "".join(f'<{tag} style="{cell}{b}{"color:#FF0000;" if red[i][j] else ""}">{html.escape(c)}</{tag}>'
                                    for j, c in enumerate(r)) + "</tr>")
    cap = f'<p style="text-align:center;font-family:宋体;font-weight:bold">{html.escape(title)}</p>' if title else ""
    md = QMimeData()
    md.setHtml(cap + '<table style="border-collapse:collapse">' + "".join(trs) + "</table>")
    md.setText(tsv)
    QGuiApplication.clipboard().setMimeData(md)


# ------------------------------------------------------------------ 单要素页面
class ElementPage(QWidget):
    def __init__(self, kind, log):
        super().__init__()
        self.kind, self.log = kind, log
        self.path, self.records, self.res = None, [], None
        self.rec_head, self.rec_keys = {AIR: (AIR_REC_HEAD, AIR_REC_KEYS), NOISE: (NOISE_REC_HEAD, NOISE_REC_KEYS),
                                        BNOISE: (NOISE_REC_HEAD, NOISE_REC_KEYS), STACK: (STACK_REC_HEAD, STACK_REC_KEYS),
                                        BOILER: (STACK_REC_HEAD, STACK_REC_KEYS),
                                        ODOR_STACK: (ODOR_REC_HEAD, ODOR_REC_KEYS), ODOR_FENCE: (EM_REC_HEAD, REC_KEYS),
                                        WASTEWATER: (EM_REC_HEAD, REC_KEYS), FUGITIVE: (EM_REC_HEAD, REC_KEYS)
                                        }.get(kind, (REC_HEAD, REC_KEYS))
        self._pwidgets = []            # 排放标准页的评价参数控件（变更时刷新限值列）
        i = self.rec_keys.index("report_limit") + 1          # 报告标准值右侧插入"目标类别标准值"（随评价参数实时刷新）
        self.lib_col = LIB_COLS[kind]
        self.rec_head = self.rec_head[:i] + [self.lib_col] + self.rec_head[i:]
        self.rec_keys = self.rec_keys[:i] + ["_lib"] + self.rec_keys[i:]
        self._auto_proj = False        # 项目名称是否由文件名自动填入（自动填入的随清除一并清空）

        # ---- 左侧：评价参数
        left = QVBoxLayout()
        box = QGroupBox("① 评价参数")
        form = QFormLayout(box)
        if kind in EMISSION:
            std = emission_params.build(self, form)
        if kind in (SURFACE, GROUNDWATER):
            self.cls = QComboBox()
            for t, v in CLASS_ITEMS:
                self.cls.addItem(t, v)
            self.cls.setCurrentIndex(2)
            form.addRow("目标类别：", self.cls)
        if kind == SURFACE:
            self.rb_river, self.rb_lake = QRadioButton("河流"), QRadioButton("湖、库")
            self.rb_river.setChecked(True)
            g = QButtonGroup(self)
            g.addButton(self.rb_river)
            g.addButton(self.rb_lake)
            hb = QHBoxLayout()
            hb.addWidget(self.rb_river)
            hb.addWidget(self.rb_lake)
            form.addRow("水体类型：", hb)
            self.cb_tn = QCheckBox("河流总氮参照所选类别评价")
            self.cb_drink = QCheckBox("集中式生活饮用水地表水源地\n（启用表2、表3）")
            form.addRow(self.cb_tn)
            form.addRow(self.cb_drink)
            self.rb_lake.toggled.connect(lambda on: self.cb_tn.setEnabled(not on))
            std = "执行标准：GB 3838-2002\n《地表水环境质量标准》"
        elif kind == GROUNDWATER:
            std = "执行标准：GB/T 14848-2017\n《地下水质量标准》\n标准指数：HJ 610-2016 第8.4.1.2条"
        elif kind == AIR:
            self.air_level = QComboBox()
            self.air_level.addItem("二类区（二级浓度限值）", 2)
            self.air_level.addItem("一类区（一级浓度限值）", 1)
            form.addRow("功能区：", self.air_level)
            self.air_phase = QComboBox()
            self.air_phase.addItem("过渡阶段（至2030年底）", "transition")
            self.air_phase.addItem("2031年起浓度限值", "final")
            form.addRow("限值阶段：", self.air_phase)
            std = ("执行标准：GB 3095—2026\n《环境空气质量标准》\n（2026-03-01实施，GB 3095—2012 废止）\n"
                   "标准未列项目（氨、硫化氢等）\n按报告所列限值判定并提示复核")
        elif kind == NOISE:
            self.noise_cls = QComboBox()
            for k in ("0", "1", "2", "3", "4a", "4b"):
                self.noise_cls.addItem(f"{k}类", k)
            self.noise_cls.setCurrentIndex(2)
            form.addRow("声功能区：", self.noise_cls)
            std = ("执行标准：GB 3096-2008\n《声环境质量标准》\n报告中引用 GB 12348-2008 的厂界噪声表，\n按所选功能区对应的 GB 12348 表1 限值判定\n（厂界噪声建议在\"排放标准—GB 12348-2008\"页判定）")
        elif kind in EMISSION:
            pass
        elif kind in (SEDIMENT, BIOTA):
            self.marine_cls = QComboBox()
            for k, t in ((1, "第一类"), (2, "第二类"), (3, "第三类")):
                self.marine_cls.addItem(t, k)
            form.addRow("质量类别：", self.marine_cls)
            if kind == SEDIMENT:
                std = ("执行标准：GB 18668-2002\n《海洋沉积物质量》\n第一类：渔业水域、保护区、养殖区、浴场等\n"
                       "第二类：一般工业用水区、滨海风景旅游区\n第三类：港口水域、特殊用途开发作业区\n"
                       "（重金属等以干重计，有机碳以%计）")
            else:
                std = ("执行标准：GB 18421-2001\n《海洋生物质量》\n仅适用于海洋贝类（双壳类），以去壳部分鲜重计；\n"
                       "鱼类、虾蟹等判\"不适用\"；牡蛎铜、锌第三类按括号内数值\n"
                       "（种类名称可写在站位后，如\"B1（牡蛎）\"）")
        else:
            self.land = QComboBox()
            for t, v in LAND_ITEMS:
                self.land.addItem(t, v)
            self.land.setCurrentIndex(1)
            form.addRow("用地类型：", self.land)
            std = ("建设用地：GB 36600—2018\n农用地：GB 15618—2018\n（农用地按各样品 pH 分档，\n需报告中含 pH）")
        lab = QLabel(std)
        lab.setWordWrap(True)
        lab.setStyleSheet("color:#555")
        form.addRow(lab)
        left.addWidget(box)
        box2 = QGroupBox("项目信息")
        f2 = QFormLayout(box2)
        self.proj = QLineEdit()
        self.proj.setPlaceholderText("用于导出文件名")
        self.proj.textEdited.connect(lambda _: setattr(self, "_auto_proj", False))
        f2.addRow("项目名称：", self.proj)
        left.addWidget(box2)
        left.addStretch()
        lw = QWidget()
        lw.setLayout(left)
        lw.setFixedWidth(300)
        if kind in EMISSION:               # 参数较多时可上下滚动
            sa = QScrollArea()
            sa.setWidget(lw)
            sa.setWidgetResizable(True)
            sa.setFixedWidth(318)
            sa.setFrameShape(QFrame.NoFrame)
            sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            lw = sa

        # ---- 中间：拖入区 + 三步
        center = QVBoxLayout()
        top = QHBoxLayout()
        self.drop = DropZone(self.open_path)
        top.addWidget(self.drop, 1)
        btn_open = QPushButton("打开文件")
        btn_open.clicked.connect(self.choose_file)
        top.addWidget(btn_open)
        btn_clear = QPushButton("清除数据")
        btn_clear.setToolTip("清空本页已导入的数据和判定结果，评价参数保留")
        btn_clear.clicked.connect(self.ask_clear)
        top.addWidget(btn_clear)
        center.addLayout(top)
        self.file_lab = QLabel("尚未导入报告")
        self.file_lab.setStyleSheet("color:#555")
        center.addWidget(self.file_lab)

        self.steps = QTabWidget()
        # 核对页
        p_check = QWidget()
        v = QVBoxLayout(p_check)
        tip = QLabel("请核对识别出的数据，发现错误可双击单元格直接修改，改完点\"开始判定\"。")
        tip.setStyleSheet("color:#8a6d00")
        v.addWidget(tip)
        self.lib_tip = QLabel(f"\"{self.lib_col}\"列随左侧评价参数实时更新，判定按该列执行；\"报告标准值\"为报告原文所列，仅供对照。")
        self.lib_tip.setStyleSheet("color:#2f5d8a")
        self.lib_tip.setWordWrap(True)
        v.addWidget(self.lib_tip)
        self.tbl_rec = QTableWidget()
        v.addWidget(self.tbl_rec)
        hb = QHBoxLayout()
        hb.addStretch()
        self.btn_judge = QPushButton("开始判定 →")
        self.btn_judge.setStyleSheet("QPushButton{background:#2f5d8a;color:white;padding:6px 18px;}")
        self.btn_judge.clicked.connect(self.run_judge)
        hb.addWidget(self.btn_judge)
        v.addLayout(hb)
        self.steps.addTab(p_check, "② 核对识别数据")
        # 结果页
        self.tbl_sum = QTableWidget()
        self.steps.addTab(self._result_page(self.tbl_sum, "监测结果及评价表"), "③ 判定结果")
        if kind == GROUNDWATER:
            self.tbl_stat = QTableWidget()
            self.steps.addTab(self._result_page(self.tbl_stat, "地下水水质现状监测结果统计"), "统计分析")
            self.tbl_ov = QTableWidget()
            self.steps.addTab(self._result_page(self.tbl_ov, "地下水质量综合评价结果"), "综合评价")
        center.addWidget(self.steps, 1)

        # 底部导出
        hb2 = QHBoxLayout()
        legend = QLabel("  红底：超标    黄底：未检出、不评价或需核对  ")
        legend.setStyleSheet("color:#555")
        hb2.addWidget(legend)
        hb2.addStretch()
        b_w = QPushButton("导出 Word")
        b_w.clicked.connect(lambda: self.export("docx"))
        b_x = QPushButton("导出 Excel")
        b_x.clicked.connect(lambda: self.export("xlsx"))
        hb2.addWidget(b_w)
        hb2.addWidget(b_x)
        center.addLayout(hb2)
        cw = QWidget()
        cw.setLayout(center)

        lay = QHBoxLayout(self)
        lay.addWidget(lw)
        lay.addWidget(cw, 1)
        self._watch_params()

    def _result_tables(self):
        tws = [self.tbl_sum]
        if self.kind == GROUNDWATER:
            tws += [self.tbl_stat, self.tbl_ov]
        return tws

    def ask_clear(self):
        if not (self.records or self.tbl_rec.rowCount()):
            return
        if QMessageBox.question(self, APP_TITLE, "确定清除本页已导入的数据和判定结果吗？") == QMessageBox.Yes:
            self.clear_all()
            self.log("已清除数据，可导入新报告。")

    def clear_all(self, keep_proj=False):
        """清空导入数据、核对表与结果表；评价参数（类别、水体类型等）保留"""
        self.path, self.records, self.res = None, [], None
        for tw in [self.tbl_rec] + self._result_tables():
            tw.clear()
            tw.setRowCount(0)
            tw.setColumnCount(0)
        self.file_lab.setText("尚未导入报告")
        if not keep_proj and self._auto_proj:
            self.proj.clear()
        self.steps.setCurrentIndex(0)

    def _result_page(self, tw, title):
        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(tw)
        hb = QHBoxLayout()
        hb.addStretch()
        rb = QPushButton("刷新判定")
        rb.setToolTip("修改左侧评价参数（功能区、类别、标准级别等）或核对表数据后，\n按当前参数重新判定，无需重新导入监测报告")
        rb.clicked.connect(self.refresh_judge)
        hb.addWidget(rb)
        b = QPushButton("复制表格（可直接粘贴到 Word / Excel）")
        b.clicked.connect(lambda: (table_to_clipboard(tw, title), self.log("已复制：" + title)))
        hb.addWidget(b)
        v.addLayout(hb)
        return w

    # ---- 参数
    def param_desc(self):
        if self.kind in EMISSION:
            return emission_params.desc(self)
        for name in ("cls", "air_level", "noise_cls", "land", "marine_cls"):
            w = getattr(self, name, None)
            if w is not None:
                d = w.currentText()
                if name == "cls" and self.kind == SURFACE:
                    d += "，" + ("湖、库" if self.rb_lake.isChecked() else "河流")
                if name == "air_level":
                    d += "，" + self.air_phase.currentText()
                return d
        return ""

    def params(self):
        if self.kind in EMISSION:
            return emission_params.params(self)
        if self.kind == AIR:
            return dict(level=self.air_level.currentData(), phase=self.air_phase.currentData())
        if self.kind == NOISE:
            return dict(noise_cls=self.noise_cls.currentData())
        if self.kind == SOIL:
            return dict(land=self.land.currentData())
        if self.kind in (SEDIMENT, BIOTA):
            return dict(marine_cls=self.marine_cls.currentData())
        p = dict(target=self.cls.currentData())
        if self.kind == SURFACE:
            p.update(water_body="lake" if self.rb_lake.isChecked() else "river",
                     drink=self.cb_drink.isChecked(),
                     tn_ref=self.cb_tn.isChecked() and not self.rb_lake.isChecked())
        return p

    # ---- 导入
    def choose_file(self):
        f, _ = QFileDialog.getOpenFileName(self, "选择监测报告", "", "监测报告 (*.docx *.pdf *.xlsx *.xlsm)")
        if f:
            self.open_path(f)

    def open_path(self, path):
        if not path.lower().endswith(SUPPORTED):
            QMessageBox.warning(self, APP_TITLE, "暂不支持该文件类型。\n.doc 请另存为 .docx；图片请提供原始电子版。")
            return
        try:
            records, warns = pipeline.load(path, self.kind)
        except Exception as ex:      # 扫描件、损坏文件等
            QMessageBox.warning(self, APP_TITLE, f"读取失败：{ex}")
            self.log(f"读取失败：{os.path.basename(path)}：{ex}")
            return
        self.clear_all()               # 导入新报告即替换旧数据，旧结果一并清空
        self.path, self.records = path, records
        name = os.path.basename(path)
        self.file_lab.setText(f"已导入：{name}　识别 {len(self.records)} 条数据")
        if not self.proj.text():
            self.proj.setText(re.sub(r"\.\w+$", "", name))
            self._auto_proj = True
        self.log(f"【{name}】识别 {len(self.records)} 条数据")
        for w in warns:
            self.log("  · " + w)
        if self.kind == AIR:
            for r in self.records:
                r["period_cn"] = PERIOD_CN.get(r.get("period"), "")
        fill_table(self.tbl_rec, self.rec_head, self.rec_keys, self.records, editable=True,
                   color_fn=lambda r: YELLOW if (re.search(r"[×Ll<＜]|未检出|ND", str(r.get("value")))
                                                 or any("\ufffd" in str(v) or "(cid:" in str(v) for v in r.values()))
                   else None)
        self.steps.setCurrentIndex(0)
        self.res = None
        self.refresh_lib()

    def _records_from_table(self):
        out = []
        for i in range(self.tbl_rec.rowCount()):
            r = dict(self.records[i]) if i < len(self.records) else {}     # 保留未显示的字段（表内引用标准等）
            r.update({k: (self.tbl_rec.item(i, j).text() if self.tbl_rec.item(i, j) else "")
                      for j, k in enumerate(self.rec_keys)})
            r.pop("_lib", None)
            if "period_cn" in r:
                r["period"] = r.pop("period_cn")
            if self.kind in GAS:
                r["metric"] = metric_of(r.get("metric_cn"), r.get("unit"))
            r["value"] = re.sub(r"([×x])10([⁰¹²³⁴⁵⁶⁷⁸⁹⁻]+)",
                                lambda m: "×10^" + m.group(2).translate(str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻", "0123456789-")),
                                r["value"])
            out.append(r)
        return out

    # ---- 判定
    # ---- 评价参数变化：刷新"目标类别标准值"列；已判定的自动重新判定
    def _watch_params(self):
        for name in ("cls", "air_level", "air_phase", "noise_cls", "land", "marine_cls"):
            w = getattr(self, name, None)
            if w is not None:
                w.currentIndexChanged.connect(self.on_params_changed)
        for name in ("rb_lake", "cb_tn", "cb_drink"):
            w = getattr(self, name, None)
            if w is not None:
                w.toggled.connect(self.on_params_changed)
        for w in self._pwidgets:
            (w.toggled if isinstance(w, QCheckBox) else w.currentIndexChanged).connect(self.on_params_changed)

    def on_params_changed(self, *_):
        if not self.tbl_rec.rowCount():
            return
        self.refresh_lib()
        if self.res is not None:
            self.run_judge(auto=True)

    def refresh_judge(self):
        """刷新判定按钮：按左侧当前参数和核对表现有数据重新判定"""
        if not self.tbl_rec.rowCount():
            QMessageBox.information(self, APP_TITLE, "请先导入监测报告。")
            return
        self.refresh_lib()
        self.log("已按当前评价参数刷新：")
        self.run_judge()

    def refresh_lib(self):
        if not self.tbl_rec.rowCount():
            return
        col = self.rec_keys.index("_lib")
        rl_col = self.rec_keys.index("report_limit")
        try:
            vals = lib_limit.compute(self._records_from_table(), self.kind, self.params())
        except Exception as ex:          # 核对表中有尚未改正的数据时不影响界面
            self.log(f"{self.lib_col}刷新失败：{ex}")
            return
        n_diff = 0
        for i, (txt, diff) in enumerate(vals):
            it = QTableWidgetItem(sup_unicode(txt))
            it.setTextAlignment(Qt.AlignCenter)
            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            it.setBackground(DIFF_BG if diff else LIB_BG)
            it.setToolTip("报告所列标准值与当前所选类别限值不一致，判定按本列执行" if diff
                          else "本软件按当前评价参数取用的标准限值，判定按本列执行")
            self.tbl_rec.setItem(i, col, it)
            rl = self.tbl_rec.item(i, rl_col)
            if rl is not None:
                if diff:
                    rl.setBackground(DIFF_BG)
                    rl.setToolTip(f"与“{self.lib_col}”不一致")
                    n_diff += 1
                else:
                    rl.setData(Qt.BackgroundRole, None)
                    rl.setToolTip("")
                    bg = self.tbl_rec.item(i, 0).background() if self.tbl_rec.item(i, 0) else None
                    if bg is not None and bg.style() != Qt.NoBrush:
                        rl.setBackground(bg)
        self.tbl_rec.resizeColumnToContents(col)
        self.lib_tip.setText(f"\"{self.lib_col}\"列随左侧评价参数实时更新，判定按该列执行；"
                             + (f"橙底 {n_diff} 行为报告标准值与所选限值不一致。" if n_diff else "报告标准值与所选限值一致。"))

    def run_judge(self, auto=False):
        if not self.tbl_rec.rowCount():
            if not auto:
                QMessageBox.information(self, APP_TITLE, "请先导入监测报告。")
            return
        p = self.params()
        self.res = pipeline.assess(self._records_from_table(), self.kind, **p)
        head, keys = {GROUNDWATER: (GW_SUMMARY_HEAD, SUMMARY_KEYS), AIR: (AIR_HEAD, AIR_KEYS),
                      NOISE: (NOISE_HEAD, NOISE_KEYS), SOIL: (SOIL_HEAD, SOIL_KEYS),
                      SEDIMENT: (MARINE_HEAD, MARINE_KEYS), BIOTA: (MARINE_HEAD, MARINE_KEYS)}.get(self.kind, (SUMMARY_HEAD, SUMMARY_KEYS))
        if self.kind in EMISSION:
            head, keys = em_heads(self.kind)

        def color(r):
            res = str(r.get("result", ""))
            if res.startswith("超"):
                return RED
            if res not in ("达标", "未超筛选值", "符合") or "L" in str(r.get("range")) or "＜" in str(r.get("range")) \
                    or str(r.get("cls", "")).startswith("≤") or "复核" in str(r.get("note", "")):
                return YELLOW
            return None
        fill_table(self.tbl_sum, head, keys, self.res["summary"], color_fn=color)
        if self.kind == GROUNDWATER:
            fill_table(self.tbl_stat, GW_STAT_HEAD, GW_STAT_KEYS, self.res["stats"])
            fill_table(self.tbl_ov, GW_OVERALL_HEAD, GW_OVERALL_KEYS,
                       _mark_overall(self.res["overall"], self.params()["target"]))
        ex = [r for r in self.res["summary"] if str(r["result"]).startswith("超")]

        def desc(r):
            if self.kind in (NOISE, BNOISE):
                return f"{r['station']} {r['date']} {r['period']}（超标 {r['over']} dB(A)）"
            if self.kind in EMISSION:
                return f"{r['station']} {r['item']}{(' ' + r['metric']) if r.get('metric') else ''}（最大超标 {r['max_exceed']} 倍）"
            if self.kind == SOIL:
                return f"{r['station']} {r['item']}（{r['result']}）"
            if self.kind in (SEDIMENT, BIOTA):
                return f"{r['station']} {r['item']}（{r['cls']}，标准指数 {r['max_index']}）"
            return f"{r['station']} {r['item']}（最大超标 {r['max_exceed']} 倍）"
        self.log(f"{'重新判定' if auto else '判定'}完成（{self.param_desc()}）：{len(self.res['summary'])} 项，超标 {len(ex)} 项" +
                 ("：" + "；".join(desc(r) for r in ex) if ex else "。"))
        for o in self.res["overall"]:
            self.log(f"  综合评价：{o['station']} {o['cls']}（最差指标：{o['worst_items']}）")
        self.refresh_lib()
        if auto:
            self.log("  （评价参数已变更，已按新参数自动重新判定）")
        else:
            self.steps.setCurrentIndex(1)

    # ---- 导出
    def export(self, ext):
        if not self.res:
            QMessageBox.information(self, APP_TITLE, "请先完成判定。")
            return
        name = (self.proj.text() or "判定结果") + KIND_FILE[self.kind] + "_判定结果." + ext
        default = os.path.join(os.path.dirname(self.path or ""), name)
        f, _ = QFileDialog.getSaveFileName(self, "导出", default, f"*.{ext}")
        if not f:
            return
        self.save_to(f)

    def save_to(self, f):
        p = self.params()
        fn = pipeline.export_word if f.endswith(".docx") else pipeline.export_excel
        if self.kind in MORE or self.kind in EMISSION:
            fn(f, self.res, self.kind, **p)
        else:
            fn(f, self.res, self.kind, p["target"], p.get("water_body", "river"))
        self.log("已导出：" + f)


# ------------------------------------------------------------------ 主窗口
# 工作台大类：(名称, 说明, 是否已开发)。以后新增大类在此登记，并在 MainWindow._build_category 中返回页面
CATEGORIES = [
    ("环境质量标准", "地表水、地下水、环境空气、声环境、土壤、海洋沉积物、海洋生物质量现状监测数据达标判定", True),
    ("排放标准", "废水、有组织废气、无组织废气、厂界噪声污染源监测数据达标判定", True),
    ("污染源强核算", "产排污系数法、物料衡算法、类比法等源强核算（建设中）", False),
]
# 排放标准大类：一个标准一个页签；GB 16297 下分有组织、无组织两个子页签
EMISSION_TABS = (("GB 8978-1996 污水综合排放标准", [(WASTEWATER, "")]),
                 ("GB 16297-1996 大气污染物综合排放标准", [(STACK, "有组织排放"), (FUGITIVE, "无组织排放")]),
                 ("GB 13271-2014 锅炉大气污染物排放标准", [(BOILER, "")]),
                 ("GB 14554-93 恶臭污染物排放标准", [(ODOR_STACK, "有组织排放（表2）"), (ODOR_FENCE, "厂界（表1）")]),
                 ("GB 12348-2008 工业企业厂界环境噪声排放标准", [(BNOISE, "")]))
QUALITY_TABS = ((SURFACE, "地表水"), (GROUNDWATER, "地下水"), (AIR, "环境空气"), (NOISE, "声环境"), (SOIL, "土壤"),
                (SEDIMENT, "海洋沉积物"), (BIOTA, "海洋生物质量"))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1360, 820)
        self.logbox = QPlainTextEdit()
        self.logbox.setReadOnly(True)
        self.logbox.setMaximumHeight(130)
        self.logbox.setStyleSheet("background:#fffbea;")
        self.pages = {}

        # ---- 顶部工具条：通用工具
        bar = QHBoxLayout()
        bar.setContentsMargins(8, 6, 8, 0)
        b = QPushButton("泉州环评审批工作台")
        b.setToolTip("环评类别 · 审批层级 · 受理窗口判别（单文件离线页面，在默认浏览器中打开）")
        b.setStyleSheet("QPushButton{background:#16a34a;color:white;font-weight:bold;padding:4px 12px;}")
        b.clicked.connect(self.open_approval)
        bar.addWidget(b)
        bar.addSpacing(12)
        self.cat_title = QLabel()
        self.cat_title.setStyleSheet("font-size:15px;font-weight:bold;color:#2f5d8a")
        bar.addWidget(self.cat_title)
        bar.addStretch()
        for text, fn in (("标准下载", self.open_download), ("环评云助手：时效核查 / 检索 / 问答", self.open_cloud)):
            b = QPushButton(text)
            b.setStyleSheet("QPushButton{color:#2f5d8a;padding:4px 12px;}")
            b.clicked.connect(fn)
            bar.addWidget(b)

        # ---- 左侧大类目录 + 右侧工作台
        self.nav = QListWidget()
        self.nav.setFixedWidth(150)
        self.nav.setStyleSheet("QListWidget{background:#f3f6fa;border:none;font-size:14px;}"
                               "QListWidget::item{padding:12px 10px;}"
                               "QListWidget::item:selected{background:#2f5d8a;color:white;}")
        self.stack = QStackedWidget()
        for name, desc, ready in CATEGORIES:
            it = QListWidgetItem(name if ready else f"{name}\n（建设中）")
            it.setToolTip(desc)
            if not ready:
                it.setForeground(QColor("#999"))
            self.nav.addItem(it)
            self.stack.addWidget(self._build_category(name, desc, ready))
        self.nav.currentRowChanged.connect(self._switch)
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.addWidget(self.nav)
        body.addWidget(self.stack, 1)
        top = QWidget()
        tv = QVBoxLayout(top)
        tv.setContentsMargins(0, 0, 0, 0)
        tv.addLayout(bar)
        tv.addLayout(body, 1)

        sp = QSplitter(Qt.Vertical)
        sp.addWidget(top)
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(6, 0, 6, 6)
        v.addWidget(QLabel("提示区"))
        v.addWidget(self.logbox)
        sp.addWidget(box)
        sp.setStretchFactor(0, 5)
        self.setCentralWidget(sp)
        self.nav.setCurrentRow(0)
        self.log("欢迎使用。左侧选择工作台大类，选择评价参数后，将监测报告拖入对应页面。")

    def _build_category(self, name, desc, ready):
        if name == "环境质量标准":
            self.tabs = QTabWidget()
            for kind, title in QUALITY_TABS:
                self.pages[kind] = ElementPage(kind, self.log)
                self.tabs.addTab(self.pages[kind], title)
            return self.tabs
        if name == "排放标准":
            self.em_tabs = QTabWidget()
            for title, subs in EMISSION_TABS:
                for kind, _ in subs:
                    self.pages[kind] = ElementPage(kind, self.log)
                if len(subs) == 1:
                    self.em_tabs.addTab(self.pages[subs[0][0]], title)
                else:
                    inner = QTabWidget()
                    for kind, sub in subs:
                        inner.addTab(self.pages[kind], sub)
                    self.em_tabs.addTab(inner, title)
            return self.em_tabs
        w = QWidget()
        v = QVBoxLayout(w)
        lab = QLabel(f"<h2 style='color:#2f5d8a'>{html.escape(name)}</h2><p style='color:#555;font-size:14px'>"
                     f"{html.escape(desc)}</p><p style='color:#999'>该工作台尚在规划，后续开发后将在此显示。</p>")
        lab.setAlignment(Qt.AlignCenter)
        v.addWidget(lab)
        return w

    def _switch(self, row):
        self.stack.setCurrentIndex(row)
        self.cat_title.setText(CATEGORIES[row][0] + "工作台")

    def open_approval(self):
        """泉州环评审批工作台：随程序打包的离线 HTML，复制到本机数据目录后用默认浏览器打开"""
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        src = os.path.join(base, "tools", "qz_approval.html")
        d = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "EnvQualityWorkbench")
        dst = os.path.join(d, "泉州环评审批工作台.html")
        try:
            os.makedirs(d, exist_ok=True)
            shutil.copyfile(src, dst)
        except OSError as e:
            QMessageBox.warning(self, "泉州环评审批工作台", f"无法准备页面文件：{e}")
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(dst)):
            QMessageBox.information(self, "泉州环评审批工作台", f"未能自动打开浏览器，请手动打开：\n{dst}")
        else:
            self.log("已在默认浏览器中打开“泉州环评审批工作台”。判定结果仅供参考，请对照名录和审批目录原文复核。")

    def open_download(self):
        download_panel.DownloadDialog(self).exec()

    def cited_standards(self):
        """各页面已导入报告中引用的标准号"""
        out = []
        for pg in self.pages.values():
            for r in pg.records:
                out += [x for x in str(r.get("table_std") or "").split("；") if x]
        return list(dict.fromkeys(out))

    def open_cloud(self):
        dlg = cloud_panel.CloudDialog(self, self.cited_standards)
        dlg.exec()

    def log(self, msg):
        self.logbox.appendPlainText(msg)


def main():
    # 命令行辅助：仅打印本机机器码（供打包流水线/用户快速获取），不弹界面
    if "--print-machine" in sys.argv:
        import license_verify
        print(license_verify.machine_code())
        return

    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei", 10))

    import license_verify
    from PySide6.QtWidgets import QMessageBox
    from PySide6.QtCore import QTimer

    # 无人值守自检（打包后验证界面与各模块可正常载入）：构建主窗口并处理事件后退出
    if "--selftest" in sys.argv:
        w = MainWindow()
        w.show()
        app.processEvents()
        print("SELFTEST OK")
        return

    # 启动门禁：已授权直接运行；未授权则给予首次试用，到时弹授权窗并锁定；试用用完则直接要求授权
    state, payload, reason = license_verify.license_state()
    if state == "expired":
        license_verify.show_gate("试用时间已用完（共 %d 分钟），请授权后继续使用。"
                                 % license_verify.TRIAL_MINUTES)
        return

    w = MainWindow()
    w.show()

    if state == "trial":
        remaining = max(1, int(payload))
        mins = max(1, (remaining + 59) // 60)
        QMessageBox.information(w, "试用",
                               "未检测到授权，您可先试用本软件。\n"
                               "本次试用剩余约 %d 分钟，到时将提示授权。" % mins)

        def _on_trial_end():
            license_verify.show_gate("试用时间已到（共 %d 分钟），请授权后继续使用。"
                                     % license_verify.TRIAL_MINUTES, parent=w)
            try:
                w.close()
            except Exception:
                pass
            app.quit()

        QTimer.singleShot(remaining * 1000, _on_trial_end)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
