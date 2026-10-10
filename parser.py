# -*- coding: utf-8 -*-
"""
监测报告解析模块

思路：各类文件先统一转成"表格网格"（二维字符串列表），再由 parse_grid 识别结构，
输出长表记录 dict(station, date, item, value, unit, report_limit, src)。

支持：
  Excel（.xlsx）：openpyxl 读取，合并单元格自动填充
  Word（.docx）：python-docx 读取表格，合并单元格自动重复
  PDF（有文字层）：pdfplumber 提取表格
  图片 / 扫描件：暂不直接判定，见 README 说明（OCR 易错读数值与上标）

识别的表格版式（第三方报告常见"断面为列"宽表）：
  | 检测日期 | 检测项目 | 断面1 | 断面2 | ... | 标准值或范围 |
  表头可有多行（断面名称行、样品编号行），项目列形如"氨氮（mg/L）"。
"""
import re
from collections import OrderedDict
import statistics
from judge import match_item

_SUP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺", "0123456789-+")


def clean_text(s):
    if s is None:
        return ""
    s = str(s).replace("\n", "").replace("\r", "").strip()
    return re.sub(r"\s+", " ", s)


def normalize_value(s):
    """
    统一监测值写法，返回 (规范化字符串, 附注)。
      7.2(26℃)      → "7.2"，附注"测定温度26℃"
      4.7×10³       → "4.7×10^3"
      4.00×10⁻⁵L    → "4.00×10^-5L"
      1.0X10-3L     → "1.0×10^-3L"
    """
    s = clean_text(s).replace("（", "(").replace("）", ")").replace(" ", "")
    note = ""
    m = re.match(r"^(.+?)\((\d+(?:\.\d+)?)[℃°C'′]*C?\)$", s)
    if m:
        s, note = m.group(1), f"测定温度{m.group(2)}℃"
    # 上标指数：先标记"×10"后紧跟的上标字符
    m = re.match(r"^([0-9.]+)[×xX\*]10([⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺\-+0-9]+?)(L?)$", s)
    if m:
        s = f"{m.group(1)}×10^{m.group(2).translate(_SUP)}{m.group(3)}"
    else:
        s = s.translate(_SUP)
    return s, note


def split_item_unit(cell):
    """"氨氮（mg/L）" → ("氨氮", "mg/L")；"pH（无量纲）" → ("pH", "无量纲")"""
    t = clean_text(cell).replace("（", "(").replace("）", ")")
    t = re.sub(r"\(cid:\d+\)", "\ufffd", t)          # 未还原的乱码字符记为 �，便于人工核对
    m = re.match(r"^(.*?)\s*\(([^()]*?(?:/|无量纲|个|℃|°C|NTU|Bq|\ufffd|[×xX]\s*10|%)[^()]*|度|倍|铂钴色度单位)\)\s*$", t)
    if m:
        return _strip_symbol(m.group(1).strip()), m.group(2).strip().replace("mgL", "mg/L")
    return _strip_symbol(t), ""


_ELEMENTS = {"As", "Hg", "Cd", "Pb", "Cu", "Ni", "Cr", "Zn", "Sb", "Be", "Co", "V", "Mn", "Fe", "Se", "Ag", "Mo",
             "Tl", "Ba", "Al", "Sn", "B", "F"}


def _strip_symbol(name):
    """"砷As""汞（Hg）""镉 Cd" → "砷"……；仅去掉紧跟中文名后的元素符号"""
    m = re.match(r"^(.*[\u4e00-\u9fff])\s*\(?([A-Z][a-z]?)\)?$", name)
    if m and m.group(2) in _ELEMENTS:
        return m.group(1)
    return name


DATE_RE = re.compile(r"(19|20)\d{2}\s*[.\-/年]\s*\d{1,2}\s*[.\-/月]\s*\d{1,2}")


def _find(row, keys):
    for j, c in enumerate(row):
        if any(k in clean_text(c) for k in keys):
            return j
    return None


