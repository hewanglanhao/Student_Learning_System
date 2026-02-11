# DKT Backend API

Base URL: `http://localhost:8000`

This service reads data from MongoDB:
- Database: `user_profiles_db`
- Collections: `practice` (questions), `user_profiles` (profiles)

Question documents are normalized from either English fields (`question_id`, `question_text`, `options`, `answer`, `knowledge_points`) or Chinese fields (`题目ID`, `题目描述`, `选项`, `答案`, `知识点`).  
All question responses are returned in Chinese field names to match your frontend data format.

## Health

`GET /health`

Response:
```json
{"status":"ok"}
```

## Single Question (Weakest-KC First)

`POST /questions/single/weakest`

Request:
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

Response:
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

## Single Question (Spaced Repetition)

`POST /questions/single/spaced`

Request:
```json
{
  "user_id": "u_001",
  "zpd_min": 0.6,
  "zpd_max": 0.8,
  "expected_mode": "min",
  "interval_days": 7,
  "alpha": 0.6,
  "beta": 0.4,
  "mastery_threshold": 0.6,
  "top_k_review": 5,
  "top_k_weak": 5,
  "max_candidates": 2000
}
```

Response: same shape as the weakest endpoint, with `strategy: "spaced"`.

## Question Set (Diversity + Coverage)

`POST /questions/set`

Request:
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

Response:
```json
{
  "strategy": "set",
  "zpd_applied": true,
  "questions": [
    {"题目ID":"C00001","题目类型":"选择题","题目描述":"...","选项":{"A":"...","B":"...","C":"...","D":"..."},"知识点":["..."]}
  ]
}
```

## Submit Answer (Update LSTM Mastery)

`POST /questions/answer`

Request:
```json
{
  "user_id": "u_001",
  "question_id": "C00001",
  "selected_option": "B"
}
```

Response:
```json
{
  "is_correct": false,
  "correct_option": "C",
  "selected_option": "B",
  "updated_kc_mastery": {"数据文件处理": 0.42},
  "profile_update_time": "2026-02-11T13:22:10.123456+00:00"
}
```

## Notes

- All questions returned include 4 options only. Non-multiple-choice items are skipped.
- Question responses do not include `答案` to avoid leaking the correct option.
- The service stores an `interaction_history` array and updates `knowledge_mastery`, `kc_last_practiced`, and `kc_review_count` in `user_profiles`.
- Knowledge point indices are loaded from `最终结果.py` (list `knowledge_points`), and LSTM inference uses `DKT_backend/dkt_model.pt`.

## Run

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Environment Variables

All settings can be overridden using `DKT_` prefix:

- `DKT_MONGODB_URI`
- `DKT_DB_NAME`
- `DKT_PRACTICE_COLLECTION`
- `DKT_USER_COLLECTION`
- `DKT_MODEL_PATH`
- `DKT_KNOWLEDGE_POINTS_PATH`
