# DKT Backend

基于 FastAPI + MongoDB + PyTorch 的自适应出题后端，核心目标是：
- 根据用户知识点掌握度动态推荐题目
- 支持补弱、间隔复习和套题生成
- 在用户提交答案后，使用 DKT（LSTM）更新知识点掌握度画像

详细接口字段与示例请查看 [api.md](./api.md)。

## 主要功能

- 用户画像管理
  - 自动创建用户画像（初始掌握度、作答历史、复习统计、`interval_days=7`）
  - 查询用户画像与交互历史
  - 支持用户单独设置 `interval_days`（间隔复习周期），接口：`PUT /users/{user_id}/interval_days`
- 单题推荐
  - `weakest`：优先补弱（选择“最薄弱知识点”相关题目）
  - `spaced`：补弱 + 间隔复习（结合遗忘风险）
- 套题推荐
  - 按难度比例（easy/medium/hard）抽题
  - 在满足难度目标的同时尽量扩大知识点覆盖
- 答案提交与画像更新
  - 单题/套题判题
  - 更新 `interaction_history`、`kc_last_practiced`、`kc_review_count`
  - 基于历史交互序列调用 DKT 推理，刷新 `knowledge_mastery`

## 实现说明

### 1) 数据层与服务层

- 数据库：MongoDB
  - `practice`：题库
  - `user_profiles`：用户画像
- 服务：FastAPI 异步接口，`motor` 访问 MongoDB
- 启动时加载 DKT 推理器，关闭时释放 MongoDB 连接

### 2) 题目数据规范化

题库同时兼容中英文字段，服务内部会统一解析，例如：
- `question_id` / `题目ID`
- `question_text` / `题目描述`
- `options` / `选项`
- `answer` / `答案`
- `answer_explanation` / `答案解析`
- `knowledge_points` / `知识点`

返回前端时统一使用中文字段，并且默认不返回正确答案，避免泄题。

### 3) 推荐策略

- ZPD 筛选（最近发展区）
  - 先估计题目“预计正确率”，再按 `[zpd_min, zpd_max]` 过滤候选题
  - 若 ZPD 后无题可用，则回退到未筛选候选集
- `weakest` 单题策略
  - 按知识点掌握度计算薄弱分数（`sum/max/min`）
  - 选分数最高题目
- `spaced` 单题策略
  - 综合得分 = `alpha * 薄弱度 + beta * 遗忘风险`
  - 遗忘风险来自 `kc_last_practiced` 与 `interval_days`
- 套题策略
  - 先按预计正确率划分 `easy/medium/hard`
  - 按 `difficulty_ratio` 计算目标数量
  - 选题时优先提高知识点覆盖，再考虑薄弱度

#### 3.1 候选集构建流程（所有出题接口通用）

1. 读取用户画像 `knowledge_mastery` 与 `interaction_history`。  
2. 从历史中提取 `answered_ids`，默认不重复出已做过的题。  
3. 根据策略选取目标知识点（仅弱点，或弱点+复习点）。  
4. 在题库 `practice` 中查询包含这些知识点的题目，并做数据规范化。  
5. 过滤非选择题，只保留四选一题型。  
6. 先做 ZPD 过滤，若结果为空则回退到原候选池。

#### 3.2 预计正确率与 ZPD

题目关联知识点集合为 `K`，用户对知识点 `k` 的掌握度为 `p_k`。  
预计正确率 `E(q)` 支持 3 种聚合方式：

- `min`：`E(q) = min(p_k), k∈K`
- `mean`：`E(q) = avg(p_k), k∈K`
- `product`：`E(q) = Π p_k, k∈K`

仅保留满足 `zpd_min <= E(q) <= zpd_max` 的题；若无满足项则跳过 ZPD 直接选题。

#### 3.3 `weakest`（补弱优先）实现

- 先取 `top_k_weak` 个最低掌握度知识点作为目标范围。  
- 对每道候选题计算薄弱度（deficit）：
  - 对单知识点 deficit：`d_k = 1 - p_k`
  - `sum`：`score = Σ d_k`
  - `max`：`score = max(d_k)`
  - `min`：`score = 1 - min(p_k)`（等价于“最强短板”）
- 取 `score` 最高的题作为返回结果。

`weakest` 实际执行流程（对应代码）：