def parse_grid(grid, matcher=match_item, join_header=False):
    """
    grid: list[list[str]] → (records, warnings)；matcher 为指标名称识别函数（地表水/地下水）。
    依次尝试三种常见版式，取识别条数最多者：
      A. 项目为行、点位为列（宽表，如德福报告）
      B. 点位为行、项目为列（转置宽表）
      C. 长表（每行一条：点位、日期、项目、结果、单位）——也是"通用导入模板"的格式
    """
    g = [[clean_text(c) for c in row] for row in grid if any(clean_text(c) for c in row)]
    # 按版式特征判定，而不是比条数：长表表头同时含"点位、项目、结果"三列；转置表表头含≥2个标准项目名
    for fn in (_parse_long, _parse_items_in_cols, _parse_items_in_rows):
        r = fn(g, matcher, join_header) if fn is _parse_items_in_rows else fn(g, matcher)
        if r[0]:
            return r
    return [], ["未找到'检测项目'列或未识别到任何标准项目"]


_ST_KEYS = ["监测点位", "检测点位", "采样点位", "点位名称", "点位", "断面", "采样点", "监测点", "站位"]
_VAL_KEYS = ["检测结果", "监测结果", "监测值", "检测值", "结果", "浓度", "测定值"]


def _parse_long(grid, matcher):
    """版式 C：长表"""
    for hi, row in enumerate(grid):
        sc, ic = _find(row, _ST_KEYS), _find(row, ["检测项目", "监测项目", "分析项目", "项目", "指标"])
        vc = _find(row, _VAL_KEYS)
        if None not in (sc, ic, vc) and len({sc, ic, vc}) == 3:
            break
    else:
        return [], []
    dc, uc = _find(row, ["日期", "时间"]), _find(row, ["单位"])
    lc = _find(row, ["标准值", "标准限值", "限值"])
    recs, warns, cur = [], [], {}
    for r in grid[hi + 1:]:
        r = r + [""] * (len(row) - len(r))
        for k, c in (("st", sc), ("date", dc)):        # 合并单元格 / 省略重复时沿用上一行
            if c is not None and r[c]:
                cur[k] = r[c]
        name, unit = split_item_unit(r[ic])
        if not name or not r[vc] or re.match(r"^(备注|注)", r[0]):
            continue
        if matcher(name)[1] is None:
            warns.append(f"项目'{name}'未在标准中找到，已保留待核")
        val, vnote = normalize_value(r[vc])
        recs.append(dict(station=cur.get("st", ""), date=cur.get("date", ""), item=name, value=val,
                         unit=(r[uc] if uc is not None and r[uc] else unit),
                         report_limit=r[lc] if lc is not None else "", raw=r[vc], src_note=vnote))
    return recs, warns


