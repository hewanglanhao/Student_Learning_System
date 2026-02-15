from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from bson import ObjectId

from .config import settings
from .db import get_client, get_db
from .dkt_infer import DKTInference
from .recommender import (
    Question,
    expected_correct,
    normalize_question,
    pick_question_set,
    pick_spaced_question,
    pick_weakest_question,
    weakness_score,
)
from .schemas import (
    AnswerRequest,
    AnswerResponse,
    BatchAnswerRequest,
    BatchAnswerResponse,
    BatchAnswerResult,
    QuestionResponse,
    QuestionSetRequest,
    QuestionSetResponse,
    SingleQuestionRequest,
    SpacedQuestionRequest,
)


app = FastAPI(title="DKT Backend", version="0.1.0")


@app.on_event("startup")
async def on_startup() -> None:
    app.state.dkt = DKTInference(
        model_path=settings.resolved_model_path(),
        knowledge_points_path=settings.resolved_knowledge_points_path(),
    )


@app.on_event("shutdown")
async def on_shutdown() -> None:
    client = get_client()
    client.close()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_mastery(knowledge_points: list[str]) -> dict[str, float]:
    return {name: 0.0 for name in knowledge_points}


async def _get_or_create_profile(db, user_id: str, knowledge_points: list[str]) -> dict:
    profile = await db[settings.user_collection].find_one({"user_id": user_id})
    if profile:
        if "knowledge_mastery" not in profile:
            profile["knowledge_mastery"] = _default_mastery(knowledge_points)
        return profile

    profile = {
        "user_id": user_id,
        "knowledge_mastery": _default_mastery(knowledge_points),
        "interaction_history": [],
        "kc_last_practiced": {},
        "kc_review_count": {},
        "profile_update_time": _now_iso(),
    }
    await db[settings.user_collection].insert_one(profile)
    return profile


def _get_answered_ids(profile: dict) -> set[str]:
    history = profile.get("interaction_history") or []
    answered = set()
    for item in history:
        qid = item.get("question_id")
        if qid:
            answered.add(str(qid))
    return answered


def _weak_kcs(mastery: dict[str, float], top_k: int) -> list[str]:
    return [k for k, _ in sorted(mastery.items(), key=lambda kv: kv[1])[:top_k]]


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


def _review_kcs(
    mastery: dict[str, float],
    kc_last_practiced: dict[str, str],
    mastery_threshold: float,
    top_k: int,
) -> list[str]:
    candidates = []
    for kc, prob in mastery.items():
        if prob < mastery_threshold:
            continue
        days = _days_since(kc_last_practiced.get(kc))
        if days <= 0:
            continue
        candidates.append((kc, days))
    candidates.sort(key=lambda x: x[1], reverse=True)
    return [kc for kc, _ in candidates[:top_k]]


async def _fetch_candidates(db, knowledge_points: list[str], max_candidates: int) -> list[Question]:
    query: dict[str, Any]
    if knowledge_points:
        query = {
            "$or": [
                {"knowledge_points": {"$in": knowledge_points}},
                {"知识点": {"$in": knowledge_points}},
            ]
        }
    else:
        query = {}

    docs = await db[settings.practice_collection].find(query).limit(max_candidates).to_list(length=max_candidates)
    questions: list[Question] = []
    for doc in docs:
        q = normalize_question(doc)
        if not q:
            continue
        if q.question_type and q.question_type != "选择题":
            continue
        questions.append(q)
    return questions


def _filter_answered(questions: list[Question], answered_ids: set[str]) -> list[Question]:
    if not answered_ids:
        return questions
    return [q for q in questions if q.question_id not in answered_ids]


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/users/{user_id}")
async def get_user_profile(user_id: str, db=Depends(get_db)):
    profile = await db[settings.user_collection].find_one({"user_id": user_id})
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")
    if "_id" in profile and isinstance(profile["_id"], ObjectId):
        profile["_id"] = str(profile["_id"])
    return profile


