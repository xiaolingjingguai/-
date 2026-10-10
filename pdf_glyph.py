# -*- coding: utf-8 -*-
"""
PDF 乱码字形还原。

经"虚拟打印机"（PScript5 / Acrobat Distiller、部分 PDF 打印机）生成的 PDF，常把字体以 CID 方式嵌入
却不带 ToUnicode 映射表，pdfplumber 提取出来是"(cid:1234)"，看不到真实文字。
这类 PDF 的 CID 就是原字体中的字形编号（glyph id），嵌入字形的轮廓与本机同名字体完全一致，因此：
  1. 读取 PDF 内嵌字体中该字形的轮廓；
  2. 到本机字体目录（Windows\\Fonts）找同名字体（宋体、黑体、Times New Roman 等），比对轮廓；
  3. 轮廓一致即用本机字体的字符表（cmap）反查出真实文字。
轮廓比对不上的字符保留"(cid:N)"，由界面提示人工核对，不做猜测。

另外顺带识别上标：字号明显小于同行文字且位置抬高的数字/负号，转为 Unicode 上标（如 ×10⁻³），
供 parser.normalize_value 统一处理。
"""
import os
import re
import hashlib
import statistics

CID_RE = re.compile(r"^\(cid:(\d+)\)$")

# PDF 字体名（去掉子集前缀与编码后缀）→ Windows 字体文件，(文件名, ttc 序号)
KNOWN_FILES = {
    "simsun": [("simsun.ttc", 0), ("simsun.ttf", 0)],
    "nsimsun": [("simsun.ttc", 1)],
    "simhei": [("simhei.ttf", 0)],
    "kaiti": [("simkai.ttf", 0)], "kaiti_gb2312": [("simkai.ttf", 0)],
    "fangsong": [("simfang.ttf", 0)], "fangsong_gb2312": [("simfang.ttf", 0)],
    "microsoftyahei": [("msyh.ttc", 0), ("msyh.ttf", 0)],
    "microsoftyahei-bold": [("msyhbd.ttc", 0), ("msyhbd.ttf", 0)],
    "stxinwei": [("stxinwei.ttf", 0)], "stsong": [("stsong.ttf", 0)],
    "stkaiti": [("stkaiti.ttf", 0)], "stfangsong": [("stfangso.ttf", 0)],
    "stzhongsong": [("stzhongs.ttf", 0)],
    "timesnewromanpsmt": [("times.ttf", 0)], "timesnewroman": [("times.ttf", 0)],
    "timesnewromanps-boldmt": [("timesbd.ttf", 0)], "timesnewroman,bold": [("timesbd.ttf", 0)],
    "timesnewromanps-italicmt": [("timesi.ttf", 0)],
    "timesnewromanps-bolditalicmt": [("timesbi.ttf", 0)],
    "arialmt": [("arial.ttf", 0)], "arial": [("arial.ttf", 0)],
    "arial-boldmt": [("arialbd.ttf", 0)],
    "calibri": [("calibri.ttf", 0)], "cambriamath": [("cambria.ttc", 1)],
    "symbolmt": [("symbol.ttf", 0)],
}


def font_dirs(extra=None):
    ds = list(extra or [])
    env = os.environ.get("ENVTOOL_FONT_DIRS")
    if env:
        ds += env.split(os.pathsep)
    win = os.environ.get("WINDIR") or os.environ.get("SystemRoot")
    if win:
        ds.append(os.path.join(win, "Fonts"))
    la = os.environ.get("LOCALAPPDATA")
    if la:
        ds.append(os.path.join(la, "Microsoft", "Windows", "Fonts"))
    ds += ["/usr/share/fonts", "/usr/local/share/fonts", os.path.expanduser("~/.fonts")]
    return [d for d in ds if os.path.isdir(d)]


def clean_name(base):
    n = base.split("+", 1)[-1]
    n = re.sub(r"-(GBK|GB|UniGB|Identity|UCS2)-.*$", "", n, flags=re.I)
    return n.replace(" ", "").lower()


# ---------------------------------------------------------------- 轮廓指纹
def _raw(glyf, name):
    g = glyf.glyphs.get(name) if hasattr(glyf, "glyphs") else None
    if g is None:
        return b""
    data = getattr(g, "data", None)
    if data is None:                       # 已展开的字形，重新编码
        try:
            data = g.compile(glyf)
        except Exception:
            return b""
    return data or b""


def _glyph_hash(glyf, order, gid):
    """字形指纹：取 glyf 原始数据，去掉提示指令（instructions）后取 MD5；空字形返回 None"""
    if gid >= len(order):
        return None
    d = _raw(glyf, order[gid])
    if len(d) < 10:
        return None
    n = int.from_bytes(d[0:2], "big", signed=True)
    if n > 0:                              # 简单字形：跳过 bbox 与指令段
        p = 10 + 2 * n
        if p + 2 > len(d):
            return None
        il = int.from_bytes(d[p:p + 2], "big")
        body = d[10:p] + d[p + 2 + il:]
    else:                                  # 复合字形：整体比对
        body = d[10:]
    return hashlib.md5(body.rstrip(b"\0")).hexdigest()


