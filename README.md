# 📈 A股智能分析系统

[![GitHub stars](https://img.shields.io/github/stars/ZhuLinsen/daily_stock_analysis?style=social)](https://github.com/ZhuLinsen/daily_stock_analysis/stargazers)
[![CI](https://github.com/ZhuLinsen/daily_stock_analysis/actions/workflows/ci.yml/badge.svg)](https://github.com/ZhuLinsen/daily_stock_analysis/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-Ready-2088FF?logo=github-actions&logoColor=white)](https://github.com/features/actions)

> 🤖 基于 AI 大模型的 A/H 股自选股智能分析系统，每日自动分析并推送「决策仪表盘」到企业微信/飞书/Telegram/邮箱

![运行效果演示](./sources/all_2026-01-13_221547.gif)

## ✨ 功能特性

### 🎯 核心功能
- **AI 决策仪表盘** - 一句话核心结论 + 精确买卖点位 + 检查清单
- **🎯 每日股票精选** - 全市场智能筛选优质股票，多维度评分排序 **[NEW]**
- **多维度分析** - 技术面 + 筹码分布 + 舆情情报 + 实时行情
- **大盘复盘** - 每日市场概览、板块涨跌、北向资金
- **多渠道推送** - 支持企业微信、飞书、Telegram、邮件（自动识别）
- **零成本部署** - GitHub Actions 免费运行，无需服务器
- **💰 白嫖 Gemini API** - Google AI Studio 提供免费额度，个人使用完全够用
- **🔄 多模型支持** - 支持 OpenAI 兼容 API（DeepSeek、通义千问等）作为备选

### 📊 数据来源
- **行情数据**: AkShare（免费）、Tushare、Baostock、YFinance - **全部A股真实数据**
- **新闻搜索**: Tavily、SerpAPI、Bocha
- **AI 分析**: 
  - 主力：Google Gemini（gemini-3-flash-preview）—— [免费获取](https://aistudio.google.com/)
  - 备选：应大家要求，也支持了OpenAI 兼容 API（DeepSeek、通义千问、Moonshot 等）

> **数据真实性说明**：本系统使用的股票数据全部来自真实的A股交易数据，通过AkShare等库从东方财富、新浪财经等官方数据源获取，覆盖上海证券交易所和深圳证券交易所的全部股票，非虚拟数据。详见 [数据来源确认](DATA_SOURCE_CONFIRMATION.md)。

### 🛡️ 交易理念内置
- ❌ **严禁追高** - 乖离率 > 5% 自动标记「危险」
- ✅ **趋势交易** - MA5 > MA10 > MA20 多头排列
- 📍 **精确点位** - 买入价、止损价、目标价
- 📋 **检查清单** - 每项条件用 ✅⚠️❌ 标记

## 🚀 快速开始

### 方式一：GitHub Actions（推荐，零成本）

**无需服务器，每天自动运行！**

#### 1. Fork 本仓库(顺便点下⭐呀)

点击右上角 `Fork` 按钮

#### 2. 配置 Secrets

进入你 Fork 的仓库 → `Settings` → `Secrets and variables` → `Actions` → `New repository secret`

**AI 模型配置（二选一）**

| Secret 名称 | 说明 | 必填 |
|------------|------|:----:|
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/) 获取免费 Key | ✅* |
| `OPENAI_API_KEY` | OpenAI 兼容 API Key（支持 DeepSeek、通义千问等） | 可选 |
| `OPENAI_BASE_URL` | OpenAI 兼容 API 地址（如 `https://api.deepseek.com/v1`） | 可选 |
| `OPENAI_MODEL` | 模型名称（如 `deepseek-chat`） | 可选 |

> *注：`GEMINI_API_KEY` 和 `OPENAI_API_KEY` 至少配置一个

**通知渠道配置（可同时配置多个，全部推送）**

| Secret 名称 | 说明 | 必填 |
|------------|------|:----:|
| `WECHAT_WEBHOOK_URL` | 企业微信 Webhook URL | 可选 |
| `FEISHU_WEBHOOK_URL` | 飞书 Webhook URL | 可选 |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token（@BotFather 获取） | 可选 |
| `TELEGRAM_CHAT_ID` | Telegram Chat ID | 可选 |
| `EMAIL_SENDER` | 发件人邮箱（如 `xxx@qq.com`） | 可选 |
| `EMAIL_PASSWORD` | 邮箱授权码（非登录密码） | 可选 |
| `EMAIL_RECEIVERS` | 收件人邮箱（多个用逗号分隔，留空则发给自己） | 可选 |
| `CUSTOM_WEBHOOK_URLS` | 自定义 Webhook（支持钉钉等，多个用逗号分隔） | 可选 |
| `CUSTOM_WEBHOOK_BEARER_TOKEN` | 自定义 Webhook 的 Bearer Token（用于需要认证的 Webhook） | 可选 |
| `SINGLE_STOCK_NOTIFY` | 单股推送模式：设为 `true` 则每分析完一只股票立即推送 | 可选 |

> *注：至少配置一个渠道，配置多个则同时推送
>
> 📖 更多配置（Pushover 手机推送、飞书云文档等）请参考 [完整配置指南](docs/full-guide.md)

**其他配置**

| Secret 名称 | 说明 | 必填 |
|------------|------|:----:|
| `STOCK_LIST` | 自选股代码，如 `600519,300750,002594` | ✅ |
| `TAVILY_API_KEYS` | [Tavily](https://tavily.com/) 搜索 API（新闻搜索） | 推荐 |
| `BOCHA_API_KEYS` | [博查搜索](https://open.bocha.cn/) Web Search API（中文搜索优化，支持AI摘要，多个key用逗号分隔） | 可选 |
| `SERPAPI_API_KEYS` | [SerpAPI](https://serpapi.com/) 备用搜索 | 可选 |
| `TUSHARE_TOKEN` | [Tushare Pro](https://tushare.pro/) Token | 可选 |

#### 3. 启用 Actions

进入 `Actions` 标签 → 点击 `I understand my workflows, go ahead and enable them`

#### 4. 手动测试

`Actions` → `每日股票分析` → `Run workflow` → 选择模式 → `Run workflow`

#### 5. 完成！

默认每个工作日 **18:00（北京时间）** 自动执行

### 方式二：本地运行 / Docker 部署

> 📖 本地运行、Docker 部署详细步骤请参考 [完整配置指南](docs/full-guide.md)

## 📱 推送效果

### 决策仪表盘
```
📊 2026-01-10 决策仪表盘
3只股票 | 🟢买入:1 🟡观望:2 🔴卖出:0

🟢 买入 | 贵州茅台(600519)
📌 缩量回踩MA5支撑，乖离率1.2%处于最佳买点
💰 狙击: 买入1800 | 止损1750 | 目标1900
✅多头排列 ✅乖离安全 ✅量能配合

🟡 观望 | 宁德时代(300750)
📌 乖离率7.8%超过5%警戒线，严禁追高
⚠️ 等待回调至MA5附近再考虑

---
生成时间: 18:00
```

### 每日股票精选 **[NEW]**
```
🎯 2026-01-19 每日股票精选

精选统计: 共15只 | 🔥强推:2 🟢推荐:8 🟡关注:5

## 强烈推荐 (2只)

🔥 贵州茅台(600519)
综合评分: 92.3分 | 当前价格: ¥1850.00
操作建议: 买入¥1820 | 止损¥1750 | 目标¥2100
技术面: 88.5分 | 基本面: 95.0分 | 流动性: 92.0分
推荐理由: 技术面强势、基本面优秀、流动性充足

🔥 宁德时代(300750)
综合评分: 90.1分 | 当前价格: ¥185.50
操作建议: 买入¥182 | 止损¥175 | 目标¥210
技术面: 85.2分 | 基本面: 92.8分 | 流动性: 94.5分
推荐理由: 技术面强势、基本面优秀、流动性充足

## 推荐 (8只)
🟢 比亚迪(002594) - 推荐 - 86.7分
🟢 招商银行(600036) - 推荐 - 84.2分
...

---
使用命令: python main.py --stock-selection
```

### 大盘复盘

![大盘复盘推送效果](./sources/dapan_2026-01-13_22-14-52.png)

```
🎯 2026-01-10 大盘复盘

📊 主要指数
- 上证指数: 3250.12 (🟢+0.85%)
- 深证成指: 10521.36 (🟢+1.02%)
- 创业板指: 2156.78 (🟢+1.35%)

📈 市场概况
上涨: 3920 | 下跌: 1349 | 涨停: 155 | 跌停: 3

🔥 板块表现
领涨: 互联网服务、文化传媒、小金属
领跌: 保险、航空机场、光伏设备
```

## ⚙️ 配置说明

> 📖 完整环境变量、定时任务配置请参考 [完整配置指南](docs/full-guide.md)

### 🎯 股票精选功能使用 **[NEW]**

```bash
# 基础用法：运行股票精选
python main.py --stock-selection

# 自定义精选数量和策略
python main.py --stock-selection --selection-count 30 --selection-strategy trend_following

# GitHub Actions 中选择 "selection-only" 模式
```

**精选策略**：
- `comprehensive`：综合策略（默认）
- `trend_following`：趋势跟踪
- `value_hunting`：价值挖掘  
- `momentum`：动量策略
- `reversal`：反转策略

**评分体系**：技术面(40%) + 基本面(35%) + 流动性(25%)

> 📖 详细使用指南请参考 [股票精选功能指南](STOCK_SELECTION_GUIDE.md)

## 🖥️ 本地 WebUI（可选）

本地运行时，可启用简易 WebUI 来方便查看/修改 `.env` 里的自选股列表。

- 启动命令：`python main.py --webui`
- 访问地址：`http://127.0.0.1:8000`
- 详细说明请参考 [配置指南 - WebUI](docs/full-guide.md#本地-webui-管理界面)

## 📁 项目结构

```
daily_stock_analysis/
├── main.py              # 主程序入口
├── analyzer.py          # AI 分析器（Gemini）
├── stock_selector.py    # 股票精选模块 **[NEW]**
├── market_analyzer.py   # 大盘复盘分析
├── search_service.py    # 新闻搜索服务
├── notification.py      # 消息推送
├── scheduler.py         # 定时任务
├── storage.py           # 数据存储
├── config.py            # 配置管理
├── data_provider/       # 数据源适配器
│   ├── akshare_fetcher.py
│   ├── tushare_fetcher.py
│   ├── baostock_fetcher.py
│   └── yfinance_fetcher.py
├── test_stock_selection.py    # 股票精选测试脚本 **[NEW]**
├── demo_stock_selection.py    # 股票精选演示脚本 **[NEW]**
├── STOCK_SELECTION_GUIDE.md  # 股票精选使用指南 **[NEW]**
├── DATA_SOURCE_CONFIRMATION.md # 数据来源确认说明 **[NEW]**
├── .github/workflows/   # GitHub Actions
├── Dockerfile           # Docker 镜像
└── docker-compose.yml   # Docker 编排
```

## 🗺️ Roadmap

> 📢 以下功能将视后续情况逐步完成，如果你有好的想法或建议，欢迎 [提交 Issue](https://github.com/ZhuLinsen/daily_stock_analysis/issues) 讨论！

### 🔔 通知渠道扩展
- [x] 企业微信机器人
- [x] 飞书机器人
- [x] Telegram Bot
- [x] 邮件通知（SMTP）
- [x] 自定义 Webhook（支持钉钉、Discord、Slack、Bark 等）
- [x] iOS/Android 推送（Pushover）

### 🤖 AI 模型支持
- [x] Google Gemini（主力，免费额度）
- [x] OpenAI 兼容 API（支持 GPT-4/DeepSeek/通义千问/Claude/文心一言 等）
- [x] 本地模型（Ollama）

### 📊 数据源扩展
- [x] AkShare（免费）
- [x] Tushare Pro
- [x] Baostock
- [x] YFinance

### 🎯 功能增强
- [x] 决策仪表盘
- [x] 大盘复盘
- [x] 定时推送
- [x] GitHub Actions
- [x] 港股支持
- [x] Web 管理界面 (简易版)
- [ ] 历史分析回测
- [ ] 美股支持

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

详见 [贡献指南](CONTRIBUTING.md)

## 📄 License
[MIT License](LICENSE) © 2026 ZhuLinsen

如果你在项目中使用或基于本项目进行二次开发，
非常欢迎在 README 或文档中注明来源并附上本仓库链接。
这将有助于项目的持续维护和社区发展。

## 📬 联系与合作
- GitHub Issues：[提交 Issue](https://github.com/ZhuLinsen/daily_stock_analysis/issues)

## ⭐ Star History

<a href="https://star-history.com/#ZhuLinsen/daily_stock_analysis&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=ZhuLinsen/daily_stock_analysis&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=ZhuLinsen/daily_stock_analysis&type=Date" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=ZhuLinsen/daily_stock_analysis&type=Date" />
 </picture>
</a>

## ⚠️ 免责声明

本项目仅供学习和研究使用，不构成任何投资建议。股市有风险，投资需谨慎。作者不对使用本项目产生的任何损失负责。

---

**如果觉得有用，请给个 ⭐ Star 支持一下！**

<!-- 赞赏锚点 -->
<a id="sponsor"></a>
###### ☕ 请我喝杯咖啡
- 如果觉得本项目对你有帮助且行有余力，可以请我喝杯咖啡，支持项目的持续维护与迭代；不赞赏也完全不影响使用。   
<small>（赞赏时可备注联系方式，方便私信致谢与后续交流反馈）</small>
- 感谢支持, 祝您股市长虹，拿主力当提款机。

<div align="center">
  <img src="./sources/wechatpay.jpg" alt="WeChat Pay" width="200" style="margin-right: 20px;">
  <img src="./sources/alipay.jpg" alt="Alipay" width="200">
</div>