def _parse_items_in_cols(grid, matcher):
    """版式 B：点位为行、项目为列"""
    for hi, row in enumerate(grid):
        items = {j: split_item_unit(c) for j, c in enumerate(row) if c and matcher(split_item_unit(c)[0])[0]}
        if len(items) >= 2:
            break
    else:
        return [], []
    sc = _find(row, _ST_KEYS)
    dc = _find(row, ["日期", "时间"])
    spc = _find(row, ["生物种类", "生物名称", "种类", "物种", "样品名称"])     # 海洋生物质量：样品种类并入站位名
    if spc is not None and spc in items:
        spc = None
    if sc is None:
        sc = next((j for j in range(min(items)) if j != dc), None)
    if sc is None:
        return [], []
    # 同名表头相邻列（合并单元格横跨两列）归为一组；取值时跳过从左侧单元格"溢出"的重复值
    groups = OrderedDict()
    for j in sorted(items):
        key = items[j]
        if groups and list(groups)[-1][0] == key and max(groups[list(groups)[-1]]) == j - 1:
            groups[list(groups)[-1]].append(j)
        else:
            groups[(key, j)] = [j]

    def pick(r, cols):
        left = r[cols[0] - 1] if cols[0] > 0 else None
        cand = [r[j] for j in cols if r[j] and r[j] != left]
        return cand[0] if cand else r[cols[0]]

    recs, warns, limits, cur = [], [], {}, {}
    for r in grid[hi + 1:]:
        r = r + [""] * (len(row) - len(r))
        lead = " ".join(r[:min(items)])
        if re.match(r"^(备注|注)", r[0]):
            continue
        if re.search(r"标准|限值", lead):                  # 标准值行
            limits = {g: pick(r, cols) for g, cols in groups.items()}
            continue
        if re.search(r"最大值|最小值|平均值|均值|范围|超标", lead):   # 统计行
            continue
        if dc is not None and r[dc]:
            cur["date"] = r[dc]
        if r[sc]:
            cur["st"] = r[sc]
        if spc is not None and spc != sc and r[spc]:
            cur["st"] = f"{r[sc] or cur.get('st', '')}（{r[spc]}）"
        if re.match(r"^[A-Z]{0,4}\d{4,}[-\d]*$", r[sc] or ""):  # 样品编号行
            continue
        for g, cols in groups.items():
            name, unit = g[0]
            v = pick(r, cols)
            if not v:
                continue
            val, vnote = normalize_value(v)
            recs.append(dict(station=cur.get("st", ""), date=cur.get("date", ""), item=name, value=val,
                             unit=unit, report_limit="", raw=v, src_note=vnote, _g=g))
    for x in recs:
        x["report_limit"] = limits.get(x.pop("_g"), "")
    return recs, warns


def _parse_items_in_rows(grid, matcher, join_header=False):
    """版式 A：项目为行、点位为列"""
    warnings = []
    item_col = std_col = date_col = None
    first_data = None
    for i, row in enumerate(grid):
        if item_col is None:
            j = _find(row, ["检测项目", "监测项目", "分析项目", "项目"])
            if j is not None:
                item_col = j
                date_col = _find(row, ["日期", "时间"])
                std_col = _find(row, ["标准值", "标准限值", "限值", "标准"])
            continue
        name, _ = split_item_unit(row[item_col]) if item_col < len(row) else ("", "")
        if matcher(name)[0] is not None:
            first_data = i
            break
    if item_col is None or first_data is None:
        return [], ["未找到'检测项目'列或未识别到任何标准项目"]

    header_rows = grid[:first_data]
    ncol = max(len(r) for r in grid)
    # 按表头文字区分辅助列（单位、检出限、标准值、方法、评价等），其余为点位（样品）列
    head_txt = {j: "".join(clean_text(r[j]) for r in header_rows if j < len(r)) for j in range(ncol)}
    unit_col = dl_col = None
    aux = set()
    for j in range(item_col + 1, ncol):
        t = head_txt[j]
        if re.search(r"结果|测定值|监测值|检测值|浓度", t):
            continue
        if re.search(r"单位", t):
            unit_col = j if unit_col is None else unit_col
            aux.add(j)
        elif re.search(r"检出限|检测限", t):
            dl_col = j if dl_col is None else dl_col
            aux.add(j)
        elif re.search(r"标准|限值|筛选值|管制值|方法|依据|仪器|评价|达标|结论|备注|序号|类别", t):
            aux.add(j)
            if std_col is None and re.search(r"标准|限值|筛选值", t):
                std_col = j
    st_cols = [j for j in range(item_col + 1, ncol) if j != std_col and j != date_col and j not in aux]
    # 断面名称：取表头中该列"像名称"的那一行（排除样品编号、大标题）
    # 表头中的日期行（如"2023.7.3"跨三列合并），向右填充到各列
    col_date = {}
    date_rows = set()
    for k, r in enumerate(header_rows):
        if sum(bool(DATE_RE.search(clean_text(c))) for c in r) >= 1 and \
                all(not clean_text(c) or DATE_RE.search(clean_text(c)) for c in r[item_col + 1:]):
            date_rows.add(k)
            cur = ""
            for j in range(item_col + 1, len(r)):
                if clean_text(r[j]):
                    cur = clean_text(r[j])
                col_date[j] = cur
    stations = {}
    for j in st_cols:
        cand = [r[j] for k, r in enumerate(header_rows) if j < len(r) and r[j] and k not in date_rows]
        cand = [c for c in cand if not re.match(r"^[A-Z]{0,4}\d{4,}[-\d]*$", c)
                and "监测点位" not in c and "检测点位" not in c]
        if join_header:      # 土壤：点位、采样深度分行书写，合并为"T1 0~0.2m"
            cand = [c for c in cand if not re.search(r"结果|监测|检测|样品|单位|标准|项目", c)]
            stations[j] = " ".join(dict.fromkeys(cand)) if cand else f"第{j}列"
        else:
            stations[j] = cand[-1] if cand else f"第{j}列"
    # 去掉重复（合并单元格导致的同名列）
    seen, uniq = set(), []
    for j in st_cols:
        if (stations[j], col_date.get(j, "")) not in seen:
            seen.add((stations[j], col_date.get(j, "")))
            uniq.append(j)
    st_cols = uniq

    records, cur_date = [], ""
    for row in grid[first_data:]:
        row = row + [""] * (ncol - len(row))
        if date_col is not None and row[date_col]:
            cur_date = row[date_col]
        name, unit = split_item_unit(row[item_col])
        if unit_col is not None and clean_text(row[unit_col]):
            unit = clean_text(row[unit_col])
        if not name or re.match(r"^(备注|注)", row[0] or name):
            continue
        if matcher(name)[1] is None and matcher(name)[0] != "pH":
            warnings.append(f"项目'{name}'未在标准中找到，已保留待核")
        if not any(row[j] for j in st_cols):
            warnings.append(f"项目'{name}'报告未给出监测值（{row[std_col] if std_col is not None else ''}），未判定")
        for j in st_cols:
            raw = row[j]
            if not raw:
                continue
            val, vnote = normalize_value(raw)
            records.append(dict(station=stations[j], date=col_date.get(j) or cur_date, item=name, value=val,
                                unit=unit, report_limit=row[std_col] if std_col is not None else "",
                                raw=raw, src_note=vnote))
    return records, warnings