@app.get("/users/{user_id}/interaction_history")
async def get_user_interaction_history(user_id: str, db=Depends(get_db)):
    profile = await db[settings.user_collection].find_one({"user_id": user_id})
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "user_id": user_id,
        "interaction_history": profile.get("interaction_history", []),
    }


@app.get("/debug/dbinfo")
async def debug_dbinfo():
    return {
        "mongodb_uri": settings.mongodb_uri,
        "db_name": settings.db_name,
        "practice_collection": settings.practice_collection,
        "user_collection": settings.user_collection,
    }


@app.post("/questions/single/weakest", response_model=QuestionResponse)
async def single_weakest(
    payload: SingleQuestionRequest,
    db=Depends(get_db),
):
    dkt: DKTInference = app.state.dkt
    profile = await _get_or_create_profile(db, payload.user_id, dkt.knowledge_points)
    mastery = profile.get("knowledge_mastery", {})
    answered_ids = _get_answered_ids(profile)

    weak_kcs = _weak_kcs(mastery, payload.top_k_weak)
    candidates = await _fetch_candidates(db, weak_kcs, payload.max_candidates)
    candidates = _filter_answered(candidates, answered_ids)

    zpd_candidates = [
        q for q in candidates
        if expected_correct(q.knowledge_points, mastery, payload.expected_mode) is not None
        and payload.zpd_min <= expected_correct(q.knowledge_points, mastery, payload.expected_mode) <= payload.zpd_max
    ]
    zpd_applied = bool(zpd_candidates)
    pool = zpd_candidates if zpd_applied else candidates

    question = pick_weakest_question(
        pool,
        mastery,
        payload.score_mode,
        payload.expected_mode,
        payload.zpd_min,
        payload.zpd_max,
    )
    if not question:
        raise HTTPException(status_code=404, detail="No available question found")

    return QuestionResponse(question=question.to_public_dict(), strategy="weakest", zpd_applied=zpd_applied)


@app.post("/questions/single/spaced", response_model=QuestionResponse)
async def single_spaced(
    payload: SpacedQuestionRequest,
    db=Depends(get_db),
):
    dkt: DKTInference = app.state.dkt
    profile = await _get_or_create_profile(db, payload.user_id, dkt.knowledge_points)
    mastery = profile.get("knowledge_mastery", {})
    answered_ids = _get_answered_ids(profile)
    kc_last_practiced = profile.get("kc_last_practiced", {}) or {}

    weak_kcs = _weak_kcs(mastery, payload.top_k_weak)
    review_kcs = _review_kcs(mastery, kc_last_practiced, payload.mastery_threshold, payload.top_k_review)
    target_kcs = list({*weak_kcs, *review_kcs})

    candidates = await _fetch_candidates(db, target_kcs, payload.max_candidates)
    candidates = _filter_answered(candidates, answered_ids)

    zpd_candidates = [
        q for q in candidates
        if expected_correct(q.knowledge_points, mastery, payload.expected_mode) is not None
        and payload.zpd_min <= expected_correct(q.knowledge_points, mastery, payload.expected_mode) <= payload.zpd_max
    ]
    zpd_applied = bool(zpd_candidates)
    pool = zpd_candidates if zpd_applied else candidates

    question = pick_spaced_question(
        pool,
        mastery,
        kc_last_practiced,
        payload.mastery_threshold,
        payload.interval_days,
        payload.alpha,
        payload.beta,
        payload.expected_mode,
        payload.zpd_min,
        payload.zpd_max,
    )
    if not question:
        raise HTTPException(status_code=404, detail="No available question found")

    return QuestionResponse(question=question.to_public_dict(), strategy="spaced", zpd_applied=zpd_applied)


