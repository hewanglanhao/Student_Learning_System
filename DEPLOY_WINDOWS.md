# DKT Backend Windows 本地部署文档

本文档仅针对 Windows 本地部署，内容以当前仓库中的 `app/*.py`、`requirements.txt`、`environment.yml`、`README.md`、`api.md` 为准。

## 1. 项目简介

这是一个基于 FastAPI + MongoDB + PyTorch 的自适应出题后端，主要能力如下：

- 根据用户知识点掌握度推荐单题或套题
- 支持补弱推荐和间隔复习推荐
- 用户提交答案后，调用 DKT 模型更新知识点掌握度画像

当前仓库的核心模块：

- `app/main.py`：FastAPI 路由、启动逻辑、用户画像更新、题目推荐与判题入口
- `app/recommender.py`：题目字段规范化、ZPD 过滤、补弱/复习/组卷策略
- `app/dkt_infer.py`：加载 `dkt_model.pt` 和知识点文件，执行 DKT 推理
- `app/db.py`：MongoDB 连接
- `app/config.py`：读取 `DKT_` 前缀环境变量

## 2. 环境要求

### 2.1 必需环境

| 组件 | 是否必需 | 版本要求 / 说明 |
| --- | --- | --- |
| Windows | 是 | 建议 Windows 10 / 11 64 位 |
| Git | 是 | 仓库未固定 Git 版本，安装可正常使用的 Git for Windows 即可 |
| Python | 是 | `environment.yml` 固定为 `3.10.19`，建议按 `Python 3.10.x` 部署 |
| MongoDB | 是 | 仓库代码要求可访问 MongoDB，默认连接 `mongodb://localhost:27017` |
| Conda | 否 | 如果使用 `environment.yml`，需要安装 Miniconda 或 Anaconda |

### 2.2 当前仓库未使用的环境

以下组件在当前后端仓库中没有实际依赖，不需要安装：

- Node.js
- Java
- Go
- Redis

## 3. 如何获取代码

当前仓库远程地址为：

- HTTPS：`https://github.com/hewanglanhao/Student_Learning_System.git`

如果使用 HTTPS：

```powershell
git clone https://github.com/hewanglanhao/Student_Learning_System.git DKT_backend
cd DKT_backend
```

如果使用 SSH：

```powershell
git clone git@github.com:hewanglanhao/Student_Learning_System.git DKT_backend
cd DKT_backend
```

## 4. 项目目录说明

只列部署相关的关键目录和关键文件：

```text
DKT_backend/
├─ app/
│  ├─ main.py            # FastAPI 入口、接口定义、启动/关闭逻辑
│  ├─ config.py          # 环境变量配置（DKT_ 前缀）
│  ├─ db.py              # MongoDB 客户端与数据库对象
│  ├─ recommender.py     # 题目规范化、ZPD、选题策略
│  ├─ dkt_infer.py       # DKT 模型加载与推理
│  └─ schemas.py         # 请求/响应模型
├─ dkt_model.pt          # DKT 模型权重文件
├─ requirements.txt      # pip 安装依赖
├─ environment.yml       # Conda 环境定义（Python 3.10.19）
├─ README.md             # 项目说明
└─ api.md                # 接口说明
```

额外注意：

- 代码默认还会读取“项目上一级目录”的 `最终结果.py`
- 这个文件不在当前仓库根目录内，但 `app/config.py` 默认就是这样解析路径的
- 如果你只单独拿到了当前后端仓库，通常需要手动设置 `DKT_KNOWLEDGE_POINTS_PATH`

## 5. 环境配置

### 5.1 是否需要复制示例配置文件

当前仓库中没有 `.env`、`.env.example`、`application.yml`、`application.yaml` 这类配置文件。

也就是说：

- 不需要复制示例配置文件
- 配置全部通过环境变量完成
- 环境变量前缀固定为 `DKT_`

### 5.2 关键配置项

`app/config.py` 中实际使用的配置如下：

| 环境变量 | 默认值 | 是否建议显式设置 | 说明 |
| --- | --- | --- | --- |
| `DKT_MONGODB_URI` | `mongodb://localhost:27017` | 建议 | MongoDB 连接串 |
| `DKT_DB_NAME` | `user_profiles_db` | 建议 | 数据库名 |
| `DKT_PRACTICE_COLLECTION` | `practice` | 建议 | 题库集合名 |
| `DKT_USER_COLLECTION` | `user_profiles` | 建议 | 用户画像集合名 |
| `DKT_MODEL_PATH` | 当前项目根目录下的 `dkt_model.pt` | 一般不用改 | DKT 模型文件路径 |
| `DKT_KNOWLEDGE_POINTS_PATH` | 当前项目上一级目录的 `最终结果.py` | 强烈建议检查 | 知识点文件路径 |

