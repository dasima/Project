from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import generator_context

ROOT = Path(__file__).resolve().parents[3]
CONTEXT = generator_context(ROOT, 'Build the deployment architecture Word document.')
OUT = CONTEXT.output_root / 'docs/deployment'
OUT.mkdir(parents=True, exist_ok=True)

pages = [{'title': '集运系统 Python 技术方案与部署架构',
  'meta': '项目名称待定    2026年11月18日    方案版本 1.1',
  'blocks': [('p',
              '正式环境建议采用无状态 Django 应用、两台不同故障域的应用主机、托管冗余负载均衡和托管高可用 PostgreSQL。每台主机使用 Docker Compose 管理 Caddy 与 Gunicorn，无需 '
              'Kubernetes。应用可横向扩展，并通过共享会话、数据和任务锁支持跨主机运行。'),
             ('h', '1 业务目标与一期范围'),
             ('p', '客户登录后查看自己的运单、最近运输位置、预计送达时间和历史轨迹；运营人员在后台维护客户与运单，补录物流节点。具备承运商接口条件后，再接入自动同步和回调。'),
             ('table',
              (['能力', '原有演示', '本次实现与后续部署'],
               [['登录与权限', '浏览器内示例账号', '本地 Django Session 登录；按客户隔离数据'],
                ['运单与轨迹', 'localStorage 示例数据', '新增数据库模型、迁移、JSON API 与 SQL 文件'],
                ['运营管理', '前端演示更新', 'Django Admin；多管理员按权限组管理'],
                ['客户页面', '单浏览器演示', '接入 API 后支持多用户查看各自业务数据'],
                ['正式部署', '单机本地演示', '本文提供跨主机 HA、域名、备份与运维方案']],
               [1.0, 2.1, 3.8])),
             ('h', '2 选型依据与方案边界'),
             ('p',
              'Django 提供 ORM、数据库迁移、会话认证、权限与管理后台，适合运单录入、查询和维护。当前采用 Django JSON views 提供客户 API，首期不引入 Django REST Framework。保留 '
              'HTML、CSS 和 JavaScript 客户页面，通过同域 API 连接正式数据。'),
             ('p', '无状态设计使应用实例可替换、可增加；多实例是部署手段。避免整体单点还必须覆盖主机、负载均衡、数据库、DNS 和任务调度。单机 Compose 可保留为低成本本地开发或试运行方式。'),
             ('p', '本次新增本地数据库、API 与后台基础，具体可运行范围及测试记录以交付 README 为准。跨主机云端部署、自动故障切换和承运商真实接入仍为实施方案，尚未在云上部署或完成高可用验证。')]},
 {'title': '正式环境跨主机高可用架构',
  'blocks': [('p', '推荐两台应用主机分别位于不同故障域或可用区。托管 DNS 与负载均衡自身采用冗余服务；负载均衡根据就绪检查分发请求，应用故障时摘除目标。数据库采用托管主备与自动故障切换。'),
             ('image', 'assets/deployment/ha-architecture.png'),
             ('caption', '图 1 无需 Kubernetes 的双主机正式部署方案'),
             ('h', '高可用边界与验证'),
             ('p', '单独将数据库移出应用主机仍可能留下单库故障点。必须核对所购数据库规格确实包含高可用主备与自动切换；应用连接应支持切换后的重连及受控重试。'),
             ('p', '两台主机可独立触发同步任务，共享数据库锁、租约与幂等规则。本文描述目标架构；云端容灾和切换演练尚未执行，实际可用性取决于部署、配置及验收。')]},
 {'title': '低成本单机试运行架构',
  'blocks': [('p', '该方案保留为本地开发或可接受停机的试运行方式。一台主机运行入口、应用、数据库与调度，成本较低，但主机故障会同时中断这些组件；正式避免单点应采用前述双主机方案。'),
             ('image', 'assets/deployment/architecture.png'),
             ('caption', '图 2 单服务器试运行部署架构'),
             ('h', '访问与数据更新路径'),
             ('p',
              '客户和管理员通过域名访问。Caddy 提供 HTTPS 和静态文件，将 /api/、/admin/ 转发给 Gunicorn 与 Django；后端校验共享 Session '
              '及业务归属。单机也使用相同的无状态应用和数据库会话设计，便于后续扩展。'),
             ('p', '宿主机定时启动同步容器，承运商可通过验签 Webhook 推送轨迹。数据库和证书使用持久化卷；前端静态随版本镜像发布。备份加密保存到主机之外。单机本地卷仅用于此模式，不作为正式多实例共享业务存储。')]},
 {'title': '无状态应用与多用户管理',
  'blocks': [('h', '跨实例运行约束'),
             ('p', '应用进程和容器不保存需要跨请求保留的业务状态。任何健康实例都可处理下一次请求，实例删除或重建不影响共享业务数据；负载均衡无需 sticky session。'),
             ('table',
              (['状态或资源', '共享方式', '运行约束'],
               [['登录会话', 'PostgreSQL 数据库 Session', '显式 db 后端；所有实例使用稳定的同一 SECRET_KEY'],
                ['运单和轨迹', '共享高可用 PostgreSQL', 'ORM 与事务写入；归属校验在服务端执行'],
                ['同步任务', '数据库任务记录和 advisory lock', '共享锁与租约；异常可回收；更新幂等'],
                ['前端与静态文件', '随版本镜像发布', '各实例内容一致；不依赖运行时本机修改'],
                ['用户附件', '对象存储', '按客户授权访问；禁止容器本地持久保存']],
               [1.15, 2.0, 3.75])),
             ('p', '各实例使用兼容代码、数据库结构和安全设置；SECRET_KEY 由密钥服务或受限配置提供。不能每次容器启动随机生成密钥，否则会破坏已有 Session。部署时先验证跨实例登录和数据库迁移兼容性。'),
             ('h', '后台管理员与普通客户'),
             ('p', '运营通过 Django Admin 管理账号、客户、运单和轨迹。可建立多个管理员账号，使用 is_staff、模型权限和岗位权限组授权；超级管理员仅用于必要维护，不作为日常共用账号。'),
             ('p', '普通客户登录客户页面，只能查看所属客户的运单与轨迹。多个客户可同时访问，同一客户可按业务需要绑定多个账号。权限由后端过滤查询和校验写入，不能仅靠前端隐藏按钮或传入 customer_id。'),
             ('p', '验收应覆盖客户 A 无法读取客户 B 数据、普通客户无法进入后台、不同管理员的权限差异，以及一次登录后请求轮流落到两台实例仍保持会话。实际测试范围以交付测试记录为准。')]},
 {'title': '主域名备用入口与公司信息',
  'blocks': [('h', '双域名接入同一套服务'),
             ('p', '主域名与备用域名均接入托管负载均衡。此安排主要覆盖单个域名、解析或入口地址问题；两域名共享负载均衡和后端时，不能解决这套共享服务的整体故障。域名均为待配置，正式启用前需确认所有权和续费责任。'),
             ('table',
              (['配置项', '主域名与备用域名均需完成'],
               [['DNS 与 TLS', '提前解析至正确入口；证书覆盖对应主机名并监控续期'],
                ['入口与 Django', '配置 LB 路由和 Caddy 站点；ALLOWED_HOSTS 使用精确白名单'],
                ['写操作可信来源', 'CSRF_TRUSTED_ORIGINS 列出准确的 HTTPS 来源，不使用任意通配'],
                ['Session Cookie', '使用各域 host-only Cookie，不扩大 SESSION_COOKIE_DOMAIN'],
                ['健康探测', '独立检查 DNS、TLS、HTTP 与 API；区分跨域策略失败和业务故障']],
               [1.45, 5.45])),
             ('h', '客户切换与提前告知'),
             ('p', '从主域名切换到备用域名后重新登录；不在 URL 拼接令牌，不跨域自动传送密码。第一阶段可由维护人确认故障后人工通知切换，不要求自动切域。'),
             ('p',
              '若主域名无法解析或首屏无法加载，页面中的 JavaScript 无法显示备用地址。因此应提前通过合同、邮件、客户书签及独立状态页公布备用入口。页面已加载但 API 请求失败时，可提示已配置的备用入口，并显示数据最后更新时间。'),
             ('h', '公司信息占位与上线替换'),
             ('table',
              (['项目', '当前值', '发布前要求'],
               [['项目或公司名称', '待定', '确认正式显示名称'],
                ['联系电话', '000-00000000', '占位号码；替换为经核实的业务电话'],
                ['联系邮箱', 'support@example.com', '示例邮箱；替换并验证实际收件能力'],
                ['业务域名', '主域名 待配置\n备用域名 待配置', '确认 DNS、TLS、续费及维护负责人']],
               [1.25, 2.0, 3.65])),
             ('p', '跨地域灾备属于后续独立方案，需要另一地域站点、数据复制、恢复目标和切换演练；不得仅凭备用域名标注为灾备已完成。')]},
 {'title': '技术栈与组件职责',
  'blocks': [('p', '以下版本是实施基线，并非要求使用固定旧补丁。开发启动和上线前应按官方兼容矩阵锁定受支持的补丁版本，并记录依赖锁文件及镜像版本。'),
             ('table',
              (['层级', '推荐技术', '职责与选用原因'],
               [['运行环境', 'Ubuntu 24.04 LTS\nPython 3.12', '成熟的 Linux 长期支持环境；Python 使用应用容器内版本'],
                ['后端框架', 'Django 5.2 LTS', '业务模型、ORM、迁移、账号认证及权限基础'],
                ['接口与后台', 'Django JSON views\nDjango Admin', '当前客户 API；后台与权限组；首期无需 DRF'],
                ['数据库', 'PostgreSQL 17\npsycopg 3', '保存客户、运单、轨迹、任务与审计记录；事务与约束'],
                ['应用服务', 'Gunicorn WSGI', '托管 Django；首期普通 HTTP 接口无需 ASGI 或 WebSocket'],
                ['HTTPS 入口', 'Caddy 2', '证书管理、HTTPS、静态文件和反向代理'],
                ['客户页面', 'HTML5 CSS3\nJavaScript ES Modules', '复用现有 Demo 布局；通过 fetch 调用同域 API'],
                ['物流接入', 'HTTPX\nDjango management command', '调用承运商 HTTPS API；设置超时、重试和限流'],
                ['任务调度', 'systemd timer\nPostgreSQL 任务表', '冗余入口；共享数据库 advisory lock、租约和重试记录'],
                ['部署与检查', 'Docker Compose v2\npytest pytest-django Ruff', '管理服务；验证业务规则、权限和代码规范']],
               [1.05, 2.3, 3.55])),
             ('h', '首期按需配置'),
             ('p', '地图可先沿用路线示意，实际运输位置以承运商最近扫描为准。附件上传需要时使用对象存储，校验类型、大小和访问权限；禁止将用户上传文件留在某个应用容器或宿主机本地。'),
             ('p',
              'Redis 与 Celery 暂不部署。数据库任务轮询无法满足延迟、积压或并发要求时，再增加队列。多主机 Compose 配合托管负载均衡与高可用数据库即可满足本方案，无需为横向扩展先引入 Kubernetes。')]},
 {'title': '应用模块与数据接口',
  'blocks': [('h', '业务模块与核心数据'),
             ('table',
              (['模块', '核心对象', '主要规则'],
               [['客户与账号', 'User Customer\nCustomerUser', 'Django 密码哈希；账号关联客户；管理员按组授权'],
                ['运单管理', 'Shipment Package', '内部 ID、客户 ID、外部单号、承运商、起终点及 ETA'],
                ['物流轨迹', 'TrackingEvent', '发生时间与接收时间分开记录；事件来源、地点及原始状态'],
                ['承运商接入', 'Carrier SyncJob', '按服务商适配；记录重试次数、时间与结果'],
                ['操作审计', 'AuditLog', '记录谁在何时修改了什么；人工更正保留原因']],
               [1.1, 1.9, 3.9])),
             ('p', '数据库模型、迁移、SQL 与字段说明随实现交付。运单按客户、状态和更新时间索引；单号按服务商范围约束，轨迹按事件 ID 或指纹去重。具体字段以代码和 README 为准。'),
             ('h', '本地客户 API 与后台接口'),
             ('table',
              (['方法与路径', '功能与权限'],
               [['GET /api/public/config/\nGET /api/auth/me/', '读取公司与域名配置；恢复当前登录会话'],
                ['GET /api/auth/csrf/', '建立 CSRF Cookie，供登录及写操作使用'],
                ['POST /api/auth/login/\nPOST /api/auth/logout/', '建立或注销数据库 Session；写操作验证 CSRF'],
                ['GET /api/shipments/', '本人运单；limit 与 offset 分页；返回 results count next'],
                ['GET /api/shipments/{number}/', '本人运单详情及轨迹；禁止跨客户访问'],
                ['POST /api/shipments/{number}/events/', '管理员追加轨迹；提交 status location note sourceKey'],
                ['POST /api/package-prealerts/', '提交本人待确认预报；返回 prealert 编号与状态'],
                ['GET /admin/', '正式运营后台；仅具有相应权限的 staff 账号']],
               [3.0, 3.9])),
             ('p', '客户 API 与后台共用数据库，归属由登录账号在服务端确定。轨迹追加可传 occurredAt；预报使用 submissionKey 保证重试幂等，入库需运营确认。承运商 Webhook、轮询与真实同步仍属后续接入；已完成测试范围以 README 记录为准。'),
             ('p', '时间以带时区 UTC 保存并转换展示；最近扫描、预计送达与实际签收明确区分。')]},
 {'title': '服务器配置与发布运维',
  'blocks': [('h', '正式部署资源与网络'),
             ('table',
              (['项目', '起步建议', '说明'],
               [['应用主机', '2 台 Linux VM\n每台 2 vCPU 4 GB', '分别位于不同故障域；根据压测和同步耗时调整'],
                ['数据库', '托管高可用 PostgreSQL', '启用主备、自动故障切换、自动备份及恢复验证'],
                ['公网入口', '托管冗余 LB\n主域名和备用域名', '两域名同一套服务；入口健康检查摘除故障实例'],
                ['应用端口', 'Caddy 受 LB 访问\nGunicorn 内部 8000', '源站限制来自 LB；Web 不直接暴露公网'],
                ['数据库与运维', 'PG 私网 5432\nSSH 来源限制', 'DB 无公网入口；运维经 VPN 或指定来源']],
               [1.15, 2.0, 3.75])),
             ('p',
              '每台主机运行相同版本镜像及兼容配置，前端和 collectstatic 产物随镜像发布。用户附件保存在对象存储；数据库、Session 和任务状态均在共享 '
              'PostgreSQL。密钥由受限配置或密钥服务注入，生产与测试环境分开。'),
             ('h', '发布顺序'),
             ('number', '在测试环境检查客户隔离、共享 Session、轨迹去重、承运商异常和数据库迁移；构建同一版本镜像。'),
             ('number', '备份并确认可恢复；预配两域名的 DNS、TLS、精确主机白名单及 CSRF 可信来源。'),
             ('number', '由一次发布任务执行 migrate；每台主机执行 collectstatic，生成 Caddy 共享静态卷内容。数据库变更兼容新旧应用并存，避免各实例重复迁移。'),
             ('number', '逐台更新应用：先从 LB 摘除，更新并通过就绪检查后接回。保留另一实例提供服务，并监控错误率。'),
             ('number', '验收登录、跨实例会话、客户隔离、后台更新及备用入口；再启用两个主机上的同步 timer，验证任务防重入。'),
             ('h', '回滚与维护'),
             ('p', '保留上一版本镜像和配置。优先使用向后兼容的数据库变更，使代码回滚无需恢复数据库。破坏性迁移应单独安排维护窗口；镜像回滚不等于数据库回滚。'),
             ('p', '定期演练停止应用实例、隔离一台主机、数据库故障切换及备份恢复。LB 应自动摘除故障实例；Compose restart 仅处理进程退出，不能替代健康检查与告警。单机试运行发布仍需约定维护窗口。')]},
 {'title': '物流同步与安全保障',
  'blocks': [('h', '物流接入与任务执行'),
             ('p', '人工录入与承运商接口写入统一的轨迹模型，并记录来源。承运商能力以实际合同和文档为准：通常返回城市、网点或扫描地点；只有实际提供连续坐标和授权时，才能支持实时定位。接口不可用时，页面保留最后已知轨迹并显示更新时间。'),
             ('p',
              '两台主机均可每 10 分钟触发 systemd oneshot 同步命令，batch-size 初值 100，按限流与耗时调整。调度入口冗余；专用数据库连接持有 advisory lock '
              '防止不同主机同时运行。业务记录使用租约或超时回收，主机故障后由其他入口继续。'),
             ('p', '任务记录尝试次数、下次重试、最后成功时间和错误。设置请求与任务超时，租约过期后回收；网络故障、429 和可恢复错误按退避重试。轨迹更新必须幂等，不能只依赖进程内锁或本机文件锁。客户查件不实时等待外部承运商请求。'),
             ('p', 'Webhook 按服务商机制验签、防重放、限制请求体大小。验证通过后先保存原始事件，再返回成功，后续由周期任务处理。Webhook 和轮询共享归一化及去重逻辑；乱序旧事件可以补入历史，但不应覆盖较新的当前状态。'),
             ('h', '账号与数据保护'),
             ('p',
              '会话显式使用 django.contrib.sessions.backends.db，所有实例共享稳定 SECRET_KEY 与兼容设置。Session Cookie 为 '
              'HttpOnly、Secure、SameSite=Lax，且只对当前主机有效；CSRF Cookie 为 Secure 和 SameSite=Lax。写操作显式验证 CSRF，首期无需 JWT 或粘性会话。'),
             ('p',
              '生产设置 DEBUG=False，仅信任受控代理的 HTTPS 头，精确配置允许主机与可信来源。后台管理员按岗位授权，建议 MFA '
              '或受控身份入口；登录失败限速尚未实现，上线前需补齐。审计人工修改，日志不记录密码、密钥、完整地址或敏感回调正文。'),
             ('h', '监控与告警'),
             ('p', '监控 HTTPS 可用性、延迟与错误率、每台主机资源、LB 健康目标、数据库主备和连接、任务积压、同步延迟及备份时间。外部探测独立于业务主机运行；主域名与备用域名分别检查 DNS、TLS 与 HTTP。'),
             ('p', '同步失败、任务积压、磁盘不足、故障切换和备份超期均通知指定维护人。存活检查验证进程，就绪检查验证数据库依赖；日志附请求 ID、运单 ID 和任务 ID，便于跨实例排查。')]},
 {'title': '备份成本与实施安排',
  'blocks': [('h', '数据备份与恢复目标'),
             ('p', '单机试运行可每日 pg_dump 自定义格式导出，加密后上传异机对象存储。正式托管数据库启用自动备份、时间点恢复及所需跨域备份，核对供应商能力。保留周期按政策配置；附件、配置、角色重建方式和解密密钥也纳入恢复安排。'),
             ('p', 'RPO 24 小时、RTO 4 小时仅作为试运行的备份恢复演练目标，需以恢复演练证明。正式高可用的故障切换时间及数据丢失窗口应另定并实测，不能沿用备份指标推导。高可用主备不能替代备份，备份也不能替代在线冗余。'),
             ('h', '成本构成与扩展条件'),
             ('p', '持续费用包括两台应用主机、负载均衡、托管高可用数据库、流量、域名、对象存储、备份、承运商接口和维护工时。云厂商、地区和业务量待确认，不使用未经核实报价；若先用低成本单机，应明确接受其停机风险。'),
             ('p', '正式上线以双主机、冗余入口和高可用数据库为推荐基线。持续任务积压时评估 Celery、Redis 或托管队列；跨地域灾备需独立站点、数据复制和切换演练。两个域名接同一服务，不能替代地域灾备。'),
             ('h', '实施顺序与验收'),
             ('table',
              (['阶段', '主要产出', '验收重点'],
               [['本次本地基础', '数据库、登录 API、权限与 Admin', '按 README 启动；客户 A 不可读客户 B 数据'],
                ['客户页面接入', '调用 API 显示运单与轨迹', '跨设备读取数据库内容；服务端校验归属'],
                ['承运商接入', '适配、同步、验签回调', '重复与乱序正确；限流、失败与租约可恢复'],
                ['正式部署验收', '双主机、双域名、监控与备份', '跨实例会话、单机故障、DB 切换及恢复演练']],
               [1.2, 2.5, 3.2])),
             ('p', '上线前确认承运商权限、地区与数据量、账号来源、正式域名、公司电话邮箱、可接受停机及数据丢失窗口。公司名称待定；页面占位联系方式需替换并核实后再发布。'),
             ('h', '官方实施参考'),
             ('refs',
              [('Django 部署检查清单', 'https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/'),
               ('Django 数据库会话', 'https://docs.djangoproject.com/en/5.2/topics/http/sessions/'),
               ('PostgreSQL 高可用', 'https://www.postgresql.org/docs/17/high-availability.html'),
               ('PostgreSQL 备份恢复', 'https://www.postgresql.org/docs/17/backup.html'),
               ('Docker Compose 部署', 'https://docs.docker.com/compose/production/'),
               ('Caddy 反向代理', 'https://caddyserver.com/docs/caddyfile/directives/reverse_proxy')])]}]

