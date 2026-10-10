# -*- coding: utf-8 -*-
"""
污染源排放监测报告解析（废水、有组织废气、无组织废气、厂界噪声）

各类文件先由 parser.py 转成表格网格，再按下列思路识别（排放监测表版式多样，识别结果须在核对表中人工核对）：
  · 表头行含"检测项目/监测项目/污染物/项目/参数"列；项目为行。
  · 点位列（排气筒、排放口、采样点位等）可在项目列左侧，合并单元格自动沿用；
    无点位列时，若数值列表头为点位名称（如"上风向1#""下风向2#""污水处理站出口"），以表头作为点位。
  · 数值列表头为"第1次""第一次""1""2""3""采样日期"等，作为样品（频次）标识；同时有逐次值和均值/最大值列时，
    只取逐次值，避免重复；只有均值列时取均值。
  · 有组织废气：项目文字或"参数/指标"列区分实测浓度、折算浓度、排放速率；"标干流量""含氧量""排气筒高度"等参数行
    不作判定，其中含氧量按同一点位、同一频次并入对应浓度记录，排气筒高度并入该排气筒的全部记录；
    整行只有一段文字的行（如"DA001 喷涂废气排放口 排气筒高度 15 m"）视为排气筒标题行。
  · 厂界噪声沿用 parser._parse_noise（昼间、夜间、Lmax）。
"""
import re

from parser import (clean_text, normalize_value, split_item_unit, DATE_RE, _ST_KEYS, table_kind, table_standards,
                    grids_from_excel, grids_from_word, grids_from_pdf, _parse_noise)
from judge import parse_value
import emission_judge as E

KIND_CN = {E.WASTEWATER: "废水", E.STACK: "有组织废气", E.FUGITIVE: "无组织废气", E.BOILER: "锅炉废气", E.ODOR_STACK: "恶臭有组织排放",
           E.ODOR_FENCE: "恶臭厂界", E.BNOISE: "厂界噪声"}
ITEM_KEYS = ["检测项目", "监测项目", "分析项目", "污染物名称", "污染物", "检测因子", "监测因子", "检测参数", "项目", "参数"]
ST_KEYS = ["排气筒编号", "排气筒名称", "排放口编号", "排放口名称", "排气筒", "排放口", "采样位置", "检测位置", "监测位置",
           "采样口", "测点"] + _ST_KEYS
SAMPLE_RE = re.compile(r"第\s*[一二三四五六七八九十\d]+\s*[次个]|^[1-9]\d?$|^[一二三四五六七八九十]+$|频次|次数|样品|小时")
MEAN_RE = re.compile(r"均值|平均|日均|最大值|最小值|范围")
AUX_RE = re.compile(r"单位|检出限|检测限|标准|限值|方法|依据|仪器|评价|达标|结论|备注|序号|是否|执行|超标")
VALUE_HEAD_RE = re.compile(r"检测结果|监测结果|测定结果|分析结果|结果|测定值|检测值|监测值|实测值|浓度值|数值")
HEIGHT_RE = re.compile(r"(?:排气筒|烟囱|筒)?高度[^0-9\n]{0,6}(\d+(?:\.\d+)?)\s*(?:m|米)|"
                       r"(\d+(?:\.\d+)?)\s*(?:m|米)\s*(?:高)?(?:的)?(?:排气筒|烟囱)", re.I)
PARAM_RE = re.compile(r"标干|流量|含氧|氧含量|O2|O₂|高度|温度|流速|湿度|含湿|压力|动压|静压|截面|工况|负荷|"
                      r"采样时间|时间段|烟道|管道|内径|直径|废气量|风量")
METRIC_WORDS = re.compile(r"(实测|折算|基准氧含量|基准|排放|最高允许)(浓度|速率)|(排放)?速率|排放量|实测值|折算值")


def _num_cell(c):
    c = clean_text(c)
    if not c or DATE_RE.search(c) or re.search(r"[:：]", c):
        return False
    pv = parse_value(normalize_value(c)[0])
    return pv["ok"]


