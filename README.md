# 企业级 AI 赋能测试平台

从需求文档到接口压测的全链路测试平台。支持 AI 辅助解析、用例生成、契约检查、压测分析与 Allure 报告，配套本地 Mock 商城 API，可直接联调。

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Django 5 + Django REST Framework |
| 前端 | Vue 3 + TypeScript + Element Plus + Vite + ECharts |
| 数据库 | SQLite  |
| 异步 | Celery |
| AI | 智谱 / OpenAI 兼容 / DeepSeek / 通义 / Moonshot 等，支持 CC Switch 导入 |
| Mock | Flask |

## 功能一览

### 需求中心

- 项目管理、需求文档上传（多格式预览 / 分片上传）
- AI 需求解析、测试点树生成

### 测试用例

- 用例管理（拖拽排序、字段配置、AI 生成）
- 用例格式转换

### 接口测试

- **接口文档解析**：Markdown / 上传文档 → 批量导入接口
- **接口自动化**：执行、断言、依赖链、Token 传递；支持手动新增 / 编辑接口
- **接口安全扫描**：SQL 注入、XSS 等规则扫描；支持手动维护目标接口
- **接口压测**：JMeter 式指标（RPS、P95、错误率）、资源监控图表、瓶颈 / 拐点分析；支持从自动化页一键压测、联调调试、压测时 Token 刷新

### 测试报告

- 自动化 / 安全扫描 / 压测完成后可生成 **Allure HTML 报告**
- 报告中心统一查看、打开报告链接

### AI 增强

| 模块 | 能力 |
|------|------|
| 契约测试 | OpenAPI 本地规则校验（中文）、修复建议、单项 / 一键自动修复 |
| 覆盖率分析 | 源码 + 用例覆盖评估、图表与改进建议 |
| 日志分析 | ERROR/WARN 统计、错误模式识别、排查建议 |

三个分析模块均支持：**会话自动保存**（刷新 / 切页不丢数据）、**分析记录**（自动入库、加载历史、下载 JSON / Markdown）。

### 工具箱

- 假数据生成、JSON 工具、编码转换（Base64 / URL / MD5 / SHA 等）

### 系统管理

- **大模型配置**：多厂商 API、连通性测试、CC Switch 导入
- **Skills 配置**：本地扫描 / 手动维护，注入 AI Prompt
- **系统设置**：数据概览、清理分析记录 / 报告 / 运行数据、**一键格式化业务数据**（保留 AI 配置并重建演示环境）

## 环境要求

| 依赖 | 版本建议 | 用途 |
|------|----------|------|
| **Python** | 3.10 ~ 3.12 | 后端 Django、Mock API |
| **Node.js** | 18+（推荐 20 LTS） | 前端 Vite 开发 / 构建 |
| **npm** | 9+ | 安装前端依赖（随 Node 安装） |
| **Git** | 任意较新版本 | 克隆仓库 |

可选（非必须）：

- **Redis**：Celery 异步任务（不启动也不影响主流程）
- **Allure CLI**：仅在你希望本地命令行打开 Allure 报告时需要；平台已内置 HTML 报告生成

## 安装与初始化

### 1. 获取项目

```bash
git clone <https://github.com/SandmCode/AI-TestOps>
cd ai-test-platform
```

也可在 GitHub 页面下载 ZIP 后解压进入项目目录。

### 2. 安装 Python 依赖

建议使用虚拟环境（任选一种）：

```bash
# 方式 A：venv
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

python -m pip install -U pip
python -m pip install -r requirements.txt
```

Mock 服务单独一份依赖（体积极小）：

```bash
cd mock-shop-api
python -m pip install -r requirements.txt
```

> 若已激活 `backend/.venv`，可在同一虚拟环境中安装 mock 依赖，无需重复建环境。

### 3. 安装前端依赖

```bash
cd frontend
npm install
```

首次安装或更新前端代码后执行即可，主要依赖包括 Vue 3、Element Plus、ECharts、Axios、Vite 等（详见 `frontend/package.json`）。

### 4. 初始化数据库与演示数据

```bash
cd backend
python manage.py migrate
python manage.py seed_demo
```

### 5. 环境变量（可选）

