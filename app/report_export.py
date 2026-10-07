"""计算书导出：纯文本、Word（.docx，三线表）、Excel（.xlsx）。

计算书数据结构 report：
  title    标题，如“（二）液体泄漏速率计算”
  basis    依据条款，如“附录F.1.1 式(F.1)、表F.1”
  params   [[参数, 取值, 单位, 来源]]
  steps    [(计算项目, 公式及依据, 代入数值, 计算结果)]
  results  [结论句]
  warn     [提示]
  tables   可选，结果表 [(表名, 表头, 行, 列宽cm)]，置于“计算结果”中、结论段落之前
"""
STD = "《建设项目环境风险评价技术导则》（HJ 169-2018）"


def make_report(title, basis, params, steps, results, warn, tables=None):
    return {"title": title, "basis": basis, "params": [[str(x) for x in p] for p in params],
            "steps": [tuple(str(x) for x in s) for s in steps], "results": list(results), "warn": list(warn),
            "tables": [(c, list(h), [[str(x) for x in r] for r in rows], list(w)) for c, h, rows, w in (tables or [])]}


def to_text(rep):
    t = "%s\n依据：%s%s。\n1. 参数取值\n" % (rep["title"], STD, rep["basis"].strip())
    for i, p in enumerate(rep["params"], 1):
        t += "（%d）%s：%s%s（%s）\n" % (i, p[0], p[1], " " + p[2] if p[2] else "", p[3])
    t += "2. 计算过程\n"
    for i, s in enumerate(rep["steps"], 1):
        t += "（%d）%s：%s；代入 %s；得 %s\n" % (i, s[0], s[1], s[2], s[3])
    t += "3. 计算结果\n"
    for cap, head, rows, _ in rep.get("tables", []):
        t += cap + "\n" + "\t".join(head) + "\n" + "".join("\t".join(r) + "\n" for r in rows)
    t += "".join(r + "\n" for r in rep["results"])
    if rep["warn"]:
        t += "4. 提示\n" + "".join("（%d）%s\n" % (i, w) for i, w in enumerate(rep["warn"], 1))
    return t


# ---------------------------------------------------------------- Word
def _font(run, size=None, bold=None, east="宋体", west="Times New Roman"):
    from docx.oxml.ns import qn
    from docx.shared import Pt
    run.font.name = west
    rpr = run._element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = rpr.makeelement(qn("w:rFonts"), {})
        rpr.append(rf)
    rf.set(qn("w:eastAsia"), east)
    rf.set(qn("w:ascii"), west)
    rf.set(qn("w:hAnsi"), west)
    if size:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold


def _para(doc, text, size=12, bold=False, east="宋体", indent=True, align=None, space_before=0, space_after=0, line=1.5):
    from docx.shared import Pt
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.line_spacing = line
    pf.space_before = Pt(space_before)
    pf.space_after = Pt(space_after)
    if indent:
        pf.first_line_indent = Pt(size * 2)
    if align is not None:
        p.alignment = align
    _font(p.add_run(text), size, bold, east)
    return p


def _three_line(table):
    """三线表：顶线、底线 1.5 磅，表头下线 0.75 磅，无竖线。"""
    from docx.oxml.ns import qn
    tbl = table._tbl
    tblPr = tbl.tblPr
    borders = tblPr.makeelement(qn("w:tblBorders"), {})
    for edge, sz in (("top", "12"), ("bottom", "12"), ("left", None), ("right", None), ("insideH", None), ("insideV", None)):
        el = borders.makeelement(qn("w:" + edge), {})
        if sz:
            el.set(qn("w:val"), "single")
            el.set(qn("w:sz"), sz)
            el.set(qn("w:color"), "000000")
        else:
            el.set(qn("w:val"), "nil")
        borders.append(el)
    old = tblPr.find(qn("w:tblBorders"))
    if old is not None:
        tblPr.remove(old)
    # 按 OOXML 架构顺序插在 shd/tblLayout/tblCellMar/tblLook 之前
    after = next((tblPr.find(qn("w:" + t)) for t in ("shd", "tblLayout", "tblCellMar", "tblLook") if tblPr.find(qn("w:" + t)) is not None), None)
    if after is not None:
        after.addprevious(borders)
    else:
        tblPr.append(borders)
    for cell in table.rows[0].cells:
        tcPr = cell._tc.get_or_add_tcPr()
        tcb = tcPr.makeelement(qn("w:tcBorders"), {})
        b = tcb.makeelement(qn("w:bottom"), {qn("w:val"): "single", qn("w:sz"): "6", qn("w:color"): "000000"})
        tcb.append(b)
        tcPr.append(tcb)


def _table(doc, caption, header, rows, widths_cm):
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Cm, Pt
    _para(doc, caption, 10.5, True, "黑体", indent=False, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=6, line=1.0)
    t = doc.add_table(rows=1 + len(rows), cols=len(header))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    for ci, w in enumerate(widths_cm):
        t.columns[ci].width = Cm(w)
    for ri, vals in enumerate([header] + rows):
        for ci, v in enumerate(vals):
            c = t.cell(ri, ci)
            c.width = Cm(widths_cm[ci])
            p = c.paragraphs[0]
            p.paragraph_format.line_spacing = 1.0
            p.paragraph_format.space_after = Pt(0)
            if ri == 0 or ci == 0:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            _font(p.add_run(str(v)), 10.5, ri == 0)
    _three_line(t)
    return t


