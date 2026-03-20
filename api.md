# DKT Backend API

基础地址：`http://localhost:8000`

服务读取 MongoDB 数据：
- 数据库：`user_profiles_db`
- 集合：`practice`（题库），`user_profiles`（用户画像）

题目文档会从英文字段（`question_id`, `question_text`, `options`, `answer`, `answer_explanation`, `knowledge_points`）或中文字段（`题目ID`, `题目描述`, `选项`, `答案`, `答案解析`, `知识点`）中规范化读取。  
所有题目响应均返回中文字段名，以匹配前端数据格式。

## 健康检查

`GET /health`

响应：
```json
{"status":"ok"}
```

## 获取用户画像

`GET /users/{user_id}`

说明：按 `user_id` 返回用户画像全文；`_id` 会被转换为字符串。

响应（示例）：
```json
{
  "_id": "65c8f0f4f2a1b1f3a9c9b1a2",
  "user_id": "u_001",
  "interval_days": 7,
  "knowledge_mastery": {"数据文件处理": 0.42},
  "interaction_history": [
    {
      "question_id": "C00001",
      "knowledge_points": ["数据文件处理"],
      "is_correct": false,
      "selected_option": "B",
      "correct_option": "C",
      "答案解析": "文件可以是二进制文件或文本文件，描述为数据序列。",
      "answered_at": "2026-02-11T13:22:10.123456+00:00"
    }
  ]
}
```

## 设置用户间隔复习天数

`PUT /users/{user_id}/interval_days`

说明：设置该用户画像中的 `interval_days`。若用户不存在会自动创建画像。默认值为 `7`。

请求：
```json
{
  "interval_days": 10
}
```

字段说明：
1. `interval_days`：间隔复习周期（天），范围 1~365。

响应：
```json
{
  "user_id": "u_001",
  "interval_days": 10,
  "profile_update_time": "2026-03-10T08:00:00+00:00"
}
```

## 获取用户作答历史

`GET /users/{user_id}/interaction_history`

说明：按 `user_id` 返回该用户的 `interaction_history`。

响应（示例）：
```json
{
  "user_id": "u_001",
  "interaction_history": [
    {
      "question_id": "C00001",
      "knowledge_points": ["数据文件处理"],
      "is_correct": false,
      "selected_option": "B",
      "correct_option": "C",
      "答案解析": "文件可以是二进制文件或文本文件，描述为数据序列。",
      "answered_at": "2026-02-11T13:22:10.123456+00:00"
    }
  ]
}
```

## 调试数据库连接信息

`GET /debug/dbinfo`

说明：返回后端当前使用的 MongoDB 连接与集合配置，便于核对 Compass 是否连到同一个实例。

响应（示例）：
```json
{
  "mongodb_uri": "mongodb://localhost:27017",
  "db_name": "user_profiles_db",
  "practice_collection": "practice",
  "user_collection": "user_profiles"
}
```

## 单题（补弱优先）

`POST /questions/single/weakest`

请求：
```json
{
  "user_id": "u_001",
  "zpd_min": 0.6,
  "zpd_max": 0.8,
  "expected_mode": "min",
  "score_mode": "sum",
  "top_k_weak": 5,
  "max_candidates": 2000
}
```

字段说明：
1. `user_id`：用户唯一标识。
2. `zpd_min`：最近发展区下限（预计正确率下限，0~1）。
3. `zpd_max`：最近发展区上限（预计正确率上限，0~1）。
4. `expected_mode`：预计正确率的聚合方式，`min`/`mean`/`product`。
5. `score_mode`：补弱打分方式，`sum`/`max`/`min`。
6. `top_k_weak`：参与候选的最弱知识点数量。
7. `max_candidates`：从题库中最多拉取的候选题数量。

响应：
```json
{
  "strategy": "weakest",
  "zpd_applied": true,
  "question": {
    "题目ID": "C00001",
    "题目类型": "选择题",
    "题目描述": "Question text...",
    "选项": {"A":"...", "B":"...", "C":"...", "D":"..."},
    "知识点": ["数据文件处理"]
  }
}
```

