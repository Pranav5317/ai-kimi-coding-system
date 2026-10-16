from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from backend.database import get_db
from backend.models.project import Project
from backend.auth.auth import get_current_active_user

router = APIRouter(
    prefix="/projects",
    tags=["Projects"],
)

@router.get("/", response_model=List[Project])
async def read_projects(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    projects = db.query(Project).offset(skip).limit(limit).all()
    return projects

@router.get("/{project_id}", response_model=Project)
async def read_project(project_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@router.post("/", response_model=Project)
async def create_project(project: Project, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    db.add(project)
    db.commit()
    db.refresh(project)
    return project

@router.put("/{project_id}", response_model=Project)
async def update_project(project_id: int, project_update: Project, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    for key, value in project_update.dict(exclude_unset=True).items():
        setattr(project, key, value)
    
    db.commit()
    db.refresh(project)
    return project

@router.delete("/{project_id}")
async def delete_project(project_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    db.delete(project)
    db.commit()
    return {"message": "Project deleted successfully"}