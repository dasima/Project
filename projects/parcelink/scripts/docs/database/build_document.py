"""Build the schema reference from authoritative Django metadata, without DB I/O."""
from pathlib import Path
import sys
import json

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import generator_context

ROOT = Path(__file__).resolve().parents[3]
CONTEXT = generator_context(ROOT, 'Build Word and Markdown schema references from current Django models.')
sys.path.insert(0, str(ROOT / 'backend'))
# Load model metadata only. These standalone settings neither read application
# secrets nor open a PostgreSQL connection; the backend supplies db_type().
from django.conf import settings
settings.configure(
    SECRET_KEY='documentation-metadata-only',
    INSTALLED_APPS=[
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'logistics.apps.LogisticsConfig',
    ],
    DATABASES={'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'docs_metadata_only',
    }},
    DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
    AUTH_USER_MODEL='auth.User',
    USE_TZ=True,
    TIME_ZONE='UTC',
)
import django
django.setup()
from django.apps import apps
from django.db import connection
from django.db.models import NOT_PROVIDED
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

OUT=CONTEXT.output_root/'docs/database'
QA=CONTEXT.output_root/'qa/database'
OUT.mkdir(parents=True,exist_ok=True)
QA.mkdir(parents=True,exist_ok=True)
MODELS={m.__name__:m for m in apps.get_app_config('logistics').get_models()}
FIELD_COUNT=sum(len(m._meta.fields) for m in MODELS.values())
PURPOSES={
 'id':'内部主键；授权仍须校验客户',
 'created_at':'创建时间，由 ORM 首次保存赋值',
 'updated_at':'最后修改时间，由 ORM 保存时更新',
 'customer_id':'所属客户；服务端用于数据隔离',
 'carrier_id':'关联承运商',
 'shipment_id':'关联运单',
 'code':'稳定业务代码', 'name':'显示名称',
 'is_active':'是否启用当前对象',
 'email':'联系邮箱；无值时用空字符串',
 'phone':'联系电话；无值时用空字符串',
 'user_id':'Django 用户；一个账号只能映射一个客户',
 'api_base_url':'承运商 API 地址；不存 API 密钥',
 'number':'内部运单业务编号，全局唯一',
 'carrier_account':'承运商账号范围标识；不是凭据',
 'tracking_number':'承运商追踪单号；可为空字符串',
 'goods_summary':'运单货物概述',
 'transport_method':'运输方式文本，如海运专线',
 'origin_country':'起运国家或地区', 'origin_city':'起运城市',
 'destination_country':'目的国家或地区', 'destination_city':'目的城市',
 'recipient_name':'收件人姓名', 'recipient_phone':'收件人电话',
 'recipient_address':'收件地址；按敏感个人信息保护',
 'status':'对象状态，取值见状态字典',
 'pieces':'件数；必须大于零', 'weight_kg':'重量，单位 kg；未知可空',
 'volume_cbm':'体积，单位 m³；未知可空',
 'estimated_delivery_date':'预计送达日期；不是实际签收时间',
 'delivered_at':'实际签收时间；仅 delivered 状态有值',
 'current_location':'最近已应用轨迹的扫描地点',
 'latest_event_at':'主表当前状态对应的事件发生时间',
 'prealert_number':'预报业务编号，全局唯一',
 'domestic_tracking_number':'国内快递单号；可为空字符串',
 'submission_key':'客户范围内预报幂等键；旧数据可空',
 'description':'包裹内容描述或轨迹说明，依所属表解释',
 'received_at':'接收时间；具体语义见各表说明',
 'source':'来源 manual poll webhook',
 'source_key':'同一运单范围内的稳定事件去重键',
 'title':'轨迹标题', 'location':'轨迹扫描地点文本',
 'occurred_at':'事件实际发生时间，含时区',
 'raw_status':'承运商原始状态文本；可为空字符串',
 'latitude':'纬度；与经度同时有值或同时为空',
 'longitude':'经度；与纬度同时有值或同时为空',
 'event_key':'承运商范围内的回调去重键',
 'payload':'验签后的 JSON 正文；限制敏感信息保留',
 'processed_at':'回调处理完成时间；未处理可空',
 'attempt_count':'处理或同步尝试次数；非负整数',
 'last_error':'最近错误摘要；不记录密钥或完整敏感正文',
 'next_retry_at':'到期可执行或重试时间',
 'locked_until':'运行租约截止时间；running 时必须有值',
 'last_success_at':'上次同步成功时间',
 'actor_id':'操作用户；系统操作或已删用户可空',
 'action':'审计动作代码', 'reason':'操作原因；可为空字符串',
 'changes':'结构化变更摘要；避免复制敏感信息',
}
TABLE_NOTES={
 'Customer':'客户是隔离边界。is_active=False 时，客户 API 拒绝该客户账号读取业务数据。联系字段 blank=True 表示表单允许空字符串，不表示数据库允许 NULL。',
 'CustomerUser':'一名用户最多属于一个客户；同一客户可关联多名用户。user_id 的数据库类型是 integer，匹配 Django 内置 auth_user.id；本表主键仍为 bigint。',
 'Carrier':'承运商配置与业务数据分离。api_base_url 是地址，访问密钥从受限环境配置或密钥服务注入，不增设明文密钥字段。真实承运商适配尚未交付。',
 'Shipment':'主表保存面向查询的当前状态投影；轨迹表保存发生过的事件。由客户归属、当前状态和更新时间支持客户列表，不靠浏览器传入 customer_id 决定授权。',
 'Package':'预报可暂不分配运单，shipment_id=NULL 且 status=prealert。预报成功不代表入库；授权运营确认收货后才写 received_at 与 received。当前预报 API 将运输方式 method 和目的地 destination 拼入 description，没有独立同名字段。',
 'TrackingEvent':'occurred_at 是扫描发生时间，received_at 是系统接收时间。人工更新服务在事务中锁定运单主行，先去重再追加轨迹，仅将不早于 latest_event_at 的事件应用到主表。shipment 的 ORM 删除行为为 CASCADE。',
 'WebhookReceipt':'仅允许未来承运商适配器在完成验签、防重放和请求体检查后写入。表结构已经建立；真实 HTTPS 验签入口与承运商处理 worker 尚未交付。carrier 的 ORM 删除行为为 PROTECT。',
 'SyncJob':'一个运单最多有一个同步任务，shipment 的 ORM 删除行为为 CASCADE。任务表与队列索引已经建立；真实承运商同步 worker 尚未交付。operations.sql 的租约认领与回收是可执行演示，不能视为已有调度服务。',
 'AuditLog':'记录动作、操作者及结构化摘要。人工轨迹服务把详细说明留在关联轨迹，审计只保存事件 ID、前后状态和是否更新投影，避免重复存放个人信息。',
}
CONSTRAINTS={
 'Customer':[('唯一键','code 全局唯一；id 为主键')],
 'CustomerUser':[('唯一键','user_id UNIQUE；customer_id 不唯一'),('ORM 删除行为','customer 使用 PROTECT；user 使用 CASCADE')],
 'Carrier':[('唯一键','code 全局唯一；id 为主键')],
 'Shipment':[
  ('shipment_status_valid','status 必须在六种运单状态内'),
  ('shipment_pieces_positive','pieces > 0；PositiveIntegerField 另有非负 CHECK'),
  ('shipment_weight_nonnegative','weight_kg 为空或 ≥ 0'),
  ('shipment_volume_nonnegative','volume_cbm 为空或 ≥ 0'),
  ('shipment_delivery_time_matches','delivered 状态必须有 delivered_at；其他状态必须为空'),
  ('shipment_tracking_requires_carrier','tracking_number 非空字符串时 carrier_id 必填'),
  ('shipment_carrier_tracking_unique','carrier_id 非空且 tracking_number 非空时，承运商 账号 单号三列组合唯一'),
  ('shipment_id_customer_unique','UNIQUE(id, customer_id)，作为包裹复合 FK 的被引用候选键'),
 ],
 'Package':[
  ('package_customer_submission_unique','submission_key 非 NULL 且非空字符串时，UNIQUE(customer_id, submission_key)；重试复用同一预报'),
  ('package_status_valid','status 仅 prealert received packed'),
  ('package_pieces_positive','pieces > 0；另有非负 CHECK'),
  ('package_weight_nonnegative','weight_kg 为空或 ≥ 0'),
  ('package_packed_requires_shipment','packed 必须绑定 shipment_id'),
  ('package_shipment_customer_fk','(shipment_id, customer_id) → shipment(id, customer_id)；禁止跨客户绑定；NOT DEFERRABLE'),
 ],
 'TrackingEvent':[
  ('tracking_event_dedup_unique','UNIQUE(shipment_id, source_key)；source 不属于唯一键'),
  ('tracking_event_source_valid','source 仅 manual poll webhook'),
  ('tracking_event_status_valid','status 必须在六种运单状态内'),
  ('tracking_event_coordinates_valid','经纬度均空，或均非空且纬度 [-90,90] 经度 [-180,180]'),
 ],
 'WebhookReceipt':[
  ('webhook_carrier_event_unique','UNIQUE(carrier_id, event_key)'),
  ('webhook_receipt_status_valid','status 仅 pending processed failed；attempt_count 有非负 CHECK'),
 ],
 'SyncJob':[
  ('唯一键','shipment_id UNIQUE，运单与任务为一对零或一'),
  ('sync_job_status_valid','status 仅 pending running succeeded failed；attempt_count 有非负 CHECK'),
  ('sync_job_lock_matches_status','running 必须有 locked_until；其他状态必须为空'),
 ],
 'AuditLog':[('ORM 删除行为','actor 使用 SET_NULL；shipment 使用 PROTECT')],
}