字段说明：
1. `strategy`：出题策略标识，`weakest` 表示补弱优先。
2. `zpd_applied`：是否成功应用 ZPD 筛选。
3. `question`：题目对象（中文字段格式）。
4. `question.题目ID`：题目编号。
5. `question.题目类型`：题型，通常为 `选择题`。
6. `question.题目描述`：题干。
7. `question.选项`：四个选项键值（A/B/C/D）。
8. `question.知识点`：题目关联知识点列表。

## 单题（间隔重复）

`POST /questions/single/spaced`

请求：
```json
{
  "user_id": "u_001",
  "zpd_min": 0.6,
  "zpd_max": 0.8,
  "expected_mode": "min",
  "alpha": 0.6,
  "beta": 0.4,
  "mastery_threshold": 0.6,
  "top_k_review": 5,
  "top_k_weak": 5,
  "max_candidates": 2000
}
```

字段说明：
1. `user_id`：用户唯一标识。
2. `zpd_min`：最近发展区下限（预计正确率下限，0~1）。
3. `zpd_max`：最近发展区上限（预计正确率上限，0~1）。
4. `expected_mode`：预计正确率的聚合方式，`min`/`mean`/`product`。
5. `alpha`：补弱权重（0~1）。
6. `beta`：遗忘风险权重（0~1）。
7. `mastery_threshold`：认为“已掌握”的阈值（0~1）。
8. `top_k_review`：参与复习候选的知识点数量。
9. `top_k_weak`：参与补弱候选的知识点数量。
10. `max_candidates`：从题库中最多拉取的候选题数量。

补充：该接口计算遗忘风险时使用用户画像中的 `interval_days`（默认 7），不再从请求参数读取。

响应：与补弱优先接口相同结构，仅 `strategy` 为 `"spaced"`。

## 出一套题（多样性 + 覆盖）

`POST /questions/set`

请求：
```json
{
  "user_id": "u_001",
  "count": 10,
  "zpd_min": 0.5,
  "zpd_max": 0.9,
  "expected_mode": "mean",
  "max_candidates": 3000,
  "difficulty_ratio": {"easy": 0.2, "medium": 0.6, "hard": 0.2}
}
```

字段说明：
1. `user_id`：用户唯一标识。
2. `count`：需要出题的数量。
3. `zpd_min`：最近发展区下限（预计正确率下限，0~1）。
4. `zpd_max`：最近发展区上限（预计正确率上限，0~1）。
5. `expected_mode`：预计正确率的聚合方式，`min`/`mean`/`product`。
6. `max_candidates`：从题库中最多拉取的候选题数量。
7. `difficulty_ratio`：难度比例配置，`easy`/`medium`/`hard` 之和建议为 1。

响应：
```json
{
  "strategy": "set",
  "zpd_applied": true,
  "questions": [
    {"题目ID":"C00001","题目类型":"选择题","题目描述":"...","选项":{"A":"...","B":"...","C":"...","D":"..."},"知识点":["..."]}
  ]
}
```

字段说明：
1. `strategy`：出题策略标识，`set` 表示出一套题。
2. `zpd_applied`：是否成功应用 ZPD 筛选。
3. `questions`：题目数组（中文字段格式）。

## 单题提交答案（更新 LSTM 掌握度）

`POST /questions/answer`

请求：
```json
{
  "user_id": "u_001",
  "question_id": "C00001",
  "selected_option": "B",
  "答案解析": "用户提交的答案解析（可选）"
}
```

字段说明：
1. `user_id`：用户唯一标识。
2. `question_id`：题目编号（与题库一致）。
3. `selected_option`：用户选择的选项（A/B/C/D）。
4. `答案解析`：可选。前端传入的解析文本；若不传则使用题库中的 `答案解析`。

