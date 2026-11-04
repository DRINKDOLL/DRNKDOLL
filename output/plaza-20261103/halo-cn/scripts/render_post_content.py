#!/usr/bin/env python3
"""把文章快照里的 markdown 原稿渲染成 HTML 并重新发布。

背景：这批成果是用接口直接写入的，快照里 raw 有内容、渲染产物 content 为空，
      所以前台详情页只剩标题、没有正文。控制台接口 PUT /posts/{name}/content
      可以把 raw 和渲染后的 content 一起写回，再 PUT /posts/{name}/publish 发布，
      详情页就能看到正文了。

用法：
    python scripts/render_post_content.py            # 处理全部文章
    python scripts/render_post_content.py --dry-run  # 只打印渲染结果
"""
import base64
import html
import json
import re
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8092"
AUTH = "Basic " + base64.b64encode(b"admin:Passw0rd!2026").decode()


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Authorization", AUTH)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw.strip() else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:600]


def inline_md(text):
    """行内 markdown：**粗体**、*斜体*、`代码`、[文字](链接)。"""
    out = html.escape(text, quote=False)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<em>\1</em>", out)
    out = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" rel="noopener">\1</a>', out
    )
    return out


IMG_LINE_RE = re.compile(r"^!\[([^\]]*)\]\(([^)\s]+)\)$")


def table_html(lines):
    """把 markdown 管道表格转成 HTML 表格（移动端可横向滚动）。"""
    rows = []
    for line in lines:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append(cells)
    if len(rows) < 2:
        return ""
    head, body = rows[0], rows[2:] if re.fullmatch(r"[\s|:-]+", lines[1]) else rows[1:]
    out = ['<div class="table-wrap" style="overflow-x:auto;margin:1.25rem 0">']
    out.append("<table><thead><tr>%s</tr></thead><tbody>" % "".join(
        "<th>%s</th>" % inline_md(c) for c in head
    ))
    for row in body:
        out.append("<tr>%s</tr>" % "".join("<td>%s</td>" % inline_md(c) for c in row))
    out.append("</tbody></table></div>")
    return "".join(out)


def img_html(alt, src):
    caption = ""
    if alt.strip():
        caption = '<figcaption style="margin-top:.5rem;text-align:center;font-size:.8125rem;color:#6b7280">%s</figcaption>' % html.escape(alt, quote=False)
    return (
        '<figure style="margin:1.5rem 0">'
        '<img src="%s" alt="%s" loading="lazy" '
        'style="display:block;width:100%%;height:auto;max-height:520px;object-fit:contain;'
        'border-radius:.75rem;border:1px solid rgba(148,163,184,.35);background:#f8fafc" />%s</figure>'
        % (html.escape(src, quote=False), html.escape(alt, quote=False), caption)
    )


