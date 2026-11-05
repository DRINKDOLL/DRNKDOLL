# -*- coding: utf-8 -*-
"""列出 widgets.js 默认布局 le 中 quick-action 与 notifications 的所有断点条目。"""
import re

path = r"C:/Users/LENOVO/Desktop/成果广场/output/plaza-20261103/scripts/_widgets_orig.js"
s = open(path, encoding="utf-8").read()

i = s.find("var le={")
print("le 起始:", i)

pat = re.compile(r"\{i:`[0-9a-f-]+`,x:\d+,y:\d+,w:\d+,h:\d+,minW:\d+,minH:\d+,id:`core:(quick-action|notifications)`")
for m in pat.finditer(s):
    print(m.group(0))
print("总数:", len(pat.findall(s)))