def _outline(glyf, order, gid):
    """解码后的轮廓（坐标、轮廓终点、在线标志），用于原始数据不一致时的二次比对"""
    if gid >= len(order):
        return None
    try:
        g = glyf[order[gid]]
        if g.numberOfContours <= 0:
            return None
        return (tuple(g.coordinates), tuple(g.endPtsOfContours), tuple(f & 1 for f in g.flags))
    except Exception:
        return None


class SysFont:
    """本机字体：按需计算字形指纹，必要时建立全表索引"""

    def __init__(self, path, index):
        from fontTools.ttLib import TTFont
        self.f = TTFont(path, fontNumber=index, lazy=True)
        self.glyf = self.f["glyf"]
        self.order = self.f.getGlyphOrder()
        rev = {}
        for code, name in self.f.getBestCmap().items():
            cur = rev.get(name)
            if cur is None or _prefer(code, cur):
                rev[name] = code
        self.uni = rev                      # 字形名 → 码位
        self._index = None

    def char(self, gid):
        if gid < len(self.order):
            c = self.uni.get(self.order[gid])
            return chr(c) if c is not None else None
        return None

    def hash(self, gid):
        try:
            return _glyph_hash(self.glyf, self.order, gid)
        except Exception:
            return None

    def match(self, eglyf, eorder, gid):
        """返回内嵌字形 gid 对应的文字；比不上返回 None"""
        h = _glyph_hash(eglyf, eorder, gid)
        if h is None:
            return " " if (self.hash(gid) is None and self.char(gid) == " ") else None
        if self.hash(gid) == h:                             # 同号字形原始数据一致（最常见）
            return self.char(gid)
        o = _outline(eglyf, eorder, gid)
        if o is not None and o == _outline(self.glyf, self.order, gid):
            return self.char(gid)                           # 同号字形轮廓一致
        g2 = self.lookup(h)                                 # 字形编号不同，按指纹全表查找
        return self.char(g2) if g2 is not None else None

    def lookup(self, h):
        if self._index is None:
            self._index = {}
            for gid, name in enumerate(self.order):
                if name in self.uni:
                    hh = self.hash(gid)
                    if hh and hh not in self._index:
                        self._index[hh] = gid
        return self._index.get(h)


def _prefer(a, b):
    """同一字形对应多个码位时的取舍：避开私用区与兼容区，取较小码位"""
    bad = lambda c: 0xE000 <= c <= 0xF8FF or 0xF900 <= c <= 0xFAFF or c >= 0x10000
    return (bad(a), a) < (bad(b), b)


_SYS_CACHE = {}


def find_sys_font(name, dirs):
    key = (name, tuple(dirs))
    if key in _SYS_CACHE:
        return _SYS_CACHE[key]
    found = None
    cands = KNOWN_FILES.get(name, [])
    files = {}
    for d in dirs:
        for root, _, fs in os.walk(d):
            for f in fs:
                files.setdefault(f.lower(), os.path.join(root, f))
    for fn, idx in cands:
        if fn in files:
            found = (files[fn], idx)
            break
    if not found:                                    # 按字体内部名称兜底查找
        from fontTools.ttLib import TTFont, TTCollection
        for fl, path in files.items():
            if not fl.endswith((".ttf", ".ttc", ".otf")):
                continue
            try:
                fonts = TTCollection(path, lazy=True).fonts if fl.endswith(".ttc") else [TTFont(path, lazy=True)]
            except Exception:
                continue
            for i, ft in enumerate(fonts):
                try:
                    names = {str(r).replace(" ", "").lower() for r in ft["name"].names if r.nameID in (1, 4, 6)}
                except Exception:
                    continue
                if name in names:
                    found = (path, i)
                    break
            if found:
                break
    sf = None
    if found:
        try:
            sf = SysFont(*found)
        except Exception:
            sf = None
    _SYS_CACHE[key] = sf
    return sf


# ---------------------------------------------------------------- PDF 字体
def _embedded_font(fontobj):
    """返回 (内嵌 TTFont 或 None, CIDToGID 映射函数)"""
    from pdfminer.pdftypes import resolve1
    from fontTools.ttLib import TTFont
    import io
    f = resolve1(fontobj)
    desc = f
    if "DescendantFonts" in f:
        desc = resolve1(resolve1(f["DescendantFonts"])[0])
    c2g = lambda cid: cid
    m = resolve1(desc.get("CIDToGIDMap")) if desc.get("CIDToGIDMap") is not None else None
    if m is not None and hasattr(m, "get_data"):
        data = m.get_data()
        c2g = lambda cid, d=data: (d[2 * cid] << 8 | d[2 * cid + 1]) if 2 * cid + 1 < len(d) else cid
    fd = resolve1(desc.get("FontDescriptor") or {})
    ff = resolve1(fd.get("FontFile2")) if fd else None
    emb = None
    if ff is not None:
        try:
            emb = TTFont(io.BytesIO(ff.get_data()), lazy=True)
        except Exception:
            emb = None
    return emb, c2g