def rules(f):
 if f.primary_key:return 'PK；DB identity'
 values=[]
 if f.is_relation:
  target=f.remote_field.model._meta.db_table.removeprefix('logistics_')
  values.append('FK → '+target+'.id')
 if f.unique:values.append('UNIQUE')
 if getattr(f,'auto_now_add',False):values.append('ORM 首次保存时间')
 elif getattr(f,'auto_now',False):values.append('ORM 保存时间')
 elif f.default is not NOT_PROVIDED:
  v=f.default
  if v is dict:v='{}'
  elif callable(v):v='当前时间'
  elif isinstance(v,str):v="'"+v+"'"
  values.append('ORM '+str(v))
 elif f.null:values.append('无默认；可省略为 NULL')
 elif f.blank and f.get_internal_type() in ['CharField','EmailField','URLField','TextField']:
  values.append("ORM 空值 ''")
 else:values.append('无默认')
 return '；'.join(values)


def fieldrows(name,subset=None):
 fs=list(MODELS[name]._meta.fields)
 if subset is not None:fs=fs[subset]
 rows=[]
 for f in fs:
  typ=f.db_type(connection).replace('timestamp with time zone','timestamptz').replace(', ', ',')
  purpose=PURPOSES[f.column]
  if f.column=='description':purpose='包裹内容；当前 API 附运输方式和目的地' if name=='Package' else '轨迹详情及人工操作说明'
  if name=='Package' and f.column=='received_at':purpose='实际入库时间；预报时为空'
  if name in ['TrackingEvent','WebhookReceipt'] and f.column=='received_at':purpose='系统接收时间；ORM 首次保存赋值'
  rows.append([f.column,typ,'是' if f.null else '否',rules(f),purpose])
 return rows


