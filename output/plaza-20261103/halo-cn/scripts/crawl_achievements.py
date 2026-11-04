#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""成果详情爬虫：抓取公开技术资料 -> 落盘图片 -> 写入 Halo 文章正文。

只依赖 Python 标准库（urllib + html.parser），不需要 pip 安装任何东西。

流程
----
1. 读取 scripts/achievement_sources.json 里每个项目配置的来源页（支持一个项目多个来源）；
2. 抓取页面 HTML（自动处理 gzip/deflate、重定向、超时重试）；
3. 用 content_selector 定位正文节点，按白名单抽取 h2~h4 / 段落 / 列表 / 图片 / 表格，
   跳过脚本、导航、徽章图、代码块（主题对代码块做了模糊处理）；
4. 下载正文图片到 workdir/static/images/achievements/<slug>/，并把 markdown 里的
   图片地址改写为站内地址 /images/achievements/<slug>/xxx.jpg（无需重启即可访问）；
5. 合并原稿（作品说明 / 项目信息 / 体验方式）+ 抓取内容 + 参考资料，生成 markdown；
6. 调用控制台接口写回正文并重新发布：
   PUT /apis/api.console.halo.run/v1alpha1/posts/{name}/content   {raw, content, rawType}
   PUT /apis/api.console.halo.run/v1alpha1/posts/{name}/publish

用法
----
    python scripts/crawl_achievements.py --dry-run          # 只抓取并打印，不写库
    python scripts/crawl_achievements.py                    # 抓取全部项目并写库
    python scripts/crawl_achievements.py --slug work-traffic # 只处理一个项目
    python scripts/crawl_achievements.py --no-images        # 不下载图片（仅取文字）
    python scripts/crawl_achievements.py --prune-images     # 先清空该项目的历史图片
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONFIG_PATH = os.path.join(HERE, "achievement_sources.json")
STATIC_DIR = os.path.join(ROOT, "workdir", "static", "images", "achievements")

BASE = os.environ.get("HALO_BASE", "http://127.0.0.1:8092")
USER = os.environ.get("HALO_USER", "admin")
PASS = os.environ.get("HALO_PASS", "Passw0rd!2026")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}
SKIP_TAGS = {
    "script", "style", "noscript", "svg", "iframe", "form", "button",
    "input", "select", "textarea", "video", "audio", "canvas", "template",
    "nav", "footer", "header", "aside",
}
# 正文里要跳过的小装饰（用较精确的 token，避免误伤 rno-markdown 这类正文容器）
SKIP_CLASS_HINTS = (
    "anchor", "octicon", "sr-only", "badge", "breadcrumb", "heading-link",
    "zeroclipboard", "table-of-contents", "toc-", "gist", "sponsor",
    "sidebar", "footer", "share-",
)
SKIP_IMG_HINTS = (
    "shields.io", "badge", "badgen", "/badge/", ".svg", "star-history",
    "logo", "icon", "avatar", "favicon", "wechat", "qrcode", "qr-code",
)
# README 里以安装/依赖/问答/协议为主的章节，对成果展示页无价值，整节跳过
SECTION_SKIP = re.compile(
    r"(安装|部署|依赖|环境要求|环境准备|快速开始|快速上手|快速安装|"
    r"install|setup|dependenc|requirement|prerequisite|"
    r"常见问题|faq|q\s*[：:]|troubleshoot|"
    r"许可|协议|license|contribut|参与贡献|代码贡献|"
    r"更新|变更|changelog|release note|版本历史|"
    r"致谢|acknowledg|citation|引用|"
    r"star|捐赠|打赏|赞助|sponsor|"
    r"交流|社区|联系|关于我们|友情|相关链接|related|"
    r"待补充|todo|roadmap|计划)",
    re.I,
)


