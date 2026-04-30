import os
from sqlalchemy import create_url, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Render 환경변수가 있으면 그걸 쓰고, 없으면 로컬 sqlite 사용
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

# 만약 postgres 주소가 'postgres://'로 시작한다면 sqlalchemy 호환을 위해 'postgresql://'로 변경
if SQLALCHEMY_DATABASE_URL and SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

if not SQLALCHEMY_DATABASE_URL:
    SQLALCHEMY_DATABASE_URL = "sqlite:///./rehab_ai.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()