doc = Document()
sec = doc.sections[0]
sec.page_width=Inches(8.5); sec.page_height=Inches(11)
sec.top_margin=Inches(.66); sec.bottom_margin=Inches(.65)
sec.left_margin=Inches(.8); sec.right_margin=Inches(.8)
sec.header_distance=Inches(.22); sec.footer_distance=Inches(.25)
styles=doc.styles
for name in ['Normal','Title','Heading 1','Heading 2','Caption','List Bullet','List Number']:
 st=styles[name]; st.font.name=CONTEXT.font_family; st.font.color.rgb=RGBColor.from_string('000000')
 fonts=st.element.get_or_add_rPr().get_or_add_rFonts()
 for attr in list(fonts.attrib):
  if attr.endswith('Theme') or attr.endswith('theme'): del fonts.attrib[attr]
 fonts.set(qn('w:eastAsia'),CONTEXT.font_family)
 for border in st.element.findall('.//' + qn('w:pBdr')): border.getparent().remove(border)
 for color in st.element.findall('.//' + qn('w:color')):
  for attr in list(color.attrib):
   if attr != qn('w:val'): del color.attrib[attr]
 st.paragraph_format.widow_control=True
normal=styles['Normal']; normal.font.size=Pt(11); normal.paragraph_format.line_spacing=Pt(16.5); normal.paragraph_format.space_after=Pt(7)
styles['Title'].font.size=Pt(23); styles['Title'].font.bold=True; styles['Title'].paragraph_format.space_after=Pt(10)
styles['Heading 1'].font.size=Pt(19);styles['Heading 1'].font.bold=True;styles['Heading 1'].paragraph_format.space_after=Pt(10)
styles['Heading 2'].font.size=Pt(12.5);styles['Heading 2'].font.bold=True;styles['Heading 2'].paragraph_format.space_before=Pt(10);styles['Heading 2'].paragraph_format.space_after=Pt(5)
styles['Caption'].font.size=Pt(9);styles['Caption'].font.italic=False;styles['Caption'].paragraph_format.space_after=Pt(9)
for n in ['List Number','List Bullet']:
 styles[n].font.size=Pt(11);styles[n].paragraph_format.line_spacing=Pt(16.5);styles[n].paragraph_format.space_after=Pt(5)