# ---------------------------------------------------------------- HTTP 工具
def http_get(url, timeout=40, retries=3, referer=None):
    """GET 一个地址，返回 (bytes, 最终 URL, Content-Type)。"""
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", UA)
            req.add_header("Accept", "text/html,application/xhtml+xml,image/*,*/*")
            req.add_header("Accept-Language", "zh-CN,zh;q=0.9,en;q=0.8")
            req.add_header("Accept-Encoding", "gzip, deflate")
            if referer:
                req.add_header("Referer", referer)
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                data = resp.read()
                enc = (resp.headers.get("Content-Encoding") or "").lower()
                if "gzip" in enc:
                    data = gzip.decompress(data)
                elif "deflate" in enc:
                    try:
                        data = zlib.decompress(data)
                    except zlib.error:
                        data = zlib.decompress(data, -zlib.MAX_WBITS)
                return data, resp.geturl(), resp.headers.get("Content-Type", "")
        except Exception as exc:  # noqa: BLE001 - 网络异常统一重试
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("抓取失败 %s: %s" % (url, last))


def decode_html(data, content_type=""):
    charset = None
    m = re.search(r"charset=([\w\-]+)", content_type or "", re.I)
    if m:
        charset = m.group(1)
    if not charset:
        m = re.search(rb'<meta[^>]+charset=["\']?([\w\-]+)', data[:4096], re.I)
        if m:
            charset = m.group(1).decode("ascii", "ignore")
    for enc in filter(None, [charset, "utf-8", "gb18030"]):
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", "ignore")


# ---------------------------------------------------------------- 迷你 DOM
class Node:
    __slots__ = ("tag", "attrs", "children", "text")

    def __init__(self, tag=None, attrs=None, text=None):
        self.tag = tag
        self.attrs = attrs or {}
        self.children = []
        self.text = text

    def cls(self):
        return (self.attrs.get("class") or "").lower()

    def __repr__(self):  # pragma: no cover
        return "<%s %s>" % (self.tag or "#text", self.attrs.get("class", ""))


class DomParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, {k.lower(): (v or "") for k, v in attrs})
        self.stack[-1].children.append(node)
        if tag not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        node = Node(tag, {k.lower(): (v or "") for k, v in attrs})
        self.stack[-1].children.append(node)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        if data:
            self.stack[-1].children.append(Node(None, text=data))


def build_dom(html_text):
    parser = DomParser()
    parser.feed(html_text)
    parser.close()
    return parser.root


def iter_nodes(node):
    yield node
    for child in node.children:
        if child.tag:
            yield from iter_nodes(child)


def match(node, tag=None, cls=None, ident=None):
    if tag and node.tag != tag:
        return False
    if cls and cls not in node.cls():
        return False
    if ident and node.attrs.get("id") != ident:
        return False
    return True


def find_all(node, tag=None, cls=None, ident=None):
    return [n for n in iter_nodes(node) if n.tag and match(n, tag, cls, ident)]


def find_first(node, tag=None, cls=None, ident=None):
    for n in iter_nodes(node):
        if n.tag and match(n, tag, cls, ident):
            return n
    return None


BAD_CONTAINER_HINTS = (
    "nav", "footer", "comment", "recommend", "related", "sidebar", "banner",
    "breadcrumb", "hot-", "share", "copyright", "advert", "asider", "menu",
    "toolbar", "header", "pagination",
)


def pick_content(root, selector):
    """selector 支持 "tag.cls" / "#id" / ".cls"；同类节点取正文最多的那个。"""
    selector = (selector or "").strip()
    if not selector:
        return None
    if selector.startswith("#"):
        matches = find_all(root, ident=selector[1:])
    elif selector.startswith("."):
        matches = find_all(root, cls=selector[1:])
    else:
        tag, cls = None, None
        for part in selector.split("."):
            if not part:
                continue
            if tag is None and not part.isdigit():
                tag = part
            else:
                cls = part
        matches = find_all(root, tag=tag, cls=cls)
    if not matches:
        return None
    return max(matches, key=lambda n: len(text_of(n)))


def parent_map(root):
    parents = {}
    for node in iter_nodes(root):
        for child in node.children:
            parents[id(child)] = node
    return parents


def _depth(node, parents):
    depth = 0
    cur = node
    while id(cur) in parents:
        depth += 1
        cur = parents[id(cur)]
    return depth


