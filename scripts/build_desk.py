#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
素材库 → 个人信息台（单文件 HTML）

这是本 skill 的主生成器：别人装了 skill，只要填好素材库，跑这一条命令就能得到
一个双击可开、离线可用、零外链、零后端的个人工作台。

用法
----
  # 1) 生成一份空白素材库（含说明与示例行）
  python build_desk.py --init ./我的素材库

  # 2) 素材库 → 工作台
  python build_desk.py --lib ./我的素材库 --out 我的信息台.html

  # 3) 只校验素材库，不生成
  python build_desk.py --lib ./我的素材库 --check

素材库结构
----------
  素材库/
    00-访谈记录.md      需求来源（可选，用于复盘，不参与生成）
    01-字段定义.csv     列定义：key,label,type,width,filter,sort,search
    02-数据.csv         数据行（UTF-8，表头 = 字段 key）
    03-视图配置.json    标题/副标题/主题/主键/状态流转/KPI

只用 03-视图配置.json 也能跑：把数据行直接写进它的 "rows" 字段即可。
01 与 02 存在时优先读它们（更适合 Excel 编辑）。

输出特性
--------
侧栏 KPI + 筛选 · 顶部搜索 + 状态流转 + 排序 · 表格/卡片响应式 ·
状态与备注存 localStorage（换数据不丢）· 导出 JSON/CSV 回环 · 数据内嵌（file:// 可用）
"""
import argparse
import csv
import json
import os
import shutil
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(os.path.dirname(HERE), "assets", "素材库模板")

THEMES = {
    "mckinsey": dict(sideBg="#051C2C", sideFg="#E8EEF4", sideSub="#8FA3B5",
                     accent="#034EA2", bg="#FFFFFF", fg="#16202A",
                     line="#E3E8ED", chip="#EEF2F6", radius="6px"),
    "warm": dict(sideBg="#EDE8F7", sideFg="#3A3355", sideSub="#7A7398",
                 accent="#FF7F6B", bg="#FBF8F3", fg="#2E2A32",
                 line="#E9E2D8", chip="#F4EFFA", radius="22px"),
    "ink": dict(sideBg="#1C1C1E", sideFg="#F2F2F7", sideSub="#8E8E93",
                accent="#0A84FF", bg="#FFFFFF", fg="#1C1C1E",
                line="#E5E5EA", chip="#F2F2F7", radius="10px"),
}

DEFAULT_STATUS = ["未开始", "进行中", "已完成", "已放弃"]

# ---------------------------------------------------------------- 素材库读取


def _read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_lib(lib):
    """读素材库，返回 (config, rows, warnings)"""
    warn = []
    if not os.path.isdir(lib):
        raise SystemExit("[build] 找不到素材库目录：%s" % lib)

    cfg_path = os.path.join(lib, "03-视图配置.json")
    if not os.path.exists(cfg_path):
        raise SystemExit("[build] 缺少 03-视图配置.json（跑 --init 生成模板）")
    cfg = json.load(open(cfg_path, encoding="utf-8"))

    cols_path = os.path.join(lib, "01-字段定义.csv")
    data_path = os.path.join(lib, "02-数据.csv")

    if os.path.exists(cols_path):
        cols = []
        for r in _read_csv(cols_path):
            key = (r.get("key") or "").strip()
            if not key:
                continue
            cols.append({
                "key": key,
                "label": (r.get("label") or key).strip(),
                "type": (r.get("type") or "text").strip(),
                "width": int(r.get("width") or 0) or None,
                "filter": str(r.get("filter", "true")).strip().lower() in ("true", "1", "yes", "y", "是"),
                "sort": str(r.get("sort", "true")).strip().lower() in ("true", "1", "yes", "y", "是"),
                "search": str(r.get("search", "true")).strip().lower() in ("true", "1", "yes", "y", "是"),
            })
        if cols:
            cfg["columns"] = cols

    rows = cfg.get("rows")
    if os.path.exists(data_path):
        rows = _read_csv(data_path)
        rows = [{k: (v if v is not None else "") for k, v in r.items() if k is not None} for r in rows]
    if rows is None:
        rows = []
        warn.append("素材库里没有数据行（02-数据.csv 为空，或配置里没有 rows）")

    cfg.setdefault("title", "我的信息台")
    cfg.setdefault("subtitle", "")
    cfg.setdefault("idFields", [])
    cfg.setdefault("columns", [])
    cfg.setdefault("kpis", [{"label": "总条目", "op": "count"}])
    if cfg.get("status") is None:
        cfg["status"] = {"enabled": True, "options": list(DEFAULT_STATUS), "default": DEFAULT_STATUS[0]}
    cfg["status"].setdefault("options", list(DEFAULT_STATUS))
    cfg["status"].setdefault("default", cfg["status"]["options"][0])
    cfg["status"].setdefault("enabled", True)

    if not cfg["columns"]:
        keys = []
        for r in rows[:50]:
            for k in r.keys():
                if k and k not in keys:
                    keys.append(k)
        cfg["columns"] = [{"key": k, "label": k, "type": "text",
                           "filter": True, "sort": True, "search": True} for k in keys]
        warn.append("未定义字段，已按数据列自动生成 %d 列" % len(keys))

    if not cfg["idFields"]:
        first = cfg["columns"][0]["key"]
        cfg["idFields"] = [first] if len(cfg["columns"]) == 1 else cfg["columns"][:2]
        cfg["idFields"] = [c["key"] if isinstance(c, dict) else c for c in cfg["idFields"]]
        warn.append("未指定主键，已自动取前两列：%s" % " + ".join(cfg["idFields"]))

    keys = [c["key"] for c in cfg["columns"]]
    ids = [f for f in cfg["idFields"] if f in keys]
    if not ids:
        ids = [keys[0]]
    cfg["idFields"] = ids

    return cfg, rows, warn


# ---------------------------------------------------------------- 渲染

def theme_vars(cfg):
    t = cfg.get("theme") or {}
    name = t.get("name", "mckinsey")
    v = dict(THEMES.get(name, THEMES["mckinsey"]))
    v.update(t.get("vars") or {})
    return "\n".join("    --%s: %s;" % (k, v) for k, v in v.items())


CSS = r"""
*{box-sizing:border-box;-webkit-text-size-adjust:100%}
html,body{margin:0;padding:0}
body{
  font:14px/1.55 -apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB",
       "Microsoft YaHei","Segoe UI",Roboto,sans-serif;
  background:var(--bg);color:var(--fg);
}
:root{
__THEME__
}
.app{display:flex;min-height:100vh}

