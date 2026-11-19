# 集运通 Parcelink

中文集运系统 Demo，使用 Python / Django 5.2、PostgreSQL 17 和原生 JavaScript。客户登录后查看自己公司的运单、当前位置、路线示意和物流轨迹；管理员通过 Django Admin 管理客户、账号、运单、包裹和轨迹。

默认页面连接真实后端 API。业务数据、用户和 Session 存在 PostgreSQL，支持多个账号、跨设备查看和多实例服务。地图为路线示意，不代表实时 GPS。

## 在总仓库中使用

本项目位于 `projects/parcelink/`。下文命令均从本项目目录执行：

```sh
cd projects/parcelink
```

项目内的前端、后端、数据库和部署文件一起维护，与总仓库其他项目独立。服务网址中的 `/api/`、`/admin/` 无需添加仓库目录前缀。

导入演示数据后会有客户账号 `db_demo_a`（6 票运单）、`db_demo_b`（1 票专属运单）和演示管理员 `db_operator`，密码默认禁用，需按下文自行设置。同一浏览器在多个标签页共享登录会话，可使用不同浏览器同时演示多个客户。

## 使用 Docker Compose 初始化

需要 Docker 和 Docker Compose。复制配置并设置非空 `DJANGO_SECRET_KEY`、`DB_PASSWORD`；密钥可用 `python3 -c 'import secrets; print(secrets.token_urlsafe(48))'` 生成。不要提交 `.env`。

```sh
cp .env.example .env
# 编辑 .env，填写上述两个必填值。
docker compose build
docker compose up -d db
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py collectstatic --noinput
docker compose up -d
```

本地试运行访问 http://localhost/ ，管理后台 http://localhost/admin/ 。根目录 `.env.example` 默认开启 DEBUG 并使用本地 HTTP，仅用于本机试运行。正式环境按后面的多实例部署说明配置 HTTPS。

可选导入示例数据，再为三个账号分别设置密码：

```sh
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' < db/demo_data.sql
docker compose exec web python manage.py changepassword db_demo_a
docker compose exec web python manage.py changepassword db_demo_b
docker compose exec web python manage.py changepassword db_operator
```

新建自己的管理员用 `docker compose exec web python manage.py createsuperuser`。正式环境不要导入演示客户，也不要共用演示管理员。

## 不使用 Docker 开发

安装 Python 3.12 和 PostgreSQL，创建独立数据库及账号。安装依赖后，参考 `backend/.env.example` 将配置导出为进程环境变量；Django 不会自动读取该文件。

```sh
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
# 设置 DJANGO_SECRET_KEY、DJANGO_DEBUG=true、DB_* 等环境变量。
.venv/bin/python backend/manage.py migrate
.venv/bin/python backend/manage.py collectstatic --noinput
.venv/bin/python backend/manage.py createsuperuser
.venv/bin/python backend/manage.py runserver 127.0.0.1:8766
```

DEBUG 模式由 Django 提供允许列表中的前端文件及 Admin 静态资源；正式运行用 Gunicorn 和 Caddy。

设置好后端环境变量后，可用 `npm run dev` 启动 Django 开发服务；也可直接使用上面的 Python 命令，无需安装任何前端 npm 依赖。

只演示界面时执行 `python3 server.py` 或 `npm run demo`，打开 http://localhost:8765/?demo=1 。此模式用 `demo / 123456` 或 `admin / 123456`，数据只在当前页面内存中，刷新会恢复，不提供真实权限、数据库或 Django Admin。访问不带 `?demo=1` 的页面则需要同源后端 API。

## 功能与权限

- 客户：查看所属客户的运单、详情、包裹、轨迹，按状态筛选、搜索、手动刷新；页面可见时每 30 秒刷新。一个客户可绑定多个账号，每个账号仅绑定一个客户。
- 包裹预报：提交后进入待确认状态，不会虚构已入库运单。相同 `submissionKey` 重试返回同一条预报，内容冲突返回 409。
- 管理员：管理客户及账号归属、承运商、运单和包裹，追加物流轨迹。权限由服务端账号与 Django 权限组决定，登录页的角色选项不会提升权限。
- 轨迹与审计：统一事务服务追加事件，按来源标识去重并记录操作者；旧事件可补入历史，但不会回退当前状态。审计、同步任务、回调记录在后台只读展示。
- 联系方式：登录页、页脚和帮助中心显示公司信息。当前公司 `项目名称待定`、电话 `000-00000000`、邮箱 `support@example.com` 均明确标注为占位。
- 多域名：展示已配置的主入口与备用入口；域名尚未确定时显示待配置。不同域名需重新登录。主域名完全无法打开时，其页面无法运行并提示备用地址，应提前发布并收藏备用地址。

修改 `COMPANY_NAME`、`PHONE`、`EMAIL`、`PRIMARY_DOMAIN`、`BACKUP_DOMAINS` 环境变量后重启应用。备用域名用逗号分隔，生产链接使用 HTTPS。纯静态演示的对应配置在 `site-config.js`。

## 数据库与文档

