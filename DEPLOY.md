# 🏛️ 门神文化景区 AI 智能体 — 部署指南

> 面向景区 IT 人员或运维人员。  
> 如果您不熟悉命令行，建议联系技术人员协助部署。

---

## 一、部署前准备

### 你需要有

| 项目 | 说明 | 费用 |
|------|------|------|
| 一台服务器 | Linux 系统（推荐 Ubuntu 22.04+），2 核 4G 内存以上 | 约 ¥50-100/月（云服务器） |
| Docker | 容器运行环境 | 免费 |
| API Key | 大模型接口密钥（DeepSeek 或阿里云百炼） | 约 ¥0.5-2/天（按用量计费） |
| 域名（可选） | 如果需要从微信/官网访问 | 约 ¥50/年 |

### 推荐服务器配置

| 场景 | 配置 | 预估月费 |
|------|------|----------|
| 测试体验 | 2 核 4G | ¥50 |
| 景区正式使用（日均 500 对话） | 4 核 8G | ¥150 |
| 景区正式使用（日均 2000+ 对话） | 4 核 8G + 按需扩容 | ¥300+ |

---

## 二、安装部署

### 第 1 步：安装 Docker（如果你还没装）

```bash
# Ubuntu / Debian
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# 重新登录后生效
```

验证安装：`docker --version` 和 `docker compose version`

### 第 2 步：下载系统

```bash
# 从 GitHub 下载
git clone https://github.com/GassamFlower/ai-agent-methodology.git
cd ai-agent-methodology/05-工程实践/门神景区多智能体运营中枢
```

### 第 3 步：配置 API Key

```bash
# 复制配置模板
cp .env.example .env

# 编辑配置文件
nano .env
```

找到 `.env` 文件，修改以下内容：

```ini
# 选择一种 LLM 服务即可

# 方式一：DeepSeek（推荐，性价比高）
CREWAI_LLM=deepseek/deepseek-chat
DEEPSEEK_API_KEY=sk-你的DeepSeek密钥

# 方式二：阿里云百炼（国内访问稳定）
# CREWAI_LLM=dashscope/qwen-plus
# DASHSCOPE_API_KEY=你的阿里云百炼密钥

# 管理后台密码（务必修改！）
ADMIN_PASSWORD=设置一个安全的密码
```

### 第 4 步：启动系统

```bash
docker compose up -d
```

等待约 30 秒（首次启动需要下载镜像）。

### 第 5 步：验证是否启动成功

```bash
# 检查运行状态
docker compose ps

# 访问健康检查
curl http://localhost:8000/health
# 应返回: {"status":"ok","env":"dev"}
```

### 第 6 步：访问系统

| 页面 | 地址 | 说明 |
|------|------|------|
| 对话测试 | `http://你的IP:8000/` | 测试智能体对话 |
| 管理后台 | `http://你的IP:8000/admin/login.html` | 管理知识库、查看对话记录 |
| 嵌入组件 | `http://你的IP:8000/widget/chat.html` | 可嵌入官网的对话组件 |
| API 文档 | `http://你的IP:8000/docs` | 技术接口文档 |

---

## 三、首次使用指引

### 1. 初始化知识库

访问管理后台 → 登录（账号 `admin`，密码是你设的 `ADMIN_PASSWORD`）→ 点击「知识库管理」，系统已内置 15 条景区常见问题。你可以：

- 查看已有条目
- 修改回答内容（点击「编辑」）
- 新增你们景区的专属问题
- 停用不合适的条目

### 2. 配置景区信息

点击「景区配置」标签页，修改以下信息：

| 配置项 | 示例值 |
|--------|--------|
| 景区名称 | 你的景区名称 |
| 开放时间 | 每日 09:00-18:00 |
| 成人票价 | ¥60/张 |
| 学生票价 | ¥30/张 |
| 景区地址 | 你的景区地址 |
| 客服电话 | 你的电话 |
| 购票链接 | 你的购票小程序/网页链接 |

修改后 Agent 回复会**立即生效**，无需重启。

### 3. 嵌入到官网

在你的网站中加入以下 HTML 代码：

```html
<iframe 
  src="http://你的IP:8000/widget/chat.html"
  width="100%" 
  height="600" 
  frameborder="0"
  style="border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,.1)">
</iframe>
```

品牌色修改：打开 `static/widget/chat.html`，修改 `:root` 中的 CSS 变量：

```css
:root {
  --primary: #你的品牌主色;
  --header-bg: linear-gradient(135deg, #色1, #色2);
  /* ...其他变量... */
}
```

---

## 四、日常维护

### 查看日志
```bash
docker compose logs -f --tail=50
```

### 重启服务
```bash
docker compose restart
```

### 升级版本
```bash
git pull
docker compose up -d --build
```

### 备份数据
```bash
# 数据存储在 ./data/ 目录
tar -czf backup-$(date +%Y%m%d).tar.gz data/
```

---

## 五、常见问题排查

### Q: 启动后访问页面一直转圈/无响应
→ 检查 API Key 是否配置正确：`docker compose logs agent-hub | grep -i error`

### Q: Agent 回答不准确/答非所问
→ 在管理后台检查知识库条目是否准确 → 补充景区专属信息 → 观察「未命中问题」标签页，补充缺失的知识库条目

### Q: 管理后台无法登录
→ 检查 `.env` 中 `ADMIN_PASSWORD` 是否设置正确 → 重启：`docker compose restart`

### Q: 对话提示"网络错误"
→ 检查服务器网络是否能访问 LLM API（DeepSeek/阿里云）→ 确认 `.env` 中 API Key 正确

### Q: 想修改对话组件的品牌颜色
→ 修改 `static/widget/chat.html` 的 `:root` CSS 变量

### Q: 如何统计每天有多少人使用？
→ 管理后台的「热门统计」可以看到热门问题 Top 10 → 对话记录可以查看所有会话 → 更详细的数据可通过 API 获取

---

## 六、费用估算

| 项目 | 月费用 |
|------|--------|
| 云服务器（2 核 4G） | ¥50-80 |
| LLM API（日均 500 次对话） | ¥15-60 |
| 域名（可选） | ¥5 |
| **合计** | **约 ¥70-145/月** |

---

## 七、技术支持

- GitHub Issues：https://github.com/GassamFlower/ai-agent-methodology/issues
- 如需定制开发或部署协助，请联系作者
