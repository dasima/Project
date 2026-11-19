# 文档与架构图生成器

这里保存部署方案、数据库说明及配图的可复现源码。推荐 Python 3.12。下面命令从 Parcelink 项目根目录执行；脚本根据自身位置定位项目，因此也可使用脚本的绝对路径从其他工作目录运行。

## 安装依赖

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r scripts/docs/requirements-docs.txt
```

生成 Word 和图片不需要 LibreOffice、真实数据库、数据库账号或生产密钥。数据库说明通过独立的 Django 文档设置载入当前 `backend/logistics/models.py`，使用 PostgreSQL 后端确定字段类型，不连接数据库，也不运行迁移或查询业务数据。

## 默认生成

先生成配图，再生成引用这些图片的 Word 文档：

```sh
.venv/bin/python scripts/docs/deployment/draw_architecture.py
.venv/bin/python scripts/docs/deployment/draw_ha_architecture.py
.venv/bin/python scripts/docs/database/draw_er.py
.venv/bin/python scripts/docs/deployment/build_document.py
.venv/bin/python scripts/docs/database/build_document.py
```

默认输出根目录为项目内的 `build/docs/`，不会覆盖已有交付物。输出根目录内保留项目的相对目录结构：

- `assets/deployment/architecture.png` 和 `.svg`：单机试运行架构图。
- `assets/deployment/ha-architecture.png` 和 `.svg`：双主机正式部署架构图。
- `assets/database/er-overview.png` 和 `.svg`：业务数据库关系图。
- `docs/deployment/集运系统Python技术方案与部署架构.docx`：部署方案。
- `docs/database/数据库表结构与SQL操作说明.docx` 和 `数据库表结构.md`：数据库说明。
- `qa/database/field-counts.json`：模型字段计数与计划页数。

Word 生成器优先读取输出根目录中的配图；未找到时读取项目现有 `assets/` 中的图片。每个入口支持 `--help`。

## 隔离预览与更新交付物

用 `--output-root DIR` 或 `DOCS_OUTPUT_ROOT` 设置输出根目录；命令行参数优先。相对路径以运行命令时的工作目录为基准。

例如将全部结果写到隔离目录：

```sh
export DOCS_OUTPUT_ROOT=/tmp/parcelink-doc-preview
.venv/bin/python scripts/docs/deployment/draw_architecture.py
.venv/bin/python scripts/docs/deployment/draw_ha_architecture.py
.venv/bin/python scripts/docs/database/draw_er.py
.venv/bin/python scripts/docs/deployment/build_document.py
.venv/bin/python scripts/docs/database/build_document.py
```

完成内容与排版检查后，才显式指定项目根目录更新正式交付物。以下命令会覆盖对应的现有文件：

```sh
# 在 Parcelink 项目根目录执行；只运行需要更新的入口。
.venv/bin/python scripts/docs/database/draw_er.py --output-root .
.venv/bin/python scripts/docs/database/build_document.py --output-root .
```

## 中文字体

绘图需要支持中文的 TrueType 或 OpenType 字体。脚本会查找常见的 Noto Sans CJK、思源黑体、文泉驿、微软雅黑及苹方字体；找不到可用字体时会提示配置，不会静默使用缺字字体。

可使用 `--font PATH` 或 `DOCS_FONT_PATH` 指定字体文件，使用 `--font-family NAME` 或 `DOCS_FONT_FAMILY` 指定 Word 与 SVG 使用的字体族名称。命令行参数优先；未指定字体族时从选中的字体文件探测名称。字体文件路径和字体族名称是不同的值，例如：

```sh
# Linux 示例：先通过系统包管理器安装 fonts-noto-cjk。
export DOCS_FONT_PATH=/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc
export DOCS_FONT_FAMILY='Noto Sans CJK SC'
.venv/bin/python scripts/docs/database/draw_er.py --output-root /tmp/parcelink-doc-preview
.venv/bin/python scripts/docs/database/build_document.py --output-root /tmp/parcelink-doc-preview
```

其他常见字体文件位置包括 macOS 的 `/System/Library/Fonts/PingFang.ttc` 和 Windows 的 `C:/Windows/Fonts/msyh.ttc`。实际路径因系统或安装方式不同而变化；也可指定自己安装的思源黑体或 Noto 字体。字体须按其许可自行安装，仓库不打包系统字体。

`DOCS_FONT_PATH` 让 Pillow 能读取字体文件，不会自动把该字体安装到 Word、LibreOffice 或 SVG 查看器。打开和渲染文档的环境也应安装对应字体族。不同字体与软件版本可能改变换行和页数，因此输出应再次检查。

## 内容维护与渲染检查

数据库字段名称、PostgreSQL 类型、可空属性、ORM 默认值及字段计数从当前模型提取。用途解释、约束说明、SQL 示例、部署方案和图中文字仍在生成器中维护；修改模型、迁移或业务行为后，应同步核对这些说明。生成成功仅确认文件已写入，不能代替 SQL 执行验证或逐页排版检查。

如需本地渲染检查，另行安装 LibreOffice 和 Poppler。以下示例将 Word 转为 PDF，再查看页数和生成逐页 PNG；它们不是 Python 生成器的依赖：

```sh
mkdir -p /tmp/parcelink-doc-preview/render/database
soffice --headless --convert-to pdf \
  --outdir /tmp/parcelink-doc-preview/render/database \
  /tmp/parcelink-doc-preview/docs/database/数据库表结构与SQL操作说明.docx
pdfinfo /tmp/parcelink-doc-preview/render/database/数据库表结构与SQL操作说明.pdf
pdftoppm -png -r 120 \
  /tmp/parcelink-doc-preview/render/database/数据库表结构与SQL操作说明.pdf \
  /tmp/parcelink-doc-preview/render/database/page
```

部署方案使用同样方式转换。检查每页图片中的中文缺字、表格溢出、断行、标题与分页，并核对 Markdown 中的图片引用；不要仅凭计划页数判断排版通过。
