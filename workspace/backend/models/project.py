from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ProjectBase(BaseModel):
    title: str
    description: str
    technologies: str
    github_url: Optional[str] = None
    demo_url: Optional[str] = None

class ProjectCreate(ProjectBase):
    pass

class ProjectUpdate(ProjectBase):
    title: Optional[str] = None
    description: Optional[str] = None
    technologies: Optional[str] = None
    github_url: Optional[str] = None
    demo_url: Optional[str] = None

class Project(ProjectBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True