@app.post("/questions/set", response_model=QuestionSetResponse)
async def question_set(
    payload: QuestionSetRequest,
    db=Depends(get_db),
):
    dkt: DKTInference = app.state.dkt
    profile = await _get_or_create_profile(db, payload.user_id, dkt.knowledge_points)
    mastery = profile.get("knowledge_mastery", {})
    answered_ids = _get_answered_ids(profile)

    weak_kcs = _weak_kcs(mastery, min(10, len(mastery)))
    candidates = await _fetch_candidates(db, weak_kcs, payload.max_candidates)
    candidates = _filter_answered(candidates, answered_ids)

    zpd_candidates = [
        q for q in candidates
        if expected_correct(q.knowledge_points, mastery, payload.expected_mode) is not None
        and payload.zpd_min <= expected_correct(q.knowledge_points, mastery, payload.expected_mode) <= payload.zpd_max
    ]
    zpd_applied = bool(zpd_candidates)
    pool = zpd_candidates if zpd_applied else candidates

    selected = pick_question_set(
        pool,
        mastery,
        payload.count,
        payload.expected_mode,
        payload.zpd_min,
        payload.zpd_max,
        payload.difficulty_ratio,
    )
    if not selected:
        raise HTTPException(status_code=404, detail="No available question found")

    return QuestionSetResponse(
        questions=[q.to_public_dict() for q in selected],
        strategy="set",
        zpd_applied=zpd_applied,
    )


@app.post("/questions/answer", response_model=AnswerResponse)
async def submit_answer(
    payload: AnswerRequest,
    db=Depends(get_db),
):
    dkt: DKTInference = app.state.dkt
    profile = await _get_or_create_profile(db, payload.user_id, dkt.knowledge_points)

    question_doc = await db[settings.practice_collection].find_one(
        {"$or": [{"question_id": payload.question_id}, {"题目ID": payload.question_id}]}
    )
    if not question_doc:
        raise HTTPException(status_code=404, detail="Question not found")
    question = normalize_question(question_doc)
    if not question:
        raise HTTPException(status_code=400, detail="Question data is invalid")

    selected = payload.selected_option.strip().upper()
    correct = question.answer.strip().upper()
    if selected not in {"A", "B", "C", "D"}:
        raise HTTPException(status_code=400, detail="selected_option must be one of A/B/C/D")

    is_correct = selected == correct

    history = profile.get("interaction_history") or []
    interactions: list[tuple[list[int], bool]] = []
    for item in history:
        kp_names = item.get("knowledge_points") or []
        indices = [dkt.kc_to_idx[k] for k in kp_names if k in dkt.kc_to_idx]
        if indices:
            interactions.append((indices, bool(item.get("is_correct"))))

    current_indices = [dkt.kc_to_idx[k] for k in question.knowledge_points if k in dkt.kc_to_idx]
    if current_indices:
        interactions.append((current_indices, is_correct))

    mastery_probs = dkt.predict_mastery(interactions) if current_indices else []
    mastery_map = profile.get("knowledge_mastery") or _default_mastery(dkt.knowledge_points)
    if mastery_probs:
        for name, idx in dkt.kc_to_idx.items():
            mastery_map[name] = float(mastery_probs[idx])

    now = _now_iso()
    answer_explanation = payload.answer_explanation or question.answer_explanation
    history_item = {
        "question_id": question.question_id,
        "knowledge_points": question.knowledge_points,
        "is_correct": is_correct,
        "selected_option": selected,
        "correct_option": correct,
        "答案解析": answer_explanation,
        "answered_at": now,
    }

    kc_last_practiced = profile.get("kc_last_practiced") or {}
    kc_review_count = profile.get("kc_review_count") or {}
    for kc in question.knowledge_points:
        kc_last_practiced[kc] = now
        kc_review_count[kc] = int(kc_review_count.get(kc, 0)) + 1

    await db[settings.user_collection].update_one(
        {"user_id": payload.user_id},
        {
            "$set": {
                "knowledge_mastery": mastery_map,
                "profile_update_time": now,
                "kc_last_practiced": kc_last_practiced,
                "kc_review_count": kc_review_count,
            },
            "$push": {"interaction_history": history_item},
        },
    )

    updated_kc_mastery = {kc: mastery_map.get(kc, 0.0) for kc in question.knowledge_points}

    return AnswerResponse(
        is_correct=is_correct,
        correct_option=correct,
        selected_option=selected,
        updated_kc_mastery=updated_kc_mastery,
        profile_update_time=now,
    )


