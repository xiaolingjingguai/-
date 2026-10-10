# -*- coding: utf-8 -*-
"""
官方渠道标准检索与下载（仅用 Python 标准库）

渠道（只用官方网站，不用第三方下载站）：
1. 生态环境部标准库 https://www.mee.gov.cn/ywgz/fgbz/bz/bzwb/
   环保类 GB、HJ 全文 PDF 可直接下载。本模块首次使用时抓取标准库各栏目列表页，在本机建立目录索引
   （栏目页 index.shtml、index_1.shtml …；条目链接形如 …/202606/t20260629_1160476.shtml；
   详情页内附 PDF，形如 …/W020260630329276425685.pdf），之后检索在本机完成，可随时"更新目录"。
2. 国家标准全文公开系统 https://openstd.samr.gov.cn/
   非环保类国家标准（GB、GB/T）。全文下载需在网页上输入验证码，本软件只列出标准信息并打开官网详情页，
   由用户在浏览器中下载。该系统不收录环境保护、工程建设、食品安全类标准。
3. 地方标准（如 DB35）、行业标准：本软件不检索，界面提供官方平台首页链接。
"""
import html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

MEE_ROOT = os.environ.get("ENVTOOL_MEE_ROOT", "https://www.mee.gov.cn/ywgz/fgbz/bz/bzwb/")   # 环境变量仅供测试
OPENSTD_LIST = "https://openstd.samr.gov.cn/bzgk/gb/std_list"
OPENSTD_INFO = "https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno="
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36")
MAX_PAGES = 80                      # 单个栏目最多翻页数（防止异常循环）


class DownloadError(Exception):
    pass


def _get(url, timeout=30, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
            if binary:
                return data
            ctype = r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise DownloadError(f"{url}：HTTP {e.code}") from None
    except urllib.error.URLError as e:
        raise DownloadError(f"无法连接 {urllib.parse.urlparse(url).netloc}（{e.reason}），请检查网络") from None
    except TimeoutError:
        raise DownloadError(f"连接 {urllib.parse.urlparse(url).netloc} 超时") from None
    m = re.search(r"charset=([\w-]+)", ctype)
    enc = m.group(1) if m else "utf-8"
    try:
        return data.decode(enc, "replace")
    except LookupError:
        return data.decode("utf-8", "replace")


def _text(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s))).strip()