- [数据库文件说明](db/README.md)：初始化与 SQL 验证方法。
- [业务建表 SQL](db/business_schema.sql)：9 张业务表及其约束、索引，由 Django 迁移生成。
- [完整空库快照](db/schema.sql)：业务表及 Django 用户、权限、Session 表，含迁移和权限基础记录；只能作为全新空库初始化的替代路径。
- [演示数据](db/demo_data.sql)、[查询 SQL](db/queries.sql)、[写入操作 SQL](db/operations.sql)：可查看实际语句；写入示例均以 ROLLBACK 结束。
- [数据库字段字典](docs/database/数据库表结构.md)：9 表、96 字段、关系、约束和 SQL 说明。
- [数据库说明 Word](docs/database/数据库表结构与SQL操作说明.docx)：完整表结构与操作说明，15 页。
- [部署架构与技术栈 Word](docs/deployment/集运系统Python技术方案与部署架构.docx)：单机和多实例架构、域名、账号、安全与运维方案，10 页。
- [文档生成源码](scripts/docs/README.md)：从任意克隆路径重新生成数据库说明、部署 Word 与架构图，默认写入隔离的 `build/docs/`。

模型与新增版本迁移是结构的权威来源。不要在已迁移的数据库重复执行建表快照，也不要将表结构 SQL 当作日常升级脚本。

## 无状态与多实例部署

应用进程不保存用户会话和业务状态。所有实例共享 PostgreSQL、同一稳定 `DJANGO_SECRET_KEY` 及兼容配置，使用数据库 Session，无需粘性会话。迁移作为单独发布步骤执行，不在各 Web 进程启动时运行。

正式方案为：托管 HTTPS 负载均衡 → 不同故障域的两台 VM（Caddy + Gunicorn/Django）→ 托管高可用 PostgreSQL。无需 Kubernetes 或 Redis。单机 `compose.yaml` 属于试运行方案；`deploy/compose.ha.yaml` 是每台 VM 使用的独立应用栈，连接外部共享数据库。

已有 Compose 部署迁移目录时，应沿用原 `docker compose -p <原项目名>`，或受控迁移卷；目录改名可能改变默认 Compose 项目名及卷名前缀。本次仓库整理不迁移或删除现有数据库卷。

全新 HA 部署建议在下列所有命令中额外指定 `-p parcelink-ha`，将其与其他子项目的 Compose 资源区分；已有部署继续使用原项目名。

准备私有配置文件（示例路径 `/secure/path/parcelink.env`），在每台 VM 配置相同密钥和数据库。设置 `DJANGO_DEBUG=false`、真实主备域名的 `DJANGO_ALLOWED_HOSTS` 与 HTTPS `DJANGO_CSRF_TRUSTED_ORIGINS`、`DB_HOST`、`DB_SSLMODE=require` 及真实 LB 源 CIDR `TRUSTED_PROXY_CIDRS`。配置文件在所有服务启动前应保持一致。

```sh
docker compose --env-file /secure/path/parcelink.env -f deploy/compose.ha.yaml build
# 以下迁移仅在一台主机执行一次。
docker compose --env-file /secure/path/parcelink.env -f deploy/compose.ha.yaml run --rm web python manage.py migrate
# 以下静态资源收集需在每台主机执行。
docker compose --env-file /secure/path/parcelink.env -f deploy/compose.ha.yaml run --rm web python manage.py collectstatic --noinput
docker compose --env-file /secure/path/parcelink.env -f deploy/compose.ha.yaml up -d
```

LB 终止 HTTPS、覆盖 `X-Forwarded-Proto`，健康探测 `/readyz/`，防火墙仅允许 LB 访问每台 VM 的 8080；Gunicorn 8000 与 PostgreSQL 5432 不暴露公网。`/healthz/` 检查应用存活，`/readyz/` 同时检查数据库依赖。正式 HA 需要负载均衡和数据库本身具备冗余，并完成故障切换与备份恢复演练。

若采用单机 Caddy 自动签发双域名证书，`SITE_ADDRESSES` 需使用逗号加空格，例如 `"main.example.com, backup.example.com"`；两域名均需正确解析并放行 80/443。HA 文件在 LB 后使用内部 HTTP 8080，由 LB 管理公网证书。

## 验证与当前边界

```sh
node --test tests/*.test.js
python backend/manage.py test logistics.tests
python backend/manage.py check
python backend/manage.py makemigrations --check --dry-run
```

后端测试须连接专用 PostgreSQL 测试环境，测试账号需要创建测试库权限。当前测试覆盖客户隔离、CSRF、共享数据库会话、轨迹事务/去重/并发、后台编辑并发和预报幂等；前端覆盖接口、展示规则和交互更新。完整 SQL 快照另在独立空库导入验证。

本次交付验证：52 项后端测试、17 项前端测试通过；两份 Compose 配置、app/edge 镜像构建及 Caddy 配置校验通过。最新 SQL 在独立空库恢复、导入样例、执行查询及回滚操作成功。真实双进程 HTTP 验证了共享登录、客户隔离、跨实例预报幂等与退出失效；这些验证不等同于云端主机或数据库故障切换演练。

当前提供本地可运行 Demo、SQL、文档及多实例部署配置；未创建云端 LB、VM、数据库主备或真实域名，也未执行云端故障切换。承运商接口、验签回调和同步 worker 尚未接入，目前只有相关模型和 SQL 示例；登录失败限速需在正式上线前补齐。路线示意与样例数据不能作为真实物流位置。
