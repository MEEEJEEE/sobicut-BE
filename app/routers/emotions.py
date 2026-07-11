from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import EmotionTag, User
from app.schemas.emotion import EmotionOut

router = APIRouter(prefix="/emotions", tags=["Emotions"])


@router.get("", response_model=list[EmotionOut])
def list_emotions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(EmotionTag).order_by(EmotionTag.id).all()