pages=[]
def page(title,blocks):pages.append((title,blocks))
def p(value):return ('p',value)
def h(value):return ('h',value)
def tab(headers,rows,widths=None):return ('table',(headers,rows,widths))
def code(value):return ('code',value.strip())
def fields(name,subset=None):return tab(['字段','PG 类型','可空','默认与键','中文用途'],fieldrows(name,subset),[1.50,1.05,.40,1.70,2.25])
def tablehead(name):return h(MODELS[name]._meta.db_table)
def constraint_rows(name):return tab(['约束或规则','数据库含义'],CONSTRAINTS[name],[2.9,4.0])

page('集运系统数据库表结构与 SQL 操作说明',[
 p(f'本手册供后端开发与数据库维护人员查阅，覆盖 PostgreSQL 17 的 {len(MODELS)} 张业务表、{FIELD_COUNT} 个字段、客户隔离约束，以及可复现的查询与事务写入示例。Django 5.2 模型与迁移是结构的维护入口，推荐使用 migrate 建表。'),
 h('交付文件与使用顺序'),
 tab(['项目文件','用途'],[
  ['backend/logistics/models.py','字段、关系、状态与业务检查的权威模型'],
  ['backend/logistics/migrations/','0001 初始结构；0002 客户一致性；0003 中文名称；0004 预报幂等键'],
  ['db/schema.sql','完整 PostgreSQL 结构及 Django 基础数据，仅用于全新隔离审阅库'],
  ['db/business_schema.sql','业务迁移 SQL 审阅版；依赖先有 Django 框架表'],
  ['db/demo_data.sql','本地示例数据；2 客户 7 运单 26 轨迹'],
  ['db/queries.sql','客户范围只读查询与数据库结构检查'],
  ['db/operations.sql','预报 轨迹 任务 回调写入演示；每段 ROLLBACK'],
 ],[2.85,4.05]),
 p('推荐路径：先配置独立开发数据库与环境变量，再在 backend 目录执行 python manage.py migrate，随后按需载入 demo_data.sql。SQL 审阅路径：仅在全新空库导入完整 schema.sql；它包含 django_migrations、content type 与 permission 基础数据，无用户及业务数据。两条路径二选一，不能在已建表数据库重复导入结构。'),
 p('完整 schema 已在 PostgreSQL 17 的空库中恢复，并通过 migrate --check；示例查询及 operations.sql 也已实际执行验证。结构变化继续创建迁移，不直接修改已应用迁移或用手工 SQL 替代发布迁移。'),
])
page('1 业务关系与存储约定',[
 ('image','assets/database/er-overview.png'),
 ('caption','图 1 业务实体与端点基数  框架表仅显示 auth_user'),
 p('客户可有多个账号；账号最多属于一个客户。包裹在预报阶段可不绑定运单，一旦绑定必须与运单属于同一客户。运单可暂未指定承运商，并可有多条轨迹与审计记录；同步任务最多一条。'),
 p('业务主键是 bigint identity；Django 内置 auth_user.id 是 integer，对应 user_id 与 actor_id 也是 integer。timestamptz 是 timestamp with time zone 的 PostgreSQL 别名。应用 USE_TZ=True、TIME_ZONE=UTC，界面按业务时区显示；日期型 ETA 不包含时区。'),
])
page('2 字段字典的默认值与删除语义',[
 p('字段表中的可空指 SQL NULL，不等同于 Django blank=True。文本字段允许空白时通常保存空字符串。除主键 identity 外，当前迁移没有为业务字段保留服务器默认值；表内的 ORM 默认值只在 Django 创建对象时生效。'),
 p('带 auto_now_add 的 created_at 或 received_at，以及带 auto_now 的 updated_at，均由 ORM 赋值，不是 PostgreSQL DEFAULT now() 或触发器。裸 INSERT 必须提供必填时间、JSON、布尔及状态值；更新 SQL 必须显式写 updated_at。ORM bulk_update 与 QuerySet.update 也不自动执行 auto_now。字段表的 FK 目标省略 logistics_ 前缀，auth_user 保留全名。'),
 tablehead('Customer'),p(TABLE_NOTES['Customer']),fields('Customer'),
 tablehead('CustomerUser'),p(TABLE_NOTES['CustomerUser']),fields('CustomerUser'),
])
page('3 承运商与账号关系',[
 tablehead('Carrier'),p(TABLE_NOTES['Carrier']),fields('Carrier'),
 h('主键 唯一键与外键'),
 p('所有 PostgreSQL 外键使用 ON UPDATE NO ACTION 和 ON DELETE NO ACTION。PROTECT、CASCADE、SET_NULL 是 Django 删除收集器行为，直接 SQL DELETE 不会据此级联。常规 Django FK 为 DEFERRABLE INITIALLY DEFERRED；0002 复合 FK 为 NOT DEFERRABLE。'),
 p('客户和承运商的 code 分别全局唯一。CustomerUser.customer_id 指向 logistics_customer.id，ORM 为 PROTECT；user_id 指向 auth_user.id 并有 UNIQUE，ORM 为 CASCADE。创建第二条相同 user_id 的客户映射会被数据库拒绝。'),
 p('Shipment.customer_id 与 carrier_id 均使用 ORM PROTECT；Package.customer_id 与 shipment_id 同样为 PROTECT。客户或承运商仍被引用时，应用层拒绝删除；数据库外键也阻止留下悬空记录。'),
 h('框架表与共享 Session'),
 p('auth_user、auth_group、auth_permission、auth_user_groups、auth_user_user_permissions、auth_group_permissions、django_content_type、django_session、django_admin_log 与 django_migrations 由 Django migrate 创建和维护。密码使用 Django 哈希与验证流程，不手写认证表或明文密码。'),
 p('Session 引擎为 django.contrib.sessions.backends.db。多应用实例共享同一个数据库与稳定 SECRET_KEY；会话不存本机文件或进程缓存。数据库账号密码和 SECRET_KEY 是部署配置，不属于业务表字段。'),
])
page('4 运单字段与收件信息',[
 tablehead('Shipment'),p(TABLE_NOTES['Shipment']),fields('Shipment',slice(0,16)),
 p('number 与数据库内部 id 含义不同。number 是可显示的唯一业务编号，示例为 PL20261118001；tracking_number 是承运商单号。当前业务模型仅限制长度与唯一性，未用正则约束编号格式。'),
])
page('5 运单度量 时间与完整性',[
 tablehead('Shipment'),fields('Shipment',slice(16,None)),
 constraint_rows('Shipment'),
 p('estimated_delivery_date 是承诺或估算日期，delivered_at 是实际签收时间。签收状态与签收时间由数据库 CHECK 保持一致。手工修正状态应追加轨迹及审计，避免只改主表状态而丢失原因。'),
])
page('6 包裹与客户预报',[
 tablehead('Package'),p(TABLE_NOTES['Package']),fields('Package'),
 constraint_rows('Package'),
])
page('7 物流轨迹与事件去重',[
 tablehead('TrackingEvent'),p(TABLE_NOTES['TrackingEvent']),fields('TrackingEvent'),
 constraint_rows('TrackingEvent'),
 p('调用人工事件服务时，同 source_key 且内容一致返回已有事件；同键不同内容抛出 EventConflict。数据库唯一键负责最终防重，服务负责检查内容一致性。轮询和 Webhook 应按提供商稳定 ID 或统一指纹生成键，避免相同事件跨来源重复。'),
])
page('8 已验签回调',[
 tablehead('WebhookReceipt'),p(TABLE_NOTES['WebhookReceipt']),fields('WebhookReceipt'),
 constraint_rows('WebhookReceipt'),
 h('验签与正文保留'),
 p('event_key 在承运商范围内唯一，抵御服务商重试导致重复入库。SQL INSERT 本身不能验证网络请求签名；验签、时间窗、防重放及体积限制必须由接入适配器在入库前执行。'),
 p('payload 可能包含电话、地址及承运商标识。正式接入前需确定保留天数、授权角色、脱敏方式及定期删除策略，区分原始正文与需长期保留的业务轨迹。当前未交付自动清理任务，不能将日志或备份视为无限期正文存储。'),
])
page('9 同步任务与多实例认领',[
 tablehead('SyncJob'),p(TABLE_NOTES['SyncJob']),fields('SyncJob'),
 constraint_rows('SyncJob'),
 p('operations.sql 使用 FOR UPDATE SKIP LOCKED 认领到期任务，并设置 locked_until。多 worker 可取得不同任务；worker 必须保留返回的租约截止值作为令牌，完成与续租时核对该值，过期 worker 不得再发布结果。'),
 p('回收语句将过期 running 任务变为 failed、清空 locked_until 并推迟 next_retry_at。示例事务以 ROLLBACK 结束，仅演示结构可支持的执行模式；生产还需实际承运商适配、超时、退避、限流、令牌校验与监控。'),
])
page('10 审计与索引',[
 tablehead('AuditLog'),p(TABLE_NOTES['AuditLog']),fields('AuditLog'),
 p('actor_id 引用 auth_user.id，ORM 删除为 SET_NULL；shipment_id 可空且 ORM 为 PROTECT。直接 SQL 删除仍受 NO ACTION 外键限制。action 当前无数据库枚举约束，调用方需使用一致的动作代码。'),
 h('显式业务索引'),
 tab(['索引名','列与用途'],[
  ['ship_cust_status_updated_idx','customer_id, status, updated_at DESC；客户状态列表'],
  ['ship_customer_updated_idx','customer_id, updated_at DESC；客户最近更新列表'],
  ['event_shipment_timeline_idx','shipment_id, occurred_at DESC, id DESC；稳定轨迹时间线'],
  ['webhook_pending_queue_idx','status, received_at；待处理回调队列'],
  ['sync_job_retry_queue_idx','status, next_retry_at；到期重试任务'],
  ['audit_shipment_created_idx','shipment_id, created_at DESC；运单审计查询'],
 ],[3.05,3.85]),
 p('主键、UNIQUE、外键字段及 varchar 模式匹配还会形成 Django 自动索引。最终索引定义与外键名称以 db/schema.sql 或 pg_indexes 查询为准；不要仅按 ER 图推断。'),
])
page('11 状态 编号与示例数据',[
 h('运单及轨迹状态'),
 tab(['数据库值','中文含义'],[
  ['warehouse','待出库'],['shipped','已发货'],['transit','运输中'],
  ['customs','清关中'],['delivery','派送中'],['delivered','已签收'],
 ],[2.35,4.55]),
 tab(['对象','合法状态或来源'],[
  ['包裹 status','prealert 已预报；received 已入库；packed 已装箱'],
  ['轨迹 source','manual 人工录入；poll 主动查询；webhook 承运商推送'],
  ['回调 status','pending 待处理；processed 已处理；failed 失败'],
  ['同步 status','pending 待执行；running 执行中；succeeded 已成功；failed 失败'],
 ],[1.45,5.45]),
 h('编号与演示账号'),
 p('客户 code 示例 DEMO-A 与 DEMO-B；承运商 code 为 DEMO。运单 PL20261118001 至 PL20261118007 共 7 条，A 客户 6 条、B 客户 1 条。示例预报号 PA-PL20261118001 与运单业务号相关联；当前预报 API 生成 PRE 加 UTC 日期与随机后缀，均非数据库格式规则。'),
 p('demo_data.sql 创建 db_demo_a、db_demo_b 和 db_operator 三个禁用密码账号。前两个是客户账号，db_operator 是仅供本地样例操作的超级管理员；禁用密码表示不能直接登录，SQL 的 is_active 过滤仍可用于示例数据查询。'),
 code('cd backend\npython manage.py changepassword db_demo_a\npython manage.py changepassword db_demo_b\npython manage.py changepassword db_operator'),
 p('只在本地样例需要登录时分别设置密码。生产使用独立账号与最小权限，不部署样例超级管理员。'),
 h('预报提交重试'),
 p('预报 API 必传 submissionKey，长度不超过 64 且为有效 UUID。首次创建返回 201；同客户同键且内容一致返回原预报和 200；同键不同内容返回 409。历史行可为 NULL，条件唯一索引只约束非空键；前端超时重试必须保留原键。'),
])
page('12 建表与客户范围查询',[
 h('初始化执行顺序'),
 code('# 路径 A 推荐  在 backend 目录\npython manage.py migrate\n# 路径 B 仅全新隔离空库  在项目根目录\npsql "$REVIEW_DATABASE_URL" -v ON_ERROR_STOP=1 -f db/schema.sql\n# 二选一完成结构后  按需载入本地示例\npsql "$REVIEW_DATABASE_URL" -v ON_ERROR_STOP=1 -f db/demo_data.sql\npsql "$REVIEW_DATABASE_URL" -v ON_ERROR_STOP=1 -f db/queries.sql'),
 p('REVIEW_DATABASE_URL 指向隔离数据库，凭据从受限环境注入。完整 schema 已含迁移记录，导入后 migrate 应识别为已应用；migrate --check 可用于检查是否存在待应用迁移。business_schema.sql 是审阅版，不包含先决框架结构，不能当作完整建库文件。'),
 h('按登录账号查询客户运单'),
 code("SELECT s.number, s.status, s.goods_summary, s.current_location,\n       s.latest_event_at, s.estimated_delivery_date, s.delivered_at\nFROM logistics_shipment AS s\nJOIN logistics_customer_user AS m ON m.customer_id = s.customer_id\nJOIN logistics_customer AS c ON c.id = m.customer_id AND c.is_active\nJOIN auth_user AS u ON u.id = m.user_id AND u.is_active\nWHERE u.username = 'db_demo_a'\nORDER BY s.updated_at DESC, s.id DESC\nLIMIT 50 OFFSET 0;"),
 p('应用必须以已认证用户 ID 绑定参数；上例用户名仅用于本地 psql 复现。客户端不能自由选择 requester_username 或 customer_id。明细和轨迹同样在一次查询中同时校验归属、用户启用与客户启用。完整列表、详情、时间线和统计查询见 db/queries.sql。'),
])
page('13 原子追加轨迹与主表投影',[
 p('人工写入由 backend/logistics/services.py 的 record_manual_event 执行权限校验、full_clean、行锁、事务及审计。API 与 Admin 复用该服务。以下是 operations.sql 第 2 段的核心结构；完整可执行版本另含所有必填字段和审计 INSERT，不应拆开提交。'),
 code("BEGIN;\nSELECT id FROM logistics_shipment\nWHERE number='PL20261118001' FOR UPDATE;\nWITH inserted AS (\n  INSERT INTO logistics_tracking_event\n    (shipment_id,source,source_key,status,title,description,location,\n     occurred_at,received_at,raw_status,latitude,longitude)\n  SELECT id,'manual','sql-review-event-1','customs','目的地清关中',\n    'SQL 事务示例','吉隆坡海关','2026-11-19 09:00:00+08',\n    now(),'',NULL,NULL\n  FROM logistics_shipment WHERE number='PL20261118001'\n  ON CONFLICT (shipment_id,source_key) DO NOTHING\n  RETURNING *\n)\nUPDATE logistics_shipment s\nSET status=e.status,current_location=e.location,\n    latest_event_at=e.occurred_at,updated_at=now(),\n    delivered_at=CASE WHEN e.status='delivered'\n                      THEN e.occurred_at ELSE NULL END\nFROM inserted e WHERE s.id=e.shipment_id\n  AND (s.latest_event_at IS NULL\n       OR e.occurred_at>=s.latest_event_at);\nROLLBACK;"),
 p('FOR UPDATE 将同一运单的并发更新串行化，UNIQUE(shipment_id, source_key) 防重复。ON CONFLICT 不插入时返回集为空，主表也不更新；较旧事件仍可进入历史，但不能覆盖较新的投影。同一发生时间按当前实现允许后到事件更新投影。'),
 p('SQL 示例的 DO NOTHING 仅演示数据库去重，不验证同键内容是否改变；服务会比较内容并拒绝冲突。完整 operations.sql 还在同一事务中追加审计。所有示例最终 ROLLBACK，正式写入走应用服务。'),
])
page('14 结构检查与操作边界',[
 h('查看真实列 约束与索引'),
 code('\\d+ logistics_shipment\n\\d+ logistics_package\n\\d+ logistics_tracking_event\n\\di+ *shipment*'),
 code("SELECT table_name,column_name,data_type,is_nullable,column_default\nFROM information_schema.columns\nWHERE table_schema='public' AND table_name LIKE 'logistics_%'\nORDER BY table_name,ordinal_position;\n\nSELECT conrelid::regclass,conname,pg_get_constraintdef(oid)\nFROM pg_constraint\nWHERE connamespace='public'::regnamespace\n  AND conrelid::regclass::text LIKE 'logistics_%'\nORDER BY conrelid::regclass::text,conname;"),
 p('information_schema.columns 的 column_default 对 ORM 默认字段为空是预期行为；identity 可进一步检查 is_identity 与 identity_generation。queries.sql 还包含 pg_indexes 查询，可直接查看索引列顺序、DESC 和条件唯一索引。'),
 h('操作演示与交付边界'),
 p('db/operations.sql 共 5 段：创建预报及同客户入库绑定、原子追加轨迹及审计、SKIP LOCKED 租约认领、过期任务回收、已验签回调去重入库。每段以 ROLLBACK 结束，便于复现而不保留演示更改。正式写入不能绕过权限、验证与审计服务。'),
 p('包裹复合 FK 已在 PostgreSQL 强制检查；用 SQL、ORM 或其他工具尝试跨客户绑定均会失败。预报状态不会自动改成已入库，现有 CHECK 只强制 packed 绑定运单，没有规定 received_at 与包裹状态严格一一对应；业务流程还须验证。'),
 p('当前交付包含数据库结构、客户隔离查询、预报幂等提交及人工轨迹事务服务。同步任务与回调表可承载后续接入，但真实承运商 worker、验签适配、自动清理策略与生产调度需要另外实现和验收。'),
])