def table_kind(grid):
    """
    判断表格类别：surface（地表水）/ groundwater（地下水）/ air（环境空气）/ noise（声环境）/ soil（土壤）/
    sediment（海洋沉积物）/ biota（海洋生物质量）/ stack（有组织废气）/ fugitive（无组织废气）/
    wastewater（废水）/ other。
    依据表内单位和引用标准（通常在表尾"备注：执行《……》"）判别；废气、无组织厂界废气等排放类表格归为 other。
    未注明标准的水质表，若表头含"检测项目"且能识别出 GB 3838 项目，返回 unknown（按所选水体读取并提示）。
    """
    text = "".join(clean_text(c) for row in grid for c in row)
    t = text.replace("^", "").replace("³", "3").replace("µ", "μ")
    if re.search(r"dB(?![\s/]*\d)|Leq|噪声|声级", t, re.I):     # 排除"DB35/ 2324"等地方标准编号
        return "noise"
    if re.search(r"18421|生物质量|生物体|贝类|双壳|牡蛎|鲜重", t):
        return "biota"
    if re.search(r"18668|沉积物", t):
        return "sediment"
    if re.search(r"mg/kg|μg/kg|ug/kg|36600|15618|土壤", t, re.I):
        return "soil"
    if (re.search(r"无组织", t) or re.search(r"厂界", t) and re.search(r"mg/m3|μg/m3|废气|臭气|恶臭|14554", t, re.I)
            and not re.search(r"排气筒|标干流量|DA\d{3}|排放速率", t)) and not re.search(r"环境空气|3095", t):
        return "fugitive"                                # 无组织废气（排放标准）
    if re.search(r"标干流量|排气筒|有组织|DA\d{3}|废气|排放速率|烟气|折算浓度|含氧量|13271", t):
        return "stack"                                   # 固定源废气
    if re.search(r"mg/m3|μg/m3|ug/m3|环境空气|3095", t, re.I):
        if re.search(r"厂界|无组织|14554|16297", t) and not re.search(r"环境空气|3095|HJ ?2\.2", t):
            return "fugitive"                            # 无组织厂界废气（排放标准）
        return "air"
    if re.search(r"8978|废水|污水|DW\d{3}|排放口|总排口|出水口|进水口|处理设施出口", t) and \
            not re.search(r"3838|14848|地表水|地下水|断面|上游|下游|水井", t):
        return "wastewater"                              # 废水（排放标准）
    if "14848" in t or "地下水" in t:
        return "groundwater"
    if "3838" in t or "地表水" in t:
        return "surface"
    if re.search(r"(检测|监测|分析)项目", t) and parse_grid(grid)[0]:
        return "unknown"
    return "other"


