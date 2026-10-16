from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from backend.database import get_db
from backend.models.task import Task
from backend.auth.auth import get_current_active_user

router = APIRouter(
    prefix="/tasks",
    tags=["Tasks"],
)

@router.get("/", response_model=List[Task])
async def read_tasks(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    tasks = db.query(Task).offset(skip).limit(limit).all()
    return tasks

@router.get("/{task_id}", response_model=Task)
async def read_task(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.post("/", response_model=Task)
async def create_task(task: Task, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    db.add(task)
    db.commit()
    db.refresh(task)
    return task

@router.put("/{task_id}", response_model=Task)
async def update_task(task_id: int, task_update: Task, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    for key, value in task_update.dict(exclude_unset=True).items():
        setattr(task, key, value)
    
    db.commit()
    db.refresh(task)
    return task

@router.delete("/{task_id}")
async def delete_task(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    db.delete(task)
    db.commit()
    return {"message": "Task deleted successfully"}