def auto_content(root):
    """没有任何选择器时的兜底：找「段落文字最多、层级最深」的容器。

    一次 DFS 统计每个节点的正文长度与段落数，避免大页面上的重复遍历。
    """
    stats = {}

    def dfs(node, depth):
        text_len = 0
        paras = 0
        for child in node.children:
            if child.tag is None:
                text_len += len(child.text or "")
                continue
            if child.tag in ("script", "style", "noscript", "svg"):
                continue
            sub_text, sub_paras = dfs(child, depth + 1)
            text_len += sub_text
            paras += sub_paras
            if child.tag == "p":
                paras += 1
        stats[id(node)] = (text_len, paras, depth, node)
        return text_len, paras

    dfs(root, 0)
    best_score = 0
    for ident, (text_len, paras, depth, node) in stats.items():
        if node.tag not in ("div", "article", "section", "main"):
            continue
        cls = (node.cls() + " " + (node.attrs.get("id") or "")).lower()
        if any(h in cls for h in BAD_CONTAINER_HINTS):
            continue
        if paras < 3 or text_len < 300:
            continue
        best_score = max(best_score, text_len)
    if not best_score:
        return None
    best, best_depth = None, -1
    for ident, (text_len, paras, depth, node) in stats.items():
        if node.tag not in ("div", "article", "section", "main"):
            continue
        cls = (node.cls() + " " + (node.attrs.get("id") or "")).lower()
        if any(h in cls for h in BAD_CONTAINER_HINTS):
            continue
        if paras < 3 or text_len < best_score * 0.9:
            continue
        if depth > best_depth:
            best, best_depth = node, depth
    return best


def text_of(node):
    buf = []
    for child in node.children:
        if child.tag is None:
            buf.append(child.text)
        elif child.tag in ("br",):
            buf.append("\n")
        elif child.tag not in SKIP_TAGS:
            buf.append(text_of(child))
    return "".join(buf)


def squash(text):
    return re.sub(r"[ \t\u3000]+", " ", (text or "").replace("\xa0", " ")).strip()