def _find_all(row, keys):
    return [j for j, c in enumerate(row) if any(k in clean_text(c) for k in keys)]


def _header(g):
    for hi, row in enumerate(g):
        cand = _find_all(row, ITEM_KEYS)
        cand = [j for j in cand if len(clean_text(row[j])) <= 12]
        if cand and hi + 1 < len(g):
            return hi, cand[0]
    return None, None


def _clean_name(text):
    name, unit = split_item_unit(text)
    n = METRIC_WORDS.sub("", name).strip(" -—:：/")
    return (n or name), unit


def parse_rows(grid, kind):
    """项目为行的通用解析，返回 (records, warnings)"""
    g = [[clean_text(c) for c in row] for row in grid if any(clean_text(c) for c in row)]
    hi, ic = _header(g)
    if hi is None:
        return [], []
    ncol = max(len(r) for r in g)
    g = [r + [""] * (ncol - len(r)) for r in g]
    fd = next((i for i in range(hi + 1, len(g)) if any(_num_cell(c) for c in g[i][ic + 1:])), None)
    if fd is None:
        return [], []
    heads = g[hi:fd]
    head_txt = {j: "".join(dict.fromkeys(r[j] for r in heads if r[j])) for j in range(ncol)}
    match = E.matcher(kind)

    st_cols = [j for j in _find_all(g[hi], ST_KEYS) if j != ic]
    sc = st_cols[0] if st_cols else None
    dc = next((j for j in range(ncol) if j not in (ic, sc) and re.search(r"日期|采样时间", head_txt[j])
               and not VALUE_HEAD_RE.search(head_txt[j])), None)
    unit_c = next((j for j in range(ncol) if j != ic and re.search(r"单位", head_txt[j])), None)
    std_c = next((j for j in range(ncol) if j != ic and re.search(r"标准|限值", head_txt[j])
                  and not VALUE_HEAD_RE.search(head_txt[j])), None)
    h_c = next((j for j in range(ncol) if j != ic and re.search(r"高度", head_txt[j])), None)
    o2_c = next((j for j in range(ncol) if j != ic and re.search(r"含氧|氧含量", head_txt[j])), None)
    freq_c = next((j for j in range(ncol) if j not in (ic, sc, dc) and re.search(r"频次|次数", head_txt[j])
                   and not any(_num_cell(r[j]) and "." in r[j] for r in g[fd:])), None)
    # 参数/指标列：在项目列右侧，数据行中多为"实测浓度""排放速率"等
    sub_c = None
    for j in range(ic + 1, ncol):
        cells = [r[j] for r in g[fd:] if r[j]]
        if re.search(r"^(参数|指标|类别|内容|检测参数|监测参数)$", head_txt[j]) or \
                (cells and sum(bool(re.search(r"浓度|速率|流量|含氧|折算|实测|黑度", c)) for c in cells) >= max(2, len(cells) // 2)):
            sub_c = j
            break
    fixed = {x for x in (ic, sc, dc, unit_c, std_c, h_c, o2_c, freq_c, sub_c) if x is not None}
    val_cols = [j for j in range(ic + 1, ncol) if j not in fixed and not
                (AUX_RE.search(head_txt[j]) and not VALUE_HEAD_RE.search(head_txt[j]))]
    val_cols = [j for j in val_cols if any(_num_cell(r[j]) for r in g[fd:])]
    if not val_cols:
        return [], []
    each = [j for j in val_cols if not MEAN_RE.search(head_txt[j])]
    val_cols = each or val_cols

    # 数值列标识：点位名称或样品（频次、日期）
    labels = {}
    for j in val_cols:
        parts = [r[j] for r in heads if r[j]]
        parts = [p for p in dict.fromkeys(parts) if not VALUE_HEAD_RE.fullmatch(p) and not re.fullmatch(
            r"(检测|监测)?(结果|数据)(\(.*\))?|单位.*|mg/.*|kg/h", p)]
        parts = [VALUE_HEAD_RE.sub("", p).strip("（）() ") or p for p in parts]
        parts = [re.sub(r"^及?(频次|次数)$", "", p) for p in parts
                 if not re.match(r"^[A-Z]{0,4}\d{4,}[-\d]*$", p)]          # 去掉"及频次"残字和样品编号
        labels[j] = " ".join(p for p in parts if p).strip()
    col_is_station = sc is None and any(labels[j] and not SAMPLE_RE.search(labels[j]) and not DATE_RE.search(labels[j])
                                        for j in val_cols)
    if len({labels[j] for j in val_cols}) < len(val_cols):      # 表头重复（合并单元格）时以列序号区分
        seen = {}
        for j in val_cols:
            seen[labels[j]] = seen.get(labels[j], 0) + 1
            if seen[labels[j]] > 1 or not labels[j]:
                labels[j] = f"{labels[j]}第{seen[labels[j]]}列".strip()

    table_text = " ".join(" ".join(r) for r in g)
    hs = list(dict.fromkeys(float(a or b) for a, b in HEIGHT_RE.findall(table_text)))
    table_h = hs[0] if len(hs) == 1 else None

    recs, warns, cur = [], [], {}
    o2map, hmap = {}, {}
    for r in g[hi + 1:fd]:              # 表头区内的"样品编号"等行可能已带点位、日期（PDF 合并单元格只在首行有值）
        if sc is not None and r[sc] and r[sc] != g[hi][sc]:
            cur["st"] = r[sc]
        if dc is not None and DATE_RE.search(r[dc] or ""):
            cur["date"] = r[dc]
    for r in g[fd:]:
        if re.match(r"^(备注|注|说明)", r[0]) or re.match(r"^(备注|注)", r[ic]):
            continue
        texts = list(dict.fromkeys(c for c in r if c))
        if len(texts) == 1 and not _num_cell(texts[0]):             # 排气筒标题行
            cur["st"] = texts[0]
            m = HEIGHT_RE.search(texts[0])
            if m:
                hmap[texts[0]] = float(m.group(1) or m.group(2))
            continue
        if sc is not None and r[sc]:
            cur["st"] = r[sc]
            m = HEIGHT_RE.search(r[sc])
            if m:
                hmap[r[sc]] = float(m.group(1) or m.group(2))
        if dc is not None and r[dc]:
            cur["date"] = r[dc]
        if freq_c is not None and r[freq_c]:
            cur["freq"] = r[freq_c]
        st = cur.get("st", "")
        if h_c is not None and _num_cell(r[h_c]):
            hmap[st] = float(re.sub(r"[^\d.]", "", r[h_c]) or 0) or None
        item_txt = r[ic]
        sub = r[sub_c] if sub_c is not None else ""
        if not item_txt and sub:                     # 合并单元格（PDF 只在首行有值）沿用上一项目
            item_txt = cur.get("item_txt", "")
        cur["item_txt"] = item_txt
        full = f"{item_txt} {sub}".strip()
        if not item_txt or re.search(r"^(标准|限值|执行标准|评价标准)", item_txt):
            continue
        name, unit = _clean_name(item_txt)
        su = split_item_unit(sub)[1] if sub else ""
        unit = (r[unit_c] if unit_c is not None and r[unit_c] else "") or su or unit
        if PARAM_RE.search(full) and not match(name)[0]:
            what = "o2" if re.search(r"含氧|氧含量|O2|O₂", full) else ("h" if "高度" in full else "")
            for j in val_cols:
                if not _num_cell(r[j]):
                    continue
                v = float(parse_value(normalize_value(r[j])[0])["value"] or 0)
                key_st = labels[j] if col_is_station else st
                if what == "o2":
                    o2map[(key_st, _sample(cur, labels[j], col_is_station))] = v
                elif what == "h":
                    hmap[key_st] = v
            continue
        if kind in E.GAS and not match(name)[0] and re.fullmatch(r"(实测|折算|排放)?(浓度|速率)", name):
            name = cur.get("pollutant", name)
        else:
            cur["pollutant"] = name
        if not match(name)[0]:
            warns.append(f"项目“{name}”未在限值库中，已保留，按报告限值判定")
        metric = E.metric_of(f"{full} {item_txt}", unit) if kind in E.GAS else ""
        o2_row = r[o2_c] if o2_c is not None else ""
        for j in val_cols:
            raw = r[j]
            if not raw or raw in ("/", "-", "—", "--") or not re.search(r"\d|ND|未检出", raw, re.I):
                continue
            val, vnote = normalize_value(raw)
            station = labels[j] if col_is_station else st
            rec = dict(station=station, date=_sample(cur, labels[j], col_is_station), item=name, value=val, unit=unit,
                       report_limit=r[std_c] if std_c is not None else "", raw=raw, src_note=vnote)
            if kind in E.GAS:
                rec.update(metric=metric, metric_cn=E.METRIC_CN.get(metric, metric), height="", o2=o2_row)
            recs.append(rec)
    if kind in E.GAS:
        for x in recs:
            h = hmap.get(x["station"]) or table_h
            x["height"] = f"{h:g}" if h else ""
            if not x["o2"]:
                o2 = o2map.get((x["station"], x["date"]))
                x["o2"] = f"{o2:g}" if o2 is not None else ""
    return recs, warns


SKIP_ROW_RE = re.compile(r"最大值|最小值|均值|平均|范围|标准|限值|达标|评价|结论|备注|^注")


def parse_cols(grid, kind):
    """项目为列的解析（如"采样日期｜采样点位｜样品编号｜臭气浓度（无量纲）｜氨（mg/m3）｜硫化氢（mg/m3）"），
    每行为一个样品；"最大值""均值"等统计行不读取，"标准限值"行作为报告所列限值"""
    g = [[clean_text(c) for c in row] for row in grid if any(clean_text(c) for c in row)]
    if not g:
        return [], []
    ncol = max(len(r) for r in g)
    g = [r + [""] * (ncol - len(r)) for r in g]
    match = E.matcher(kind)
    hi = next((i for i, r in enumerate(g[:6]) if sum(1 for c in r if c and match(_clean_name(c)[0])[0]) >= 1
               and not any(_num_cell(c) for c in r)), None)
    if hi is None:
        return [], []
    head = g[hi]
    icols = [j for j, c in enumerate(head) if c and match(_clean_name(c)[0])[0]]
    sc = next((j for j in _find_all(head, ST_KEYS) if j not in icols), None)
    dc = next((j for j, c in enumerate(head) if j not in icols and re.search(r"日期|采样时间", c)), None)
    nc = next((j for j, c in enumerate(head) if j not in icols + [sc, dc] and re.search(r"样品|编号|频次|次数", c)), None)
    if sc is None:
        return [], []
    limits, recs = {}, []
    carry = {}
    for r in g[hi + 1:]:
        lab = " ".join(r[j] for j in (sc, nc) if j is not None)
        if re.match(r"^(备注|注|说明)", r[0]):
            continue
        if re.search(r"标准|限值", lab):
            limits = {j: r[j].lstrip("≤<＜ ") for j in icols}
            continue
        if SKIP_ROW_RE.search(lab):
            continue
        r = list(r)
        for j in (sc, dc):                    # 合并单元格（PDF 中只在首行有值）沿用上一行
            if j is not None:
                r[j] = r[j] or carry.get(j, "")
                carry[j] = r[j]
        if not r[sc] or not any(_num_cell(r[j]) or re.search(r"ND|未检出|[<＜]", r[j], re.I)
                                                          for j in icols):
            continue
        date = " ".join(x for x in (r[dc] if dc is not None else "", r[nc] if nc is not None else "") if x)
        for j in icols:
            raw = r[j]
            if not raw or raw in ("/", "-", "—", "--"):
                continue
            name, unit = _clean_name(head[j])
            val, vnote = normalize_value(raw)
            rec = dict(station=r[sc], date=date, item=match(name)[0] and name, value=val, unit=unit, report_limit="",
                       raw=raw, src_note=vnote, _col=j)
            if kind in E.GAS:
                metric = E.metric_of(head[j], unit)
                rec.update(metric=metric, metric_cn=E.METRIC_CN.get(metric, metric), height="", o2="")
            recs.append(rec)
    for x in recs:
        x["report_limit"] = limits.get(x.pop("_col"), "")
    return recs, []


def _sample(cur, label, col_is_station):
    parts = [cur.get("date", "")]
    if cur.get("freq"):
        parts.append(cur["freq"])
    if not col_is_station and label:
        parts.append(label)
    return " ".join(p for p in dict.fromkeys(parts) if p)


def read_emission(path, kind):
    p = path.lower()
    notes = []
    if p.endswith((".xlsx", ".xlsm")):
        grids = grids_from_excel(path)
    elif p.endswith(".docx"):
        grids = grids_from_word(path)
    elif p.endswith(".pdf"):
        grids = grids_from_pdf(path, notes)
    else:
        return [], [f"暂不支持的文件类型：{path}（.doc 请另存为 .docx，图片请提供原始电子版）"]
    want = {E.BNOISE: "noise", E.BOILER: "stack", E.ODOR_STACK: "stack", E.ODOR_FENCE: "fugitive"}.get(kind, kind)
    # 厂界噪声页不读取只引用 GB 3096（声环境质量）的表格
    records, warnings = [], list(notes)
    for k, g in enumerate(grids, 1):
        tk = table_kind(g)
        if tk != want:
            continue
        stds = "；".join(table_standards(g))
        if kind == E.BNOISE and "3096" in stds and "12348" not in stds:
            continue
        r, w = _parse_noise(g) if kind == E.BNOISE else parse_rows(g, kind)
        if not r and kind != E.BNOISE:
            r, w = parse_cols(g, kind)
        for x in r:
            x["table_std"] = stds
            x["table_no"] = k
        records += r
        if r:
            warnings += list(dict.fromkeys(w))
    # 一个标准一个页签：恶臭项目（GB 14554-93）与 GB 16297-1996 项目分页判定
    if kind in E.ODOR and records:
        keep = [x for x in records if E.match_odor(x["item"])[0]]
        if not keep:
            warnings.append("文件的废气监测表中没有 GB 14554-93 所列项目（氨、硫化氢、臭气浓度等），"
                            "其余项目请在“GB 16297-1996”页判定")
        elif len(keep) < len(records):
            other = list(dict.fromkeys(x["item"] for x in records if not E.match_odor(x["item"])[0]))
            warnings.append("本页只读取 GB 14554-93 所列项目，已跳过：" + "、".join(other))
        records = keep
    elif kind in (E.STACK, E.FUGITIVE) and records:
        od = list(dict.fromkeys(x["item"] for x in records if E.odor_only(x["item"])))
        if od:
            warnings.append("以下项目为恶臭污染物，请在“GB 14554-93”页判定，本页已跳过：" + "、".join(od))
            records = [x for x in records if not E.odor_only(x["item"])]
    if kind in (E.STACK, E.BOILER) and records:        # 锅炉废气与一般工艺废气分页判定：锅炉废气（GB 13271）与一般工艺废气（GB 16297）分页判定
        std = "13271" if kind == E.BOILER else "16297"
        keep = [x for x in records if E.stack_std(x) == std]
        other = sorted({x["station"] for x in records if E.stack_std(x) != std})
        if keep:
            if other:
                warnings.append(("以下排气筒为一般工艺废气，请在“GB 16297-1996”页判定，本页已跳过：" if kind == E.BOILER
                                 else "以下排气筒为锅炉废气，请在“GB 13271-2014”页判定，本页已跳过：") + "、".join(other))
            records = keep
        elif kind == E.BOILER:
            warnings.append("未识别到锅炉标记（点位名称含“锅炉”或表内引用 GB 13271），已读取全部有组织废气数据，"
                            "请在核对表中删除非锅炉数据")
        else:
            records = []
            warnings.append("文件中的有组织废气均为锅炉废气，请在“GB 13271-2014”页判定")
    if not records:
        warnings.append(f"未在文件中识别到{KIND_CN[kind]}监测数据表；可按“通用导入模板”整理成长表后导入")
    return records, warnings
