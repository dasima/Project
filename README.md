# Project

个人项目集合。每个项目放在独立目录中，分别维护依赖、环境配置、数据库、部署文件和文档。

## 子项目

- [Parcelink 集运系统](projects/parcelink/README.md)：Python / Django + PostgreSQL 集运查询与运营管理 Demo，支持客户登录、运单轨迹、多个客户账号与管理后台。
- [Visa Appointment 留学签证预约系统](projects/visa-appointment/README.md)：法国、德国和英国留学签证预约监测与抢号方案，包含会话预备、低延迟执行及官方结果核验；当前处于系统设计阶段。

集运系统的启动入口：

```sh
cd projects/parcelink
# 按该目录 README 配置 .env 并启动。
```

## 新增项目的约定

1. 在 `projects/<project-name>/` 下创建新项目，使用简短的小写英文目录名。
2. 项目内提供独立 `README.md`，说明依赖、初始化、启动、测试和部署方式；环境模板与部署文件也放在项目内。
3. 总仓库只保留一个 `.git/`；子项目直接作为普通目录管理，不再执行 `git init`。需要独立仓库时，再单独评估拆分或 Git submodule。
4. 更新本页的项目索引。CI 放在 `.github/workflows/`，按项目目录过滤触发；每个任务在对应子目录执行。
5. 实际密码、私有环境文件、数据库备份、依赖缓存和运行产物不提交；提交环境示例、数据库迁移和必要的构建源码。

每个项目使用自己的部署环境和数据卷。更新某个子项目不会自动发布其他项目。

## 原有内容

保留既有目录和文件：[Python 脚本](python/)、[Shell 脚本](shell/)、[C++ 示例](test.cpp) 和 [markdown 文件](markdown)。新增集运系统不改变这些内容。



