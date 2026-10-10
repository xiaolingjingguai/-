# -*- coding: utf-8 -*-
"""
环评云助手（eiacloud）MCP 服务客户端（仅用 Python 标准库）

协议：MCP streamable HTTP。POST 端点，JSON-RPC 2.0：initialize → notifications/initialized → tools/list / tools/call。
服务端可能以 application/json 或 text/event-stream（data: 行）返回，两种均可解析；
若响应头带 Mcp-Session-Id，后续请求原样带回。
鉴权：Authorization: Bearer <令牌>。令牌为用户本人的环评云助手凭证，由界面"设置令牌"保存在本机，
或用环境变量 HPYZS_MCP_TOKEN 提供；本程序不内置任何令牌。

返回数据（据环评云助手技能说明）：
  law-keyword：namecn 标题、documentNum 文号、departmenttext 发布部门、pubDate、implDate、isFail（0 现行有效 / 1 已失效）、url
  law-semantic / qa / emission：fileName、fileNumber、text、pubDate、area、hpyDetailUrl
各工具参数名以服务端 tools/list 返回的 inputSchema 为准，本模块按 schema 自动填写。
"""
import json
import os
import re
import urllib.error
import urllib.request

BASE = os.environ.get("HPYZS_MCP_BASE", "https://mcp.eiacloud.com/")
SERVERS = ("law-keyword", "law-semantic", "qa", "emission")

# 界面可选的检索方式：(显示名, server, tool)
SEARCH_TOOLS = [
    ("标准导则 · 关键词（标准号/名称）", "law-keyword", "search_keyword_standard"),
    ("政策法规 · 关键词（名称/文号）", "law-keyword", "search_keyword_policy"),
    ("全国标准 · 语义检索", "law-semantic", "search_nationwide_semantic_standard"),
    ("全国法规 · 语义检索", "law-semantic", "search_nationwide_semantic_policy"),
    ("地方标准与政策 · 语义检索", "law-semantic", "search_semantic_province_sta_pol"),
    ("实务问答 · 语义检索", "qa", "search_semantic_qa"),
    ("实务问答 · 关键词", "qa", "search_keyword_qa"),
    ("生态环境标准与政策 · 关键词（综合）", "law-keyword", "eco_env_std_pol_kw_search"),
    ("国家大气污染物排放限值", "emission", "air_poll_national_emi_std_retrieval"),
    ("地方大气污染物排放限值", "emission", "air_poll_local_emi_std_retrieval"),
    ("国家水污染物排放限值", "emission", "water_poll_national_dis_std_retrieval"),
    ("地方水污染物排放限值", "emission", "water_poll_local_dis_std_retrieval"),
]
# 工具名以服务端 tools/list 为准（2026-10-06 用户"连接测试"实测）；旧名仅作兼容
_ALIAS = {"query_emission_gas_country": "air_poll_national_emi_std_retrieval",
          "query_emission_gas_place": "air_poll_local_emi_std_retrieval",
          "query_emission_water_country": "water_poll_national_dis_std_retrieval",
          "query_emission_water_place": "water_poll_local_dis_std_retrieval"}


def clean_token(t):
    """去掉用户连同复制的"Bearer "前缀、引号和空白"""
    t = (t or "").strip().strip("\"'“”‘’").strip()
    t = re.sub(r"^(authorization\s*:\s*)?bearer\s+", "", t, flags=re.I)
    return t.strip()

_TEXT_KEYS = ("query", "keyword", "keywords", "name", "title", "question", "content", "text", "q", "search")
_AREA_KEYS = ("province", "area", "region", "place", "city")


class HpyzsError(Exception):
    pass


