# 🔧 错误处理指南

## 常见错误及解决方案

### 1. 网络连接错误
**错误信息**：
- `Connection aborted`
- `Remote end closed connection without response`
- `timeout`

**原因**：
- 网络不稳定
- API服务器响应慢
- 请求频率过高被限流

**解决方案**：
1. 检查网络连接
2. 增加请求间隔时间
3. 使用不同的数据源

### 2. AkShare API 调用失败
**错误信息**：
- `ak.stock_zh_a_spot_em() 获取失败`
- `API调用超时`

**解决方案**：
1. 在 `.env` 文件中设置更长的超时时间：
   ```
   AKSHARE_TIMEOUT=30
   ```
2. 使用EFinance数据源（更稳定）：
   ```bash
   python main.py --stock-selection --data-source efinance
   ```

### 3. 缠论分析错误
**错误信息**：
- 缠论分析相关错误

**解决方案**：
- 系统已自动处理，会跳过有问题的股票
- 不影响整体分析流程

### 4. 股票评估失败
**错误信息**：
- `股票评估失败: too many values to unpack`

**解决方案**：
- 已修复，重新运行即可

## 🚀 推荐运行方式

### 稳定模式（推荐）
```bash
# 使用EFinance数据源，更稳定
python main.py --stock-selection --data-source efinance --selection-count 10
```

### 快速模式
```bash
# 使用快速选择模式
python main.py --stock-selection --selection-strategy momentum --selection-count 5
```

### 调试模式
```bash
# 查看详细错误信息
python main.py --stock-selection --debug --selection-count 3
```

## 📊 错误统计

系统会自动处理以下错误：
- ✅ 网络连接超时 → 自动跳过
- ✅ 数据获取失败 → 自动重试或跳过
- ✅ 缠论分析错误 → 使用默认值
- ✅ API限流 → 自动延时重试

## 🔍 日志查看

查看详细错误信息：
```bash
# 查看最新日志
tail -f logs/stock_analysis_$(date +%Y%m%d).log

# 查看调试日志
tail -f logs/stock_analysis_debug_$(date +%Y%m%d).log
```

## 💡 优化建议

1. **网络优化**：
   - 使用稳定的网络环境
   - 避免在网络高峰期运行

2. **数据源选择**：
   - EFinance：最稳定，推荐
   - AkShare：功能全面，但可能不稳定
   - 自动选择：系统自动切换

3. **运行时间**：
   - 避免在交易时间运行（9:30-15:00）
   - 推荐在晚上或周末运行

4. **批量大小**：
   - 减少同时分析的股票数量
   - 使用 `--selection-count` 参数控制