@app.post("/questions/set/answer", response_model=BatchAnswerResponse)
async def submit_answer_set(
    payload: BatchAnswerRequest,
    db=Depends(get_db),
):
    if not payload.answers:
        raise HTTPException(status_code=400, detail="answers is empty")

    dkt: DKTInference = app.state.dkt
    profile = await _get_or_create_profile(db, payload.user_id, dkt.knowledge_points)

    question_ids = [item.question_id for item in payload.answers]
    question_docs = await db[settings.practice_collection].find(
        {"$or": [{"question_id": {"$in": question_ids}}, {"题目ID": {"$in": question_ids}}]}
    ).to_list(length=len(question_ids))

    question_map: dict[str, Question] = {}
    for doc in question_docs:
        q = normalize_question(doc)
        if not q:
            continue
        if q.question_type and q.question_type != "选择题":
            continue
        question_map[q.question_id] = q

    missing = [qid for qid in question_ids if qid not in question_map]
    if missing:
        raise HTTPException(status_code=404, detail=f"Questions not found or invalid: {missing}")

    history = profile.get("interaction_history") or []
    interactions: list[tuple[list[int], bool]] = []
    for item in history:
        kp_names = item.get("knowledge_points") or []
        indices = [dkt.kc_to_idx[k] for k in kp_names if k in dkt.kc_to_idx]
        if indices:
            interactions.append((indices, bool(item.get("is_correct"))))

    results: list[BatchAnswerResult] = []
    history_items = []
    kc_last_practiced = profile.get("kc_last_practiced") or {}
    kc_review_count = profile.get("kc_review_count") or {}
    now = _now_iso()

    for item in payload.answers:
        question = question_map[item.question_id]
        selected = item.selected_option.strip().upper()
        if selected not in {"A", "B", "C", "D"}:
            raise HTTPException(status_code=400, detail=f"selected_option must be A/B/C/D for {item.question_id}")
        correct = question.answer.strip().upper()
        answer_explanation = item.answer_explanation or question.answer_explanation
        is_correct = selected == correct

        current_indices = [dkt.kc_to_idx[k] for k in question.knowledge_points if k in dkt.kc_to_idx]
        if current_indices:
            interactions.append((current_indices, is_correct))

        for kc in question.knowledge_points:
            kc_last_practiced[kc] = now
            kc_review_count[kc] = int(kc_review_count.get(kc, 0)) + 1

        history_items.append(
            {
                "question_id": question.question_id,
                "knowledge_points": question.knowledge_points,
                "is_correct": is_correct,
                "selected_option": selected,
                "correct_option": correct,
                "答案解析": answer_explanation,
                "answered_at": now,
            }
        )

        results.append(
            BatchAnswerResult(
                question_id=question.question_id,
                is_correct=is_correct,
                correct_option=correct,
                selected_option=selected,
            )
        )

    mastery_probs = dkt.predict_mastery(interactions)
    mastery_map = profile.get("knowledge_mastery") or _default_mastery(dkt.knowledge_points)
    for name, idx in dkt.kc_to_idx.items():
        mastery_map[name] = float(mastery_probs[idx])

    await db[settings.user_collection].update_one(
        {"user_id": payload.user_id},
        {
            "$set": {
                "knowledge_mastery": mastery_map,
                "profile_update_time": now,
                "kc_last_practiced": kc_last_practiced,
                "kc_review_count": kc_review_count,
            },
            "$push": {"interaction_history": {"$each": history_items}},
        },
    )

    return BatchAnswerResponse(
        results=results,
        updated_kc_mastery=mastery_map,
        profile_update_time=now,
    )
