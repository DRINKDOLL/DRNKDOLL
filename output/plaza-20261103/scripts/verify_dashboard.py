# -*- coding: utf-8 -*-
"""验证 _widgets_new.js 的布局修改结果。"""
import re

s = open(r"C:/Users/LENOVO/Desktop/成果广场/output/plaza-20261103/scripts/_widgets_new.js", encoding="utf-8").read()
i = s.find("var le=")
seg = s[i:i+6000]

print("=== notifications 布局条目（x/y/w/h） ===")
for m in re.finditer(r"\{i:`[0-9a-f-]+`,x:(\d+),y:(\d+),w:(\d+),h:(\d+),minW:\d+,minH:\d+,id:`core:notifications`", seg):
    print(f"  x={m.group(1)} y={m.group(2)} w={m.group(3)} h={m.group(4)}")

qa = len(re.findall(r"id:`core:quick-action`", seg))
print("\nquick-action 布局条目残留:", qa, "（应为 0）")

# 标题
title_idx = s.find("title:`个人中心`")
print("\n标题改为「个人中心」:", title_idx > 0)

# 统计卡片是否保留
stats = re.findall(r"id:`core:(post|comment|user|view):stats`", seg)
print("统计卡片 widget 保留:", len(stats), "个")
