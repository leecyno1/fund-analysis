# 专业基金研究与 Newma-Desk 模组架构 v2

状态：Canonical
方法论版本：`2.0.0`
Desk：Manifest `1.1` / Bridge `1.0` / ViewSpec `1.0`

## 1. 架构结论

本项目不再把“基金筛选”理解为一次加权排名，而是一个有证据门槛、尽调责任、结论版本和持续复核的研究系统。

新版决策模型固定为：

```text
研究范围 → 证据质量 → 同类/基准 → 量化轨迹 → 持仓/风格
        → 投资与运营尽调 → 决策治理 → 持续监控 → 方法审计
```

输出采用 `Gates + Pillars + Confidence`：

- Gates：身份、数据、同类、基准、关键人员和运营完整性等硬门槛。
- Pillars：量化、持仓、People、Process、Parent、Price、运营等分柱判断。
- Confidence：证据覆盖、时效、一致性和统计不确定性共同决定的置信度。
- Counter-evidence：每个结论必须记录反证和未决问题。
- Reversal conditions：每个结论必须说明在什么变化下失效。

禁止使用一个合成总分直接生成研究晋级或优势结论。历史 `Score` 和旧评分页面仅作兼容展示，不是 v2 的决策核心。

## 2. 九层专业研究域

| 层 | 研究问题 | 核心方法 | 现有可复用资产 |
| --- | --- | --- | --- |
| 1. 研究范围与身份 | 研究对象是谁，哪些份额属于同一基金，终止基金是否保留 | 份额合并、point-in-time universe、主动/被动分支 | `FundEntity`、`FundShareClass`、`FundLifecycleEvent` |
| 2. 证据与数据质量 | 数据来自哪里、何时有效、缺了什么 | as-of、vintage、coverage、lineage、replay | `DataSourceSnapshot`、`MetricSnapshot`、`EvidenceLedger` |
| 3. 同类组与基准 | 与谁比较，什么基准能解释策略 | category peer、benchmark suitability、RBSA | `PeerGroup`、`BenchmarkMapping`、`peer-group-benchmark` |
| 4. 量化轨迹 | 净费后表现是否稳健，技能和运气如何区分 | rolling、capture、drawdown、factor alpha、bootstrap、value added | `MetricSnapshot`、`FactorExposure`、`PerformanceAttribution` |
| 5. 持仓、风格与容量 | 实际做了什么，是否漂移或隐形指数化 | Active Share、HBSA/RBSA、look-through、capacity | `Holding`、`HoldingLookthroughSnapshot`、`holding-deep-research` |
| 6. 投资与运营尽调 | People、Process、Parent、Price 与运营是否可靠 | investment DDQ、operational DDQ、key-person review | `ManagerTenureSlice`、`FundCompanyResearchProfile` |
| 7. 决策治理 | 为什么形成当前结论，反证和反转条件是什么 | Type I/II error、版本化 thesis、reviewer trail | `ResearchReport`、`ResearchMethodologyTemplate` |
| 8. 持续监控 | 什么变化会触发重新研究 | manager/style/risk/fee/data triggers | `FundChangeHistory`、`AlertRule`、`AlertEvent` |
| 9. 方法与审计 | 结论能否复现，方法是否一致 | methodology version、snapshot、audit trail | `ResearchMethodologyDimension`、`ResearchMethodologyMapping` |

领域定义的代码规范源位于：

- `lib/fund-research/contracts/research-decision.ts`
- `lib/fund-research/methodology/professional-methodology.ts`

## 3. 系统分层

```text
Newma-Desk Suite / 独立 Web 页面
  └─ ViewSpec 语义页面 + Context Bridge + security.selected
      └─ Research Application Services
          ├─ Universe & Identity
          ├─ Evidence Quality
          ├─ Peer & Benchmark
          ├─ Quant / Holdings / Style
          ├─ Due Diligence
          ├─ Decision Governance
          └─ Monitoring
              └─ Research Tools
                  └─ Dedicated PostgreSQL + Source Adapters
```

### 展示层

- `overview` 是每日基金研究驾驶舱，先显示今天需要处理的变化、证据健康、当前对象和复核任务。
- 其他工作区显示研究状态、证据、门槛、分柱判断和可执行 Action。
- 不在 React 页面复制核心规则。
- 重要表格使用真实 `<table>`，页面提供 `data-vibe-*` 语义。
- 页面独立运行时可直接访问；嵌入 Desk 时接受宿主主题、语言、时区和 Context 请求。

### 应用服务层

- 负责编排研究阶段，不直接发明指标。
- 把旧工具输出归一为 `ResearchGate`、`PillarAssessment` 和 `FundResearchDecision`。
- 所有正式结论必须绑定方法版本与证据快照。

### 工具与分析层

- 保留现有 `peer-group-benchmark`、`benchmark-attribution`、`holding-deep-research`、`manager-research-loop` 等工具。
- 后续新增 bootstrap alpha、RBSA、Active Share、capacity/value-added 时，必须作为可独立测试工具实现。
- AI 只能解释、组织问题和生成草稿，不能绕过确定性工具或证据门槛。

### 数据层