class Client:
    def __init__(self, token, timeout=30):
        if not token:
            raise HpyzsError("未设置环评云助手令牌")
        self.token, self.timeout = clean_token(token), timeout
        self._sid, self._tools, self._id = {}, {}, 0

    # ---------------------------------------------------------------- 底层
    def _post(self, server, payload):
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
                   "Authorization": f"Bearer {self.token}"}
        if self._sid.get(server):
            headers["Mcp-Session-Id"] = self._sid[server]
        req = urllib.request.Request(BASE + server, json.dumps(payload).encode("utf-8"), headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                sid = resp.headers.get("Mcp-Session-Id")
                if sid:
                    self._sid[server] = sid
                body = resp.read().decode("utf-8", "replace")
                ctype = resp.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            msg = {401: "令牌无效或已过期（401）", 403: "无访问权限（403）", 404: "服务地址不存在（404）"}.get(e.code, f"HTTP {e.code}")
            raise HpyzsError(f"{server}：{msg}") from None
        except urllib.error.URLError as e:
            raise HpyzsError(f"{server}：无法连接（{e.reason}），请检查网络或代理") from None
        except TimeoutError:
            raise HpyzsError(f"{server}：连接超时") from None
        if "id" not in payload or not body.strip():
            return None
        return self._parse(body, ctype, payload["id"])

    @staticmethod
    def _parse(body, ctype, rid):
        msgs = []
        if "event-stream" in ctype or body.lstrip().startswith(("event:", "data:")):
            for block in re.split(r"\r?\n\r?\n", body):
                data = "\n".join(l[5:].lstrip() for l in block.splitlines() if l.startswith("data:"))
                if data:
                    try:
                        msgs.append(json.loads(data))
                    except ValueError:
                        pass
        else:
            m = json.loads(body)
            msgs = m if isinstance(m, list) else [m]
        for m in msgs:
            if m.get("id") == rid:
                if "error" in m:
                    raise HpyzsError(f"服务端错误：{m['error'].get('message', m['error'])}")
                return m.get("result")
        raise HpyzsError("服务端未返回结果")

    def _rpc(self, server, method, params=None):
        self._id += 1
        return self._post(server, {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or {}})

    def _ensure(self, server):
        if server in self._tools:
            return
        self._rpc(server, "initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                                         "clientInfo": {"name": "env-quality-workbench", "version": "1.0"}})
        self._post(server, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        res = self._rpc(server, "tools/list") or {}
        self._tools[server] = {t["name"]: t for t in res.get("tools", [])}

    # ---------------------------------------------------------------- 对外
    def tools(self, server):
        self._ensure(server)
        return self._tools[server]

    def build_args(self, server, tool, text, area="", only_valid=False, extra=None):
        """按 inputSchema 自动填写参数：文本参数、地区参数、仅现行有效"""
        tools = self.tools(server)
        tool = tool if tool in tools else _ALIAS.get(tool, tool)
        t = tools.get(tool)
        if t is None:
            raise HpyzsError(f"{server} 未提供工具 {tool}")
        sch = t.get("inputSchema") or {}
        props, req = sch.get("properties") or {}, sch.get("required") or []
        args = {}
        tk = next((k for k in _TEXT_KEYS if k in props), None)
        if tk is None:
            tk = next((k for k in req if (props.get(k) or {}).get("type", "string") == "string"
                       and k not in _AREA_KEYS), None)
        if tk is None:
            tk = next((k for k, v in props.items() if v.get("type", "string") == "string" and k not in _AREA_KEYS), "query")
        args[tk] = text
        ak = next((k for k in _AREA_KEYS if k in props), None)
        if ak and area:
            args[ak] = area
        if only_valid and "is_fail" in props:
            args["is_fail"] = 1
        if "sort" in props and server == "law-keyword":
            args["sort"] = 2                     # 发布时间降序，最新版本在前
        for k, v in (extra or {}).items():
            if k in props:
                args[k] = v
        missing = [k for k in req if k not in args]
        if missing:
            raise HpyzsError(f"{tool} 还需要参数：{'、'.join(missing)}（参数说明：{json.dumps(props, ensure_ascii=False)[:300]}）")
        return args

    def call(self, server, tool, args):
        res = self._rpc(server, "tools/call", {"name": tool, "arguments": args}) or {}
        if res.get("isError"):
            raise HpyzsError("工具调用失败：" + " ".join(c.get("text", "") for c in res.get("content", [])))
        if isinstance(res.get("structuredContent"), dict):
            return _unwrap(res["structuredContent"])
        texts = [c.get("text", "") for c in res.get("content", []) if c.get("type") == "text"]
        out = []
        for tx in texts:
            try:
                out += _unwrap(json.loads(tx))
            except ValueError:
                out.append({"text": tx})
        return out

    def search(self, server, tool, text, area="", only_valid=False):
        args = self.build_args(server, tool, text, area, only_valid)
        return self.call(server, tool if tool in self.tools(server) else _ALIAS.get(tool, tool), args)

    def describe(self, server):
        """连接测试用：工具名及其参数（*为必填）"""
        out = []
        for name, t in self.tools(server).items():
            sch = t.get("inputSchema") or {}
            req = set(sch.get("required") or [])
            ps = [k + ("*" if k in req else "") for k in (sch.get("properties") or {})]
            out.append(f"{name}（{'，'.join(ps) or '无参数'}）")
        return out


def _unwrap(obj):
    """{code, msg, data} → data 列表"""
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        if "code" in obj and str(obj.get("code")) not in ("200", "0") and not obj.get("data"):
            raise HpyzsError(f"服务端返回：{obj.get('msg') or obj.get('code')}")
        d = obj.get("data", obj)
        if isinstance(d, dict):
            for k in ("list", "records", "rows", "items", "result"):
                if isinstance(d.get(k), list):
                    return d[k]
            return [d]
        return d if isinstance(d, list) else [obj]
    return [{"text": str(obj)}]


# -------------------------------------------------------------------- 结果字段归一
def field(item, *keys):
    for k in keys:
        v = item.get(k)
        if v not in (None, ""):
            return str(v)
    return ""


def norm_item(it):
    fail = it.get("isFail", it.get("is_fail"))
    status = {"0": "现行有效", "1": "已废止/失效"}.get(str(fail), "") if fail is not None else ""
    return dict(
        name=field(it, "namecn", "fileName", "name", "title"),
        num=field(it, "documentNum", "fileNumber", "standardNum", "code"),
        dept=field(it, "departmenttext", "department"),
        pub=field(it, "pubDate", "publishDate"),
        impl=field(it, "implDate", "implementDate"),
        status=status or field(it, "status", "state"),
        area=field(it, "area"),
        text=re.sub(r"\s+", " ", field(it, "text", "content", "answer", "summary"))[:4000],
        url=field(it, "url", "hpyDetailUrl", "detailUrl", "link"),
    )


# -------------------------------------------------------------------- 标准时效核查
_CODE_RE = re.compile(r"^(GB|HJ|DB\d{2}|GBJ|CJ|HG)\s*/?\s*(T)?\s*([\d.]+)\s*[-—－–]\s*(\d{4})$", re.I)


def split_code(code):
    """'GB/T 14848-2017' → ('GB/T', '14848', '2017')；无法识别返回 None"""
    m = _CODE_RE.match(re.sub(r"\s+", " ", code.strip()))
    if not m:
        return None
    pre = m.group(1).upper() + ("/T" if m.group(2) else "")
    return pre, m.group(3), m.group(4)


def canon(code):
    """规范写法：'GB3095-2012' → 'GB 3095-2012'；无法识别原样返回"""
    sp = split_code(code)
    return f"{sp[0]} {sp[1]}-{sp[2]}" if sp else code.strip()


def _codes_in(text):
    out = []
    for m in re.finditer(r"(GB|HJ|DB\d{2})\s*/?\s*(T)?\s*([\d.]+)\s*[-—－–]\s*(\d{4})", text or "", re.I):
        out.append((m.group(1).upper(), m.group(3), m.group(4)))
    return out


def check_standard(client, code):
    """
    返回 dict(code, name, conclusion, latest, impl, url, hits)。
    conclusion：现行有效 / 已废止 / 有新版本 / 未检索到（信息不足）
    """
    sp = split_code(code)
    if not sp:
        return dict(code=code, name="", conclusion="标准号格式无法识别", latest="", impl="", url="", hits=[])
    pre, num, year = sp
    items = [norm_item(x) for x in client.search("law-keyword", "search_keyword_standard", f"{pre.split('/')[0]} {num}")]
    same = []                      # 同一标准号（不同年份版本）
    for it in items:
        for p2, n2, y2 in _codes_in(it["num"] + " " + it["name"]):
            if n2 == num and p2[:2] == pre[:2]:
                same.append((y2, it))
                break
    out = dict(code=code, name="", conclusion="未检索到（信息不足）", latest="", impl="", url="", hits=items[:10])
    if not same:
        return out
    this = [it for y, it in same if y == year]
    newer = sorted(((y, it) for y, it in same if y > year), key=lambda x: x[0], reverse=True)
    if this:
        it = this[0]
        out.update(name=it["name"], url=it["url"], impl=it["impl"])
        out["conclusion"] = it["status"] or "已检索到，状态字段缺失（信息不足）"
    if newer:
        y, it = newer[0]
        out["latest"] = f"{it['num'] or (pre + ' ' + num + '-' + y)}（{it['status'] or '状态未注明'}，实施 {it['impl'] or '—'}）"
        if not this or "现行" not in out["conclusion"]:
            out["conclusion"] = "有新版本" if not this else out["conclusion"] + "；有新版本"
        else:
            out["conclusion"] += "；另有新版本，请核对"
    return out


# 本软件判定所依据的标准
BUILTIN_STANDARDS = [
    "GB 3838-2002", "GB/T 14848-2017", "HJ 610-2016", "GB 3095-2026", "GB 3096-2008", "GB 12348-2008",
    "HJ 2.2-2018", "GB 36600-2018", "GB 15618-2018", "GB 18668-2002", "GB 18421-2001",
]


def token_from_env():
    return os.environ.get("HPYZS_MCP_TOKEN", "")
