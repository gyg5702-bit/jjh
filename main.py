from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import os
from sqlalchemy import create_engine, Column, String, JSON, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

# --- DB 설정 ---
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./local.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class RevitData(Base):
    __tablename__ = "revit_data"
    id = Column(String, primary_key=True)
    project_name = Column(String)
    payload = Column(JSON)
    summary = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(engine)

# --- FastAPI ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 모델 ---
class RevitPayload(BaseModel):
    id: str
    project_name: str
    payload: dict
    summary: str | None = None

class ChatRequest(BaseModel):
    question: str
    project_id: str | None = None

# --- 엔드포인트 ---

@app.post("/api/revit/data")
def save_revit_data(data: RevitPayload):
    db = SessionLocal()
    try:
        item = RevitData(
            id=data.id,
            project_name=data.project_name,
            payload=data.payload,
            summary=data.summary,
        )
        db.merge(item)
        db.commit()
        return {"status": "ok", "id": data.id}
    finally:
        db.close()

@app.get("/api/revit/data")
def list_revit_data():
    db = SessionLocal()
    try:
        items = db.query(RevitData).all()
        return [
            {"id": i.id, "project_name": i.project_name, 
             "summary": i.summary, "created_at": i.created_at}
            for i in items
        ]
    finally:
        db.close()

@app.get("/api/revit/data/{item_id}")
def get_revit_data(item_id: str):
    db = SessionLocal()
    try:
        item = db.query(RevitData).filter(RevitData.id == item_id).first()
        if not item:
            raise HTTPException(404, "Not found")
        return {
            "id": item.id, "project_name": item.project_name,
            "payload": item.payload, "summary": item.summary,
        }
    finally:
        db.close()

@app.post("/api/chat")
def chat(req: ChatRequest):
    """챗봇 - API 키 있을 때만 작동"""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {"answer": "ANTHROPIC_API_KEY가 설정되지 않았습니다. Render Environment에서 추가해주세요."}
    
    import anthropic
    claude = anthropic.Anthropic(api_key=api_key)
    
    db = SessionLocal()
    try:
        context = ""
        if req.project_id:
            item = db.query(RevitData).filter(RevitData.id == req.project_id).first()
            if item:
                context = f"Revit 프로젝트 데이터:\n{item.payload}\n\n"
        
        message = claude.messages.create(
            model="claude-opus-4-5",
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": f"{context}질문: {req.question}"
            }]
        )
        return {"answer": message.content[0].text}
    finally:
        db.close()

@app.get("/")
def root():
    return {"status": "running"}
