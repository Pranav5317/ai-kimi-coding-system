from sqlalchemy import Column, Integer, String, Text, Date, ForeignKey
from sqlalchemy.orm import relationship
from backend.database import Base

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    start_date = Column(Date)
    end_date = Column(Date)
    status = Column(String(50), default="active")
    
    # Relationship with tasks
    tasks = relationship("Task", back_populates="project")

    def __repr__(self):
        return f"<Project(id={self.id}, title='{self.title}')>"