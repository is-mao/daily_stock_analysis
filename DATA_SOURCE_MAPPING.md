# 📊 数据源对应关系和XX_selection_only模式完整指南

## 🎯 概述

本系统支持8个数据源，每个数据源都有对应的`XX_selection_only`模式，用于快速股票精选。所有数据源都已实现统一的接口，确保数据源切换的一致性。

## 📋 数据源完整列表

| 数据源 | 优先级 | 速度 | 实时行情 | 基本面数据 | GitHub Actions模式 | 特点 |
|--------|--------|------|----------|------------|-------------------|------|
| **SinaFetcher** | 0.1 | ⚡⚡⚡ | ✅ | ✅(构造) | `sina-selection-only` | 极速，毫秒级响应 |
| **TencentFetcher** | 0 | ⚡⚡⚡ | ✅ | ✅(构造) | `tencent-selection-only` | 最快，批量查询 |
| **TonghuashunFetcher** | 0.5 | ⚡⚡ | ✅ | ✅(构造) | `tonghuashun-selection-only` | 快速，稳定性好 |
| **TushareFetcher** | 2 | ⚡ | ✅ | ✅ | `tushare-selection-only` | 专业，需Token |
| **BaostockFetcher** | 3 | ⚡ | ✅(模拟) | ❌ | `baostock-selection-only` | 稳定，免费无限制 |
| **YfinanceFetcher** | 4 | ⚡ | ✅ | ✅ | `yfinance-selection-only` | 国际，兜底方案 |
| **EfinanceFetcher** | 5 | ⚡⚡ | ✅ | ✅(构造) | `efinance-selection-only` | 快速，东财数据 |
| **AkshareFetcher** | 10 | ⚪ | ✅ | ✅ | `akshare-selection-only` | 全面，易被限流 |

## 🚀 GitHub Actions 使用指南

### 快速模式（推荐）⚡
适合日常快速筛选，2-8分钟完成：

```yaml
# 新浪极速模式（最快）
mode: sina-selection-only
# 特点：毫秒级响应，~10只股票，2-5分钟

# 腾讯极速模式（次快）  
mode: tencent-selection-only
# 特点：批量查询，~10只股票，3-5分钟

# 同花顺快速模式
mode: tonghuashun-selection-only
# 特点：稳定性好，~10只股票，5-8分钟

# EFinance快速模式
mode: efinance-selection-only
# 特点：东财数据，~10只股票，5-10分钟
```

### 标准模式 📊
适合深度分析，10-20分钟完成：

```yaml
# AkShare标准模式
mode: akshare-selection-only
# 特点：数据全面，~15只股票，10-15分钟

# Tushare专业模式（需配置Token）
mode: tushare-selection-only  
# 特点：专业数据，~15只股票，15-20分钟

# Baostock稳定模式
mode: baostock-selection-only
# 特点：免费稳定，~15只股票，10-15分钟

# Yahoo Finance国际模式
mode: yfinance-selection-only
# 特点：国际数据，~15只股票，15-20分钟
```

## 🔧 本地使用方法

### 命令行参数

```bash
# 使用新浪数据源（极速）
python main.py --stock-selection --data-source sina --selection-count 10

# 使用腾讯数据源（最快）
python main.py --stock-selection --data-source tencent --selection-count 10

# 使用同花顺数据源（快速）
python main.py --stock-selection --data-source tonghuashun --selection-count 10

# 使用EFinance数据源（快速）
python main.py --stock-selection --data-source efinance --selection-count 10

# 使用AkShare数据源（标准）
python main.py --stock-selection --data-source akshare --selection-count 15

# 使用Tushare数据源（专业，需Token）
python main.py --stock-selection --data-source tushare --selection-count 15

# 使用Baostock数据源（稳定）
python main.py --stock-selection --data-source baostock --selection-count 15

# 使用Yahoo Finance数据源（国际）
python main.py --stock-selection --data-source yfinance --selection-count 15
```

### 支持的筛选策略

```bash
--selection-strategy comprehensive    # 综合策略（默认）
--selection-strategy trend_following  # 趋势跟踪
--selection-strategy value_hunting    # 价值挖掘  
--selection-strategy momentum         # 动量策略
--selection-strategy reversal         # 反转策略
```

## 📊 数据源详细对比

### 🏆 速度排行榜

1. **SinaFetcher** (0.1) - 毫秒级响应，极速模式首选
2. **TencentFetcher** (0) - 批量查询优化，速度最快
3. **TonghuashunFetcher** (0.5) - 快速且稳定
4. **EfinanceFetcher** (5) - 东财数据，速度较快
5. **TushareFetcher** (2) - 专业数据，中等速度
6. **BaostockFetcher** (3) - 稳定但略慢
7. **YfinanceFetcher** (4) - 国际数据，网络延迟
8. **AkshareFetcher** (10) - 功能全面但易限流

### 🎯 功能对比

| 功能 | Sina | Tencent | Tonghuashun | EFinance | Tushare | Baostock | YFinance | AkShare |
|------|------|---------|-------------|----------|---------|----------|----------|---------|
| 实时行情 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅(模拟) | ✅ | ✅ |
| 历史K线 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| PE/PB | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ✅ |
| 市值 | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ✅ |
| ROE | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ✅ |
| 量比 | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ |
| 换手率 | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ |
| 筹码分布 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |

### 🔧 配置要求

| 数据源 | Token要求 | 网络要求 | 限制 |
|--------|-----------|----------|------|
| Sina | 无 | 国内网络 | 无 |
| Tencent | 无 | 国内网络 | 无 |
| Tonghuashun | 无 | 国内网络 | 无 |
| EFinance | 无 | 国内网络 | 无 |
| Tushare | **需要Token** | 任意 | 80次/分钟 |
| Baostock | 无 | 任意 | 无 |
| YFinance | 无 | 国际网络 | 可能被限制 |
| AkShare | 无 | 国内网络 | 易被反爬 |

## 🎯 推荐使用场景

### 🚀 日常快速筛选
**推荐：sina-selection-only 或 tencent-selection-only**
- 适合：每日快速查看市场热点
- 时间：2-5分钟
- 股票数：10只精选

### 📊 深度分析
**推荐：tushare-selection-only 或 akshare-selection-only**
- 适合：周末深度研究
- 时间：15-20分钟  
- 股票数：15只，包含详细基本面数据

### 🌐 国际对比
**推荐：yfinance-selection-only**
- 适合：对比国际市场
- 时间：15-20分钟
- 特点：包含国际估值指标

### 🔒 稳定可靠
**推荐：baostock-selection-only**
- 适合：避免反爬风险
- 时间：10-15分钟
- 特点：免费无限制，数据稳定

## ⚠️ 注意事项

### Tushare配置
使用`tushare-selection-only`需要配置Token：
```bash
# 在GitHub Secrets中配置
TUSHARE_TOKEN=your_token_here
```

### 网络环境
- **国内数据源**：Sina、Tencent、Tonghuashun、EFinance、AkShare
- **国际数据源**：YFinance（可能需要代理）
- **通用数据源**：Tushare、Baostock

### 反爬策略
系统已内置反爬策略：
- 随机延时
- User-Agent轮换
- 指数退避重试
- 批量查询优化

## 🔄 数据源切换逻辑

系统实现了统一的数据源切换逻辑：

1. **优先使用指定数据源**
2. **自动降级到AkShare**（如果指定数据源失败）
3. **智能缓存**（避免重复请求）
4. **错误处理**（网络异常自动重试）

这确保了无论选择哪个数据源，都能获得一致的用户体验。