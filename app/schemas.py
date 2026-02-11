from __future__ import annotations

from typing import Dict, Literal, Optional

from pydantic import BaseModel, Field


class SingleQuestionRequest(BaseModel):
    user_id: str
    zpd_min: float = Field(default=0.6, ge=0.0, le=1.0)
    zpd_max: float = Field(default=0.8, ge=0.0, le=1.0)
    expected_mode: Literal["min", "mean", "product"] = "min"
    score_mode: Literal["sum", "max", "min"] = "sum"
    top_k_weak: int = Field(default=5, ge=1, le=50)
    max_candidates: int = Field(default=2000, ge=10, le=10000)


class SpacedQuestionRequest(BaseModel):
    user_id: str
    zpd_min: float = Field(default=0.6, ge=0.0, le=1.0)
    zpd_max: float = Field(default=0.8, ge=0.0, le=1.0)
    expected_mode: Literal["min", "mean", "product"] = "min"
    interval_days: int = Field(default=7, ge=1, le=365)
    alpha: float = Field(default=0.6, ge=0.0, le=1.0)
    beta: float = Field(default=0.4, ge=0.0, le=1.0)
    mastery_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    top_k_review: int = Field(default=5, ge=1, le=50)
    top_k_weak: int = Field(default=5, ge=1, le=50)
    max_candidates: int = Field(default=2000, ge=10, le=10000)


class QuestionSetRequest(BaseModel):
    user_id: str
    count: int = Field(default=10, ge=1, le=100)
    zpd_min: float = Field(default=0.5, ge=0.0, le=1.0)
    zpd_max: float = Field(default=0.9, ge=0.0, le=1.0)
    expected_mode: Literal["min", "mean", "product"] = "mean"
    max_candidates: int = Field(default=3000, ge=10, le=20000)
    difficulty_ratio: Dict[str, float] = Field(default_factory=lambda: {"easy": 0.2, "medium": 0.6, "hard": 0.2})


class AnswerRequest(BaseModel):
    user_id: str
    question_id: str
    selected_option: str


class QuestionResponse(BaseModel):
    question: Dict
    strategy: str
    zpd_applied: bool


class QuestionSetResponse(BaseModel):
    questions: list[Dict]
    strategy: str
    zpd_applied: bool


class AnswerResponse(BaseModel):
    is_correct: bool
    correct_option: str
    selected_option: str
    updated_kc_mastery: Dict[str, float]
    profile_update_time: str

