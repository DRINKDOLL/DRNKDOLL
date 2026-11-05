# -*- coding: utf-8 -*-
"""删除 console-DWnzr9kt.js 中指定模块的侧边栏菜单定义（保留 meta 其余字段）。

原理：Halo 控制台侧边栏菜单由各路由 module 的 meta.menu 字段动态生成，
删除 menu 字段后该路由不再出现在侧边栏，但路由组件与后端接口完全保留。
"""
import sys
import gzip

BACKTICK = "`"

# 需要删除 menu 字段的 7 个模块（精确匹配 grep 输出的 menu:{...} 串）
MENUS_TO_REMOVE = [
    f"menu:{{name:{BACKTICK}core.sidebar.menu.items.menus{BACKTICK},group:{BACKTICK}interface{BACKTICK},icon:we(Se),priority:1}},",
    f"menu:{{name:{BACKTICK}core.sidebar.menu.items.themes{BACKTICK},group:{BACKTICK}interface{BACKTICK},icon:Oe(Ee),priority:0}},",
    f"menu:{{name:{BACKTICK}core.sidebar.menu.items.plugins{BACKTICK},group:{BACKTICK}system{BACKTICK},icon:it(nt),priority:0}},",
    f"menu:{{name:{BACKTICK}core.sidebar.menu.items.users{BACKTICK},group:{BACKTICK}system{BACKTICK},icon:vt(gt),priority:1,mobile:!0}},",
    f"menu:{{name:{BACKTICK}core.sidebar.menu.items.overview{BACKTICK},group:{BACKTICK}system{BACKTICK},icon:Re(Ie),priority:3}},",
    f"menu:{{name:{BACKTICK}core.sidebar.menu.items.backup{BACKTICK},group:{BACKTICK}system{BACKTICK},icon:Pe(Me),priority:4}},",
    f"menu:{{name:{BACKTICK}core.sidebar.menu.items.tools{BACKTICK},group:{BACKTICK}system{BACKTICK},icon:mt(ft),priority:5}},",
]

# 保留的 menu 字段（用于校验，不应被误删）
KEEP_MARKERS = [
    "items.attachments",
    "items.comments",
    "items.single_pages",
    "items.posts",
    "items.dashboard",
    "items.settings",
]


def main(path):
    with open(path, "r", encoding="utf-8") as f:
        s = f.read()

    removed = []
    for m in MENUS_TO_REMOVE:
        cnt = s.count(m)
        if cnt == 1:
            s = s.replace(m, "")
            removed.append(m)
        elif cnt > 1:
            print(f"[多匹配 {cnt} 次] {m[:60]}...")
            s = s.replace(m, "")
            removed.append(m)
        else:
            print(f"[未找到] {m[:60]}...")

    # 校验：保留项仍在
    for k in KEEP_MARKERS:
        assert k in s, f"保留项丢失！{k}"

    with open(path, "w", encoding="utf-8") as f:
        f.write(s)

    print(f"\n成功删除 {len(removed)} 个菜单字段：")
    for r in removed:
        print("  -", r[:70])
    print("\n保留项校验通过：", ", ".join(KEEP_MARKERS))


if __name__ == "__main__":
    main(sys.argv[1])
