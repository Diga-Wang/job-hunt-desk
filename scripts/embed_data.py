#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把数据 JSON 内嵌进单文件 HTML，使 file:// 双击打开也能直接看到数据，
不再依赖 fetch 或手动选择文件。每次刷新数据后重跑本脚本即可同步。

用法
----
  python embed_data.py --html 信息台.html --data data.json --var EMBEDDED_JOBS
  python embed_data.py --html 信息台.html --data data.json --var EMBEDDED_DATA --marker embeddedData
  python embed_data.py --html 信息台.html --data data.json --check   # 只报告，不写文件

原理
----
在 HTML 里生成/替换一块：
  <script id="embeddedJobs">window.EMBEDDED_JOBS = {...};</script>
插入位置为主 <script> 之前，保证 window.<VAR> 在页面脚本执行前就绪。

HTML 侧配套（autoLoad 先读内嵌、后 fetch）：
  if (window.EMBEDDED_JOBS && window.EMBEDDED_JOBS.jobs.length){ ...renderAll(); }
  tryFetch('./data.json?t='+Date.now())   // http 下再拉最新，file:// 下失败无妨
"""
import argparse
import json


def main():
    ap = argparse.ArgumentParser(description="把数据 JSON 内嵌进单文件 HTML")
    ap.add_argument("--html", required=True, help="目标 HTML 文件路径")
    ap.add_argument("--data", required=True, help="数据 JSON 文件路径")
    ap.add_argument("--var", default="EMBEDDED_DATA", help="挂到 window 上的变量名")
    ap.add_argument("--marker", default="embeddedData",
                    help="内嵌 script 标签的 id，默认 embeddedData（一个 HTML 只需一块）")
    ap.add_argument("--check", action="store_true", help="只报告条数，不写文件")
    args = ap.parse_args()

    marker_id = args.marker
    marker = '<script id="%s">' % marker_id

    raw = open(args.data, encoding="utf-8").read()
    obj = json.loads(raw)
    count = None
    if isinstance(obj, dict):
        for k in ("jobs", "items", "列表", "records", "rows"):
            if isinstance(obj.get(k), list):
                count = len(obj[k])
                break
        if count is None:
            count = sum(1 for v in obj.values() if isinstance(v, list)) and "多个数组"
    elif isinstance(obj, list):
        count = len(obj)
    print("[embed] %s 含 %s 条" % (args.data, count))

    # 转义 < 防止数据里的 </script> 截断脚本块
    safe = raw.replace("<", "\\u003c")
    block = marker + "window.%s = %s;</script>" % (args.var, safe)

    html = open(args.html, encoding="utf-8").read()
    if marker in html:
        start = html.index(marker)
        end = html.index("</script>", start) + len("</script>")
        html = html[:start] + block + html[end:]
        print("[embed] 已更新已有内嵌块 #%s" % marker_id)
    else:
        anchor = "<script>\n"
        if anchor not in html:
            raise SystemExit("[embed] 找不到主 <script> 锚点，无法插入")
        idx = html.index(anchor)
        html = html[:idx] + block + "\n" + html[idx:]
        print("[embed] 已首次插入内嵌块 #%s" % marker_id)

    if args.check:
        print("[embed] --check：未写入文件")
        return

    open(args.html, "w", encoding="utf-8").write(html)
    print("[embed] 已写入 %s（内嵌 %s 条）" % (args.html, count))


if __name__ == "__main__":
    main()