# ---------------------------------------------------------------- HTML -> Markdown
class Extractor:
    def __init__(self, page_url, heading_shift=1, max_chars=3600, max_images=3):
        self.page_url = page_url
        self.shift = heading_shift
        self.max_chars = max_chars
        self.max_images = max_images
        self.images = []

    # -- 行内
    def inline(self, node):
        out = []
        for child in node.children:
            tag = child.tag
            if tag is None:
                out.append(child.text)
            elif tag in SKIP_TAGS:
                continue
            elif tag == "br":
                out.append("\n")
            elif tag == "img":
                out.append(self.image_md(child) or "")
            elif tag == "a":
                label = squash(self.inline(child))
                href = self.abs(child.attrs.get("href", ""))
                if label and href:
                    out.append("[%s](%s)" % (label, href))
                else:
                    out.append(label)
            elif tag in ("strong", "b"):
                inner = squash(self.inline(child))
                out.append("**%s**" % inner if inner else "")
            elif tag in ("em", "i"):
                inner = squash(self.inline(child))
                out.append("*%s*" % inner if inner else "")
            elif tag == "code":
                inner = squash(text_of(child))
                out.append("`%s`" % inner if inner else "")
            else:
                out.append(self.inline(child))
        return "".join(out)

    def abs(self, href):
        if not href:
            return ""
        href = href.strip()
        if href.startswith(("#", "mailto:", "javascript:", "tel:")):
            return ""
        return urllib.parse.urljoin(self.page_url, href)

    def image_md(self, node):
        src = self.abs(node.attrs.get("src", "") or node.attrs.get("data-src", ""))
        if not src or any(h in src.lower() for h in SKIP_IMG_HINTS):
            return ""
        alt_raw = (node.attrs.get("alt") or "") + " " + (node.attrs.get("class") or "")
        if any(k in alt_raw.lower() for k in ("头像", "avatar", "emoji", "表情", "icon")):
            return ""
        for dim in ("width", "height"):
            val = (node.attrs.get(dim) or "").strip()
            if val.isdigit() and int(val) < 120:
                return ""
        if len(self.images) >= self.max_images:
            return ""
        alt = squash(node.attrs.get("alt", ""))[:60]
        self.images.append(src)
        safe = urllib.parse.quote(src, safe=":/?&=#%+,;@!$*'~")
        safe = safe.replace("(", "%28").replace(")", "%29").replace(" ", "%20")
        return "![%s](%s)" % (alt, safe)

    # -- 块级
    def blocks(self, node, depth=0):
        """按白名单抽取块级内容；命中小节黑名单的整节丢弃。"""
        out = []
        skip = False
        for child in node.children:
            tag = child.tag
            if tag is None:
                para = squash(child.text)
                if not skip and len(para) >= 30:
                    out.append(para)
                continue
            if tag in SKIP_TAGS or any(h in child.cls() for h in SKIP_CLASS_HINTS):
                continue

            if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
                raw_level = int(tag[1])
                title = squash(self.inline(child))
                if raw_level == 1:
                    skip = False  # README 一级标题只是页面名，丢弃但重置状态
                    continue
                title = title.replace("**", "").replace("`", "").strip()
                if raw_level == 2:
                    skip = bool(SECTION_SKIP.search(title))
                if not skip and title:
                    level = min(6, raw_level + self.shift)
                    out.append("%s %s" % ("#" * level, title))
                continue
            if skip:
                continue

            if tag == "p":
                text = squash(self.inline(child))
                if text:
                    out.append(text)
            elif tag in ("ul", "ol"):
                items = []
                for li in child.children:
                    if li.tag != "li":
                        continue
                    body = squash(self.inline(li))
                    if body and len(body) >= 6:
                        items.append("- " + body)
                if items:
                    out.append("\n".join(items[:8]))
            elif tag == "blockquote":
                text = squash(self.inline(child))
                if text:
                    out.append("> " + text)
            elif tag == "table":
                table = self.table_md(child)
                if table:
                    out.append(table)
            elif tag == "hr":
                out.append("---")
            elif tag == "pre":
                continue  # 主题对代码块做了模糊处理，且对成果展示无必要
            elif tag == "figure":
                for sub in child.children:
                    if sub.tag == "figcaption":
                        cap = squash(self.inline(sub))
                        if cap:
                            out.append("*%s*" % cap)
                    elif sub.tag:
                        sub_blocks = self.blocks(sub)
                        out.extend(b for b in sub_blocks if b.startswith("!["))
            elif tag == "img":
                img = self.image_md(child)
                if img:
                    out.append(img)
            elif tag in ("div", "section", "article", "main", "span", "dl", "dd",
                         "details", "summary", "center"):
                out.extend(self.blocks(child, depth + 1))
            else:
                text = squash(self.inline(child))
                if len(text) >= 40:
                    out.append(text)
        return out

    def table_md(self, node):
        rows = []
        for tr in find_all(node, "tr"):
            cells = []
            for cell in tr.children:
                if cell.tag in ("td", "th"):
                    cells.append(squash(self.inline(cell)).replace("|", "\\|"))
            if cells:
                rows.append(cells)
        if len(rows) < 2:
            return ""
        width = max(len(r) for r in rows)
        rows = [r + [""] * (width - len(r)) for r in rows]
        head = rows[0]
        body = rows[1:]
        lines = ["| " + " | ".join(head) + " |", "| " + " | ".join(["---"] * width) + " |"]
        for r in body:
            lines.append("| " + " | ".join(r) + " |")
        return "\n".join(lines)


LINK_ONLY_RE = re.compile(r"^(\[[^\]]*\]\([^)]*\)\s*)+$")


def polish(blocks):
    """去掉纯链接行、过短碎片、依赖清单式的列表，保证正文可读。"""
    out = []
    for block in blocks:
        plain = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", block)
        plain = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", plain)
        plain = re.sub(r"[#*`>\-\s]", "", plain)
        if len(plain) < 12:
            if not plain.strip() and "![" in block:
                out.append(block)  # 纯图片块（架构图/示意图）保留
            continue
        first = block.split("\n")[0]
        if block.startswith("#") or block.startswith("!["):
            out.append(block)
            continue
        if LINK_ONLY_RE.match(block.strip()):
            continue
        if block.startswith("**") and block.endswith("**") and block.count("**") == 2:
            block = block[2:-2].strip()
        if block.startswith("- "):
            items = block.split("\n")
            avg = sum(len(i) for i in items) / max(1, len(items))
            if avg < 12:  # 例如 "opencv-python"、"onnxruntime" 这类依赖清单
                continue
            out.append(block)
            continue
        if len(block) < 30:
            continue
        out.append(block)
    while out and out[0].startswith("#"):
        out.pop(0)  # 文章标题与页面标题重复
    return out


