# 集运通 Implementation Plan

> 历史记录：本计划对应最初的纯静态 Demo。当前 Django + PostgreSQL 实现与测试范围以项目 README 为准。

> **For agentic workers:** Use superpowers:subagent-driven-development to implement the independent modules.

**Goal:** 提供可以登录并查询集运位置的可运行演示。

**Architecture:** 静态 SPA，以数据模块管理示例运单，地图模块绘制示意路线，主应用管理页面、登录和交互。无第三方网络请求。

**Tech Stack:** HTML / CSS / JavaScript ES Modules / localStorage / Python static server / Node built-in tests.

**Spec:** docs/superpowers/specs/2026-11-18-parcelink-design.md

## Global Constraints

- 中文界面；示例数据明确标注；无构建依赖。
- 文件职责分离：data.js 数据与校验、map.js/map.css 地图、app.js 应用交互、styles.css 视觉。
- 数据渲染必须转义；状态更改持久化并添加轨迹。

## Tasks

- [x] 1. 数据模块及测试：客户/管理员示例认证、六条不同状态运单、搜索筛选、统计、状态更新与本地持久化。
- [x] 2. 地图模块：基于 origin、destination、status、location 显示对应的示意路线，清晰标明不是真实 GPS；自包含 CSS。
- [x] 3. 页面与交互：登录、侧栏导航、总览、运单详情、预报弹窗、地址与帮助、管理员更新弹窗；响应式样式。
- [x] 4. 验证和交付：Node 数据测试、浏览器关键流程、移动端布局，提供 README 与本地体验地址。

## 验证记录

- Node 内置测试 10 项通过，app.js/map.js 语法检查通过。
- 浏览器完成客户登录、错误密码、目的地查询、空结果恢复、管理员签收更新、客户同步、刷新持久化、新增预报、手机导航与390px无横向溢出检查。
- 已签收日期取实际签收轨迹；快递单号同时有HTML和JS格式校验；移动导航包含可访问名称；保存失败明确提示仅当前页面有效。
- 已恢复6条初始示例数据，退出到登录页。截图位于 artifacts/login.jpg 和 artifacts/dashboard.jpg。