STD_RE = re.compile(r"((?:GB|HJ|DB\d{2})\s*/?\s*T?\s*\d{1,5}(?:\.\d+)?\s*[-—－–]\s*\d{2,4})")


def table_standards(grid):
    """表内引用的标准编号（去重），如 GB3095-2012、HJ 2.2-2018"""
    text = "".join(clean_text(c) for row in grid for c in row)
    return list(dict.fromkeys(re.sub(r"\s+", "", m) for m in STD_RE.findall(text)))


PERIOD_HINTS = [("8h", r"8\s*小时|8h|八小时"), ("1h", r"小时|1h|时均|一次值"),
                ("24h", r"日均|日平均|24\s*小时|24h"), ("year", r"年均|年平均"), ("season", r"季平均")]


def period_hint(text):
    for key, pat in PERIOD_HINTS:
        if re.search(pat, text or "", re.I):
            return key
    return ""


def _parse_noise(grid):
    """声环境监测表：长表（每行一个点次，含 Leq 列）或宽表（昼间、夜间分列）"""
    g = [[clean_text(c) for c in row] for row in grid if any(clean_text(c) for c in row)]
    for hi, row in enumerate(g):
        day_c = [j for j, c in enumerate(row) if "昼" in c and not re.search(r"日期|时间", c)]
        night_c = [j for j, c in enumerate(row) if "夜" in c and not re.search(r"日期|时间", c)]
        val_c = _find(row, ["Leq", "LeqdB", "等效声级", "测量值", "测量结果", "检测结果", "监测结果", "噪声值"])
        if val_c is not None or (day_c and night_c):
            break
    else:
        return [], []
    if day_c and night_c and val_c in day_c + night_c:        # "昼间 Leq""夜间 Leq"分列
        val_c = None
    sc = _find(row, _ST_KEYS + ["测点", "监测位置", "检测位置", "位置"])
    dc = _find(row, ["日期"])
    tc = _find(row, ["测量时间", "监测时间", "检测时间", "时间"])
    pc = _find(row, ["时段", "昼夜"])
    lc = _find(row, ["标准限值", "标准值", "限值"])
    mc = _find(row, ["Lmax", "最大声级"])
    recs, warns, cur = [], [], {}
    for r in g[hi + 1:]:
        r = r + [""] * (len(row) - len(r))
        if re.match(r"^(备注|注)", r[0]):
            continue
        if sc is not None and r[sc]:
            cur["st"] = r[sc]
        if dc is not None and r[dc]:
            cur["date"] = r[dc]
        st, date = cur.get("st", ""), cur.get("date", "")
        if not st or re.search(r"标准|限值", st):
            continue
        cols = []
        if day_c and night_c and val_c is None:
            cols = [(day_c[0], "昼间"), (night_c[0], "夜间")]
        else:
            ctx = " ".join([r[pc] if pc is not None else "", r[dc] if dc is not None else "", r[0]])
            per = "夜间" if "夜" in ctx else ("昼间" if "昼" in ctx else "")
            if not per and tc is not None:
                m = re.match(r"(\d{1,2})[:：]", r[tc])
                if m:
                    per = "昼间" if 6 <= int(m.group(1)) < 22 else "夜间"
            cols = [(val_c, per or "未注明时段")]
        for j, per in cols:
            if j is None or not r[j] or not re.search(r"\d", r[j]):
                continue
            val, vnote = normalize_value(r[j])
            lim = r[lc] if lc is not None else ""
            m = re.search(("昼" if per == "昼间" else "夜") + r"[间：:\s]*(\d+(?:\.\d+)?)", lim)
            if m and per in ("昼间", "夜间"):              # "昼65/夜55"取对应时段
                lim = m.group(1)
            recs.append(dict(station=st, date=re.sub(r"[（(].*?[)）]", "", date), item=per, value=val, unit="dB(A)",
                             report_limit=lim, raw=r[j], src_note=vnote,
                             time=r[tc] if tc is not None else ""))
        if mc is not None and r[mc] and re.search(r"\d", r[mc]):
            val, vnote = normalize_value(r[mc])
            recs.append(dict(station=st, date=re.sub(r"[（(].*?[)）]", "", date), item="夜间突发噪声Lmax", value=val,
                             unit="dB(A)", report_limit="", raw=r[mc], src_note=vnote,
                             time=r[tc] if tc is not None else ""))
    return recs, warns