def trim_blocks(blocks, max_chars):
    """按字符预算裁剪，尽量在标题/段落边界截断。"""
    out = []
    total = 0
    for block in blocks:
        if total >= max_chars:
            break
        out.append(block)
        total += len(block)
    # 去掉末尾孤立标题
    while out and out[-1].startswith("#"):
        out.pop()
    return out


# ---------------------------------------------------------------- 图片落盘
IMG_RE = re.compile(r"!\[([^\]]*)\]\((https?://[^)\s]+)\)")


def download_images(md, slug, prune=False):
    folder = os.path.join(STATIC_DIR, slug)
    if prune and os.path.isdir(folder):
        for name in os.listdir(folder):
            try:
                os.remove(os.path.join(folder, name))
            except OSError:
                pass
    os.makedirs(folder, exist_ok=True)

    def repl(match):
        alt, url = match.group(1), match.group(2)
        try:
            data, final_url, ctype = http_get(url, timeout=45, retries=2)
        except Exception as exc:  # noqa: BLE001
            print("    [img-fail] %s (%s)" % (url[:70], str(exc)[:60]))
            return ""
        if len(data) > 3 * 1024 * 1024:
            print("    [img-skip] 过大 %s" % url[:70])
            return ""
        ext = os.path.splitext(urllib.parse.urlparse(final_url).path)[1].lower()
        if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
            ext = {"image/png": ".png", "image/gif": ".gif", "image/webp": ".webp"}.get(ctype, ".jpg")
        name = hashlib.md5(url.encode()).hexdigest()[:8] + ext
        with open(os.path.join(folder, name), "wb") as fh:
            fh.write(data)
        print("    [img-ok] %s -> /images/achievements/%s/%s" % (url[:56], slug, name))
        return "![%s](/images/achievements/%s/%s)" % (alt, slug, name)

    return IMG_RE.sub(repl, md)


# ---------------------------------------------------------------- Halo 接口
def api(method, path, body=None):
    auth = "Basic " + __import__("base64").b64encode(
        ("%s:%s" % (USER, PASS)).encode()
    ).decode()
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Authorization", auth)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=120) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw.strip() else None)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()[:600]


def post_index():
    status, data = api("GET", "/apis/api.content.halo.run/v1alpha1/posts?page=1&size=100")
    assert status == 200, (status, data)
    index = {}
    for item in data["items"]:
        index[item["spec"]["slug"]] = item
    return index


def split_sections(md):
    """把原稿按 `## 标题` 切成 {标题: 正文}，保留顺序。"""
    sections = []
    current = ("_intro", [])
    for line in (md or "").replace("\r\n", "\n").split("\n"):
        if line.startswith("## "):
            sections.append(current)
            current = (line[3:].strip(), [])
        else:
            current[1].append(line)
    sections.append(current)
    return [(title, "\n".join(body).strip()) for title, body in sections if title != "_intro" or "\n".join(body).strip()]


# ---------------------------------------------------------------- 主流程
def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def crawl_source(source):
    url = source["url"]
    print("  -> 抓取 %s" % url)
    data, final_url, ctype = http_get(url)
    html_text = decode_html(data, ctype)
    root = build_dom(html_text)

    node = pick_content(root, source.get("content_selector", ""))
    if node is not None and len(text_of(node)) < 600:
        print("    [info] 选择器命中但正文过少(%d 字符)，改用自动定位" % len(text_of(node)))
        node = None
    if node is None:
        node = auto_content(root)
        if node is None:
            node = find_first(root, "article") or find_first(root, "main") or root
        print("    [info] 选择器未命中，自动定位正文容器 <%s class=%s>" % (node.tag, node.attrs.get("class", "")[:40]))

    extractor = Extractor(
        final_url,
        heading_shift=int(source.get("heading_shift", 1)),
        max_chars=int(source.get("max_chars", 3600)),
        max_images=int(source.get("max_images", 3)),
    )
    blocks = trim_blocks(polish(extractor.blocks(node)), extractor.max_chars)
    body = "\n\n".join(blocks)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    print("    %d 字符 / %d 图 / %d 段" % (len(body), len(extractor.images), len(blocks)))
    return {"url": url, "final_url": final_url, "body": body, "images": len(extractor.images)}