1. 获取用户画像，读取 `knowledge_mastery` 和 `interaction_history`，并提取已做题集合 `answered_ids`（`app/main.py` 中 `_get_or_create_profile`、`_get_answered_ids`）。  
2. 将 `knowledge_mastery` 按掌握度升序排序，选出 `top_k_weak` 个最弱知识点（`_weak_kcs`）。  
3. 在题库中查询命中这些知识点的题，规范化后仅保留选择题（`_fetch_candidates` + `normalize_question`）。  
4. 从候选集中剔除已作答题目（`_filter_answered`），默认避免重复练习同一题。  
5. 对候选题计算预计正确率 `E(q)`，按 `zpd_min <= E(q) <= zpd_max` 进行 ZPD 过滤；若过滤后为空，则回退到未过滤候选集。  
6. 对最终候选集按 `score_mode` 计算 `weakness_score`，返回分值最高的一题（`pick_weakest_question`）。  
7. 若候选为空，接口返回 404（`No available question found`）。

#### 3.4 `spaced`（补弱 + 间隔复习）实现

- 弱点知识点：同 `weakest`，取 `top_k_weak`。  
- 复习知识点：从“已达到 `mastery_threshold`”的知识点中，按“距上次练习天数”降序取 `top_k_review`。  
- 合并为目标知识点后取候选题。  
- `interval_days` 从用户画像读取（默认 7），可通过接口更新。  
- 每题综合分：
  - `weakness = Σ(1 - p_k)`
  - `forget_risk_k = min(days_since_last_practice / interval_days, 1.0)`（仅对已掌握知识点计算）
  - `forget_risk = max(forget_risk_k)`
  - `score = alpha * weakness + beta * forget_risk`
- 取 `score` 最高题目。

#### 3.5 `set`（套题组卷）实现

1. 先按预计正确率把候选题分桶：
   - `easy`: `E(q) >= 0.8`
   - `medium`: `0.6 <= E(q) < 0.8`
   - `hard`: `E(q) < 0.6`
2. 按 `difficulty_ratio` 和 `count` 计算目标数量（四舍五入，不足量由其他桶补齐）。  
3. 按顺序从 `medium -> hard -> easy` 选题。  
4. 每次从桶内选“增量知识点覆盖最多”的题；若覆盖增量相同，选薄弱度更高的题。  
5. 若仍未达到 `count`，从剩余候选中按同一规则补满。

### 4) DKT 推理更新掌握度

- 模型：LSTM DKT（`dkt_model.pt`）
- 知识点索引：从 `最终结果.py` 的 `knowledge_points` 列表读取
- 交互编码方式：
  - 每次作答由“知识点集合 + 对错”构成
  - 正确/错误通过 embedding 偏移区分后求和，形成时间步输入
- 输出：序列最后一步的各知识点概率，回写到 `knowledge_mastery`

## 项目结构

```text
DKT_backend/
├─ app/
│  ├─ main.py          # FastAPI 路由与业务编排
│  ├─ recommender.py   # 题目规范化、ZPD、选题策略
│  ├─ dkt_infer.py     # DKT 模型加载与推理
│  ├─ schemas.py       # 请求/响应模型
│  ├─ db.py            # MongoDB 连接
│  └─ config.py        # 配置与环境变量
├─ dkt_model.pt        # 训练好的 DKT 权重
├─ api.md              # 接口详解
└─ requirements.txt
```

## 快速启动

1. 安装依赖

```bash
pip install -r requirements.txt
```

2. 启动服务

```bash
uvicorn app.main:app --reload --port 8000
```

3. 健康检查

```bash
curl http://localhost:8000/health
```

## 环境变量

支持 `DKT_` 前缀配置：

- `DKT_MONGODB_URI`（默认：`mongodb://localhost:27017`）
- `DKT_DB_NAME`（默认：`user_profiles_db`）
- `DKT_PRACTICE_COLLECTION`（默认：`practice`）
- `DKT_USER_COLLECTION`（默认：`user_profiles`）
- `DKT_MODEL_PATH`（默认：项目根目录下 `dkt_model.pt`）
- `DKT_KNOWLEDGE_POINTS_PATH`（默认：项目上级目录下 `最终结果.py`）

## 依赖

- fastapi
- uvicorn
- motor / pymongo
- pydantic / pydantic-settings
- torch