# ------------------------------------------------------------------ 文件读取
def grids_from_excel(path):
    from openpyxl import load_workbook
    wb = load_workbook(path, data_only=True)
    out = []
    for ws in wb.worksheets:
        vals = [[c.value for c in row] for row in ws.iter_rows()]
        for rng in ws.merged_cells.ranges:
            v = ws.cell(rng.min_row, rng.min_col).value
            for r in range(rng.min_row, rng.max_row + 1):
                for c in range(rng.min_col, rng.max_col + 1):
                    vals[r - 1][c - 1] = v
        out.append([["" if v is None else str(v) for v in row] for row in vals])
    return out


def grids_from_word(path):
    from docx import Document
    doc = Document(path)
    out = []
    for t in doc.tables:
        out.append([[_cell_text_with_sup(c) for c in row.cells] for row in t.rows])
    return out


def _cell_text_with_sup(cell):
    """Word 中上标指数（如 10 的 -5 次方）以 run 上标格式存储，此处还原为 ^-5。"""
    parts = []
    for p in cell.paragraphs:
        for r in p.runs:
            t = r.text
            if r.font.superscript and t.strip():
                parts.append("^" + t.strip())
            else:
                parts.append(t)
    s = "".join(parts)
    return s.replace("10^", "10^") if s else cell.text


def _page_tables(page):
    """提取表格；无左右外框的表（只画横线和内部竖线）补上两侧边界，避免首列项目名、末列数据丢失"""
    tabs = page.find_tables()
    hs = [e for e in page.edges if e["orientation"] == "h" and page.width * 0.3 < e["x1"] - e["x0"] < page.width * 0.98]
    extra = []
    for t in tabs:
        x0, top, x1, bottom = t.bbox
        # 与该表等宽或更宽的横线，逐步向上下扩展出整张表的纵向范围（表头行可能没有竖线）
        rel = [e for e in hs if e["x0"] <= x0 + 5 and e["x1"] >= x1 - 5]
        changed = True
        while changed:
            changed = False
            for e in rel:
                if top - 40 <= e["top"] < top - 0.5 or bottom + 0.5 < e["top"] <= bottom + 40:
                    top, bottom = min(top, e["top"]), max(bottom, e["top"])
                    changed = True
        inside = [e for e in rel if top - 0.5 <= e["top"] <= bottom + 0.5]
        if not inside:
            continue
        lo = statistics.median(e["x0"] for e in inside)
        hi = statistics.median(e["x1"] for e in inside)
        for x in (lo, hi):
            if x < x0 - 3 or x > x1 + 3:
                extra.append(dict(x0=x, x1=x, top=top, bottom=bottom, width=0, height=bottom - top,
                                  orientation="v", object_type="line"))
    if extra:
        return page.extract_tables({"explicit_vertical_lines": extra})
    return [t.extract() for t in tabs]


