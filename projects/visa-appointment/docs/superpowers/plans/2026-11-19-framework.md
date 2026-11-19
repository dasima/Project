# 签证预约爬虫与业务框架实施计划

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans to implement task by task. 本次用户已要求搭建框架，在现有 `codex/visa-appointment-system` 分支直接执行。

**Goal:** 建立独立运行的 Django 子项目，用真实 HTTP 采集器访问本地模拟放号站点，跑通监测、匹配、持久化预约意图、提交和结果核对，并提供管理后台、查询 API、部署及测试。

**Architecture:** 模块化业务后台与独立采集/执行 Worker；爬虫协议与业务模型解耦。PostgreSQL 是 Compose 环境事实来源，SQLite 用于无需 Docker 的本地开发。真实法国、德国、英国渠道仅登记为未启用，不执行真实预约。

**Tech Stack:** Python 3.12+、Django 5.2、httpx、PostgreSQL 17、Gunicorn、Docker Compose；测试使用 Django/unittest。

**Spec:** `../specs/2026-11-19-europe-student-visa-appointment-design.md`

## Global constraints

- 所有文件放在 `projects/visa-appointment/`；根 README 与独立 CI 可相应更新。
- 不改动 Parcelink 的业务代码、依赖和部署。
- 框架只启用本地模拟渠道；不伪造真实站点适配器、成功率或已完成生产接入。
- 一个案件至多一个有效尝试；提交前持久化意图，超时或进程中断先核对，不盲目重提。
- API 使用会话或 Bearer token 认证；演示提供方使用独立 token；端口只绑定本机。
- 不提交证件、真实账户、Cookie、私有环境、数据库或生成产物。
- 框架验收不承诺设计中的 100ms 目标；先记录关键时间并验证正确性。

## Task 1: 领域模型和运营后台

**Owns:** `backend/apps/core/`。

**Produces:** 以下 Django 模型，字段命名为跨任务接口：

- `Channel`: `name, code(unique), country, visa_category, center, adapter(default=manual), base_url, enabled(default=False), auto_book(default=False), poll_interval_seconds(default=30), next_poll_at(nullable), last_status, last_error, last_polled_at(nullable), lease_token(blank), lease_expires_at(nullable), created_at, updated_at`。
- `ApplicationCase`: `reference(unique), display_name, channel(FK), status(READY/WAITING/BOOKED/PAUSED/NEEDS_REVIEW), earliest_date, latest_date, authorization_expires_at, auto_submit(default=False), priority(default=100), created_at, updated_at`。日期范围与授权有效性检查。
- `SlotObservation`: `channel(FK), slot_id, starts_at, observed_at, available(default=True), unique(channel,slot_id)`。
- `BookingAttempt`: `operation_id(UUID unique default uuid4), case(FK), observation(FK nullable), status(PREPARED/SUBMITTING/RECONCILING/CONFIRMED/REJECTED/HUMAN_REQUIRED), confirmation_reference(blank), detail(blank), created_at, updated_at, submitted_at(nullable), confirmed_at(nullable)`；数据库约束对 PREPARED/SUBMITTING/RECONCILING/HUMAN_REQUIRED/CONFIRMED 保持每案件至多一个，已确认案件禁止普通重复预约。
- `CrawlRun`: `channel(FK), status, started_at, finished_at, slot_count(default=0), detail(blank), duration_ms(default=0)`。
- `AuditEvent`: `event_type, case(FK nullable), attempt(FK nullable), detail(blank), created_at`。

- [x] 先写模型行为测试：重复有效尝试受数据库约束、明确失败后允许新尝试、非法日期范围被拒绝。
- [x] 实现模型、迁移和管理后台；有外部副作用的尝试/审计只读，渠道与案件允许管理并校验。
- [x] 执行 `python manage.py test apps.core` 和 `makemigrations --check --dry-run`。

## Task 2: 独立爬虫协议与 HTTP 采集器

**Owns:** `backend/apps/crawler/`，不依赖 ORM。

**Produces:** `types.py` 中 `Slot(slot_id: str, starts_at: datetime)`；`ObservationResult(status: str, slots: tuple[Slot,...]=(), detail: str='', retry_after: int|None=None)`；`BookingRequest(operation_id: str, case_reference: str, slot_id: str)`；`SubmissionResult(status: str, confirmation_reference: str='', detail: str='')`。状态字符串直接作为跨模块协议，不绑定 Django。

`http.py` 提供 `HttpDemoAdapter(base_url: str, token: str, allowed_hosts: tuple[str,...], timeout: float=5.0)`，方法 `observe() -> ObservationResult`、`submit(request: BookingRequest) -> SubmissionResult`、`reconcile(operation_id: str) -> SubmissionResult`。

**External protocol:** `GET {base_url}/availability/` 返回 HTML：`<main data-state="available|no_slots|auth_required|challenge"><article data-slot-id="..." data-starts-at="ISO8601 with offset"></article></main>`。`POST {base_url}/bookings/` JSON 为 BookingRequest 字段，返回 `{status: confirmed|rejected|unknown|human_required, confirmation_reference, detail}`。`GET {base_url}/bookings/{operation_id}/` 核对结果。全程 `Authorization: Bearer <demo token>`。

观察结果：`available/no_slots/auth_required/challenge/rate_limited/parser_changed/transient_error/manual_required`。提交结果只接受 `confirmed/rejected/unknown/human_required`；只有确认编号非空的 confirmed 才算确认。确定不存在的 operation 返回 rejected；超时和不能确定的响应返回 unknown。404 查询表示未找到，但需与协议明确绑定。

