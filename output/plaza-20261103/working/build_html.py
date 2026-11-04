# -*- coding: utf-8 -*-
"""把 stage1 的 Markdown 转成 doc-typeset 规范的 HTML（消费 design_tokens 的 CSS 变量）。"""
import json, re, html

BASE = r"C:\Users\LENOVO\Desktop\成果广场\output\plaza-20261103"
md_path = BASE + r"\stage1\final_draft.md"
tok_path = BASE + r"\stage2\design_tokens.json"
out_path = BASE + r"\stage2\formatted-成果展示广场平台需求文档.html"

tokens = json.load(open(tok_path, encoding="utf-8"))["css_variables"]

raw = open(md_path, encoding="utf-8").read().split("\n")

def inline(t):
    t = html.escape(t)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)

def is_table_row(l):
    return l.strip().startswith("|") and l.strip().endswith("|")

blocks, i, title = [], 0, None
while i < len(raw):
    line = raw[i]
    s = line.strip()
    if not s:
        i += 1
        continue
    if s.startswith("# ") and title is None:
        title = s[2:].strip(); i += 1; continue
    if s.startswith("## "):
        blocks.append(("h1", s[3:].strip())); i += 1; continue
    if s.startswith("### "):
        blocks.append(("h2", s[4:].strip())); i += 1; continue
    if is_table_row(line):
        rows = []
        while i < len(raw) and is_table_row(raw[i]):
            cells = [c.strip() for c in raw[i].strip().strip("|").split("|")]
            if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                rows.append(cells)
            i += 1
        blocks.append(("table", rows)); continue
    if s.startswith("- "):
        items = []
        while i < len(raw) and raw[i].strip().startswith("- "):
            items.append(raw[i].strip()[2:].strip()); i += 1
        blocks.append(("ul", items)); continue
    if re.match(r"^\d+\.\s", s):
        items = []
        while i < len(raw) and re.match(r"^\d+\.\s", raw[i].strip()):
            items.append(re.sub(r"^\d+\.\s+", "", raw[i].strip())); i += 1
        blocks.append(("ol", items)); continue
    buf = [s]; i += 1
    while i < len(raw):
        n = raw[i].strip()
        if (not n or n.startswith("#") or n.startswith("- ")
                or is_table_row(raw[i]) or re.match(r"^\d+\.\s", n)):
            break
        buf.append(n); i += 1
    blocks.append(("p", "".join(buf)))

# ---- 目录 ----
toc = []
sec = 0
for kind, payload in blocks:
    if kind == "h1":
        sec += 1
        toc.append({"level": 1, "id": "section-%d" % sec, "text": payload})
    elif kind == "h2":
        n = len([t for t in toc if t["level"] == 1])
        sub = len([t for t in toc if t["level"] == 2 and t.get("parent") == n]) + 1
        toc.append({"level": 2, "id": "section-%d-%d" % (n, sub), "text": payload, "parent": n})

toc_html = ['<nav class="doc-toc" aria-label="文档目录">',
            '<p class="toc-title">目 录</p>', '<ol class="toc-list">']
open_sub = False
for idx, item in enumerate(toc):
    if item["level"] == 1:
        if open_sub:
            toc_html.append("</ol></li>"); open_sub = False
        toc_html.append('<li><a href="#%s">%s</a>' % (item["id"], html.escape(item["text"])))
        if idx + 1 < len(toc) and toc[idx + 1]["level"] == 2:
            toc_html.append('<ol class="toc-sub">'); open_sub = True
        else:
            toc_html.append("</li>")
    else:
        toc_html.append('<li><a href="#%s">%s</a></li>' % (item["id"], html.escape(item["text"])))
if open_sub:
    toc_html.append("</ol></li>")
toc_html.append("</ol></nav>")
toc_html = "\n".join(toc_html)