def grids_from_pdf(path, notes=None):
    """notes：传入列表时，写入乱码还原等提示"""
    import pdfplumber
    import pdf_glyph
    out = []
    dec = None
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            if any(c["text"].startswith("(cid:") for c in page.chars):
                dec = dec or pdf_glyph.Decoder()
                pdf_glyph.fix_page(page, dec)
            else:
                pdf_glyph._mark_superscripts(page.chars)
            if not (page.extract_text() or "").strip():
                raise ValueError(f"第{page.page_number}页无文字层（扫描件），需走 OCR 路线")
            for t in _page_tables(page):
                out.append([[c or "" for c in row] for row in t])
    if dec is not None and notes is not None:
        notes.append("该 PDF 字体未带文字映射（常见于虚拟打印机生成），已按本机字体比对字形还原文字，请重点核对")
        if dec.missing:
            notes.append("本机缺少字体：" + "、".join(sorted(dec.missing)) + "，相应文字无法还原")
        if dec.unknown:
            notes.append(f"仍有 {dec.unknown} 个字符无法还原（显示为 (cid:数字)），请对照原件修改或改用 Word 原件")
    return out


def _matcher(kind):
    if kind == "groundwater":
        from gw_judge import match_item as m
    elif kind == "air":
        from air_judge import match_item as m
    elif kind == "soil":
        from soil_judge import match_item as m
    elif kind in ("sediment", "biota"):
        from marine_judge import matcher
        m = matcher(kind)
    else:
        m = match_item
    return m


KIND_CN = {"surface": "地表水", "groundwater": "地下水", "air": "环境空气", "noise": "声环境", "soil": "土壤",
           "sediment": "海洋沉积物", "biota": "海洋生物质量"}


def read_report(path, kind="surface"):
    """
    读取监测报告，返回 (records, warnings)。
    kind：surface（地表水）/ groundwater（地下水）/ air（环境空气）/ noise（声环境）/ soil（土壤）
    """
    matcher = _matcher(kind)
    p = path.lower()
    pdf_notes = []
    if p.endswith((".xlsx", ".xlsm")):
        grids = grids_from_excel(path)
    elif p.endswith(".docx"):
        grids = grids_from_word(path)
    elif p.endswith(".pdf"):
        grids = grids_from_pdf(path, pdf_notes)
    else:
        return [], [f"暂不支持的文件类型：{path}（.doc 请另存为 .docx，图片请提供原始电子版）"]
    records, warnings = [], list(pdf_notes)
    water = kind in ("surface", "groundwater")
    for k, g in enumerate(grids, 1):
        tk = table_kind(g)
        if tk != kind and not (water and tk == "unknown"):
            if water and tk in ("surface", "groundwater") and parse_grid(g)[0]:
                warnings.append(f"第{k}个表格为{KIND_CN[tk]}监测结果，本页不判定，已跳过")
            continue
        if tk == "unknown":
            warnings.append(f"第{k}个表格未注明执行标准，已按所选水体类型读取，请核对")
        if kind == "noise":
            r, w = _parse_noise(g)
        else:
            r, w = parse_grid(g, matcher, join_header=(kind in ("soil", "sediment", "biota")))
        stds = "；".join(table_standards(g))
        hint = period_hint("".join(clean_text(c) for row in g[:3] for c in row)) if kind == "air" else ""
        for x in r:
            x["table_std"] = stds
            x["table_no"] = k
            if kind == "air":
                x.setdefault("period", period_hint(x["item"]) or hint)
        records += r
        if r:
            warnings += w
    if kind == "air":
        ref = {}
        for x in records:
            if x.get("report_limit"):
                ref.setdefault(x["item"], (x["report_limit"], x.get("table_std", ""), x["table_no"]))
        for x in records:
            if not x.get("report_limit") and x["item"] in ref:
                x["report_limit"], std, no = ref[x["item"]]
                x["table_std"] = x.get("table_std") or std
                x["src_note"] = "；".join(v for v in (x.get("src_note"), f"报告限值沿用第{no}个表格同名项目") if v)
    if not records:
        warnings.append("未在文件中识别到监测数据表")
    return records, warnings