doc=Document()
sec=doc.sections[0]
sec.page_width=Inches(8.5);sec.page_height=Inches(11)
sec.top_margin=Inches(.65);sec.bottom_margin=Inches(.65)
sec.left_margin=Inches(.8);sec.right_margin=Inches(.8)
sec.header_distance=Inches(.22);sec.footer_distance=Inches(.25)
for name in ['Normal','Title','Heading 1','Heading 2','Caption','List Bullet','List Number']:
 st=doc.styles[name];st.font.name=CONTEXT.font_family;st.font.color.rgb=RGBColor(0,0,0)
 rf=st.element.get_or_add_rPr().get_or_add_rFonts()
 for a in list(rf.attrib):
  if 'theme' in a.lower():del rf.attrib[a]
 rf.set(qn('w:eastAsia'),CONTEXT.font_family)
 st.paragraph_format.widow_control=True
 for x in st.element.findall('.//'+qn('w:pBdr')):x.getparent().remove(x)
normal=doc.styles['Normal'];normal.font.size=Pt(11)
normal.paragraph_format.line_spacing=Pt(16.5);normal.paragraph_format.space_after=Pt(7)
doc.styles['Title'].font.size=Pt(23);doc.styles['Title'].font.bold=True
doc.styles['Title'].paragraph_format.space_after=Pt(13)
doc.styles['Heading 1'].font.size=Pt(18);doc.styles['Heading 1'].font.bold=True
doc.styles['Heading 1'].paragraph_format.space_after=Pt(10)
doc.styles['Heading 2'].font.size=Pt(12.5);doc.styles['Heading 2'].font.bold=True
doc.styles['Heading 2'].paragraph_format.space_before=Pt(9)
doc.styles['Heading 2'].paragraph_format.space_after=Pt(5)
doc.styles['Caption'].font.size=Pt(9);doc.styles['Caption'].font.italic=False
doc.styles['Caption'].paragraph_format.line_spacing=Pt(13)
doc.styles['Caption'].paragraph_format.space_after=Pt(9)
doc.core_properties.title='集运系统数据库表结构与 SQL 操作说明'
doc.core_properties.subject='PostgreSQL 17 字段参考 客户隔离 SQL 与事务操作'
doc.core_properties.author='集运系统项目'
footer=sec.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.RIGHT
r=footer.add_run('集运系统数据库参考    ');r.font.size=Pt(8);r.font.color.rgb=RGBColor.from_string('666666')
fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');footer._p.append(fld)
md=['# 集运系统数据库表结构与 SQL 操作说明','']


