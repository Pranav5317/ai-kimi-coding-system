from sqlalchemy import Column, Integer, String, Text, Date, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from backend.database import Base

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    status = Column(String(50), default="pending")
    priority = Column(String(20), default="medium")
    due_date = Column(Date)
    completed = Column(Boolean, default=False)
    
    # Foreign key to project
    project_id = Column(Integer, ForeignKey("projects.id"))
    
    # Relationship with project
    project = relationship("Project", back_populates="tasks")

    def __repr__(self):
        return f"<Task(id={self.id}, title='{self.title}', completed={self.completed})>"