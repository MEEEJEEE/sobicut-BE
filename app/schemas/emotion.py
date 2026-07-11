from pydantic import BaseModel, ConfigDict


class EmotionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: str


class TagEmotionsRequest(BaseModel):
    emotion_tag_ids: list[int]