doc.core_properties.title='集运系统 Python 技术方案与部署架构'
doc.core_properties.subject='Python 后端选型 轻量部署架构 技术栈及实施安排'
doc.core_properties.author='项目名称待定'
doc.core_properties.keywords='Python,Django,PostgreSQL,Docker Compose,物流系统,部署架构'

footer=sec.footer.paragraphs[0]; footer.alignment=WD_ALIGN_PARAGRAPH.RIGHT
r=footer.add_run('集运系统技术方案    ');r.font.size=Pt(8);r.font.color.rgb=RGBColor.from_string('777777')
field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE');footer._p.append(field)

def table(headers,rows,widths):
 t=doc.add_table(rows=1,cols=len(headers));t.alignment=WD_TABLE_ALIGNMENT.CENTER;t.autofit=False
 for c,w in zip(t.columns,widths): c.width=Inches(w)
 for idx,rowvals in enumerate([headers]+rows):
  cells=t.rows[0].cells if idx==0 else t.add_row().cells
  if idx==0:
   rep=OxmlElement('w:tblHeader');t.rows[0]._tr.get_or_add_trPr().append(rep)
  pr=t.rows[idx]._tr.get_or_add_trPr(); el=OxmlElement('w:cantSplit');pr.append(el)
  for j,(c,value) in enumerate(zip(cells,rowvals)):
   c.width=Inches(widths[j]);c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
   c.text=value
   tcpr=c._tc.get_or_add_tcPr()
   mar=OxmlElement('w:tcMar')
   for edge in ['top','left','bottom','right']:
    e=OxmlElement('w:'+edge);e.set(qn('w:w'),'95' if edge in ['top','bottom'] else '110');e.set(qn('w:type'),'dxa');mar.append(e)
   tcpr.append(mar)
   borders=OxmlElement('w:tcBorders')
   for edge in ['top','left','bottom','right']:
    e=OxmlElement('w:'+edge);e.set(qn('w:val'),'single');e.set(qn('w:sz'),'4');e.set(qn('w:color'),'D9D9D9');borders.append(e)
   tcpr.append(borders)
   shade=OxmlElement('w:shd');shade.set(qn('w:fill'),'DCE8F3' if idx==0 else ('F6F8FA' if idx%2==0 else 'FFFFFF'));tcpr.append(shade)
   for p in c.paragraphs:
    p.paragraph_format.space_after=Pt(0);p.paragraph_format.space_before=Pt(0);p.paragraph_format.line_spacing=Pt(14.5)
    if j==0 and len(headers)==3: p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    for r in p.runs:
     r.font.size=Pt(10);r.font.bold=idx==0;r.font.color.rgb=RGBColor.from_string('000000')
 doc.add_paragraph().paragraph_format.space_after=Pt(0)