def build_markdown(project, sections, crawled, stamp):
    by_title = {t: b for t, b in sections}
    intro = by_title.get("作品说明") or (sections[0][1] if sections else "")
    info = by_title.get("项目信息", "")
    usage = by_title.get("体验方式", "")

    parts = []
    if intro:
        parts.append("## 作品说明\n\n" + intro)

    parts.append(
        "## 技术方案与实现\n\n"
        "> 本节内容由爬虫从公开技术资料抓取整理，用于补充项目的技术背景与实现路径，"
        "抓取时间 %s。原文版权归来源方所有，链接见文末「参考资料」。\n" % stamp
    )
    for item in crawled:
        if item.get("summary"):
            parts.append(item["summary"].strip())
        header = "### %s" % item["label"] if item.get("label") else "### 技术资料摘录"
        parts.append(header + "\n\n来源：<%s>" % item["final_url"])
        if item["body"]:
            parts.append(item["body"])
        else:
            parts.append("*（来源页正文提取为空，请检查 content_selector 配置）*")

    if info:
        parts.append("## 项目信息\n\n" + info)
    if usage:
        parts.append("## 体验方式\n\n" + usage)

    refs = ["- [%s](%s)" % (i.get("label") or "技术资料", i["final_url"]) for i in crawled]
    refs.append("- 抓取时间：%s，抓取脚本：`scripts/crawl_achievements.py`" % stamp)
    parts.append("## 参考资料\n\n" + "\n".join(refs))
    return "\n\n".join(parts).strip() + "\n"


def main():
    args = sys.argv[1:]
    dry = "--dry-run" in args
    no_images = "--no-images" in args
    prune = "--prune-images" in args
    only = None
    if "--slug" in args:
        only = args[args.index("--slug") + 1]

    sys.path.insert(0, HERE)
    from render_post_content import md_to_html  # 复用同一套 markdown 渲染

    config = load_config()
    stamp = time.strftime("%Y-%m-%d")
    try:
        posts = post_index()
    except Exception as exc:  # noqa: BLE001
        if not dry:
            raise
        print("[warn] 读取文章列表失败（%s），dry-run 仅展示抓取内容" % str(exc)[:80])
        posts = {}

    total = 0
    for project in config["projects"]:
        slug = project["slug"]
        if only and slug != only:
            continue
        print("[%s] %s" % (slug, project.get("title", "")))
        crawled = []
        for source in project["sources"]:
            try:
                item = crawl_source(source)
            except Exception as exc:  # noqa: BLE001
                print("    [fail] %s" % exc)
                continue
            item["label"] = source.get("label", "")
            item["summary"] = source.get("summary", "")
            crawled.append(item)
        if not crawled:
            print("    [skip] 无可用来源")
            continue

        body_md = "\n\n".join(i["body"] for i in crawled)
        if not no_images and not dry and IMG_RE.search(body_md):
            for item in crawled:
                item["body"] = download_images(item["body"], slug, prune=prune)

        post = posts.get(slug)
        if post is None and not dry:
            print("    [skip] 站点上没有 slug=%s 的文章" % slug)
            continue
        sections = []
        if post is not None:
            status, head = api(
                "GET", "/apis/api.console.halo.run/v1alpha1/posts/%s/head-content" % post["metadata"]["name"]
            )
            original_raw = (head or {}).get("raw", "") if status == 200 else ""
            sections = split_sections(original_raw)

        markdown_text = build_markdown(project, sections, crawled, stamp)
        html_text = md_to_html(markdown_text)

        if dry:
            print("=" * 70)
            print(markdown_text)
            print("=" * 70)
            continue

        name = post["metadata"]["name"]
        status, res = api(
            "PUT",
            "/apis/api.console.halo.run/v1alpha1/posts/%s/content" % name,
            {"raw": markdown_text, "content": html_text, "rawType": "markdown"},
        )
        if status != 200:
            print("    [fail] 写入正文 %s %s" % (status, res))
            continue
        st2, res2 = api("PUT", "/apis/api.console.halo.run/v1alpha1/posts/%s/publish" % name, {})
        print("    [ok] 正文 %d 字符 markdown / %d 字节 HTML，发布=%s" % (len(markdown_text), len(html_text), st2))
        if st2 != 200:
            print("        ", str(res2)[:200])
        total += 1

    if not dry:
        print("\n完成 %d 个项目" % total)


if __name__ == "__main__":
    main()
