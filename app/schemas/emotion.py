from pydantic import BaseModel, ConfigDict, Field


class EmotionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: str


class DecisionClassifyRequest(BaseModel):
    description: str = Field(min_length=1, max_length=300)


class DecisionCandidateOut(BaseModel):
    emotion_tag_id: int
    name: str
    bpti_type: str  # FIRE | FOG | LAZY | SAGE | VISION
    score: float


class DecisionClassifyResponse(BaseModel):
    confidence_level: str  # auto | top3 | manual
    top: DecisionCandidateOut
    candidates: list[DecisionCandidateOut]


class TagEmotionsRequest(BaseModel):
    description: str = Field(min_length=1, max_length=300)
    emotion_tag_id: int | None = None  # 후보 중 사용자가 직접 골랐을 때만 지정. 없으면 서버가 자동 분류.