/* ---------- 侧栏 ---------- */
.side{
  width:260px;flex:0 0 260px;background:var(--sideBg);color:var(--sideFg);
  padding:22px 18px;display:flex;flex-direction:column;gap:18px;
}
.brand .ttl{font-size:19px;font-weight:650;letter-spacing:.3px;line-height:1.3}
.brand .sub{font-size:12px;color:var(--sideSub);margin-top:5px;line-height:1.5}
.kpis{display:flex;flex-direction:column;gap:8px}
.kpi{background:rgba(255,255,255,.07);border-radius:var(--radius);padding:10px 12px}
.kpi .v{font-size:22px;font-weight:650;line-height:1.1}
.kpi .l{font-size:11px;color:var(--sideSub);margin-top:3px}
.flabel{font-size:11px;letter-spacing:.6px;color:var(--sideSub);
  text-transform:uppercase;margin-bottom:6px}
.side select{
  width:100%;padding:8px 10px;font-size:16px;border-radius:var(--radius);
  border:1px solid rgba(255,255,255,.16);background:rgba(255,255,255,.07);
  color:var(--sideFg);margin-bottom:10px;
}
.side select option{color:#111}
.sidefoot{margin-top:auto;font-size:11px;color:var(--sideSub);line-height:1.7}
.ghost{background:transparent;border:1px solid rgba(255,255,255,.2);
  color:var(--sideSub);border-radius:var(--radius);padding:6px 10px;
  font-size:11px;cursor:pointer;margin-top:8px;width:100%}
.ghost:hover{color:var(--sideFg);border-color:rgba(255,255,255,.4)}

/* ---------- 主区 ---------- */
.main{flex:1;min-width:0;display:flex;flex-direction:column}
.topbar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;
  padding:14px 20px;border-bottom:1px solid var(--line)}
