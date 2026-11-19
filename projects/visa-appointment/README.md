# Visa Appointment 留学签证预约系统

独立的 Django 5.2 预约业务框架：通过真实 HTTP 请求访问本地模拟放号服务，跑通采集、案件匹配、持久化预约意图、提交与结果核对。提供 Django 运营后台、受保护的只读 API，以及独立的监测和预约 Worker。

目前只实现 `demo_http` 模拟适配器。法国、德国长期留学及英国 Student visa 渠道仅登记为关闭的 `manual` 渠道，尚未实现官方站点采集、真实账户登录、浏览器会话、验证码、付款或真实预约。框架没有验证设计文档中的生产容量和 100ms 延迟目标。

## 无 Docker 本地运行

需要 Python 3.12+。从仓库根目录执行：

```sh
cd projects/visa-appointment
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r backend/requirements.txt
python scripts/bootstrap_env.py
python backend/manage.py migrate
python backend/manage.py seed_demo --base-url http://127.0.0.1:8010/demo-provider
python backend/manage.py createsuperuser
python backend/manage.py runserver 127.0.0.1:8010 --noreload
```

`bootstrap_env.py` 根据 `.env.example` 创建权限为 `0600` 的私有 `.env`，生成独立的 Django 密钥、API token、演示提供方 token 和数据库密码，不打印凭据，也不覆盖已有文件。默认演示配置启用本地模拟服务；应用在没有显式配置时默认关闭模拟服务。不要提交 `.env`、真实账户、证件、Cookie 或运行数据库。

未设置 `DB_HOST` 时使用项目内 `var/db.sqlite3`。本地 PostgreSQL 可在私有 `.env` 配置 `DB_HOST`、`DB_PORT`、`DB_NAME`、`DB_USER` 和 `DB_PASSWORD`。

保持 Web 运行，在另一个终端进入同一项目并激活 `.venv`，验证完整流程：

```sh
python backend/manage.py demo_pipeline
python backend/manage.py demo_pipeline
```

首次初始化有两个虚拟案件、一个容量为 1 的模拟时段。正常情况下只有一个案件获得确认，第二次运行不增加提供方预约记录；刚运行后可能显示 `not_due`。种子命令重复运行会保留原有时段、授权和预约历史，不能用它重置已预约案件。模拟放号默认持续一小时，案件授权默认七天；演示数据过期后应使用新的开发数据库，勿通过修改历史记录伪造重新预约。

持续运行时，用下面的命令替代 `demo_pipeline`。SQLite 只启动一个 `all` Worker，避免同时运行多个 Worker 或与手动演示命令竞争：

```sh
python backend/manage.py runworker --role all --interval 1
```

## Docker Compose 本地演示

需要 Docker Engine 与 Compose v2。项目使用独立 PostgreSQL 17 和运行目录数据卷，只将 Web 暴露到 `127.0.0.1:8010`。镜像不包含私有 `.env`；Compose 在启动时注入环境变量。镜像构建时收集 Django 静态文件，由 WhiteNoise 提供，应用以非 root 用户运行。

在本项目目录执行，已有 `.env` 时跳过生成步骤：

```sh
python3 scripts/bootstrap_env.py
docker compose config --quiet
docker compose build
docker compose up -d --wait db
docker compose run --rm --no-deps web python manage.py migrate
docker compose run --rm --no-deps web python manage.py seed_demo --base-url http://web:8000/demo-provider
docker compose run --rm --no-deps web python manage.py createsuperuser
docker compose up -d --wait web
```

`--wait` 等待服务健康后才继续。`createsuperuser` 交互创建管理员，不在代码或环境模板中提供默认管理员密码。迁移与种子是显式初始化步骤，不会在每次容器重启时执行。

访问 `/healthz/` 确认 Web 可用后，先验证闭环，再启动持续 Worker：

```sh
curl --fail http://127.0.0.1:8010/healthz/
docker compose exec web python manage.py demo_pipeline
docker compose exec web python manage.py demo_pipeline
docker compose up -d monitor booking
docker compose ps
```