### 5.3 推荐的 PowerShell 配置方式

请在启动服务前，在同一个 PowerShell 窗口执行：

```powershell
$env:DKT_MONGODB_URI = "mongodb://localhost:27017"
$env:DKT_DB_NAME = "user_profiles_db"
$env:DKT_PRACTICE_COLLECTION = "practice"
$env:DKT_USER_COLLECTION = "user_profiles"
$env:DKT_MODEL_PATH = "$PWD\dkt_model.pt"
$env:DKT_KNOWLEDGE_POINTS_PATH = "D:\your-path\最终结果.py"
```

其中：

- `DKT_MODEL_PATH` 通常直接使用仓库内的 `dkt_model.pt` 即可
- `DKT_KNOWLEDGE_POINTS_PATH` 必须改成你本机实际存在的 `最终结果.py` 路径
- 如果你的 MongoDB 不是本机默认端口，也要同步修改 `DKT_MONGODB_URI`

## 6. 安装依赖

当前仓库提供两种安装方式，优先推荐 Conda，因为 `environment.yml` 已固定 Python 版本和主要依赖。

### 6.1 方式一：使用 Conda 安装

```powershell
conda env create -f environment.yml
conda activate dkt
```

### 6.2 方式二：使用 venv + pip 安装

```powershell
py -3.10 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

`requirements.txt` 中的核心依赖包括：

- `fastapi==0.110.0`
- `uvicorn[standard]==0.27.1`
- `motor==3.3.2`
- `pymongo==4.6.3`
- `pydantic==2.6.1`
- `pydantic-settings==2.1.0`
- `torch==2.2.0`

## 7. 数据库准备

### 7.1 当前代码实际依赖

服务会连接 MongoDB，并使用以下数据库对象：

- 数据库：`user_profiles_db`
- 题库集合：`practice`
- 用户画像集合：`user_profiles`

说明：

- `practice` 必须有题目数据，否则推荐接口会返回 `404 No available question found`
- `user_profiles` 不需要手工预填数据，服务会在首次调用相关接口时自动创建用户画像

### 7.2 当前仓库没有提供的内容

当前仓库内没有这些内容：

- MongoDB 初始化脚本
- 自动建库脚本
- 题库导入脚本
- 仓库内可直接导入的 `practice` 集合数据文件

因此，数据库准备的真实结论是：

- 必须先安装并启动 MongoDB
- 必须自行准备并导入题库数据到 `practice`
- `user_profiles` 可以由接口自动生成

### 7.3 题库数据字段要求

`app/recommender.py` 会兼容中英文字段。题目文档至少应满足以下结构之一：

```json
{
  "question_id": "C00001",
  "question_text": "题目内容",
  "options": {
    "A": "选项A",
    "B": "选项B",
    "C": "选项C",
    "D": "选项D"
  },
  "answer": "A",
  "answer_explanation": "解析",
  "knowledge_points": ["知识点1"],
  "question_type": "选择题"
}
```

或者：

```json
{
  "题目ID": "C00001",
  "题目描述": "题目内容",
  "选项": {
    "A": "选项A",
    "B": "选项B",
    "C": "选项C",
    "D": "选项D"
  },
  "答案": "A",
  "答案解析": "解析",
  "知识点": ["知识点1"],
  "题目类型": "选择题"
}
```

### 7.4 如果你已经有题库 JSON 文件

如果你已经准备好了符合上述字段结构的 JSON 数组文件，可以使用 `mongoimport` 导入：

```powershell
mongoimport --uri "mongodb://localhost:27017/user_profiles_db" --collection practice --file "D:\your-path\practice.json" --jsonArray
```

## 8. 启动项目

推荐按下面顺序启动。

### 8.1 进入项目目录

```powershell
cd D:\your-path\DKT_backend
```

### 8.2 激活 Python 环境

如果你使用 Conda：

```powershell
conda activate dkt
```

如果你使用 venv：

```powershell
.venv\Scripts\Activate.ps1
```

### 8.3 设置环境变量

```powershell
$env:DKT_MONGODB_URI = "mongodb://localhost:27017"
$env:DKT_DB_NAME = "user_profiles_db"
$env:DKT_PRACTICE_COLLECTION = "practice"
$env:DKT_USER_COLLECTION = "user_profiles"
$env:DKT_MODEL_PATH = "$PWD\dkt_model.pt"
$env:DKT_KNOWLEDGE_POINTS_PATH = "D:\your-path\最终结果.py"
```

### 8.4 确认 MongoDB 已启动

如果你是 Windows 服务方式安装的 MongoDB，可先执行：

```powershell
Get-Service MongoDB
```

### 8.5 启动 FastAPI 服务

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## 9. 启动成功验证

### 9.1 健康检查

```powershell
Invoke-WebRequest http://127.0.0.1:8000/health | Select-Object -ExpandProperty Content
```

期望返回：

```json
{"status":"ok"}
```

### 9.2 打开 Swagger 文档

FastAPI 没有禁用默认文档页，启动成功后可访问：

```text
http://127.0.0.1:8000/docs
```

### 9.3 检查实际数据库配置

```powershell
Invoke-WebRequest http://127.0.0.1:8000/debug/dbinfo | Select-Object -ExpandProperty Content
```

这个接口可以确认服务实际使用的 MongoDB 地址、数据库名、集合名。

### 9.4 验证用户画像是否能自动创建

```powershell
Invoke-RestMethod -Method Put -Uri "http://127.0.0.1:8000/users/test_user/interval_days" -ContentType "application/json" -Body '{"interval_days":7}'
```

如果返回 `user_id`、`interval_days`、`profile_update_time`，说明：

- 服务已正常启动
- MongoDB 可写
- `user_profiles` 集合可自动创建

## 10. 常见问题排查

### 10.1 `python` 或 `py` 命令不可用

说明当前机器未正确安装 Python，或者没有加入 PATH。请先安装 Python 3.10，并重新打开 PowerShell。

### 10.2 `ModuleNotFoundError` 或依赖安装失败

优先检查：

- 是否进入了正确的虚拟环境
- 是否使用了 Python 3.10
- 是否已经执行过 `pip install -r requirements.txt`

如果 `torch==2.2.0` 安装失败，优先改用 `environment.yml` 的 Conda 安装方式。

### 10.3 启动时报 `最终结果.py` 找不到

这是当前项目最常见的问题之一。原因是代码默认读取“项目上一级目录”的 `最终结果.py`，而不是仓库根目录。

解决方式：

```powershell
$env:DKT_KNOWLEDGE_POINTS_PATH = "D:\your-path\最终结果.py"
```

然后在同一个 PowerShell 窗口重新启动服务。

### 10.4 启动时报 MongoDB 连接失败

优先检查：

- MongoDB 是否已经启动
- `DKT_MONGODB_URI` 是否正确
- 本地端口 `27017` 是否可访问

可以先访问调试接口确认后端读取到的配置：

```powershell
Invoke-WebRequest http://127.0.0.1:8000/debug/dbinfo | Select-Object -ExpandProperty Content
```

### 10.5 推荐接口返回 `No available question found`

通常有以下几种原因：

- `practice` 集合为空
- 题库字段不符合代码要求，导致题目规范化失败
- 题目不是四选一选择题，已被代码过滤
- 用户做过的题太多，剩余候选题不足

### 10.6 端口 `8000` 被占用

可以换一个端口启动：

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

### 10.7 环境变量没有生效

请确认：

- 设置环境变量和启动 `uvicorn` 是在同一个 PowerShell 窗口中完成的
- 没有在设置变量之前就启动服务
- 路径包含中文或空格时，已经用双引号包裹

## 11. 最小可执行启动清单

如果你只想先把服务跑起来，最小步骤如下：

```powershell
git clone https://github.com/hewanglanhao/Student_Learning_System.git DKT_backend
cd DKT_backend
conda env create -f environment.yml
conda activate dkt
$env:DKT_MONGODB_URI = "mongodb://localhost:27017"
$env:DKT_DB_NAME = "user_profiles_db"
$env:DKT_PRACTICE_COLLECTION = "practice"
$env:DKT_USER_COLLECTION = "user_profiles"
$env:DKT_MODEL_PATH = "$PWD\dkt_model.pt"
$env:DKT_KNOWLEDGE_POINTS_PATH = "D:\your-path\最终结果.py"
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

