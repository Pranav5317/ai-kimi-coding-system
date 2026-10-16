from sqlalchemy import Column, Integer, String, Text, DateTime, Enum
from datetime import datetime
from backend.database import Base

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), index=True)
    description = Column(Text)
    technologies = Column(Text)
    github_url = Column(String(500))
    demo_url = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), index=True)
    description = Column(Text)
    status = Column(String(50))  # 'todo', 'in_progress', 'completed'
    priority = Column(String(50))  # 'low', 'medium', 'high'
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)