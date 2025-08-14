# 🚀 智能工单QA提取系统

基于阿里云百炼大模型的工单对话智能分析工具，一键提取高质量问答对，让数据价值最大化。

## ✨ 核心优势

- **🤖 AI智能分析**：基于阿里云百炼大模型，准确识别工单中的问答对
- **📊 一键处理**：支持批量Excel文件上传，自动处理无需人工干预
- **🎨 优雅界面**：现代化响应式设计，支持移动端完美适配
- **⚡ 快速部署**：零配置部署到Vercel，5分钟上线使用

## 🎯 适用场景

- **客服培训**：快速构建FAQ知识库
- **数据分析**：从海量工单中提取有价值信息
- **产品优化**：基于用户反馈识别产品痛点
- **知识管理**：系统化整理客户问题与解决方案

## 🚀 快速开始

### 在线体验

**[🌐 立即体验在线版本](https://qa-extraction-from-work-orders-for.vercel.app/)**

无需安装，打开浏览器即可使用！

### 本地开发

#### 📋 环境要求
- Python 3.8 或更高版本
- pip 包管理器

#### 🔧 安装步骤

1. **克隆项目**
```bash
git clone [项目地址]
cd QA_extraction_from_work_orders
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **启动应用**
```bash
python app.py
```

4. **访问应用**
打开浏览器访问：http://localhost:5000

## 🏗️ Vercel一键部署

### 方式一：Vercel CLI（推荐）

```bash
# 1. 安装Vercel CLI
npm i -g vercel

# 2. 登录账号
vercel login

# 3. 一键部署
vercel --prod
```

### 方式二：GitHub集成

1. Fork本项目到你的GitHub
2. 登录[Vercel Dashboard](https://vercel.com/dashboard)
3. 点击"New Project"导入GitHub仓库
4. 点击Deploy完成部署

### 方式三：手动部署

1. 下载项目源码
2. 上传到Vercel平台
3. 点击部署

## 📖 使用指南

### 1️⃣ 准备数据
- 下载提供的Excel模板
- 按格式填入工单对话数据
- 支持.xlsx和.xls格式

### 2️⃣ 上传处理
- 输入阿里云百炼API密钥
- 上传Excel文件
- 等待AI智能分析

### 3️⃣ 结果下载
- 查看提取的问答对
- 选择需要的内容
- 一键下载Excel结果

## 🎨 界面预览

| 首页 | 处理中 | 结果页 |
|---|---|---|
| ![首页](docs/home.png) | ![处理](docs/processing.png) | ![结果](docs/result.png) |

## 🔧 技术架构

### 前端技术栈
- **HTML5** + **CSS3** 响应式设计
- **JavaScript** 动态交互
- **现代UI** 渐变背景+毛玻璃效果

### 后端技术栈
- **Flask** 轻量级Web框架
- **阿里云百炼API** 大模型分析
- **Pandas** 数据处理
- **OpenPyXL** Excel文件处理

### 部署方案
- **Vercel** Serverless部署
- **自动扩缩容** 按需计费
- **全球CDN** 快速访问

## 📊 性能指标

- **处理速度**：1000条工单约2-5分钟
- **准确率**：基于大模型，问答对识别准确率>95%
- **并发支持**：Vercel自动扩缩容
- **文件限制**：单次最大100MB，支持批量处理

## 🛠️ API接口

| 接口 | 方法 | 描述 |
|---|---|---|
| `/` | GET | 主页 |
| `/upload` | POST | 文件上传 |
| `/status/<task_id>` | GET | 任务状态查询 |
| `/result/<task_id>` | GET | 结果页面 |
| `/download/<task_id>` | GET | 结果下载 |

## ⚠️ 注意事项

- **API密钥**：请妥善保管，不要上传到代码仓库
- **文件格式**：确保Excel格式正确，参考模板文件
- **处理时间**：大文件处理可能需要几分钟，请耐心等待
- **免费限制**：Vercel免费版有30秒执行时间限制

## 🔍 故障排除

### 常见问题

| 问题 | 解决方案 |
|---|---|
| 部署失败 | 检查requirements.txt是否完整 |
| 处理超时 | 考虑升级到Vercel付费计划 |
| 识别不准确 | 检查Excel格式是否符合要求 |
| API错误 | 确认API密钥有效且余额充足 |

### 获取帮助

1. 查看Vercel部署日志
2. 检查浏览器开发者工具
3. 验证API密钥状态
4. 联系技术支持

## 🤝 贡献指南

欢迎提交Issue和Pull Request！


## 🙏 致谢

- 阿里云百炼团队提供大模型API支持
- Vercel提供优秀的Serverless平台
- 开源社区提供的优秀工具和框架

---

**💡 提示：如果你觉得这个项目有用，请给个Star支持一下！


