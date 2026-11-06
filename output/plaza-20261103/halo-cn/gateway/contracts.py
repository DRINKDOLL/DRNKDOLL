# -*- coding: utf-8 -*-
"""预留接口契约（输入输出约定 + 校验规则）。

本文档对应《广场接入说明》4.4「服务态路由（L2）」及 7「事件对接（EV）」，
并额外预留「实训工坊」后续对接接口。

接口分三类：
  一、IF-08  作品查询（广场作为「服务态提供方」，供论坛/自学/工坊后台调用）
  二、IF-07  验收状态消费（广场作为「服务态调用方」，向实训工坊取验收结论）
  三、预留   实训工坊后续对接接口（作品验收结果回写、徽章查询等）

所有「服务态」接口统一走 L2 签名（X-App-Key + HMAC-SHA256），只读，限流 100 QPS，
不返回草稿/待审/已下架/受限作品（《说明》4.4 第（四）组）。

字段类型说明：str=字符串；int=整数；bool=布尔；list[X]=X 数组；
  optional 表示可空/可省略；iso8601 表示 ISO8601 时间字符串（如 "2026-11-05T22:00:00+08:00"）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# 通用分页参数与校验
# ---------------------------------------------------------------------------
@dataclass
class PageQuery:
    page: int = 1          # 页码，从 1 起，默认 1
    size: int = 20         # 每页条数，默认 20，1 ≤ size ≤ 100（批量接口单次 ≤ 100，见《说明》第 8 章）

    def validate(self) -> list[str]:
        """返回错误信息列表，空表示通过。"""
        errs = []
        if self.page < 1:
            errs.append("page 必须 ≥ 1")
        if not (1 <= self.size <= 100):
            errs.append("size 必须在 1~100 之间")
        return errs


# ---------------------------------------------------------------------------
# 一、IF-08 作品查询（广场提供，L2 只读）
# ---------------------------------------------------------------------------
@dataclass
class WorkSummary:
    """作品摘要（对外只读，绝不返回草稿/待审/下架/受限作品）。"""
    work_id: str            # 作品主键 workId
    title: str              # 标题
    cover_url: str          # 封面（媒体签名 URL，30 分钟有效）
    author_uid: str         # 作者 uid
    project_id: str         # 关联项目 projectId（可空串）
    team_id: str            # 关联团队 teamId（可空串）
    category: str           # 分类
    tags: list[str]         # 标签
    like_count: int         # 点赞数
    collect_count: int      # 收藏数
    review_status: str      # 审核状态：pending / passed / rejected
    certified: bool         # 认证徽章（由工坊验收结论派生，不可手动标注）
    publish_time: str       # 发布时间 iso8601
    visibility: str         # 可见性：public / restricted（受限作品不对外返回）


@dataclass
class WorkDetail(WorkSummary):
    """作品详情摘要（IF-08 按 workId 查询时返回，比列表多摘要字段）。"""
    excerpt: str = ""       # 摘要
    member_uids: list[str] = field(default_factory=list)  # 团队成员 uid 列表


@dataclass
class WorkPage:
    """分页列表返回。"""
    page: int
    size: int
    total: int
    items: list[WorkSummary]


# ---------------------------------------------------------------------------
# 二、IF-07 验收状态消费（广场调用实训工坊，L2）
# ---------------------------------------------------------------------------
@dataclass
class AcceptanceResult:
    """实训工坊返回的作品验收结论。"""
    project_id: str         # 项目 projectId
    team_id: str            # 团队 teamId
    accepted: bool          # 是否验收通过
    score: float | None     # 评分（0~100，未验收为 None）
    comment: str            # 评语（可空串）
    verified_at: str        # 验收时间 iso8601（可空串）


@dataclass
class BadgeState:
    """认证徽章状态（广场侧派生）。"""
    work_id: str
    certified: bool
    verified_at: str | None
    pending_check: bool     # 是否「待核验」（IF-07 不可用时沿用上次结果）


# ---------------------------------------------------------------------------
# 三、预留：实训工坊后续对接接口
# ---------------------------------------------------------------------------
@dataclass
class LessonProjection:
    """作品转课例（EV-06）载荷。"""
    work_id: str
    operator_uid: str
    purpose: str            # 转课例用途
    target_course_id: str   # 目标课程 id


@dataclass
class EventEnvelope:
    """事件通用信封（鉴权文档 3.7 事件通用字段）。"""
    event_id: str           # 全局唯一事件 id（幂等去重键）
    event_type: str         # EV-04 / EV-05 / EV-06
    timestamp: str          # 事件发生时间 iso8601
    source: str             # 事件来源（工坊 / 广场 / 自学平台）
    payload: dict[str, Any] # 事件载荷
