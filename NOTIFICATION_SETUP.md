# 📱 通知推送配置指南

## 🚨 重要提醒
**如果没有配置通知渠道，系统不会推送任何消息！**

请按照以下步骤配置至少一个通知渠道：

## 🔧 快速配置步骤

### 1. 编辑配置文件
打开 `.env` 文件，找到通知配置部分

### 2. 选择一个通知方式（推荐企业微信）

#### 方式一：企业微信机器人 ⭐ 推荐
1. 在企业微信群中，点击右上角 `...` -> `群设置`
2. 选择 `群机器人` -> `添加机器人`
3. 选择 `自定义机器人`，设置名称和头像
4. 复制生成的 Webhook 地址
5. 在 `.env` 文件中设置：
   ```
   WECHAT_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=你的key
   ```

#### 方式二：QQ邮箱推送
1. 登录QQ邮箱 -> 设置 -> 账户
2. 开启 `POP3/SMTP服务`，获取授权码
3. 在 `.env` 文件中设置：
   ```
   EMAIL_SENDER=your_email@qq.com
   EMAIL_PASSWORD=你的授权码
   ```

#### 方式三：飞书机器人
1. 在飞书群中，点击右上角设置
2. 选择 `群机器人` -> `添加机器人` -> `自定义机器人`
3. 复制 Webhook 地址
4. 在 `.env` 文件中设置：
   ```
   FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/你的key
   ```

### 3. 配置AI模型（必须）
选择一个AI模型：

#### 选项一：Gemini（推荐，有免费额度）
1. 访问 https://aistudio.google.com/
2. 登录Google账号，获取免费API Key
3. 在 `.env` 文件中设置：
   ```
   GEMINI_API_KEY=你的gemini_api_key
   ```

#### 选项二：DeepSeek（国产，便宜）
1. 访问 https://platform.deepseek.com/
2. 注册账号，获取API Key
3. 在 `.env` 文件中设置：
   ```
   OPENAI_API_KEY=你的deepseek_api_key
   OPENAI_BASE_URL=https://api.deepseek.com/v1
   OPENAI_MODEL=deepseek-chat
   ```

### 4. 测试配置
运行以下命令测试配置：
```bash
python main.py --stock-selection --selection-count 5
```

## 📋 配置检查清单
- [ ] 已创建 `.env` 文件
- [ ] 已配置至少一个通知渠道
- [ ] 已配置AI模型API Key
- [ ] 已设置股票列表 `STOCK_LIST`
- [ ] 运行测试命令验证配置

## 🔍 故障排除

### 问题1：没有收到推送通知
- 检查 `.env` 文件中的通知配置是否正确
- 确认Webhook地址或邮箱配置无误
- 查看日志文件中的错误信息

### 问题2：AI分析失败
- 检查API Key是否正确
- 确认网络连接正常
- 查看日志中的具体错误信息

### 问题3：股票数据获取失败
- 检查股票代码格式是否正确（如：600519，不要加前缀）
- 确认网络连接正常
- 查看日志中的数据源错误信息

## 📞 获取帮助
如果遇到问题，请：
1. 查看 `logs/` 目录下的日志文件
2. 检查配置文件格式是否正确
3. 确认所有必需的配置项都已填写