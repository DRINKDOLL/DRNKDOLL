# -*- coding: utf-8 -*-
"""修改仪表盘：删除快捷访问(quick-action)，通知(notifications)扩展到整行，标题改"个人中心"。

对 widgets-BLhVoogH.js 做三类精确替换：
1. 删除 5 个断点布局里的 core:quick-action 条目（含末尾逗号）
2. core:notifications 条目：w:6 -> w:12，x:6 -> x:0
3. 通知标题 e.$t(`core.dashboard.widgets.presets.notification.title`) -> `个人中心`
"""
import re

SRC = r"C:/Users/LENOVO/Desktop/成果广场/output/plaza-20261103/scripts/_widgets_orig.js"
DST = r"C:/Users/LENOVO/Desktop/成果广场/output/plaza-20261103/scripts/_widgets_new.js"

s = open(SRC, encoding="utf-8").read()
orig_len = len(s)

# 1) 删除 quick-action 条目（含其前面的逗号分隔符）
#    条目形如 {i:`uuid`,x:N,y:N,w:6,h:12,minW:3,minH:6,id:`core:quick-action`,config:{enabled_items:[...]}}
qa_pat = re.compile(
    r",\{i:`[0-9a-f-]+`,x:\d+,y:\d+,w:\d+,h:\d+,minW:\d+,minH:\d+,"
    r"id:`core:quick-action`,config:\{enabled_items:\[[^\]]*\]\}\}"
)
s, qa_cnt = qa_pat.subn("", s)

# 2) notifications 条目 w:6 -> w:12, x:6 -> x:0
notif_pat = re.compile(
    r"(\{i:`[0-9a-f-]+`,x:)\d+(,y:\d+,w:)\d+(,h:\d+,minW:\d+,minH:\d+,id:`core:notifications`,config:\{\})"
)
def notif_repl(m):
    return m.group(1) + "0" + m.group(2) + "12" + m.group(3)
s, notif_cnt = notif_pat.subn(notif_repl, s)

# 3) 标题：通知 -> 个人中心
title_old = "e.$t(`core.dashboard.widgets.presets.notification.title`)"
title_new = "`个人中心`"
title_cnt = s.count(title_old)
s = s.replace(title_old, title_new)

open(DST, "w", encoding="utf-8").write(s)

print(f"原长度 {orig_len} -> 新长度 {len(s)}")
print(f"删除 quick-action 条目: {qa_cnt} 处（应为 5）")
print(f"扩展 notifications 条目: {notif_cnt} 处（应为 5）")
print(f"标题替换: {title_cnt} 处（应为 1）")

# 校验
assert qa_cnt == 5, f"quick-action 删除数异常: {qa_cnt}"
assert notif_cnt == 5, f"notifications 扩展数异常: {notif_cnt}"
assert title_cnt == 1, f"标题替换数异常: {title_cnt}"
assert "core:quick-action" not in re.findall(r"id:`core:quick-action`", s), "仍残留 quick-action 布局条目"
print("\n全部校验通过")
