# 贡献指南

感谢你对本项目的关注！欢迎任何形式的贡献。

## 🐛 报告 Bug

1. 先搜索 [Issues](https://github.com/ZhuLinsen/daily_stock_analysis/issues) 确认问题未被报告
2. 使用 Bug Report 模板创建新 Issue
3. 提供详细的复现步骤和环境信息

## 💡 功能建议

1. 先搜索 Issues 确认建议未被提出
2. 使用 Feature Request 模板创建新 Issue
3. 详细描述你的使用场景和期望功能

## 🔧 提交代码

### 开发环境

```bash
# 克隆仓库
git clone https://github.com/ZhuLinsen/daily_stock_analysis.git
cd daily_stock_analysis

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
```

### 提交流程

1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/your-feature`
3. 提交改动：`git commit -m 'feat: add some feature'`
4. 推送分支：`git push origin feature/your-feature`
5. 创建 Pull Request

### Commit 规范

使用 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```
feat: 新功能
fix: Bug 修复
docs: 文档更新
style: 代码格式（不影响功能）
refactor: 重构
perf: 性能优化
test: 测试相关
chore: 构建/工具相关
```

示例：
```
feat: 添加钉钉机器人支持
fix: 修复 429 限流重试逻辑
docs: 更新 README 部署说明
```

### 代码规范

- Python 代码遵循 PEP 8
- 函数和类需要添加 docstring
- 重要逻辑添加注释
- 新功能需要更新相关文档

### CI 自动检查

提交 PR 后，CI 会自动运行以下检查：

| 检查项 | 说明 | 必须通过 |
|--------|------|:--------:|
| 🐍 语法检查 | Python 语法正确性 | ✅ |
| 📦 依赖安装 | Python 3.10/3.11/3.12 多版本测试 | ✅ |
| 🐳 Docker 构建 | Docker 镜像能正常构建 | ✅ |
| 🔍 代码规范 | Black/Flake8/isort 格式检查 | ⚠️ 警告 |
| 🔒 安全检查 | Bandit/Safety 漏洞扫描 | ⚠️ 警告 |
| 🧪 单元测试 | pytest 测试（如有） | ✅ |

**本地运行检查：**

```bash
# 安装检查工具
pip install black flake8 isort bandit

# 代码格式化
black .
isort .

# 静态检查
flake8 .

# 安全扫描
bandit -r . --exclude ./demo_*.py
```

## 📋 优先贡献方向

查看 [Roadmap](README.md#-roadmap) 了解当前需要的功能：

- 🔔 新通知渠道（钉钉、飞书、Telegram）
- 🤖 新 AI 模型支持（GPT-4、Claude）
- 📊 新数据源接入
- 🐛 Bug 修复和性能优化
- 📖 文档完善和翻译

## ❓ 问题解答

如有任何问题，欢迎：
- 创建 Issue 讨论
- 查看已有 Issue 和 Discussion

再次感谢你的贡献！ 🎉