```bash
cd backend
cp .env.example .env
# 编辑 .env，填入 ZHIPUAI_API_KEY 等（也可稍后在界面「大模型配置」里填写）
```

## 启动步骤

完整功能需 **开 3 个终端**，分别启动 Mock、后端、前端（顺序不限，但建议先 Mock 和后端）。

**终端 1 — Mock 商城 API（9000）**  模块接口！！！

```bash
cd mock-shop-api
python app.py
```

**终端 2 — Django 后端（8000）**

```bash
cd backend
# 若使用 venv，先激活
python manage.py runserver 127.0.0.1:8000
```

**终端 3 — Vue 前端（5173）**

```bash
cd frontend
npm run dev
```

### 访问地址

| 服务 | 地址 |
|------|------|
| **平台首页（从这里进）** | http://127.0.0.1:5173 |
| 后端 API | http://127.0.0.1:8000/api/ |
| Mock API | http://127.0.0.1:9000/v1 |
| Mock 接口清单 | http://127.0.0.1:9000/v1/_endpoints |

### 测试账号与全局变量

| 项目 | 值 |
|------|-----|
| Mock 用户名 | `demo_user` |
| Mock 密码 | `Pass@123456` |
| 全局变量示例 | `{"baseUrl":"http://127.0.0.1:9000/v1"}` |

登录接口：`POST /v1/auth/login`，后续接口使用返回的 `access_token`（`Authorization: Bearer <token>`）。

### 启动失败常见原因

- **前端页面空白 / 接口 404**：后端 8000 未启动，或前端未用 `npm run dev`
- **接口自动化连不上**：Mock 9000 未启动，或全局变量 `baseUrl` 未配置
- **`npm install` 报错**：检查 Node 版本 ≥ 18，可尝试删除 `node_modules` 后重装：
  ```bash
  cd frontend
  rm -rf node_modules    # Windows PowerShell: Remove-Item -Recurse -Force node_modules
  npm install
  ```
- **Python 包安装失败**：确认已激活虚拟环境，并使用 `python -m pip install -r requirements.txt`

## 快速启动（已完成安装时）

若已完成上文「安装与初始化」，日常开发只需：

```bash
# 终端 1
cd mock-shop-api && python app.py

# 终端 2
cd backend && python manage.py runserver 127.0.0.1:8000

# 终端 3
cd frontend && npm run dev
```

浏览器打开：**http://127.0.0.1:5173**

> 前后端分离：页面在 **5173**。开发时 Vite 会把 `/api` 代理到 8000，请勿仅用 8000 访问前端页面。

## 配置大模型（可选）

**方式一：界面配置（推荐）**

系统管理 → 大模型配置 → AI 配置，填写厂商、API Key、Base URL、模型名。

**方式二：环境变量**

```bash
cp backend/.env.example backend/.env
# 编辑 backend/.env
ZHIPUAI_API_KEY=your_api_key_here
```

未配置时：契约 / 日志分析仍可用**本地规则**；覆盖率分析、需求解析等 AI 能力需配置后使用。

## 典型使用流程

```
创建项目 → 上传需求 / 接口文档 → AI 解析测试点 / 接口
    → 生成用例 → 接口自动化执行 → 生成 Allure 报告
    →（可选）安全扫描 / 压测 → 报告中心查看
    → 契约测试 / 覆盖率 / 日志分析 → 导出分析记录
```

## 项目结构

```
ai-test-platform/
├── backend/
│   ├── config/                 # Django 配置
│   ├── apps/
│   │   ├── projects/           # 项目、文档、分片上传
│   │   ├── testing/            # 用例、接口自动化、安全、压测
│   │   ├── tools/              # 假数据、编码等工具 API
│   │   └── ai_features/        # AI 分析、报告、大模型配置、系统维护
│   └── manage.py
├── frontend/
│   └── src/
│       ├── views/              # 业务页面
│       ├── components/         # 公共组件（接口表单、分析工作台等）
│       ├── composables/        # 会话持久化等
│       └── api/                # 接口封装
├── mock-shop-api/              # 本地可调用 Mock 服务
├── samples/
│   └── mock-api-doc.md         # 与 Mock 对齐的接口文档样例
└── README.md
```

## 常用 API

