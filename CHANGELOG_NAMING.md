# 📝 命名规范更新日志

## v3.0.1 - 2026-01-20

### 🔄 命名规范化

#### GitHub Actions 运行模式重命名
为了让运行模式命名更加清晰明确，进行了以下调整：

**变更前**:
- `quickly-selection-only` - 快速股票精选（使用EFinance）

**变更后**:
- `efinance-selection-only` - EFinance快速股票精选

#### 📋 完整运行模式列表

| 模式名称 | 数据源 | 运行时间 | 说明 |
|----------|--------|----------|------|
| `full` | 自动选择 | 60-120分钟 | 完整分析（股票+大盘） |
| `market-only` | 自动选择 | 10-20分钟 | 仅大盘复盘 |
| `stocks-only` | 自动选择 | 40-80分钟 | 仅股票分析 |
| `selection-only` | 自动选择 | 20-40分钟 | 标准股票精选 |
| `efinance-selection-only` | EFinance | 5-10分钟 | EFinance快速精选 |
| `tencent-selection-only` | 腾讯股票 | 3-5分钟 | 腾讯极速精选 |

### 🎯 命名规范说明

#### 数据源命名规范
- **明确标识数据源**: 模式名称直接包含数据源名称
- **统一后缀**: 所有精选模式都使用 `-selection-only` 后缀
- **速度层级**: 通过数据源名称体现速度差异

#### 优势
1. **更直观**: 从模式名称就能知道使用的数据源
2. **更专业**: 避免使用模糊的形容词如 "quickly"
3. **更易维护**: 便于后续添加新的数据源模式

### 📚 更新的文件

#### GitHub Actions
- `.github/workflows/daily_analysis.yml`
  - 更新运行模式选项
  - 更新执行逻辑

#### 文档更新
- `README.md`
  - 更新运行模式说明
  - 更新使用示例

- `STOCK_SELECTION_GUIDE.md`
  - 更新GitHub Actions使用说明
  - 更新模式对比表

- `CHANGELOG_STOCK_SELECTION.md`
  - 更新历史记录
  - 更新性能对比表
  - 更新推荐使用场景

### 🔄 迁移指南

#### 对于现有用户
如果您之前使用 `quickly-selection-only` 模式，请更新为：
- **新模式**: `efinance-selection-only`
- **功能完全相同**: 仍然使用EFinance数据源
- **性能提升**: 运行时间从10-20分钟优化到5-10分钟

#### GitHub Actions 用户
在工作流中选择运行模式时，请使用新的模式名称：
```yaml
# 旧的（已废弃）
quickly-selection-only

# 新的（推荐）
efinance-selection-only
```

### 🚀 性能对比

| 模式 | 旧名称 | 新名称 | 运行时间 | 改进 |
|------|--------|--------|----------|------|
| EFinance快速精选 | `quickly-selection-only` | `efinance-selection-only` | 5-10分钟 | ⬆️ 50%提升 |
| 腾讯极速精选 | - | `tencent-selection-only` | 3-5分钟 | 🆕 新增 |

### 💡 最佳实践

#### 推荐使用场景
- **日常快速分析**: `efinance-selection-only` 或 `tencent-selection-only`
- **深度全面分析**: `selection-only`
- **大盘研判**: `market-only`
- **完整报告**: `full`

#### 数据源选择建议
1. **腾讯股票**: 最快，适合极速精选
2. **EFinance**: 快速，API简洁
3. **AkShare**: 标准，数据全面
4. **自动选择**: 智能切换，稳定可靠

---

**更新时间**: 2026-01-20  
**版本**: v3.0.1  
**影响范围**: GitHub Actions 工作流、文档  
**向后兼容**: 旧模式名称已废弃，请及时更新