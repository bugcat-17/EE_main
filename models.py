from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from datetime import datetime
from sqlalchemy.orm import relationship
from database import Base

class ChatLog(Base):
    __tablename__ = "chat_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    nickname = Column(String(50))
    message = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

class Patient(Base):
    __tablename__ = "patients"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    rrn = Column(String) # [RRN Omitted] 형태로 저장 권장
    # 환자 1명이 여러 운동 기록을 가짐
    records = relationship("ExerciseRecord", back_populates="patient")

class ExerciseRecord(Base):
    __tablename__ = "exercise_records"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"))
    exercise_name = Column(String)
    target_count = Column(Integer)
    actual_count = Column(Integer)
    pain_score = Column(Integer)
    difficulty = Column(String)
    memo = Column(Text)
    # 관계 설정정
    patient = relationship("Patient", back_populates="records")
    ai_analysis = relationship("AIAnalysis", back_populates="record", uselist=False) # 1:1 관계

class AIAnalysis(Base):
    __tablename__ = "ai_analyses"
    id = Column(Integer, primary_key=True, index=True)
    record_id = Column(Integer, ForeignKey("exercise_records.id"))
    patient_feedback = Column(Text)
    therapist_summary = Column(Text)
    risk_level = Column(String)

    # 1:1 관계를 완성하는 중요한 줄
    record = relationship("ExerciseRecord", back_populates="ai_analysis")