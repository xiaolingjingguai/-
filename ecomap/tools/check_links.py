# -*- coding: utf-8 -*-
"""核实 ecomap_links.LINKS 中网址：输出 HTTP 状态、最终网址与网页标题。"""
import os
import re
import ssl
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ecomap_links as K  # noqa: E402

ctx = ssl.create_default_context()
out = []
for cat, data, site, org, url, use in K.LINKS:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0"})
        r = urllib.request.urlopen(req, timeout=30, context=ctx)
        raw = r.read(300000)
        enc = r.headers.get_content_charset() or "utf-8"
        txt = raw.decode(enc, errors="replace")
        if "�" in txt[:2000]:
            txt = raw.decode("gbk", errors="replace")
        m = re.search(r"<title[^>]*>(.*?)</title>", txt, re.S | re.I)
        t = re.sub(r"\s+", " ", m.group(1)).strip() if m else "（无标题）"
        out.append("OK %s | %s | %s | 标题：%s" % (r.status, url, r.geturl(), t[:80]))
    except Exception as e:
        out.append("FAIL | %s | %s" % (url, str(e)[:150]))
print("\n".join(out))
