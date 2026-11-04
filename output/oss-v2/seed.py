import json, base64, urllib.request, urllib.error, sys

BASE = "http://127.0.0.1:8092"
AUTH = base64.b64encode(b"admin:Passw0rd!2026").decode()
H = {"Authorization": "Basic " + AUTH, "Content-Type": "application/json"}

def req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, headers=H, method=method)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(r, timeout=20) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]

cats = ["实训项目", "竞赛作品", "算法模型", "系统应用"]
cat_names = {}
for i, c in enumerate(cats):
    st, r = req("POST", "/apis/content.halo.run/v1alpha1/categories", {
        "apiVersion": "content.halo.run/v1alpha1", "kind": "Category",
        "metadata": {"name": "", "generateName": "cat-"},
        "spec": {"displayName": c, "slug": "cat-%d" % i, "description": c, "priority": i,
                 "children": [], "cover": "", "template": "", "hideFromList": False, "preventParentPostCascadeQuery": False}
    })
    print("cat", c, st, (r.get("metadata", {}) or {}).get("name") if isinstance(r, dict) else r)
    if st in (200, 201):
        cat_names[c] = r["metadata"]["name"]

posts = [
    ("智能巡逻机器人自主路径规划", "实训项目", "基于 ROS2 与激光雷达建图，实现校园复杂路况下的自主巡逻与避障，已在模拟街区完成 200 小时联调。", "robot"),
    ("涉诈资金流向可视化分析平台", "竞赛作品", "面向电诈案件的资金链路追踪工具，支持万级账户关系图秒级渲染与可疑团伙自动聚类。", "network"),
    ("密集人群异常行为识别模型", "算法模型", "基于 YOLOv8 与时空注意力机制，在自建校园数据集上异常行为召回率达 92.4%。", "crowd"),
    ("校园反诈宣传小程序", "系统应用", "覆盖 12 类高发骗局的情景模拟答题，上线首月触达 3200 人次。", "phone"),
    ("电子物证取证工具箱", "实训项目", "集成镜像固定、哈希校验与时间线还原的取证流程工具，输出符合规范的取证报告。", "forensic"),
    ("卡口车牌识别与轨迹还原", "算法模型", "多路视频流车牌识别与跨镜头轨迹拼接，支持重点车辆布控预警。", "traffic"),
]

for title, cat, excerpt, seed in posts:
    body = {
        "apiVersion": "content.halo.run/v1alpha1", "kind": "Post",
        "metadata": {"name": "", "generateName": "post-"},
        "spec": {
            "title": title, "slug": "work-" + seed,
            "categories": [cat_names.get(cat, "")] if cat_names.get(cat) else [],
            "tags": [], "cover": "https://picsum.photos/seed/%s/1200/675" % seed,
            "excerpt": {"autoGenerate": False, "raw": excerpt},
            "content": {"raw": "## 项目简介\n\n" + excerpt + "\n\n## 技术栈\n\n- 开发周期：一学期\n- 团队成员：4 人\n- 指导老师：实训中心\n\n## 体验方式\n\n可申请校内演示账号，或观看演示视频。", "content": ""},
            "publish": True, "pinned": False, "allowComment": True, "visible": "PUBLIC",
            "priority": 0, "deleted": False, "template": "", "htmlMetas": []
        }
    }
    st, r = req("POST", "/apis/content.halo.run/v1alpha1/posts", body)
    name = (r.get("metadata", {}) or {}).get("name") if isinstance(r, dict) else None
    print("post", title, st, name, "" if name else str(r)[:200])
    if name:
        for _ in range(2):
            st2, r2 = req("POST", "/apis/content.halo.run/v1alpha1/posts/%s/publish" % name, {"headSnapshot": ""})
            print("   publish", st2, str(r2)[:120])
            if st2 in (200, 201):
                break