def render_table(headers,rows,widths):
 if widths is None:widths=[6.9/len(headers)]*len(headers)
 t=doc.add_table(rows=1,cols=len(headers));t.alignment=WD_TABLE_ALIGNMENT.CENTER;t.autofit=False
 for col,w in zip(t.columns,widths):col.width=Inches(w)
 for i,vals in enumerate([headers]+rows):
  row=t.rows[0] if i==0 else t.add_row()
  trpr=row._tr.get_or_add_trPr();trpr.append(OxmlElement('w:cantSplit'))
  if i==0:trpr.append(OxmlElement('w:tblHeader'))
  for j,(cell,val) in enumerate(zip(row.cells,vals)):
   cell.width=Inches(widths[j]);cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
   cell.text=str(val).replace('_','_\u200b') if j==0 else str(val)
   tcpr=cell._tc.get_or_add_tcPr()
   mar=OxmlElement('w:tcMar')
   for edge in ['top','left','bottom','right']:
    e=OxmlElement('w:'+edge);e.set(qn('w:w'),'70' if edge in ['top','bottom'] else '90');e.set(qn('w:type'),'dxa');mar.append(e)
   tcpr.append(mar)
   borders=OxmlElement('w:tcBorders')
   for edge in ['top','left','bottom','right']:
    e=OxmlElement('w:'+edge);e.set(qn('w:val'),'single');e.set(qn('w:sz'),'4');e.set(qn('w:color'),'D9D9D9');borders.append(e)
   tcpr.append(borders)
   sh=OxmlElement('w:shd');sh.set(qn('w:fill'),'DCE8F3' if i==0 else 'F6F8FA' if i%2==0 else 'FFFFFF');tcpr.append(sh)
   for para in cell.paragraphs:
    para.paragraph_format.line_spacing=Pt(14)
    para.paragraph_format.space_after=Pt(0);para.paragraph_format.space_before=Pt(0)
    if len(headers)==5 and j==2:para.alignment=WD_ALIGN_PARAGRAPH.CENTER
    for run in para.runs:run.font.size=Pt(9.5);run.font.bold=(i==0);run.font.color.rgb=RGBColor(0,0,0)
 p=doc.add_paragraph();p.paragraph_format.space_after=Pt(0);p.paragraph_format.line_spacing=Pt(4);p.paragraph_format.space_before=Pt(0)