class Decoder:
    """一份 PDF 的乱码还原器，按字体缓存 cid → 文字"""

    def __init__(self, font_dirs_extra=None):
        self.dirs = font_dirs(font_dirs_extra)
        self.fonts = {}          # 字体名 → dict(cid→text)
        self.missing = set()     # 找不到本机字体的字体名
        self.unknown = 0         # 未能还原的字符数

    def _font_map(self, page, fontname):
        if fontname in self.fonts:
            return self.fonts[fontname]
        from pdfminer.pdftypes import resolve1
        res = {}
        emb = c2g = None
        try:
            fdict = resolve1(page.page_obj.resources.get("Font", {}))
            for k, v in fdict.items():
                fo = resolve1(v)
                bf = fo.get("BaseFont")
                bf = getattr(bf, "name", bf)
                if isinstance(bf, bytes):
                    bf = bf.decode("latin-1")
                if str(bf).strip("/'") == fontname:
                    emb, c2g = _embedded_font(fo)
                    # 内嵌字体自带 cmap 时直接用
                    if emb is not None and "cmap" in emb:
                        for code, gname in (emb.getBestCmap() or {}).items():
                            if not (0xE000 <= code <= 0xF8FF or 0xF000 <= code <= 0xF0FF):
                                res.setdefault(("g", gname), chr(code))
                    break
        except Exception:
            pass
        self.fonts[fontname] = dict(emb=emb, c2g=c2g or (lambda c: c), sys=None, sys_tried=False, cache={}, cmap=res)
        return self.fonts[fontname]

    def char(self, page, fontname, cid):
        fm = self._font_map(page, fontname)
        if cid in fm["cache"]:
            return fm["cache"][cid]
        gid = fm["c2g"](cid)
        out = None
        emb = fm["emb"]
        if emb is not None and fm["cmap"]:
            order = emb.getGlyphOrder()
            if gid < len(order):
                out = fm["cmap"].get(("g", order[gid]))
        if out is None:
            if not fm["sys_tried"]:
                fm["sys_tried"] = True
                fm["sys"] = find_sys_font(clean_name(fontname), self.dirs)
                if fm["sys"] is None:
                    self.missing.add(clean_name(fontname))
            sf = fm["sys"]
            if sf is not None and emb is not None:
                try:
                    out = sf.match(emb["glyf"], emb.getGlyphOrder(), gid)
                except Exception:
                    out = None
        if out is None:
            self.unknown += 1
        fm["cache"][cid] = out
        return out


# ---------------------------------------------------------------- 页面处理
SUP = str.maketrans("0123456789-+−", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺⁻")


def fix_page(page, decoder):
    """就地修改 page.chars：还原 (cid:N) 乱码、标出上标。返回本页还原字符数。"""
    chars = page.chars
    n = 0
    for c in chars:
        m = CID_RE.match(c.get("text", ""))
        if m:
            t = decoder.char(page, c["fontname"], int(m.group(1)))
            if t is not None:
                c["text"] = t
                n += 1
    _mark_superscripts(chars)
    return n


def _mark_superscripts(chars):
    """字号≤邻近正文 0.8 倍、底边明显抬高的数字/正负号视为上标（如 1.0×10⁻³）"""
    bins = {}
    for c in chars:
        bins.setdefault((int(c["bottom"] // 10), int(c["x0"] // 20)), []).append(c)
    for c in chars:
        t = c.get("text", "")
        if len(t) != 1 or t not in "0123456789-+−":
            continue
        by, bx = int(c["bottom"] // 10), int(c["x0"] // 20)
        near = [o for dy in (-1, 0, 1) for dx in (-1, 0, 1) for o in bins.get((by + dy, bx + dx), ())
                if o is not c and abs(o["x0"] - c["x0"]) < 15
                and abs(o["bottom"] - c["bottom"]) < c["size"] * 1.2 and o["size"] > c["size"] * 1.25]
        if not near:
            continue
        big = statistics.median(o["size"] for o in near)
        base = statistics.median(o["bottom"] for o in near)
        if c["size"] > big * 0.8:
            continue
        if c["bottom"] < base - big * 0.2:
            c["text"] = t.translate(SUP)                 # 上标：1.0×10⁻³
        elif c["bottom"] >= base - big * 0.05:
            # 下标（如 BOD5）：位置压低会被当成下一行，挪回同一行，按普通字符处理
            ref = min(near, key=lambda o: abs(o["x0"] - c["x0"]))
            for k in ("top", "bottom", "doctop", "y0", "y1"):
                if k in ref:
                    c[k] = ref[k]