| 接口 | 说明 |
|------|------|
| `GET/POST /api/projects/` | 项目管理 |
| `GET/POST /api/documents/` | 需求 / 接口文档 |
| `GET/POST /api/test-cases/` | 测试用例 |
| `GET/POST /api/api-interfaces/` | 接口定义 |
| `POST /api/api-test-runs/execute/` | 接口自动化执行 |
| `POST /api/stress-test-runs/` | 启动压测 |
| `POST /api/test-reports/generate-automation/` | 生成自动化 Allure 报告 |
| `POST /api/ai/contract-test/` | 契约测试（自动保存分析记录） |
| `POST /api/ai/contract-test/fix/` | 契约一键 / 单项修复 |
| `POST /api/ai/coverage-analysis/` | 覆盖率分析 |
| `POST /api/ai/log-analysis/` | 日志分析 |
| `GET /api/analysis-records/` | 分析记录列表 |
| `GET /api/analysis-records/{id}/download/?file_type=md` | 下载分析报告 |
| `GET /api/system/info/` | 系统数据统计 |
| `POST /api/system/maintain/` | 数据清理 / 格式化 |

## 生产构建

```bash
cd frontend
npm run build
# 将 dist 交由 Django 静态托管，或独立部署并由 Nginx 反代 /api
```

## 管理命令

```bash
cd backend
python manage.py seed_demo          # 初始化演示数据
python manage.py migrate            # 数据库迁移
```

系统设置页也可一键格式化业务数据（等效于清空业务库后重新 `seed_demo`，**不删除 AI 配置**）。

## 依赖文件说明

| 文件 | 说明 |
|------|------|
| `backend/requirements.txt` | Django、DRF、智谱/OpenAI SDK、文档解析等 |
| `mock-shop-api/requirements.txt` | Flask Mock 服务 |
| `frontend/package.json` | 前端依赖声明，`npm install` 时读取 |
| `backend/.env.example` | 环境变量模板，复制为 `.env` 后按需填写 |

## 服务端口汇总

| 服务 | 地址 |
|------|------|
| 前端 | http://127.0.0.1:5173 |
| 后端 API | http://127.0.0.1:8000/api/ |
| Mock API | http://127.0.0.1:9000/v1 |

## License

项目截图
<img width="1877" height="838" alt="image" src="https://github.com/user-attachments/assets/5819b643-0b86-4e26-b62a-35980c6c13e4" />
<img width="1892" height="831" alt="image" src="https://github.com/user-attachments/assets/d3c7720c-ccf5-4b47-a675-cfbede9411cf" />
<img width="1905" height="833" alt="image" src="https://github.com/user-attachments/assets/e6a04305-01b3-417f-8d9b-abbc50692c87" />
<img width="1908" height="845" alt="image" src="https://github.com/user-attachments/assets/8c7ec218-a336-41be-939d-18e3d3358f62" />
<img width="1897" height="849" alt="image" src="https://github.com/user-attachments/assets/4326e3a3-66cb-403c-8f26-250706afe89e" />
<img width="1914" height="857" alt="image" src="https://github.com/user-attachments/assets/a87585d0-8aa6-4ecc-ae3d-045ee4cf2746" />
<img width="1886" height="838" alt="image" src="https://github.com/user-attachments/assets/11e951fb-28fe-4751-8d9f-d9db5fdc7d86" />
<img width="1914" height="844" alt="image" src="https://github.com/user-attachments/assets/5ea00843-d5ea-47cf-b511-7661df1106f4" />
<img width="1883" height="838" alt="image" src="https://github.com/user-attachments/assets/cd34e3c2-fab4-45a5-b5c3-cb8c548841c2" />
<img width="1885" height="827" alt="image" src="https://github.com/user-attachments/assets/b51d0c4c-8cb6-4d19-b65b-ad8cc1c605b1" />
<img width="1882" height="817" alt="image" src="https://github.com/user-attachments/assets/b3ee55ea-26c4-4180-8b68-43c29be1ddf0" />
<img width="1887" height="826" alt="image" src="https://github.com/user-attachments/assets/7e2d7799-8b4e-41b1-bebf-fb98103505df" />
<img width="1905" height="846" alt="image" src="https://github.com/user-attachments/assets/b7040dbb-50a9-4017-b6aa-ae459a61b63a" />