`monitor` 负责监测与匹配，`booking` 负责执行及不确定结果核对，两者共享 PostgreSQL。容器内种子地址必须使用 `http://web:8000/demo-provider`，不能使用容器自身的 `127.0.0.1:8010`。本地 SQLite 与 Compose PostgreSQL 是不同数据库；不要将同一数据库中已存在的演示渠道改成另一套地址。

查看日志或停止服务：

```sh
docker compose logs --tail 100 web monitor booking
docker compose down
```

`down` 保留数据卷；后续升级先停止 Worker，构建新镜像并显式执行迁移，再启动 Web 和 Worker。备份 PostgreSQL 后再执行任何数据删除操作。

这份 Compose 仅供本机 HTTP 演示：它强制 `DJANGO_DEBUG=false`、`COOKIE_SECURE=false`，允许 `localhost`、`127.0.0.1` 和内部服务名 `web`。对外部署需独立配置 HTTPS、可信主机、CSRF 来源、Secure Cookie、数据库备份和运行监控，并关闭模拟提供方；不要直接将演示端口改为公网绑定。

## 后台、API 与任务状态

- [运营后台](http://127.0.0.1:8010/admin/)：管理渠道、虚拟案件与授权；查看采集记录、预约尝试和审计事件。预约尝试等执行历史只读。
- [健康检查](http://127.0.0.1:8010/healthz/)：执行数据库连通检查，成功返回 `{"status":"ok"}`。
- 只读 API：`/api/channels/`、`/api/cases/`、`/api/observations/`、`/api/attempts/`、`/api/crawl-runs/`，使用已登录的有效 staff 会话或 `Authorization: Bearer <API_TOKEN>`；`API_TOKEN` 取自私有配置。默认每页 50 条，`limit` 上限 100，使用 `offset` 翻页。
- 模拟提供方：`/demo-provider/availability/`、`/demo-provider/bookings/` 和按 operation ID 核对的地址，使用独立的 `DEMO_PROVIDER_TOKEN`，仅在 `ENABLE_DEMO_PROVIDER=true` 时开放。

API 请求示例，其中 token 是占位符：

```sh
curl --fail -H 'Authorization: Bearer <API_TOKEN>' \
  'http://127.0.0.1:8010/api/attempts/?limit=20&offset=0'
```

提交前持久化意图；同一案件的有效尝试受数据库约束。提交超时或进程遗留的 `SUBMITTING` 尝试先按 operation ID 核对，结果不确定时保留为 `RECONCILING` 或人工处理，避免盲目重复提交。`CONFIRMED` 需要提供方返回确认编号；这里的确认仅代表本地模拟提供方。

可以单独触发一次不确定预约核对：

```sh
python backend/manage.py reconcile_bookings --once
# Compose 中使用：docker compose exec web python manage.py reconcile_bookings --once
```

## 验证与 CI

在项目目录、已安装依赖的虚拟环境中运行：

```sh
python backend/manage.py check
python backend/manage.py makemigrations --check --dry-run
python backend/manage.py test apps --verbosity 2
docker compose config --quiet
```

测试包含真实本地 HTTP 服务、解析和异常响应、API 认证、提供方幂等性，以及预约和持久化调度行为。测试服务需要允许本机 loopback 监听，不访问真实签证渠道。GitHub Actions 仅由本项目和自身工作流变更触发，以 Python 3.12 / PostgreSQL 17 运行检查、迁移检查和完整测试，另行验证 Compose 配置。CI 使用隔离测试凭据，模拟提供方默认关闭，测试按需覆盖开启。

## 项目组织与设计

`backend/apps/core` 为领域模型和后台，`crawler` 为独立 HTTP 协议和采集器，`automation` 为调度与执行，`demo_provider` 为模拟提供方，`api` 为查询接口；`backend/config` 管理应用配置。依赖、私有环境、运行数据与部署文件都在本项目目录内维护，与 Parcelink 分离；仓库根目录统一管理 Git。

- [系统设计与抢号引擎方案](docs/superpowers/specs/2026-11-19-europe-student-visa-appointment-design.md)：目标架构、渠道差异、状态机与后续生产能力规划。
- [框架实施计划](docs/superpowers/plans/2026-11-19-framework.md)：本轮实现范围与验证要求。
