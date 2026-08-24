from pydantic import BaseModel, ConfigDict, field_validator


class EmotionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: str


class TagEmotionsRequest(BaseModel):
    emotion_tag_ids: list[int]

    @field_validator("emotion_tag_ids")
    @classmethod
    def validate_emotion_tag_ids(cls, v: list[int]) -> list[int]:
        if not (1 <= len(v) <= 4):
            raise ValueError("감정 태그는 최소 1개, 최대 4개까지 선택 가능합니다.")
        if len(v) != len(set(v)):
            raise ValueError("중복된 태그는 선택할 수 없습니다.")
        return v
