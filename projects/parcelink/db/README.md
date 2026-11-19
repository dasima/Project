# 数据库文件与操作说明

本项目使用 PostgreSQL 17。`backend/logistics/models.py` 和版本迁移是结构的权威来源；SQL 文件提供真实建表语句和可执行操作示例，客户页面已通过 Django API 读取数据库。

## 从哪里查看

- `business_schema.sql`：9 张业务表的 `CREATE TABLE`、主外键、CHECK、唯一约束和索引，直接由 `sqlmigrate` 生成。用于审阅，不要与已应用的迁移重复执行。
- `schema.sql`：从真实 PostgreSQL 导出的完整空库结构，包含 Django 用户、权限、Session 等框架表及迁移、内容类型、权限基础记录，不包含客户、用户或运单数据。
- `demo_data.sql`：2 个客户、3 个密码禁用的演示账号、7 票运单、包裹、轨迹和同步任务。可重复导入，不覆盖已有行。
- `queries.sql`：带客户归属校验的运单、详情、轨迹、统计查询，以及真实字段、约束、索引查询。
- `operations.sql`：预报、入库关联、轨迹更新与审计、任务领取、超时恢复、回调去重和删除示例。每段写入使用 `ROLLBACK`，便于在演示库查看效果。
- `../docs/database/数据库表结构.md` 和同目录 Word：9 张业务表的完整字段字典与关系说明。

## 正常初始化

推荐使用 Django 迁移创建全部表。先安装 `backend/requirements.txt`，配置 `DJANGO_SECRET_KEY` 以及 `DB_NAME`、`DB_USER`、`DB_PASSWORD`、`DB_HOST`、`DB_PORT`，随后执行：

```sh
python backend/manage.py migrate
psql "$DATABASE_URL" -X -v ON_ERROR_STOP=1 -f db/demo_data.sql
python backend/manage.py changepassword db_demo_a
python backend/manage.py changepassword db_demo_b
python backend/manage.py changepassword db_operator
```

`DATABASE_URL` 供 psql 使用，Django 使用上面的 `DB_*` 配置。三名账号分别为客户 A、客户 B、演示超级管理员；密码必须由操作者自行设置。线上管理员请使用 `createsuperuser` 或按岗位配置权限组，不要导入演示客户或共用演示管理员。

## 单独验证建表 SQL

需要纯 SQL 查看或验证时，创建全新的隔离空库，并导入 `schema.sql`。这是正常 `migrate` 初始化的另一条路径，不是在已有库上追加执行：

```sh
createdb parcelink_review
psql -d parcelink_review -X -v ON_ERROR_STOP=1 -f db/schema.sql
psql -d parcelink_review -X -v ON_ERROR_STOP=1 -f db/demo_data.sql
psql -d parcelink_review -X -v ON_ERROR_STOP=1 -f db/queries.sql
psql -d parcelink_review -X -v ON_ERROR_STOP=1 -f db/operations.sql
```

连接参数沿用 psql 的 `PGHOST`、`PGPORT`、`PGUSER` 和凭据配置。快照包含迁移记录；同版本 Django 代码执行 `migrate --check` 应无待迁移。后续结构变更仍通过新增 Django migration 完成，不手改快照代替迁移。

## 业务规则

一个客户可关联多个登录账号，每个账号只关联一个客户。所有客户 API 根据服务器已认证用户的归属过滤，不能接受浏览器指定客户 ID 作为权限依据。数据库外键保证包裹不能关联其他客户的运单；这一约束不替代接口鉴权，也没有启用 PostgreSQL 行级安全策略。

轨迹使用 `(shipment_id, source_key)` 去重；人工更新经统一业务服务加行锁、追加事件、更新主表当前位置并写审计。旧事件保留在历史中，不回退当前状态。SQL 示例由数据库操作者执行；正式 API/Admin 使用 `logistics/services.py`，含参数验证、权限检查及重复标识内容冲突检查。

包裹预报的 `submission_key` 是客户范围内的幂等标识：API 要求 UUID 格式的 `submissionKey`，首次创建返回 201，相同客户以同一标识及内容重试返回原记录和 200，内容不同返回 409。数据库通过非空标识的部分唯一索引约束 `(customer_id, submission_key)`；该字段和约束由 `0004_prealert_submission_key` 迁移引入。

`created_at`、`updated_at` 以及模型默认值由 Django ORM 赋值；不要假设 `auto_now` 或 `default=` 一定对应 PostgreSQL `DEFAULT`。裸 SQL 需提供必填列。Django `on_delete` 描述 ORM 删除行为；实际 SQL 外键默认 `NO ACTION`，以 `schema.sql` 为准。

多实例共享数据库 Session、业务数据和稳定的 `DJANGO_SECRET_KEY`，不依赖本地业务缓存。真实承运商验签、同步工作进程及云端高可用部署仍需按实施方案接入；当前已有其数据表和任务 SQL 示例。