input.search{
  flex:1 1 240px;min-width:180px;padding:9px 12px;font-size:16px;
  border:1px solid var(--line);border-radius:var(--radius);background:var(--bg);color:var(--fg);
  outline:none
}
input.search:focus{border-color:var(--accent)}
.chips{display:flex;gap:6px;flex-wrap:wrap}
.chip{padding:5px 11px;border-radius:999px;border:1px solid var(--line);
  background:var(--chip);font-size:12px;cursor:pointer;user-select:none;color:var(--fg)}
.chip.on{background:var(--accent);border-color:var(--accent);color:#fff}
.spacer{flex:1}
.btn,button.act{
  padding:7px 12px;font-size:12px;border-radius:var(--radius);
  border:1px solid var(--line);background:var(--bg);color:var(--fg);cursor:pointer
}
.btn:hover,button.act:hover{border-color:var(--accent);color:var(--accent)}
.banner{margin:12px 20px 0;padding:10px 14px;border-radius:var(--radius);
  background:var(--chip);font-size:12px;color:var(--fg)}
.hide{display:none !important}

.tablewrap{flex:1;overflow:auto;padding:16px 20px 40px}
table{width:100%;border-collapse:collapse}
th{
  text-align:left;font-size:11px;letter-spacing:.5px;color:var(--sideSub);
  font-weight:600;padding:8px 10px;border-bottom:1px solid var(--line);
  white-space:nowrap;cursor:pointer;user-select:none;position:sticky;top:0;
  background:var(--bg);z-index:2
}
th.nosort{cursor:default}
th .ar{opacity:.45;margin-left:3px}
td{padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top;font-size:13px}
tbody tr:hover{background:var(--chip)}
td.num{text-align:right;white-space:nowrap}
td a{color:var(--accent);text-decoration:none}
td a:hover{text-decoration:underline}
.tag{display:inline-block;padding:2px 8px;border-radius:999px;
  background:var(--chip);font-size:11px;margin:1px 3px 1px 0}
td select,td input[type=text]{
  width:100%;padding:6px 8px;font-size:16px;border:1px solid var(--line);
  border-radius:var(--radius);background:var(--bg);color:var(--fg)
}
.count{padding:6px 20px;font-size:12px;color:var(--sideSub)}
.empty{padding:60px 20px;text-align:center;color:var(--sideSub);line-height:2}
.empty code{background:var(--chip);padding:2px 6px;border-radius:4px}

/* ---------- 响应式：表格转卡片 ---------- */
@media (max-width:820px){
  .app{flex-direction:column}
  .side{width:100%;flex:none;padding:18px 16px}
  .sidefoot{margin-top:14px}
  .kpis{flex-direction:row;flex-wrap:wrap}
  .kpi{flex:1 1 30%}
  .tablewrap{padding:12px 12px 40px}
  table,thead,tbody,tr,td{display:block;width:100%}
  thead{display:none}
  tbody tr{border:1px solid var(--line);border-radius:var(--radius);
    margin-bottom:10px;padding:8px 10px}
  td{border:0;padding:5px 0;display:flex;gap:10px}
  td::before{content:attr(data-l);flex:0 0 84px;color:var(--sideSub);font-size:11px;padding-top:3px}
  td.num{text-align:left}
}
"""

JS = r"""
(function(){
  var CFG = __CONFIG__;
  var DATA = window.EMBEDDED_DATA || {updatedAt:'', rows:[]};
  var SLUG = '__SLUG__';
  var KEY = 'desk_' + SLUG + '_v1';

  var rows = [], overlay = {}, filters = {}, q = '', stFilter = '', sortKey = null, sortDir = 1;
  var COLS = CFG.columns, ST = CFG.status;

  function esc(s){
    return String(s==null?'':s).replace(/[&<>"']/g, function(c){
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
    });
  }
  function $(id){ return document.getElementById(id); }

  /* ---- 稳定 id：业务主键拼接，绝不用随机数 ---- */
  function makeId(r){
    var f = CFG.idFields || [];
    if (f.length){
      var s = f.map(function(k){ return r[k]==null?'':String(r[k]).trim(); }).join('|');
      if (s.replace(/\|/g,'').trim()) return 'k_' + s;
    }
    return 'k_' + JSON.stringify(r);
  }
  function norm(r){
    var o = {__id: makeId(r)};
    COLS.forEach(function(c){ o[c.key] = r[c.key]==null ? '' : String(r[c.key]).trim(); });
    Object.keys(r).forEach(function(k){ if(!(k in o)) o[k] = r[k]; });  // 未列进 columns 的字段也留着，导出不丢
    return o;
  }
  function val(r, k){
    var o = overlay[r.__id];
    return (o && k in o) ? o[k] : (k === '__status' ? (ST && ST.default) : (k === '__note' ? '' : r[k]));
  }
  function setVal(r, k, v){
    if(!overlay[r.__id]) overlay[r.__id] = {};
    overlay[r.__id][k] = v; save();
  }
  function load(){ try{ return JSON.parse(localStorage.getItem(KEY)||'{}'); }catch(e){ return {}; } }
  function save(){ try{ localStorage.setItem(KEY, JSON.stringify(overlay)); }catch(e){} }

  /* ---- 日期与 KPI ---- */
  function pdate(s){
    if(!s) return null;
    var m = String(s).match(/(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})/);
    return m ? new Date(+m[1], +m[2]-1, +m[3]) : null;
  }
  function kpi(spec){
    if (spec.op === 'count') return rows.length;
    if (spec.op === 'countWhere')
      return rows.filter(function(r){ return String(val(r, spec.key)) === String(spec.eq); }).length;
    if (spec.op === 'sum'){
      return rows.reduce(function(a, r){ var n = parseFloat(val(r, spec.key)); return a + (isNaN(n)?0:n); }, 0);
    }
    if (spec.op === 'dueWithin'){
      var n = 0, now = new Date(); now.setHours(0,0,0,0);
      rows.forEach(function(r){
        var d = pdate(val(r, spec.key));
        if (d){ var diff = (d - now) / 86400000; if (diff >= 0 && diff <= spec.days) n++; }
      });
      return n;
    }
    if (spec.op === 'distinct'){
      var s = {}; rows.forEach(function(r){ s[val(r, spec.key)] = 1; }); return Object.keys(s).length;
    }
    return '—';
  }

  /* ---- 渲染 ---- */
  function renderKpis(){
    $('kpis').innerHTML = (CFG.kpis||[]).map(function(k){
      return '<div class="kpi"><div class="v">' + esc(kpi(k)) + '</div><div class="l">' + esc(k.label) + '</div></div>';
    }).join('');
  }
  function renderFilters(){
    var cols = COLS.filter(function(c){ return c.filter; });
    $('filters').innerHTML = cols.map(function(c){
      var vals = {}; rows.forEach(function(r){ var v = val(r, c.key); if (v !== '' && v != null) vals[v] = 1; });
      var list = Object.keys(vals).sort();
      if (list.length < 2) return '';
      var opts = ['<option value="">全部 · ' + esc(c.label) + '</option>']
        .concat(list.map(function(v){
          return '<option value="' + esc(v) + '"' + (filters[c.key]===v?' selected':'') + '>' + esc(v) + '</option>';
        }));
      return '<div><div class="flabel">' + esc(c.label) + '</div><select data-f="' + esc(c.key) + '">' +
             opts.join('') + '</select></div>';
    }).join('');
    Array.prototype.forEach.call($('filters').querySelectorAll('select'), function(s){
      s.onchange = function(){ var k = s.getAttribute('data-f'); filters[k] = s.value; render(); };
    });
  }
  function renderChips(){
    if (!ST || !ST.enabled) { $('statusChips').innerHTML = ''; return; }
    var all = ['全部'].concat(ST.options);
    $('statusChips').innerHTML = all.map(function(s){
      var cur = stFilter || '全部';
      return '<span class="chip' + (cur===s?' on':'') + '" data-s="' + esc(s) + '">' + esc(s) + '</span>';
    }).join('');
    Array.prototype.forEach.call($('statusChips').querySelectorAll('.chip'), function(el){
      el.onclick = function(){ stFilter = (el.getAttribute('data-s') === '全部') ? '' : el.getAttribute('data-s'); render(); };
    });
  }
  function renderHead(){
    var th = COLS.map(function(c){
      var ar = sortKey === c.key ? '<span class="ar">' + (sortDir > 0 ? '▲' : '▼') + '</span>' : '';
      var st = 'min-width:' + ((c.width || 120) + 'px');
      return '<th data-k="' + esc(c.key) + '" class="' + (c.sort?'':'nosort') + '" style="' + st + '">' +
             esc(c.label) + ar + '</th>';
    });
    if (ST && ST.enabled) th.push('<th style="min-width:110px">状态</th><th style="min-width:150px">备注</th>');
    $('thead').innerHTML = th.join('');
    Array.prototype.forEach.call($('thead').querySelectorAll('th'), function(t){
      if (t.className.indexOf('nosort') >= 0) return;
      t.onclick = function(){
        var k = t.getAttribute('data-k');
        if (sortKey === k) sortDir = -sortDir; else { sortKey = k; sortDir = 1; }
        render();
      };
    });
  }
  function cell(r, c){
    var v = val(r, c.key);
    if (c.type === 'link'){
      if (!v) return '';
      return '<a href="' + esc(v) + '" target="_blank" rel="noopener">打开</a>';
    }
    if (c.type === 'tags')
      return String(v).split(/[,，;；]/).filter(Boolean)
        .map(function(t){ return '<span class="tag">' + esc(t.trim()) + '</span>'; }).join('');
    if (c.type === 'number') return esc(v);
    if (c.type === 'date'){
      var d = pdate(v);
      if (d && ST && ST.enabled){
        var diff = Math.round((d - new Date()) / 86400000);
        if (diff >= 0 && diff <= 3) return '<b style="color:#C0392B">' + esc(v) + '</b>';
        if (diff < 0) return '<span style="opacity:.45">' + esc(v) + '</span>';
      }
      return esc(v);
    }
    return esc(v);
  }
  function visible(){
    var kw = q.trim().toLowerCase();
    var out = rows.filter(function(r){
      for (var k in filters) if (filters[k] && String(val(r, k)) !== filters[k]) return false;
      if (ST && ST.enabled && stFilter && String(val(r, '__status')) !== stFilter) return false;
      if (kw){
        var hit = COLS.filter(function(c){ return c.search !== false; })
          .some(function(c){ return String(val(r, c.key)).toLowerCase().indexOf(kw) >= 0; });
        if (!hit) return false;
      }
      return true;
    });
    if (sortKey){
      out.sort(function(a, b){
        var x = val(a, sortKey), y = val(b, sortKey);
        var dx = pdate(x), dy = pdate(y);
        var r;
        if (dx && dy) r = dx - dy;
        else if (!isNaN(parseFloat(x)) && !isNaN(parseFloat(y))) r = parseFloat(x) - parseFloat(y);
        else r = String(x).localeCompare(String(y), 'zh-CN');
        return r * sortDir;
      });
    }
    return out;
  }
  function render(){
    renderKpis(); renderChips(); renderHead();
    var list = visible();
    $('count').textContent = '显示 ' + list.length + ' / ' + rows.length + ' 条';
    if (!list.length){
      $('tbody').innerHTML = '';
      $('empty').classList.remove('hide');
      return;
    }
    $('empty').classList.add('hide');
    $('tbody').innerHTML = list.map(function(r){
      var tds = COLS.map(function(c){
        var cls = (c.type === 'number' || c.type === 'link') ? ' class="num"' : '';
        return '<td' + cls + ' data-l="' + esc(c.label) + '">' + cell(r, c) + '</td>';
      });
      if (ST && ST.enabled){
        var cur = String(val(r, '__status') || '');
        tds.push('<td data-l="状态"><select data-id="' + esc(r.__id) + '" data-k="__status">' +
          ST.options.map(function(o){
            return '<option value="' + esc(o) + '"' + (cur===o?' selected':'') + '>' + esc(o) + '</option>';
          }).join('') + '</select></td>');
        tds.push('<td data-l="备注"><input type="text" data-id="' + esc(r.__id) + '" data-k="__note" value="' +
          esc(val(r, '__note')) + '" placeholder="…"></td>');
      }
      return '<tr>' + tds.join('') + '</tr>';
    }).join('');
    Array.prototype.forEach.call($('tbody').querySelectorAll('select,input'), function(el){
      var ev = el.tagName === 'SELECT' ? 'change' : 'input';
      el.addEventListener(ev, function(){
        var id = el.getAttribute('data-id'), k = el.getAttribute('data-k');
        var r = rows.filter(function(x){ return x.__id === id; })[0];
        if (r) { setVal(r, k, el.value); if (k === '__status') render(); }
      });
    });
  }

  /* ---- 导入导出 ---- */
  function download(name, text, mime){
    var b = new Blob([text], {type: mime || 'application/octet-stream'});
    var a = document.createElement('a');
    a.href = URL.createObjectURL(b); a.download = name;
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
  }
  function exportJson(){
    var out = {
      updatedAt: new Date().toISOString().slice(0, 10),
      title: CFG.title, subtitle: CFG.subtitle,
      config: {title: CFG.title, subtitle: CFG.subtitle, theme: CFG.theme,
               idFields: CFG.idFields, columns: COLS, status: ST, kpis: CFG.kpis},
      rows: rows.map(function(r){
        var o = {}; COLS.forEach(function(c){ o[c.key] = r[c.key]; });
        Object.keys(r).forEach(function(k){ if (k !== '__id' && !(k in o)) o[k] = r[k]; });
        return o;
      }),
      overlay: overlay            // 状态与备注不能丢
    };
    download(CFG.title + '-' + new Date().toISOString().slice(0,10) + '.json',
             JSON.stringify(out, null, 2), 'application/json');
  }
  function exportCsv(){
    var head = COLS.map(function(c){ return c.label; });
    if (ST && ST.enabled) head = head.concat(['状态', '备注']);
    var q1 = function(s){ s = String(s==null?'':s); return /[",\n]/.test(s) ? '"' + s.replace(/"/g,'""') + '"' : s; };
    var lines = [head.map(q1).join(',')].concat(rows.map(function(r){
      var vs = COLS.map(function(c){ return q1(val(r, c.key)); });
      if (ST && ST.enabled) vs = vs.concat([q1(val(r,'__status')), q1(val(r,'__note'))]);
      return vs.join(',');
    }));
    download(CFG.title + '-' + new Date().toISOString().slice(0,10) + '.csv',
             '\ufeff' + lines.join('\n'), 'text/csv;charset=utf-8');
  }
  function readFile(file){
    var fr = new FileReader();
    fr.onload = function(){
      try{
        var txt = String(fr.result);
        if (/\.csv$/i.test(file.name) || txt.slice(0,1) === '\ufeff' || (txt.indexOf(',')>0 && txt.trim().slice(0,1) !== '{')){
          var lines = txt.replace(/^\ufeff/,'').split(/\r?\n/).filter(function(l){ return l.trim(); });
          var head = lines[0].split(',').map(function(s){ return s.replace(/^"|"$/g,'').trim(); });
          var rs = lines.slice(1).map(function(l){
            var vs = l.split(/,(?=(?:[^"]*"[^"]*")*[^"]*$)/).map(function(s){ return s.replace(/^"|"$/g,''); });
            var o = {}; head.forEach(function(h, i){ o[h] = vs[i] == null ? '' : vs[i]; }); return o;
          });
          apply(rs, file.name);
        } else {
          var o = JSON.parse(txt);
          var rs = o.rows || o.jobs || o.items || o.records || o.列表 || [];
          if (o.overlay) overlay = o.overlay, save();
          if (o.config && o.config.columns && !o.__keepCfg){ /* 沿用页面现有配置，避免列定义被覆盖 */ }
          apply(rs, file.name);
        }
      }catch(e){ alert('读取失败：' + e.message); }
    };
    fr.readAsText(file, 'utf-8');
  }
  function apply(rs, name){
    if (!Array.isArray(rs) || !rs.length){ alert('文件里没有数据行'); return; }
    rows = rs.map(norm);
    filters = {}; q = ''; stFilter = ''; sortKey = null; sortDir = 1;
    $('q').value = '';
    $('sideTime').textContent = (name ? name + ' · ' : '') + '共 ' + rows.length + ' 条';
    renderAll();
  }

  function renderAll(){ renderFilters(); render(); }
  function autoLoad(){
    // ① 内置数据优先：file:// 双击即可见，不依赖 fetch、不弹文件框
    if (DATA && Array.isArray(DATA.rows) && DATA.rows.length){
      rows = DATA.rows.map(norm);
      $('banner').classList.add('hide');
      $('sideTime').textContent = (DATA.updatedAt || '内置数据') + '（内置）';
    }
    // ② http 下再尝试拉最新；file:// 下必然失败，忽略即可
    if (location.protocol !== 'file:'){
      fetch('./data.json?t=' + Date.now()).then(function(r){ return r.ok ? r.json() : null; })
        .then(function(o){
          if (!o) return;
          var rs = o.rows || o.jobs || o.items || o.records || o.列表 || [];
          if (rs.length){ rows = rs.map(norm); $('sideTime').textContent = (o.updatedAt||'') + '（最新）'; renderAll(); }
        }).catch(function(){});
    }
  }

  /* ---- 启动 ---- */
  overlay = load();
  autoLoad();
  if (!rows.length){ $('empty').classList.remove('hide'); $('banner').classList.remove('hide'); }
  renderAll();

  $('q').addEventListener('input', function(){ q = this.value; render(); });
  $('btnExportJson').onclick = exportJson;
  $('btnExportCsv').onclick = exportCsv;
  $('fileUpdate').onchange = function(){ if (this.files[0]) readFile(this.files[0]); };
  $('btnReset').onclick = function(){
    if (!confirm('清空本机保存的状态与备注？数据本身不受影响。')) return;
    overlay = {}; localStorage.removeItem(KEY); renderAll();
  };
})();
"""

HTML = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>__CSS__</style>
</head>
<body>
<div class="app">
  <aside class="side">
    <div class="brand">
      <div class="ttl">__TITLE__</div>
      <div class="sub">__SUBTITLE__</div>
    </div>
    <div class="kpis" id="kpis"></div>
    <div id="filters"></div>
    <div class="sidefoot">
      <div id="sideTime">—</div>
      <button class="ghost" id="btnReset">清空本机状态</button>
    </div>
  </aside>
  <main class="main">
    <div class="topbar">
      <input id="q" class="search" type="search" placeholder="搜索…">
      <div class="chips" id="statusChips"></div>
      <div class="spacer"></div>
      <button class="act" id="btnExportJson">导出 JSON</button>
      <button class="act" id="btnExportCsv">导出 CSV</button>
      <label class="btn" for="fileUpdate">更新数据</label>
      <input id="fileUpdate" type="file" accept=".json,.csv" hidden>
    </div>
    <div class="banner hide" id="banner">
      还没有数据。点右上角「更新数据」选择 <code>data.json</code> 或 <code>data.csv</code>，
      或把数据放进素材库的 <code>02-数据.csv</code> 后重新生成本页。
    </div>
    <div class="count" id="count"></div>
    <div class="tablewrap">
      <table><thead><tr id="thead"></tr></thead><tbody id="tbody"></tbody></table>
      <div class="empty hide" id="empty">没有符合条件的条目。换个筛选条件试试。</div>
    </div>
  </main>
</div>
<script id="embeddedData">window.EMBEDDED_DATA = __DATA__;</script>
<script>
__JS__
</script>
</body>
</html>
"""


def render(cfg, rows, updated_at=""):
    payload = {"updatedAt": updated_at or datetime.now().strftime("%Y-%m-%d"), "rows": rows}
    safe = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
    cfg_json = json.dumps(cfg, ensure_ascii=False).replace("<", "\\u003c")

    html = (HTML
            .replace("__CSS__", CSS.replace("__THEME__", theme_vars(cfg)))
            .replace("__TITLE__", cfg.get("title", "我的信息台"))
            .replace("__SUBTITLE__", cfg.get("subtitle", ""))
            .replace("__DATA__", safe)
            .replace("__SLUG__", _slug(cfg.get("title", "desk")))
            .replace("__JS__", JS.replace("__CONFIG__", cfg_json).replace("__SLUG__", _slug(cfg.get("title", "desk")))))
    return html


def _slug(title):
    s = "".join(ch for ch in str(title) if ch.isalnum())
    return (s or "desk")[:24]


# ---------------------------------------------------------------- CLI

def cmd_init(target):
    if not os.path.isdir(TEMPLATE_DIR):
        raise SystemExit("[init] 技能包里找不到素材库模板：%s" % TEMPLATE_DIR)
    if os.path.exists(target):
        raise SystemExit("[init] 目录已存在：%s" % target)
    shutil.copytree(TEMPLATE_DIR, target)
    print("[init] 已生成素材库：%s" % os.path.abspath(target))
    for f in sorted(os.listdir(target)):
        print("       - %s" % f)
    print("\n下一步：填 01-字段定义.csv 与 02-数据.csv，然后：")
    print("  python %s --lib %s --out 我的信息台.html" % (
        os.path.relpath(os.path.abspath(__file__)), target))


def main():
    ap = argparse.ArgumentParser(description="素材库 → 个人信息台（单文件 HTML）")
    ap.add_argument("--init", metavar="DIR", help="生成一份空白素材库模板")
    ap.add_argument("--lib", metavar="DIR", help="素材库目录")
    ap.add_argument("--out", default="我的信息台.html", help="输出 HTML 路径")
    ap.add_argument("--check", action="store_true", help="只校验素材库，不生成")
    a = ap.parse_args()

    if a.init:
        cmd_init(a.init)
        return
    if not a.lib:
        ap.print_help()
        raise SystemExit("\n[build] 需要 --lib 或 --init")

    cfg, rows, warn = load_lib(a.lib)
    print("[build] 标题：%s" % cfg["title"])
    print("[build] 列：%s" % " / ".join(c["label"] for c in cfg["columns"]))
    print("[build] 主键：%s" % " + ".join(cfg["idFields"]))
    print("[build] 数据：%d 条" % len(rows))
    for w in warn:
        print("[warn ] %s" % w)

    # 主键唯一性检查：重复主键会让状态串台
    ids = {}
    for r in rows:
        k = "|".join(str(r.get(f, "") or "").strip() for f in cfg["idFields"])
        ids[k] = ids.get(k, 0) + 1
    dup = {k: v for k, v in ids.items() if v > 1}
    if dup:
        print("[warn ] 主键有重复（%d 组），重复行的状态会互相串台：" % len(dup))
        for k, v in list(dup.items())[:5]:
            print("         %s ×%d" % (k[:60], v))
        print("         建议：在 03-视图配置.json 的 idFields 里加一列让它唯一")

    if a.check:
        print("[build] --check：未生成文件")
        return

    html = render(cfg, rows)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(html)
    size = os.path.getsize(a.out)
    print("[build] 已生成 %s（%.0f KB，内嵌 %d 条）" % (a.out, size / 1024.0, len(rows)))
    print("[build] 双击即可打开，离线可用。数据更新后重跑本命令即可。")


if __name__ == "__main__":
    main()