- [x] 使用本地 HTTP 测试服务器先验证解析、HTTP 401/429、格式变化及提交超时的行为失败。
- [x] 实现 HTMLParser 解析、明确状态分类、超时、有界正文、主机允许列表和禁止重定向。禁止在错误详情存储 token/原始敏感页面。
- [x] 执行 `python manage.py test apps.crawler`，只访问本地受控测试服务器。

## Task 3: 持久化调度、匹配与预约执行

**Owns:** `backend/apps/automation/`。

**Consumes:** Task 1 模型与 Task 2 协议；`settings.DEMO_PROVIDER_TOKEN, settings.CRAWLER_ALLOWED_HOSTS`。

**Produces:** `services.py`：`poll_channel(channel_id: int, *, execute: bool=False) -> CrawlRun|None`；`execute_attempt(attempt_id: int) -> BookingAttempt`；`reconcile_attempt(attempt_id: int) -> BookingAttempt`。`poll_channel` 默认只建 PREPARED 任务；worker 角色控制监测与执行。

**Commands:** `runworker --role monitor|booking|all --once --interval 1`；`reconcile_bookings --once`。每轮查询持久化到期任务；SQLite 本地模式单 worker，PostgreSQL 采用条件更新/短事务抢租约。

- [x] 先写行为测试：同一机会重复轮询不重复预约、无授权/日期不合不提交、未知提交进入核对、已确认案件不重提、关闭的渠道不访问。
- [x] 采集前通过条件更新领取短租约，收集结果写 CrawlRun/Observation；完成时以 token 核对租约；为匹配到的合格案件持久化尝试与审计。
- [x] POST 前将状态原子改为 SUBMITTING；结果不明进 RECONCILING；进程遗留 SUBMITTING 只核对；PREPARED 可以竞争领取但不得重复发送。
- [x] `adapter != demo_http` 或 `enabled=False` 不执行网络；实时复核案件授权、日期、开关；人工状态保留有效约束。
- [x] 执行 `python manage.py test apps.automation`。

## Task 4: 应用入口、演示提供方、API、部署和集成

**Owns:** `backend/config/`、`backend/apps/api/`、`backend/apps/demo_provider/`、`backend/manage.py`、项目 README/依赖/部署/环境与仓库 CI。

- [x] 配置 SQLite/环境变量 PostgreSQL、Django admin、健康检查；拒绝生产缺失密钥。
- [x] 先验证未认证 API 不可访问、demo 关闭时不可访问、重复 operation_id 结果一致。
- [x] 实现保护的只读 API `/api/channels/`、`/api/cases/`、`/api/observations/`、`/api/attempts/`、`/api/crawl-runs/` 和 `/healthz/`；默认分页/上限，不暴露凭据。
- [x] 演示提供方提供 HTML 放号、原子容量扣减和幂等确认查询；仅 `ENABLE_DEMO_PROVIDER=True` 时启用并校验独立 token。开发命令 `seed_demo --base-url http://127.0.0.1:8010/demo-provider` 创建一条启用的模拟渠道、虚拟案件与关闭的三国渠道；不可更改已发生预约的案件来重置状态。
- [x] 实现 `demo_pipeline` 命令或可重复脚本，在真实 HTTP 本地服务上证明监测、匹配、提交、核验与重跑不重复。
- [x] Docker Compose 为 db、web、monitor、booking 提供独立服务，单次 migrate/seed 为显式初始化步骤；提供独立存储与 127.0.0.1:8010 绑定。
- [x] GitHub Actions 只在该项目路径变化时运行 Django 检查、迁移检查、测试；通过 PostgreSQL 测试关键约束。
- [x] 运行全套测试和本地完整演示；代码审查后修复问题。按已有用户授权提交并推送当前分支，保留 master。

## 验证与交付

单元/集成测试验证实际结果与副作用，不镜像实现结构。主机没有 Docker 守护进程时如实记录 Compose 只完成静态检查，不能声称容器已运行。首版交付为可运行框架与模拟 HTTP 闭环；真实账户会话、官方验证码/付款及生产适配器不在本轮实现范围。

## 实施与验证结果

- 已按上述模块建立框架；预先约定的模型与爬虫协议已接入运行。
- PostgreSQL 17 / Python 3.12 容器中完整 98 项测试通过，包括三项 PostgreSQL 并发测试。
- Docker 镜像实际构建、迁移、启动和健康检查通过。
- 容器内真实 HTTP 演示：两个虚拟客户、一个模拟名额，产生一条 CONFIRMED 记录；重跑返回 no_slots，提供方预约记录保持一条。
- API 认证、后台登录页面与静态资源均已运行验证；真实法国、德国、英国渠道启用数为零。
- 审查修复：未知容量时段只保留一个未决尝试；过期观测阻止提交；任务批次公平调度；运营编辑与 Worker 序列化；渠道出现尝试后冻结提供方路由。
- SQLite 开发模式与 PostgreSQL 多进程模式分开维护；SQLite 仅支持单 Worker 的本地开发，当前 Compose 是本机演示配置。

本轮已实现可运行框架，尚未实现真实签证站点适配、账户凭据保管、浏览器会话、验证码/付款及生产人工接管。生产抢号延迟目标仍需在实际渠道接入后验证。