def _module_docx(doc, rep, tno):
    from docx.shared import Pt
    _para(doc, rep["title"], 14, True, "黑体", indent=False, space_before=12, space_after=6)
    _para(doc, "1. 计算依据", 12, True, indent=False)
    _para(doc, "依据%s%s。" % (STD, rep["basis"].strip()))
    _para(doc, "2. 参数取值", 12, True, indent=False)
    name = rep["title"].split("）", 1)[-1]
    if name.endswith("计算"):
        name = name[:-2]
    _table(doc, "表%d　%s参数取值" % (tno, name), ["序号", "参数", "取值", "单位", "取值依据／来源"],
           [[str(i), p[0], p[1], p[2] or "—", p[3]] for i, p in enumerate(rep["params"], 1)], [1.3, 3.8, 2.8, 1.6, 6.5])
    _para(doc, "3. 计算过程", 12, True, indent=False, space_before=6)
    _table(doc, "表%d　%s计算过程" % (tno + 1, name), ["序号", "计算项目", "公式及依据", "代入数值", "计算结果"],
           [[str(i), s[0], s[1], s[2], s[3]] for i, s in enumerate(rep["steps"], 1)], [1.3, 2.8, 4.9, 4.6, 2.4])
    _para(doc, "4. 计算结果", 12, True, indent=False, space_before=6)
    tno += 2
    for cap, head, rows, widths in rep.get("tables", []):
        _table(doc, "表%d　%s" % (tno, cap), head, rows, widths)
        tno += 1
        _para(doc, "", 6, indent=False, line=1.0)
    for r in rep["results"]:
        _para(doc, r)
    if rep["warn"]:
        _para(doc, "5. 编制提示（核对后删除）", 12, True, indent=False)
        for i, w in enumerate(rep["warn"], 1):
            p = _para(doc, "（%d）%s" % (i, w), 10.5)
            for run in p.runs:
                from docx.shared import RGBColor
                run.font.color.rgb = RGBColor(0x8A, 0x4B, 0x00)
    return tno


def to_docx(reports, path, doc_title="环境风险计算书"):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Cm
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(2.5)
    sec.top_margin = sec.bottom_margin = Cm(2.5)
    _para(doc, doc_title, 16, True, "黑体", indent=False, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=6)
    _para(doc, "计算依据：%s；本计算书由 HJ 169 风险计算器生成，参数来源逐项列明，可复现。" % STD, 10.5, indent=False,
          align=WD_ALIGN_PARAGRAPH.CENTER, space_after=6)
    tno = 1
    for rep in reports:
        tno = _module_docx(doc, rep, tno)
    doc.save(path)


# ---------------------------------------------------------------- Excel
def to_xlsx(reports, path):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    wb = Workbook()
    wb.remove(wb.active)
    thin = Side(style="thin", color="000000")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    hfill = PatternFill("solid", fgColor="E2F0EE")
    base = Font(name="宋体", size=10.5)
    bold = Font(name="宋体", size=10.5, bold=True)
    wrap = Alignment(wrap_text=True, vertical="center")
    center = Alignment(wrap_text=True, vertical="center", horizontal="center")
    summary = wb.create_sheet("汇总")
    summary.append(["模块", "计算结果"])
    for c in summary[1]:
        c.font, c.fill, c.border, c.alignment = bold, hfill, border, center
    for rep in reports:
        name = rep["title"].split("）", 1)[-1][:28]
        ws = wb.create_sheet(name)
        ws.column_dimensions["A"].width = 6
        for col, w in zip("BCDE", (22, 42, 36, 30)):
            ws.column_dimensions[col].width = w
        ws.append([rep["title"]])
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=5)
        ws["A1"].font = Font(name="黑体", size=14, bold=True)
        ws.append(["依据：%s%s" % (STD, rep["basis"].strip())])
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=5)
        ws["A2"].font, ws["A2"].alignment = base, wrap
        ws.append([])

        def table(title, header, rows):
            ws.append([title])
            ws.cell(ws.max_row, 1).font = bold
            ws.append(header)
            for c in ws[ws.max_row]:
                c.font, c.fill, c.border, c.alignment = bold, hfill, border, center
            for r in rows:
                ws.append(r)
                for i, c in enumerate(ws[ws.max_row]):
                    c.font, c.border, c.alignment = base, border, center if i == 0 else wrap
            ws.append([])

        table("参数取值", ["序号", "参数", "取值", "单位", "取值依据／来源"],
              [[i, p[0], p[1], p[2] or "—", p[3]] for i, p in enumerate(rep["params"], 1)])
        table("计算过程", ["序号", "计算项目", "公式及依据", "代入数值", "计算结果"],
              [[i, s[0], s[1], s[2], s[3]] for i, s in enumerate(rep["steps"], 1)])
        for cap, head, rows, _ in rep.get("tables", []):
            table(cap, head, rows)
        ws.append(["计算结果"])
        ws.cell(ws.max_row, 1).font = bold
        for r in rep["results"]:
            ws.append([r])
            ws.merge_cells(start_row=ws.max_row, start_column=1, end_row=ws.max_row, end_column=5)
            ws.cell(ws.max_row, 1).font, ws.cell(ws.max_row, 1).alignment = base, wrap
        if rep["warn"]:
            ws.append([])
            ws.append(["编制提示"])
            ws.cell(ws.max_row, 1).font = bold
            for w in rep["warn"]:
                ws.append([w])
                ws.merge_cells(start_row=ws.max_row, start_column=1, end_row=ws.max_row, end_column=5)
                ws.cell(ws.max_row, 1).font = Font(name="宋体", size=10.5, color="8A4B00")
                ws.cell(ws.max_row, 1).alignment = wrap
        summary.append([rep["title"], "；".join(rep["results"])])
        for i, c in enumerate(summary[summary.max_row]):
            c.font, c.border, c.alignment = base, border, wrap
    summary.column_dimensions["A"].width = 30
    summary.column_dimensions["B"].width = 100
    wb.save(path)
