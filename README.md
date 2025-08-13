# QA提取工具 - Vercel部署版本

这是一个基于Flask的工单QA提取工具，支持在Vercel上部署。

## 功能特性

- 上传Excel格式的工单数据
- 使用阿里云百炼API进行智能分析
- 提取问题和答案对
- 支持批量处理
- 实时进度显示
- 结果导出为Excel格式

## 技术栈

- **后端**: Flask (Python)
- **前端**: HTML模板 + JavaScript
- **API**: 阿里云百炼API
- **部署**: Vercel Serverless

## 本地开发

### 环境要求

- Python 3.8+
- pip

### 安装依赖

```bash
pip install -r requirements.txt
```

### 本地运行

```bash
python app.py
```

访问 http://localhost:5000

## Vercel部署

### 1. 准备代码

确保项目结构如下：
```
QA_extraction_from_work_orders/
├── api/                   # Vercel函数目录
│   └── index.py          # Vercel入口文件
├── app.py                # 主Flask应用
├── requirements.txt      # Python依赖
├── vercel.json          # Vercel配置
├── templates/           # HTML模板
│   ├── index.html
│   ├── result.html
│   └── status.html
├── uploads/             # 上传文件目录（本地开发）
└── results/             # 结果文件目录（本地开发）
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填写实际值：

```bash
cp .env.example .env
```

编辑 `.env` 文件：
```
DASHSCOPE_API_KEY=你的阿里云百炼API密钥
SECRET_KEY=你的Flask密钥
```

### 3. 部署到Vercel

#### 方法一：使用Vercel CLI

1. 安装Vercel CLI：
```bash
npm i -g vercel
```

2. 登录Vercel：
```bash
vercel login
```

3. 部署项目：
```bash
vercel --prod
```

#### 方法二：使用GitHub集成

1. 将代码推送到GitHub仓库
2. 在 [Vercel Dashboard](https://vercel.com/dashboard) 导入GitHub仓库
3. 配置环境变量：
   - `DASHSCOPE_API_KEY`: 你的阿里云百炼API密钥
   - `SECRET_KEY`: 随机生成的Flask密钥
4. 点击部署

### 4. 配置域名（可选）

在Vercel Dashboard中可以配置自定义域名。

## 使用说明

1. 访问部署的URL
2. 上传Excel格式的工单数据
3. 输入阿里云百炼API密钥
4. 等待处理完成
5. 下载生成的QA对Excel文件

## API端点

- `GET /` - 主页
- `POST /upload` - 上传文件
- `GET /status/<task_id>` - 获取任务状态
- `GET /download/<task_id>` - 下载结果文件

## 注意事项

- Vercel免费版有执行时间限制（30秒）
- 大文件处理可能需要升级到付费计划
- API密钥请妥善保管，不要提交到代码仓库
- 上传的文件大小限制为Vercel平台限制（默认4.5MB）

## 故障排除

### 部署失败

1. 检查 `requirements.txt` 是否包含所有依赖
2. 确保 `vercel.json` 配置正确
3. 检查环境变量是否配置

### 运行时错误

1. 检查API密钥是否正确
2. 确认上传文件格式为Excel
3. 查看Vercel函数日志获取详细错误信息

## 技术支持


如有问题，请检查Vercel部署日志或联系开发团队。
