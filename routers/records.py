# routers/records.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import models, schemas, ai_service
from database import get_db

# 라우터 생성 (이름표 달기)
router = APIRouter(
    prefix="/api/records", # 이 파일의 모든 API는 주소 앞에 이게 붙습니다.
    tags=["Records"]       # 문서(Swagger)에서 보기 좋게 묶어주는 역할
)

@router.post("/submit")
async def submit_exercise_record(record: schemas.RecordCreate, db: Session = Depends(get_db)):
    # 1. DB 저장
    db_record = models.ExerciseRecord(**record.model_dump())
    db.add(db_record)
    db.commit()
    db.refresh(db_record)

    # 2. AI 분석
    ai_result = ai_service.analyze_rehab_data(record.model_dump())

    # 3. 결과 저장
    db_ai = models.AIAnalysis(
        record_id=db_record.id,
        patient_feedback=ai_result["patient_feedback"],
        therapist_summary=ai_result["therapist_summary"],
        risk_level=ai_result["risk_level"]
    )
    db.add(db_ai)
    db.commit()

    return {"status": "success", "ai_feedback": ai_result}