# ---- 正文 ----
SUMMARY = """<table class="executive-summary">
<thead><tr><th>执行摘要</th></tr></thead>
<tbody><tr><td>
<p class="sum-p">本文档是警院 WeChat 全生态五平台中第四平台（成果展示广场）的开发依据，承接总纲第三章的全局规则与 M4 里程碑。广场是五平台闭环的第五环与唯一出口，只做四件事：展示、体验、反馈、传承。</p>
<p class="sum-p">本次需求澄清确定三条关键决策：其一，广场对公网完全开放，作品提交即公开、不设前置人工审核，以"涉密承诺书 + 机审标记 + 2 小时响应下架"作为补偿性控制，构成对总纲 NFR-02 的正式偏离；其二，广场严格守住"展示"定位，不做关注关系、不做推荐流、不做热度榜，评分与榜单只作作品质量参考；其三，优秀作品的课例回流采用"作者授权 + 老师审批"双条件，不由系统自动流转。</p>
<p class="sum-p">首版 P0 范围为：投稿上墙、展示墙、作品详情、体验中转页、评论点赞评分、巡查与下架、广场管理后台。榜单、搜索、版本迭代、课例回流列 P1。</p>
<p class="sum-p">需决策层在开发启动前拍板两件事：一是总纲负责人对第九章偏离条款的书面确认（附录 D 记录确认状态）；二是非工坊来源作品的积分分值（第十三章 Q-11）。</p>
</td></tr></tbody></table>
"""

body = [SUMMARY]
sec = 0
h2_counter = {}
for kind, payload in blocks:
    if kind == "h1":
        sec += 1; h2_counter[sec] = 0
        body.append('<h1 class="chapter" id="section-%d">%s</h1>' % (sec, html.escape(payload)))
    elif kind == "h2":
        h2_counter[sec] += 1
        body.append('<h2 id="section-%d-%d">%s</h2>' % (sec, h2_counter[sec], html.escape(payload)))
    elif kind == "table":
        rows = payload
        head, rest = rows[0], rows[1:]
        t = ['<table class="tbl"><thead><tr>']
        t += ['<th>%s</th>' % inline(c) for c in head]
        t.append("</tr></thead><tbody>")
        for r in rest:
            r = (r + [""] * len(head))[:len(head)]
            t.append("<tr>" + "".join("<td>%s</td>" % inline(c) for c in r) + "</tr>")
        t.append("</tbody></table>")
        body.append("".join(t))
    elif kind == "ul":
        body.append('<ul class="bullet">' + "".join("<li>%s</li>" % inline(x) for x in payload) + "</ul>")
    elif kind == "ol":
        body.append('<ol class="num">' + "".join("<li>%s</li>" % inline(x) for x in payload) + "</ol>")
    else:
        body.append('<p class="body">%s</p>' % inline(payload))

var_root = "\n".join("    %s: %s;" % (k, v) for k, v in tokens.items())

page = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="docx-page-size" content="A4">
<title>__TITLE__</title>
<style>
:root {
__VARS__
    --fs-cover-title: var(--typography-fontSize-coverTitle, 30pt);
    --fs-cover-cat: var(--typography-fontSize-coverCategory, 12pt);
    --fs-h1: var(--typography-fontSize-h1, 18pt);
    --fs-h2: var(--typography-fontSize-h2, 14pt);
    --fs-body: var(--typography-fontSize-body, 12pt);
    --fs-small: var(--typography-fontSize-small, 10.5pt);
    --ff-heading: var(--typography-fontFamily-heading, "SimHei", sans-serif);
    --ff-body: var(--typography-fontFamily-body, "SimSun", serif);
    --lh-body: var(--typography-lineHeight-body, 1.6);
    --lh-heading: var(--typography-lineHeight-heading, 1.4);
    --fw-heading: var(--typography-fontWeight-heading, 700);
    --color-primary: var(--color-primary, #1565C0);
    --color-heading: var(--color-heading, #1A237E);
    --color-text: var(--color-text, #212121);
    --color-muted: var(--color-textSecondary, #616161);
    --color-border: var(--color-divider, #E0E0E0);
    --color-surface: var(--color-surface, #F5F7FA);
    --color-page: var(--color-background, #FFFFFF);
    --sp-paragraph: var(--spacing-paragraph, 0.55em);
    --sp-section: var(--spacing-sectionGap, 1.6em);
    --sp-list-indent: var(--spacing-listIndent, 2.2em);
    --sp-li-gap: var(--spacing-listItemGap, 0.25em);
    --sp-h1-pad: var(--spacing-h1Padding, 6px 0 6px 10px);
    --sp-h1-top: var(--spacing-h1MarginTop, 1.6em);
    --sp-h1-bottom: var(--spacing-h1MarginBottom, 0.9em);
    --sp-h2-top: var(--spacing-h2MarginTop, 1.2em);
    --sp-h2-bottom: var(--spacing-h2MarginBottom, 0.5em);
    --sp-table-top: var(--spacing-tableMarginTop, 0.4em);
    --sp-table-bottom: var(--spacing-tableMarginBottom, 0.9em);
    --sp-cell-pad: var(--spacing-cellPadding, 5px 6px);
    --sp-cover-title: var(--spacing-coverTitleMargin, 0.55em 0 0.35em 0);
    --sp-cover-meta: var(--spacing-coverMetaMargin, 0.2em 0 0 0);
    --sp-toc-li: var(--spacing-tocItemGap, 0.1em);
    --sp-toc-sub-indent: var(--spacing-tocSubIndent, 1.8em);
    --sp-toc-sub: var(--spacing-tocSubMargin, 0.1em 0 0.3em 0);
    --margin-page: var(--layout-marginLeft, 2.5cm);
    --page-content-width: var(--layout-maxContentWidth, 160mm);
}
@page { @bottom-center { content: counter(page); } }
@page cover { @bottom-center { content: none; } }
section[role="cover"] { page: cover; }
* { box-sizing: border-box; }
body {
    font-family: var(--ff-body);
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    color: var(--color-text);
    background: var(--color-page);
    max-width: var(--page-content-width);
    margin-left: auto;
    margin-right: auto;
}
p.body {
    font-family: var(--ff-body);
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    color: var(--color-text);
    text-indent: 2em;
    margin: 0 0 var(--sp-paragraph) 0;
    text-align: justify;
}
p.sum-p {
    font-family: var(--ff-body);
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    color: var(--color-text);
    text-indent: 2em;
    margin: 0 0 var(--sp-paragraph) 0;
    text-align: justify;
}
ul.bullet, ol.num {
    margin: 0 0 var(--sp-paragraph) 0;
    padding-left: var(--sp-list-indent);
    font-family: var(--ff-body);
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    color: var(--color-text);
}
ul.bullet li, ol.num li {
    text-indent: 0;
    margin-bottom: var(--sp-li-gap);
    text-align: justify;
}
h1.chapter {
    font-family: var(--ff-heading);
    font-size: var(--fs-h1);
    line-height: var(--lh-heading);
    font-weight: var(--fw-heading);
    color: var(--color-heading);
    border-left: 5px solid var(--color-primary);
    border-bottom: 1px solid var(--color-border);
    padding: var(--sp-h1-pad);
    margin: var(--sp-h1-top) 0 var(--sp-h1-bottom) 0;
    text-indent: 0;
    page-break-after: avoid;
}
h2 {
    font-family: var(--ff-heading);
    font-size: var(--fs-h2);
    line-height: var(--lh-heading);
    font-weight: var(--fw-heading);
    color: var(--color-primary);
    margin: var(--sp-h2-top) 0 var(--sp-h2-bottom) 0;
    text-indent: 0;
    page-break-after: avoid;
}
table.tbl {
    width: 100%;
    border-collapse: collapse;
    margin: var(--sp-table-top) 0 var(--sp-table-bottom) 0;
    font-family: var(--ff-body);
    font-size: var(--fs-small);
    line-height: var(--lh-heading);
    color: var(--color-text);
}
table.tbl th {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    padding: var(--sp-cell-pad);
    font-family: var(--ff-heading);
    font-size: var(--fs-small);
    font-weight: var(--fw-heading);
    color: var(--color-heading);
    text-align: left;
    text-indent: 0;
}
table.tbl td {
    border: 1px solid var(--color-border);
    padding: var(--sp-cell-pad);
    vertical-align: top;
    text-indent: 0;
}
table.executive-summary {
    width: 100%;
    border-collapse: collapse;
    margin: var(--sp-table-top) 0 var(--sp-section) 0;
}
table.executive-summary th {
    background: var(--color-primary);
    color: var(--color-page);
    font-family: var(--ff-heading);
    font-size: var(--fs-h2);
    font-weight: var(--fw-heading);
    text-align: left;
    padding: var(--sp-cell-pad);
    border: 1px solid var(--color-primary);
}
table.executive-summary td {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    padding: var(--sp-cell-pad);
}
.cover-cat {
    font-family: var(--ff-heading);
    font-size: var(--fs-cover-cat);
    color: var(--color-primary);
    font-weight: var(--fw-heading);
    letter-spacing: 0.12em;
    text-align: center;
    text-indent: 0;
    margin: 5.5cm 0 0 0;
}
.cover-title {
    font-family: var(--ff-heading);
    font-size: var(--fs-cover-title);
    font-weight: var(--fw-heading);
    color: var(--color-heading);
    line-height: var(--lh-heading);
    text-align: center;
    text-indent: 0;
    margin: var(--sp-cover-title);
}
.cover-sub {
    font-family: var(--ff-body);
    font-size: var(--fs-h2);
    color: var(--color-muted);
    text-align: center;
    text-indent: 0;
    margin: 0 0 3cm 0;
}
.cover-meta {
    font-family: var(--ff-body);
    font-size: var(--fs-small);
    color: var(--color-muted);
    text-align: center;
    text-indent: 0;
    line-height: var(--lh-heading);
    margin: var(--sp-cover-meta);
}
.cover-foot {
    font-family: var(--ff-body);
    font-size: var(--fs-small);
    color: var(--color-muted);
    text-align: center;
    text-indent: 0;
    margin: 2.4cm 0 0 0;
}
.doc-toc { padding: 0; margin: 0; }
.toc-title {
    font-family: var(--ff-heading);
    font-size: var(--fs-h1);
    font-weight: var(--fw-heading);
    color: var(--color-heading);
    text-align: center;
    text-indent: 0;
    margin: 1.2cm 0 0.8cm 0;
}
.toc-list, .toc-list ol, .toc-list ul {
    list-style: none;
    list-style-type: none;
    padding-left: 0;
    margin: 0;
}
.toc-list li {
    font-family: var(--ff-body);
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    text-indent: 0;
    margin-bottom: var(--sp-toc-li);
}
.toc-list > li > a {
    color: var(--color-heading);
    font-family: var(--ff-heading);
    font-weight: var(--fw-heading);
    text-decoration: none;
}
.toc-list ol.toc-sub {
    padding-left: var(--sp-toc-sub-indent);
    margin: var(--sp-toc-sub);
}
.toc-list ol.toc-sub li {
    font-size: var(--fs-small);
    line-height: var(--lh-heading);
}
.toc-list ol.toc-sub a {
    color: var(--color-muted);
    text-decoration: none;
}
</style>
</head>
<body>
<section role="cover">
  <p class="cover-cat">警院 WeChat 全生态五平台 · 第四平台细化</p>
  <p class="cover-title">成果展示广场平台需求文档</p>
  <p class="cover-sub">展成果 · 做反馈 · 做传承</p>
  <p class="cover-meta">文档版本：V1.0（首版，待评审）</p>
  <p class="cover-meta">编制日期：2026 年 11 月 3 日</p>
  <p class="cover-meta">文档负责人：成果展示广场平台负责人</p>
  <p class="cover-meta">上游依据：总纲 V1.0 第三章 / 3.7 / 3.9 / M4</p>
  <p class="cover-foot">本文档为五平台需求文档体系第四册，编号规则与总纲保持一致</p>
</section>
<section role="cover">
__TOC__
</section>
<section role="body" data-page-restart="1">
__BODY__
</section>
</body>
</html>
"""

page = (page.replace("__VARS__", var_root)
            .replace("__TITLE__", html.escape(title or "成果展示广场平台需求文档"))
            .replace("__TOC__", toc_html)
            .replace("__BODY__", "\n".join(body)))

open(out_path, "w", encoding="utf-8").write(page)
print("written:", out_path)
print("chapters:", sec, "toc:", len(toc))