def hyperlink(p,label,url):
 rel=p.part.relate_to(url,'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink',is_external=True)
 h=OxmlElement('w:hyperlink');h.set(qn('r:id'),rel)
 r=OxmlElement('w:r');pr=OxmlElement('w:rPr');color=OxmlElement('w:color');color.set(qn('w:val'),'31547A');pr.append(color);sz=OxmlElement('w:sz');sz.set(qn('w:val'),'18');pr.append(sz);r.append(pr)
 tx=OxmlElement('w:t');tx.text=label;r.append(tx);h.append(r);p._p.append(h)

for i,page in enumerate(pages):
 if i: doc.add_page_break()
 doc.add_paragraph(page['title'],'Title' if i==0 else 'Heading 1')
 if 'meta' in page:
  p=doc.add_paragraph(page['meta']);p.paragraph_format.space_after=Pt(18)
  for r in p.runs:r.font.size=Pt(9);r.font.color.rgb=RGBColor.from_string('777777')
 for kind,value in page['blocks']:
  if kind=='p':doc.add_paragraph(value)
  elif kind=='h':doc.add_paragraph(value,'Heading 2')
  elif kind=='number':doc.add_paragraph(value,'List Number')
  elif kind=='table':table(*value)
  elif kind=='image':
   p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.space_after=Pt(3);p.paragraph_format.line_spacing=1.0
   run=p.add_run();run.add_picture(str(CONTEXT.asset(value)),width=Inches(6.1))
   props=run._r.xpath('.//wp:docPr')[0];props.set('descr','双域名经冗余负载均衡访问不同故障域的无状态应用主机；应用和同步任务共享高可用 PostgreSQL，附件及备份使用对象存储。' if 'ha-architecture' in value else '单主机试运行：客户和管理员经 Caddy 访问 Django；Web 与同步任务共享 PostgreSQL，备份保存到异机对象存储。')
  elif kind=='caption':
   p=doc.add_paragraph(value,'Caption');p.alignment=WD_ALIGN_PARAGRAPH.CENTER
  elif kind=='refs':
   p=doc.add_paragraph();p.paragraph_format.space_after=Pt(0);p.paragraph_format.line_spacing=1.3
   for n,(label,url) in enumerate(value):
    if n==3:p.add_run().add_break()
    elif n:p.add_run('  ·  ')
    hyperlink(p,label,url)

out=OUT/'集运系统Python技术方案与部署架构.docx'
doc.save(out)
print(out)
print('Planned pages:',len(pages))