- PostgreSQL 是基金研究业务库，Storage Mode 为 `dedicated`。
- 原始数据、指标、证据和结论都带 as-of / source / methodology version。
- 终止基金和历史份额不物理删除，用生命周期状态参与 point-in-time 查询。
- Desk 主库不保存基金明细、完整报告或数据库凭据。

### 每日研究驾驶舱

驾驶舱是研究系统的操作入口，不是新的评分模型，也不替代九层研究域。其读取 seam 固定聚合：

- 基金研究业务库的全市场证据覆盖；
- 研究清单的销售规则与来源硬门槛；
- 未解决复核事件及其严重度；
- 数据同步失败、陈旧数据集和最新快照时点；
- 当前所选基金的净值时点、规模、同类组、基准、经理和数据质量。

任何入口失败都写入 `partial / unavailable` 状态并显示错误，禁止用演示值、新闻情绪比例或模型推测补齐。驾驶舱产生的是研究任务与导航，不产生买卖结论。

## 4. Newma-Desk Suite

Suite 描述文件：`desk/suite.json`。

| 页面 Mod | 路由 | 责任 |
| --- | --- | --- |
| `fund-research-overview` | `/mod/fund-research/overview` | 每日研究判断、证据健康、当前对象、补证队列与九层研究内核 |
| `fund-selection` | `/mod/fund-research/selection` | 研究范围、证据、同类和量化准入 |
| `fund-due-diligence` | `/mod/fund-research/due-diligence` | 投资与运营尽调 |
| `fund-peer-comparison` | `/mod/fund-research/peer-comparison` | 同类、基准、风格与容量横评 |
| `fund-monitoring` | `/mod/fund-research/monitoring` | 触发式复核与轻量复核索引 |
| `fund-methodology` | `/mod/fund-research/methodology` | 方法来源、版本和审计偏好 |

发现入口：`GET /.well-known/newma-desk-suite.json`。

### Bridge

`lib/newma-desk/bridge.ts` 实现：

- `vibedesk:hello → vibedesk:init → vibedesk:ack`
- 精确验证 `source`、`origin`、`modId`、`instanceId`
- 应用宿主 `theme / locale / timezone / appearance.cssVars`
- 响应 `vibedesk:context-request`
- 代理 Manifest Action 请求
- 接受和发送 `security.selected`

### Agent Context

Context 包含当前页面、稳定区块 ID、基金/ETF 选择、筛选器、数据时间与来源、Manifest Action、任务状态、方法版本和当前研究阶段。

### Storage

- 基金研究业务数据：`dedicated / fund-research-postgres`。
- `fund-monitoring` 轻量复核索引：Desk-managed `review-index`。
- `fund-methodology` 界面偏好：Desk-managed `methodology-preferences`。
- API Key、Cookie、数据库 URL、完整报告、行情明细不得进入 Desk-managed Storage。

## 5. Action 边界

确定性数据 Action：`fund.universe.query`、`fund.evidence.snapshot`、`fund.peer.evaluate`。

Agent Action：`fund.due-diligence.evaluate`、`fund.monitoring.review`、`fund.methodology.audit`、`fund.research.explain`。

每个 Action 的 Binding、权限、执行模式、输入输出 Schema 和确认级别都由 Manifest 固定，页面参数不能改写处理链路。

## 6. 事件边界

跨 Mod 研究对象使用标准事件：

```json
{
  "version": "1.0",
  "event": "security.selected",
  "payload": {
    "symbol": "000001.OF",
    "name": "示例基金",
    "market": "CN",
    "assetType": "fund",
    "researchModule": "professional-fund-research"
  }
}
```

本模组同时接受 `assetType: "etf"`，用于从 Vibe Research 的 ETF 比较页进入更深的基金研究流程。它不重复 ETF 页已有的轻量收益、波动、回撤与相关性比较。

## 7. 演进顺序

1. 已建立每日研究驾驶舱，把证据健康、对象快照和复核事件转成明确任务。
2. 统一 `FundResearchDecision`、门槛和分柱输出，逐步替换旧总分决策。
3. 完成 point-in-time 研究范围和终止基金回放测试。
4. 增加净费后滚动指标、capture、drawdown duration、bootstrap alpha。
5. 增加 RBSA / HBSA、Active Share、style drift 与 capacity/value-added。
6. 建立 People/Process/Parent/Price/ODD 的结构化问卷与证据合同。
7. 把所有结论写入带方法版本、证据快照和反转条件的决策记录。
8. 用事件触发替代定时“重算总分”，并为变化生成明确复核任务。

## 8. 验收条件

- 六个页面都可独立访问，并能在 320px 宽度使用。
- 驾驶舱只聚合真实数据；入口失败时显示降级状态，不能回落到模拟指标。
- Suite 可从 well-known 地址发现，所有页面编译为 Level 3 Manifest。
- Bridge 完成握手、主题环境同步和 Context 响应。
- `security.selected` 的 fund / etf 负载可交叉消费。
- 方法代码与文档包含九个阶段和八项公开来源。
- 决策合同没有数值型合成总分字段。
- 业务数据库凭据不进入 Manifest、前端或 Desk Storage。