响应：
```json
{
  "is_correct": false,
  "correct_option": "C",
  "selected_option": "B",
  "updated_kc_mastery": {"数据文件处理": 0.42},
  "profile_update_time": "2026-02-11T13:22:10.123456+00:00"
}
```

字段说明：
1. `is_correct`：是否答对。
2. `correct_option`：正确选项（A/B/C/D）。
3. `selected_option`：用户选择的选项（A/B/C/D）。
4. `updated_kc_mastery`：本题关联知识点的最新掌握度（0~1）。
5. `profile_update_time`：用户画像更新时间（ISO 时间）。

## 套题提交答案（统一更新 LSTM 掌握度）

`POST /questions/set/answer`

请求：
```json
{
  "user_id": "u_001",
  "answers": [
    {"question_id": "C00001", "selected_option": "B", "答案解析": "该题解析文本（可选）"},
    {"question_id": "C00002", "selected_option": "D"}
  ]
}
```

字段说明：
1. `user_id`：用户唯一标识。
2. `answers`：答题数组。
3. `answers[].question_id`：题目编号（与题库一致）。
4. `answers[].selected_option`：用户选择的选项（A/B/C/D）。
5. `answers[].答案解析`：可选。该题前端传入的解析文本；若不传则使用题库中的 `答案解析`。

响应：
```json
{
  "results": [
    {"question_id": "C00001", "is_correct": false, "correct_option": "C", "selected_option": "B"},
    {"question_id": "C00002", "is_correct": true, "correct_option": "D", "selected_option": "D"}
  ],
  "updated_kc_mastery": {"数据文件处理": 0.52},
  "profile_update_time": "2026-02-11T13:22:10.123456+00:00"
}
```

字段说明：
1. `results`：本套题每题的判题结果数组。
2. `results[].question_id`：题目编号。
3. `results[].is_correct`：是否答对。
4. `results[].correct_option`：正确选项（A/B/C/D）。
5. `results[].selected_option`：用户选择的选项（A/B/C/D）。
6. `updated_kc_mastery`：整套题完成后整体更新的知识点掌握度（0~1）。
7. `profile_update_time`：用户画像更新时间（ISO 时间）。

## 说明

- 所有题目仅返回 4 个选项，非选择题会被跳过。
- 题目响应不包含 `答案`，避免泄露正确选项。
- 服务会在 `user_profiles` 中保存 `interaction_history`（每题含 `答案解析`），并更新 `knowledge_mastery`、`kc_last_practiced`、`kc_review_count`、`interval_days`（默认 7，可通过接口修改）。
- 提交答案时，`interaction_history.答案解析` 的来源优先级：前端请求字段 `答案解析` > 题库字段 `答案解析`。
- 知识点索引来自 `最终结果.py` 的 `knowledge_points` 列表，LSTM 推理使用 `DKT_backend/dkt_model.pt`。

## 运行

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## 环境变量

所有配置可通过 `DKT_` 前缀环境变量覆盖：

- `DKT_MONGODB_URI`
- `DKT_DB_NAME`
- `DKT_PRACTICE_COLLECTION`
- `DKT_USER_COLLECTION`
- `DKT_MODEL_PATH`
- `DKT_KNOWLEDGE_POINTS_PATH`

## 使用步骤
**使用步骤**
1. 启动 MongoDB 服务，确保有数据库 `user_profiles_db`，题库集合 `practice`，画像集合 `user_profiles`。  
2. 进入后端目录并安装依赖：
```bash
cd DKT_backend
pip install -r requirements.txt
```
3. 启动服务：
```bash
uvicorn app.main:app --reload --port 8000
```
4. 按流程调用接口：先取题 → 用户答题 → 提交答案（会更新画像与掌握度）。


**可选配置（环境变量）**
- `DKT_MONGODB_URI`（默认 `mongodb://localhost:27017`）
- `DKT_DB_NAME`（默认 `user_profiles_db`）
- `DKT_PRACTICE_COLLECTION`（默认 `practice`）
- `DKT_USER_COLLECTION`（默认 `user_profiles`）
