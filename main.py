import os
from dotenv import load_dotenv # 이 줄 추가
import socket
import socketio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles # 대문자 S 주의
from sqlalchemy.orm import Session
from zeroconf import ServiceInfo
from zeroconf.asyncio import AsyncZeroconf
from routers import records # 새로 분리 파일 불러오기기

from database import engine, Base, get_db
import models, schemas, ai_service
from chat.chat_server import register_socket_events # 채팅 로직 가져오기

load_dotenv() # 이 줄 추가

# DB 테이블 생성
Base.metadata.create_all(bind=engine)

# --- [1. mDNS 및 서버 수명 주기 설정] ---
app = FastAPI()

"""
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 1))
        ip = s.getsockname()[0]
    except Exception: 
        ip = '127.0.0.1'
    finally: 
        s.close()
    return ip
"""

# ★ 라우터 연결 (records.py 안에 있는 API들을 앱에 붙임)
app.include_router(records.router)

#3.lifespan 함수 주석 처리
"""
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 서버 시작 시 mDNS 방송
    aio_zc = AsyncZeroconf()
    ip = get_local_ip()
    info = ServiceInfo("_http._tcp.local.", "RehabAI._http._tcp.local.",
                       addresses=[socket.inet_aton(ip)], port=8000, server="rehabai.local.")
    await aio_zc.async_register_service(info)
    print(f"🚀 서버 시작! 접속 주소: http://{ip}:8000")
    yield
    # 서버 종료 시 방송 중단
    await aio_zc.async_unregister_service(info)
    await aio_zc.async_close()
"""

# --- [2. 앱 초기화] ---
# app = FastAPI(lifespan=lifespan)
app = FastAPI() #이렇게만 하기
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
combined_app = socketio.ASGIApp(sio, other_asgi_app=app)

# 채팅 이벤트 등록
register_socket_events(sio)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- [3. API 엔드포인트] ---

@app.post("/api/records/submit")
async def submit_exercise_record(record: schemas.RecordCreate, db: Session = Depends(get_db)):
    # 1. DB 저장
    db_record = models.ExerciseRecord(**record.model_dump())
    db.add(db_record)
    db.commit()
    db.refresh(db_record)

    # 2. AI 분석 (gemini-1.5-flash 또는 설정한 모델)
    ai_result = ai_service.analyze_rehab_data(record.model_dump())

    # 3. AI 분석 결과 저장
    db_ai = models.AIAnalysis(
        record_id=db_record.id,
        patient_feedback=ai_result["patient_feedback"],
        therapist_summary=ai_result["therapist_summary"],
        risk_level=ai_result["risk_level"]
    )
    db.add(db_ai)
    db.commit()

    return {"status": "success", "ai_feedback": ai_result}

from pydantic import BaseModel
import google.generativeai as genai
import os

# AI 테스트 요청을 받을 데이터 형식
class AITestRequest(BaseModel):
    prompt: str

# AI 테스트 전용 엔드포인트
@app.post("/api/ai-test")
async def test_ai_api(req: AITestRequest):
    try:
        # API 키 세팅
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return {"reply": "서버에 API 키가 설정되지 않았습니다."}
        
        genai.configure(api_key=api_key)
        # 모델은 가볍고 빠른 flash 추천
        model = genai.GenerativeModel('gemini-2.5-flash') 
        
        response = model.generate_content(req.prompt)
        return {"reply": response.text}
    except Exception as e:
        return {"reply": f"에러 발생: {str(e)}"}


# 채팅 프리뷰 화면 연결
@app.get("/preview/patient")
async def get_patient_chat():
    return FileResponse("chat/preview_patient.html")

@app.get("/preview/therapist")
async def get_therapist_chat():
    return FileResponse("chat/preview_therapist.html")

# ==========================================
# ★ 새로운 진짜 메인 화면 연결 (UI 통합)
# static 폴더 안에 있는 index.html을 메인 대문(/)으로 띄웁니다.
# ==========================================
app.mount("/", StaticFiles(directory="static", html=True), name="static")

# ------------------------------------------
# 서버 실행 부
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:combined_app", host="0.0.0.0", port=8000, reload=True)

# ★ 프론트엔드 화면 연결 (맨 마지막에 위치)
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:combined_app", host="0.0.0.0", port=8000, reload=True)