for i,(title,blocks) in enumerate(pages):
 if i:md+=['## '+title,'']
 heading=doc.add_paragraph(title,'Title' if i==0 else 'Heading 1')
 heading.paragraph_format.page_break_before=bool(i)
 for kind,value in blocks:
  if kind=='p':doc.add_paragraph(value);md +=[value,'']
  elif kind=='h':doc.add_paragraph(value,'Heading 2');md+=['### '+value,'']
  elif kind=='table':
   headers,rows,widths=value;render_table(headers,rows,widths)
   md+=['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']
   md+=['| '+' | '.join(str(v).replace('|','\\|') for v in row)+' |' for row in rows];md+=['']
  elif kind=='image':
   para=doc.add_paragraph();para.alignment=WD_ALIGN_PARAGRAPH.CENTER
   para.paragraph_format.line_spacing=1.0;para.paragraph_format.space_after=Pt(3)
   run=para.add_run();run.add_picture(str(CONTEXT.asset(value)),width=Inches(6.8))
   run._r.xpath('.//wp:docPr')[0].set('descr','集运系统九张业务表与 Django 用户表的关系，标明客户隔离、可空外键和一对多及一对一基数。')
   md+=['![业务 ER 关系概览](../../'+value+')','']
  elif kind=='caption':
   para=doc.add_paragraph(value,'Caption');para.alignment=WD_ALIGN_PARAGRAPH.CENTER;md+=[value,'']
  elif kind=='code':
   for raw in value.splitlines():
    para=doc.add_paragraph();para.paragraph_format.space_after=Pt(0);para.paragraph_format.line_spacing=Pt(13)
    para.paragraph_format.keep_with_next=True
    run=para.add_run(raw or ' ');run.font.name=CONTEXT.font_family;run.font.size=Pt(9)
   para.paragraph_format.keep_with_next=False
   para=doc.add_paragraph();para.paragraph_format.space_after=Pt(2);para.paragraph_format.line_spacing=Pt(4)
   md+=['```sql',value,'```','']

out=OUT/'数据库表结构与SQL操作说明.docx'
doc.save(out)
(OUT/'数据库表结构.md').write_text('\n'.join(md),encoding='utf-8')
counts={m._meta.db_table:len(m._meta.fields) for m in MODELS.values()}
(QA/'field-counts.json').write_text(json.dumps({'field_count':sum(counts.values()),'table_counts':counts,'planned_pages':len(pages)},ensure_ascii=False,indent=2),encoding='utf-8')
print(out)
print('Fields:',sum(counts.values()),'Planned pages:',len(pages))