_A_RE = re.compile(r'<a\b[^>]*?href\s*=\s*["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.S | re.I)
CODE_RE = re.compile(r"((?:GB|HJ|GWKB|GWPB)\s*/?\s*T?\s*[\d.]+\s*[-—－–]\s*\d{2,4})", re.I)


# ==================================================================== 生态环境部标准库
def _mee_sections(progress=None):
    """标准库首页 → 一级栏目 → 二级栏目列表页地址"""
    root = _get(MEE_ROOT)
    if root is None:
        raise DownloadError("生态环境部标准库首页无法访问")
    cats, names = [], {}
    for href, t in _A_RE.findall(root):
        u = urllib.parse.urljoin(MEE_ROOT, href)
        if re.match(re.escape(MEE_ROOT) + r"\w+/$", u) and u not in cats:
            cats.append(u)
            names[u] = _text(t)
    secs = []
    for c in cats:
        if progress:
            progress(f"读取栏目 {c[len(MEE_ROOT):]}")
        page = _get(c)
        subs = []
        if page:
            for href, t in _A_RE.findall(page):
                u = urllib.parse.urljoin(c, href)
                if re.match(re.escape(c) + r"\w+/$", u) and u not in subs:
                    subs.append(u)
                    names[u] = f"{names.get(c, '')}/{_text(t)}"
        secs += subs or [c]
    return [(u, names.get(u) or u[len(MEE_ROOT):].strip("/")) for u in dict.fromkeys(secs)]


def _mee_entries(page_html, base):
    out = []
    for href, inner in _A_RE.findall(page_html):
        u = urllib.parse.urljoin(base, href)
        if not re.search(r"/\d{6}/t\d{8}_\d+\.s?html?$", u) or "/bzwb/" not in u:
            continue
        t = _text(inner)
        if len(t) < 4:
            continue
        out.append((u, t))
    return out


def build_mee_index(progress=None):
    """抓取标准库全部栏目，返回 [dict(title, code, url, section)]"""
    idx, seen = [], set()
    secs = _mee_sections(progress)
    for k, (sec, name) in enumerate(secs, 1):
        for p in range(MAX_PAGES):
            url = sec + ("index.shtml" if p == 0 else f"index_{p}.shtml")
            if progress:
                progress(f"读取目录 {k}/{len(secs)}：{name} 第{p + 1}页（已收录 {len(idx)} 项）")
            page = _get(url)
            if page is None:
                break
            new = 0
            for u, t in _mee_entries(page, url):
                if u in seen:
                    continue
                seen.add(u)
                new += 1
                m = CODE_RE.search(t)
                idx.append(dict(title=t, code=_norm_code(m.group(1)) if m else "", url=u, section=name))
            if new == 0:
                break
    if not idx:
        raise DownloadError("未从生态环境部标准库读取到任何条目，网站结构可能已调整")
    return idx


def _norm_code(c):
    c = re.sub(r"\s+", "", c).replace("—", "-").replace("－", "-").replace("–", "-")
    c = re.sub(r"^(GB|HJ)(/?T)?", lambda m: m.group(1) + ("/T" if m.group(2) else "") + " ", c, flags=re.I)
    return c.upper()


def _norm_q(s):
    s = s.replace("—", "-").replace("－", "-").replace("–", "-").replace("（", "(").replace("）", ")")
    return re.sub(r"\s+", "", s).lower()


def search_index(idx, query, limit=200):
    """多个关键词（空格分隔）同时出现即命中；标准号按忽略空格比较"""
    words = [_norm_q(w) for w in re.split(r"[\s,，;；]+", query.strip()) if w.strip()]
    if not words:
        return []
    # "GB 3095" 这类被空格拆开的标准号重新拼接
    joined = _norm_q(query)
    hits = []
    for it in idx:
        hay = _norm_q(it["title"] + " " + it["code"])
        if all(w in hay for w in words) or (len(joined) >= 4 and joined in hay):
            hits.append(it)
    return hits[:limit]


def mee_pdfs(detail_url):
    """详情页中的 PDF 附件 [(链接文字, 地址)]"""
    page = _get(detail_url)
    if page is None:
        raise DownloadError("详情页已不存在（404），该标准可能已下架")
    out = []
    for href, inner in _A_RE.findall(page):
        if re.search(r"\.pdf(\?|$)", href, re.I):
            u = urllib.parse.urljoin(detail_url, href)
            if u not in [x[1] for x in out]:
                out.append((_text(inner) or os.path.basename(u), u))
    return out


# ==================================================================== 国家标准全文公开系统
def search_openstd(query, limit=30):
    """返回 [dict(code, title, status, pub, impl, url)]；页面结构变化时返回空列表"""
    q = urllib.parse.urlencode({"r": "0.1", "page": 1, "pageSize": limit, "p.p1": 0, "p.p2": query,
                                "p.p90": "circulation_date", "p.p91": "desc"})
    page = _get(f"{OPENSTD_LIST}?{q}")
    if not page:
        return []
    out = []
    for row in re.findall(r"<tr\b.*?</tr>", page, re.S | re.I):
        m = re.search(r"([0-9A-F]{32})", row)
        if not m:
            continue
        cells = [_text(c) for c in re.findall(r"<td\b[^>]*>(.*?)</td>", row, re.S | re.I)]
        code = next((c for c in cells if CODE_RE.match(c) or re.match(r"^GB(/T)?\s*\d", c)), "")
        status = next((c for c in cells if c in ("现行", "即将实施", "废止", "被代替")), "")
        dates = [c for c in cells if re.match(r"^\d{4}-\d{2}-\d{2}$", c)]
        names = [c for c in cells if re.search(r"[一-鿿]{3,}", c) and c not in (status,)
                 and not re.match(r"^(强制性|推荐性|指导性)", c)]
        out.append(dict(code=code, title=max(names, key=len) if names else "", status=status,
                        pub=dates[0] if dates else "", impl=dates[1] if len(dates) > 1 else "",
                        url=OPENSTD_INFO + m.group(1)))
    return out


# ==================================================================== 文件名
def safe_name(title, invalid=None):
    """按用户命名规则："文件名称 标准号-年份.pdf"；已废止加"（无效）"前缀；GB/T 写作 GB_T"""
    t = re.sub(r"\s+", " ", title).strip()
    m = CODE_RE.search(t)
    if m:
        name = t[:m.start()].strip(" （(")
        t = f"{name} {_norm_code(m.group(1))}" if name else _norm_code(m.group(1))
    if invalid is None:
        invalid = "废止" in title
    t = t.replace("/", "_").replace("—", "-")
    t = re.sub(r'[\\:*?"<>|]', "", t)
    return ("（无效）" if invalid else "") + t[:150] + ".pdf"


def download(url, path, progress=None):
    data = _get(url, timeout=120, binary=True)
    if data is None:
        raise DownloadError("文件不存在（404）")
    if not data.startswith(b"%PDF"):
        raise DownloadError("下载内容不是 PDF（可能需要在网页上验证），请改用\"打开网页\"")
    with open(path, "wb") as f:
        f.write(data)
    return len(data)


# ==================================================================== 本机缓存
def cache_path():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "EnvQualityWorkbench")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "mee_standard_index.json")


def load_cache():
    try:
        with open(cache_path(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def save_cache(idx, when):
    with open(cache_path(), "w", encoding="utf-8") as f:
        json.dump(dict(updated=when, items=idx), f, ensure_ascii=False)
