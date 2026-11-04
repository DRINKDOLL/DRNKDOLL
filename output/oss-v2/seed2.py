import json, base64, urllib.request, urllib.error
BASE="http://127.0.0.1:8092"
H={"Authorization":"Basic "+base64.b64encode(b"admin:Passw0rd!2026").decode(),"Content-Type":"application/json"}
op=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def req(m,p,b=None):
    d=json.dumps(b).encode() if b is not None else None
    r=urllib.request.Request(BASE+p,data=d,headers=H,method=m)
    try:
        with op.open(r,timeout=30) as x:
            raw=x.read().decode(); return x.status,(json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as e: return e.code, e.read().decode()[:200]

# 1. 清空旧帖
st,r=req("GET","/apis/content.halo.run/v1alpha1/posts?page=0&size=50")
for it in r.get("items",[]):
    n=it["metadata"]["name"]
    c,_=req("DELETE",f"/apis/content.halo.run/v1alpha1/posts/{n}")
    print("del",c,n)

CATS={"实训项目":"cat-sqi57crw","竞赛作品":"cat-gsu9omoo","算法模型":"cat-i1uojun4","系统应用":"cat-rew7zxzj"}
POSTS=[
 ("智能巡逻机器人自主路径规划","实训项目","robot",
  "基于 ROS2 与激光雷达建图，实现校园复杂路况下的自主巡逻与避障，已在模拟街区完成 200 小时联调。",
  "- 技术栈：ROS2 / SLAM / YOLOv8 / C++\n- 团队：4 人（队长 + 感知 + 控制 + 前端）\n- 指导老师：警务技术实训中心\n- 开发周期：2026 春季学期"),
 ("涉诈资金流向可视化分析平台","竞赛作品","network",
  "面向电诈案件的资金链路追踪工具，支持万级账户关系图秒级渲染与可疑团伙自动聚类。",
  "- 技术栈：Neo4j / Vue3 / Spring Boot / ECharts\n- 团队：3 人\n- 获奖：省级竞赛二等奖\n- 开发周期：2026 春季学期"),
 ("密集人群异常行为识别模型","算法模型","crowd",
  "基于 YOLOv8 与时空注意力机制，在自建校园数据集上异常行为召回率达 92.4%。",
  "- 技术栈：PyTorch / YOLOv8 / OpenCV\n- 数据规模：标注样本 1.8 万帧\n- 指标：召回率 92.4%，误报率 6.1%\n- 已通过工坊终期验收"),
 ("校园反诈宣传小程序","系统应用","phone",
  "覆盖 12 类高发骗局的情景模拟答题，上线首月触达 3200 人次。",
  "- 技术栈：微信小程序 / Spring Boot / MySQL\n- 团队：5 人\n- 运营数据：首月 3200 人次，答题完成率 68%"),
 ("电子物证取证工具箱","实训项目","forensic",
  "集成镜像固定、哈希校验与时间线还原的取证流程工具，输出符合规范的取证报告。",
  "- 技术栈：Python / PyQt / Volatility\n- 团队：3 人\n- 验收评分：92 分（优秀）"),
 ("卡口车牌识别与轨迹还原","算法模型","traffic",
  "多路视频流车牌识别与跨镜头轨迹拼接，支持重点车辆布控预警。",
  "- 技术栈：YOLOv8 / PaddleOCR / Kafka\n- 处理能力：16 路视频流并发\n- 识别准确率：97.3%"),
]
for title,cat,seed,ex,detail in POSTS:
    body={"post":{"apiVersion":"content.halo.run/v1alpha1","kind":"Post",
      "metadata":{"name":"","generateName":"post-"},
      "spec":{"title":title,"slug":"work-"+seed,"categories":[CATS[cat]],"tags":["成果广场"],
        "cover":"https://picsum.photos/seed/%s/1200/675"%seed,
        "excerpt":{"autoGenerate":False,"raw":ex},
        "publish":True,"pinned":False,"allowComment":True,"visible":"PUBLIC","priority":0,"deleted":False,"template":"","htmlMetas":[]}},
      "content":{"raw":"## 作品说明\n\n"+ex+"\n\n## 项目信息\n\n"+detail+"\n\n## 体验方式\n\n校内用户可直接申请演示账号；访客可观看演示视频。\n","content":"","rawType":"markdown"},
      "publish":True}
    st,r=req("POST","/apis/api.console.halo.run/v1alpha1/posts",body)
    print("add",st,title)
