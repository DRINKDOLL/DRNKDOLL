#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""主题模板中文化：替换主题里硬编码的英文文案（不改结构、不动样式类名）。

Halo 主题的 i18n 语言包（i18n/zh_CN.properties）是完整的，英文残留只来自模板中
直接写死的文案，主要是页脚版权句。本脚本按“整句替换”处理，可重复执行。
"""
import argparse
import os
import shutil
import sys

# 英文原文 -> 中文译文（保持前后标签与标点结构不变）
REPLACEMENTS = [
    # 例：<a ...>站点名</a>. All Rights Reserved. Powered by <a>Halo</a>.
    ("</a>. All Rights Reserved. Powered by", "</a> 版权所有，保留所有权利。技术支持："),
    ("All Rights Reserved.", "版权所有，保留所有权利。"),
    ("Powered by", "技术支持："),
]


def patch_file(path):
    with open(path, encoding="utf-8") as f:
        original = f.read()

    text = original
    hits = []
    for en, zh in REPLACEMENTS:
        if en in text:
            hits.append((en, zh, text.count(en)))
            text = text.replace(en, zh)

    if not hits:
        return None

    shutil.copyfile(path, path + ".bak")
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True, help="Halo 数据目录，主题位于 <workdir>/themes")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    themes_root = os.path.join(args.workdir, "themes")
    if not os.path.isdir(themes_root):
        print("  主题目录尚未生成（首次启动后才会释放主题包），跳过")
        return 0

    total = 0
    for theme in sorted(os.listdir(themes_root)):
        tdir = os.path.join(themes_root, theme)
        if not os.path.isdir(tdir):
            continue
        for root, _dirs, files in os.walk(os.path.join(tdir, "templates")):
            for name in files:
                if not name.endswith((".html", ".htm")):
                    continue
                path = os.path.join(root, name)
                rel = os.path.relpath(path, os.path.dirname(args.workdir)).replace("\\", "/")
                if args.dry_run:
                    with open(path, encoding="utf-8") as f:
                        content = f.read()
                    for en, zh in REPLACEMENTS:
                        if en in content:
                            print("  [dry-run] %s : %r -> %r" % (rel, en, zh))
                    continue
                hits = patch_file(path)
                if hits:
                    total += len(hits)
                    for en, zh, n in hits:
                        print("  已中文化 %s  (%d 处)  %r -> %r" % (rel, n, en, zh))

    if total == 0 and not args.dry_run:
        print("  模板已全部为中文，无需改动")
    else:
        print("  共替换 %d 处硬编码英文" % total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
