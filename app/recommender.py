from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Literal


QuestionScoreMode = Literal["sum", "max", "min"]
ExpectedMode = Literal["min", "mean", "product"]


@dataclass
class Question:
    question_id: str
    question_text: str
    options: dict[str, str]
    answer: str
    answer_explanation: str
    knowledge_points: list[str]
    question_type: str | None = None

    def to_public_dict(self, include_answer: bool = False) -> dict:
        data = {
            "题目ID": self.question_id,
            "题目类型": self.question_type or "选择题",
            "题目描述": self.question_text,
            "选项": self.options,
            "知识点": self.knowledge_points,
        }
        if include_answer:
            data["答案"] = self.answer
        return data


def _normalize_options(options) -> dict[str, str] | None:
    if isinstance(options, dict):
        keys = ["A", "B", "C", "D"]
        if all(k in options for k in keys):
            return {k: str(options[k]) for k in keys}
        if len(options) == 4:
            return {k: str(v) for k, v in options.items()}
        return None
    if isinstance(options, list) and len(options) == 4:
        return {"A": str(options[0]), "B": str(options[1]), "C": str(options[2]), "D": str(options[3])}
    return None


def normalize_question(doc: dict) -> Question | None:
    question_id = doc.get("question_id") or doc.get("题目ID")
    question_text = doc.get("question_text") or doc.get("题目描述")
    answer = doc.get("answer") or doc.get("答案")
    answer_explanation = doc.get("answer_explanation") or doc.get("答案解析") or ""
    options = doc.get("options") or doc.get("选项")
    knowledge_points = doc.get("knowledge_points") or doc.get("知识点")
    question_type = doc.get("question_type") or doc.get("题目类型")

    if not question_id or not question_text or not answer:
        return None
    options_norm = _normalize_options(options)
    if options_norm is None:
        return None
    if isinstance(knowledge_points, str):
        knowledge_points = [knowledge_points]
    if not isinstance(knowledge_points, list):
        knowledge_points = []

    return Question(
        question_id=str(question_id),
        question_text=str(question_text),
        options=options_norm,
        answer=str(answer).strip(),
        answer_explanation=str(answer_explanation),
        knowledge_points=[str(k) for k in knowledge_points],
        question_type=str(question_type) if question_type else None,
    )


def expected_correct(kc_list: list[str], mastery: dict[str, float], mode: ExpectedMode) -> float | None:
    if not kc_list:
        return None
    probs = [float(mastery.get(k, 0.0)) for k in kc_list]
    if mode == "min":
        return min(probs)
    if mode == "product":
        prod = 1.0
        for p in probs:
            prod *= p
        return prod
    return sum(probs) / len(probs)


def weakness_score(kc_list: list[str], mastery: dict[str, float], mode: QuestionScoreMode) -> float:
    if not kc_list:
        return 0.0
    deficits = [1.0 - float(mastery.get(k, 0.0)) for k in kc_list]
    if mode == "sum":
        return sum(deficits)
    if mode == "max":
        return max(deficits)
    return 1.0 - min(float(mastery.get(k, 0.0)) for k in kc_list)


def filter_zpd(questions: Iterable[Question], mastery: dict[str, float], expected_mode: ExpectedMode,
               zpd_min: float, zpd_max: float) -> list[Question]:
    filtered = []
    for q in questions:
        exp = expected_correct(q.knowledge_points, mastery, expected_mode)
        if exp is None:
            continue
        if zpd_min <= exp <= zpd_max:
            filtered.append(q)
    return filtered


def pick_weakest_question(
    questions: Iterable[Question],
    mastery: dict[str, float],
    score_mode: QuestionScoreMode,
    expected_mode: ExpectedMode,
    zpd_min: float,
    zpd_max: float,
) -> Question | None:
    candidates = filter_zpd(questions, mastery, expected_mode, zpd_min, zpd_max)
    if not candidates:
        candidates = list(questions)
    if not candidates:
        return None
    return max(candidates, key=lambda q: weakness_score(q.knowledge_points, mastery, score_mode))


def _days_since(timestamp: str | None) -> float:
    if not timestamp:
        return 0.0
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max((now - dt).total_seconds() / 86400.0, 0.0)


def spaced_score(
    q: Question,
    mastery: dict[str, float],
    kc_last_practiced: dict[str, str],
    mastery_threshold: float,
    interval_days: float,
    alpha: float,
    beta: float,
) -> float:
    weakness = weakness_score(q.knowledge_points, mastery, "sum")
    forget_risks = []
    for kc in q.knowledge_points:
        if mastery.get(kc, 0.0) < mastery_threshold:
            continue
        days = _days_since(kc_last_practiced.get(kc))
        risk = min(days / max(interval_days, 1.0), 1.0)
        forget_risks.append(risk)
    forget_risk = max(forget_risks) if forget_risks else 0.0
    return alpha * weakness + beta * forget_risk


def pick_spaced_question(
    questions: Iterable[Question],
    mastery: dict[str, float],
    kc_last_practiced: dict[str, str],
    mastery_threshold: float,
    interval_days: float,
    alpha: float,
    beta: float,
    expected_mode: ExpectedMode,
    zpd_min: float,
    zpd_max: float,
) -> Question | None:
    candidates = filter_zpd(questions, mastery, expected_mode, zpd_min, zpd_max)
    if not candidates:
        candidates = list(questions)
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda q: spaced_score(q, mastery, kc_last_practiced, mastery_threshold, interval_days, alpha, beta),
    )


def pick_question_set(
    questions: list[Question],
    mastery: dict[str, float],
    count: int,
    expected_mode: ExpectedMode,
    zpd_min: float,
    zpd_max: float,
    difficulty_ratio: dict[str, float],
) -> list[Question]:
    if count <= 0:
        return []

    candidates = filter_zpd(questions, mastery, expected_mode, zpd_min, zpd_max)
    if not candidates:
        candidates = list(questions)

    buckets = {"easy": [], "medium": [], "hard": []}
    for q in candidates:
        exp = expected_correct(q.knowledge_points, mastery, expected_mode)
        if exp is None:
            continue
        if exp >= 0.8:
            buckets["easy"].append(q)
        elif exp >= 0.6:
            buckets["medium"].append(q)
        else:
            buckets["hard"].append(q)

    target_easy = max(int(round(difficulty_ratio.get("easy", 0.2) * count)), 0)
    target_medium = max(int(round(difficulty_ratio.get("medium", 0.6) * count)), 0)
    target_hard = max(count - target_easy - target_medium, 0)
    targets = {"easy": target_easy, "medium": target_medium, "hard": target_hard}

    selected: list[Question] = []
    covered: set[str] = set()

    def pick_from(bucket_name: str, remaining: int):
        nonlocal selected, covered
        bucket = buckets.get(bucket_name, [])
        if not bucket:
            return
        bucket = bucket.copy()
        while bucket and remaining > 0:
            best = max(
                bucket,
                key=lambda q: (len(set(q.knowledge_points) - covered), weakness_score(q.knowledge_points, mastery, "sum")),
            )
            selected.append(best)
            covered.update(best.knowledge_points)
            bucket.remove(best)
            remaining -= 1

    pick_from("medium", targets["medium"])
    pick_from("hard", targets["hard"])
    pick_from("easy", targets["easy"])

    if len(selected) < count:
        leftovers = [q for q in candidates if q not in selected]
        leftovers.sort(
            key=lambda q: (len(set(q.knowledge_points) - covered), weakness_score(q.knowledge_points, mastery, "sum")),
            reverse=True,
        )
        selected.extend(leftovers[: count - len(selected)])

    return selected[:count]