def md_to_html(markdown_text):
    """够用的 markdown 渲染：标题、无序/有序列表、引用、段落、分割线、代码块。"""
    lines = markdown_text.replace("\r\n", "\n").split("\n")
    blocks = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # 代码块
        if stripped.startswith("```"):
            i += 1
            code = []
            while i < n and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1
            blocks.append(
                "<pre><code>%s</code></pre>" % html.escape("\n".join(code), quote=False)
            )
            continue

        # 图片（独占一行）
        m = IMG_LINE_RE.match(stripped)
        if m:
            blocks.append(img_html(m.group(1), m.group(2)))
            i += 1
            continue

        # 表格
        if stripped.startswith("|") and stripped.endswith("|"):
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append(lines[i].strip())
                i += 1
            table = table_html(rows)
            if table:
                blocks.append(table)
            continue

        # 分割线
        if re.fullmatch(r"(-{3,}|\*{3,})", stripped):
            blocks.append("<hr />")
            i += 1
            continue

        # 标题
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            level = len(m.group(1))
            blocks.append("<h%d>%s</h%d>" % (level, inline_md(m.group(2)), level))
            i += 1
            continue

        # 引用
        if stripped.startswith(">"):
            quote = []
            while i < n and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip()[1:].strip())
                i += 1
            blocks.append("<blockquote><p>%s</p></blockquote>" % inline_md(" ".join(quote)))
            continue

        # 无序列表
        if re.match(r"^[-*+]\s+", stripped):
            items = []
            while i < n and re.match(r"^[-*+]\s+", lines[i].strip()):
                items.append(inline_md(re.sub(r"^[-*+]\s+", "", lines[i].strip())))
                i += 1
            blocks.append("<ul>%s</ul>" % "".join("<li>%s</li>" % it for it in items))
            continue

        # 有序列表
        if re.match(r"^\d+\.\s+", stripped):
            items = []
            while i < n and re.match(r"^\d+\.\s+", lines[i].strip()):
                items.append(inline_md(re.sub(r"^\d+\.\s+", "", lines[i].strip())))
                i += 1
            blocks.append("<ol>%s</ol>" % "".join("<li>%s</li>" % it for it in items))
            continue

        # 普通段落（相邻行合并）
        para = [stripped]
        i += 1
        while i < n:
            nxt = lines[i].strip()
            if not nxt or re.match(r"^(#{1,6}\s|[-*+]\s|\d+\.\s|>|```|\||!\[)", nxt):
                break
            para.append(nxt)
            i += 1
        blocks.append("<p>%s</p>" % inline_md(" ".join(para)))

    return "".join(blocks)


def get_posts():
    status, data = call("GET", "/apis/api.content.halo.run/v1alpha1/posts?page=1&size=100")
    assert status == 200, (status, data)
    return data["items"]


def head_content(name):
    status, data = call(
        "GET", "/apis/api.console.halo.run/v1alpha1/posts/%s/head-content" % name
    )
    assert status == 200, (status, data)
    return data


def release_content(name):
    status, data = call(
        "GET", "/apis/api.console.halo.run/v1alpha1/posts/%s/release-content" % name
    )
    return data if status == 200 else None


def snapshot_content(name, snapshot_name):
    """读取指定快照的正文（用于从原始快照恢复原稿）。"""
    status, data = call(
        "GET",
        "/apis/api.console.halo.run/v1alpha1/posts/%s/content?snapshotName=%s"
        % (name, snapshot_name),
    )
    return data if status == 200 else None


def main():
    dry = "--dry-run" in sys.argv
    force = "--force" in sys.argv
    only = None
    for idx, arg in enumerate(sys.argv):
        if arg == "--post" and idx + 1 < len(sys.argv):
            only = sys.argv[idx + 1]
    for post in get_posts():
        name = post["metadata"]["name"]
        title = post["spec"]["title"]
        if only and name != only:
            continue
        head = head_content(name)
        if head.get("content") and not force:
            print("[skip] %s 已有渲染正文" % title)
            continue
        raw = "" if force else (head.get("raw") or "").strip()
        if not raw:
            base = post["spec"].get("baseSnapshot")
            recovered = snapshot_content(name, base) if base else None
            raw = ((recovered or {}).get("raw") or "").strip()
        if not raw:
            released = release_content(name)
            raw = ((released or {}).get("raw") or "").strip()
        if not raw:
            print("[warn] %s 没有正文原稿，跳过" % title)
            continue
        body = md_to_html(raw)
        if dry:
            print("=====", title, name)
            print(body)
            continue
        status, res = call(
            "PUT",
            "/apis/api.console.halo.run/v1alpha1/posts/%s/content" % name,
            {"raw": raw, "content": body, "rawType": "markdown"},
        )
        if status != 200:
            print("[fail] %s 更新正文 -> %s %s" % (title, status, res))
            continue
        status2, res2 = call(
            "PUT", "/apis/api.console.halo.run/v1alpha1/posts/%s/publish" % name, {}
        )
        print("[ok] %s 正文 %d 字节，发布=%s" % (title, len(body), status2))
        if status2 != 200:
            print("   ", str(res2)[:300])


if __name__ == "__main__":
    main()
