from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn

# Create the FastAPI app
app = FastAPI(title="Project Management API", version="1.0.0")

# Add CORS middleware to allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory data storage (for demonstration purposes)
projects = [
    {
        "id": 1,
        "name": "Sample Project",
        "description": "A sample project for demonstration",
        "technologies": ["Python", "FastAPI", "React"],
        "github_url": "https://github.com/sample/project",
        "website_url": "https://sample-project.com"
    }
]

tasks = [
    {
        "id": 1,
        "name": "Sample Task",
        "description": "A sample task for demonstration",
        "status": "pending",
        "priority": "medium"
    }
]

# Data models
class ProjectBase(BaseModel):
    name: str
    description: str
    technologies: List[str]
    github_url: Optional[str] = None
    website_url: Optional[str] = None

class Project(ProjectBase):
    id: int

    class Config:
        from_attributes = True

class TaskBase(BaseModel):
    name: str
    description: str
    status: str
    priority: str

class Task(TaskBase):
    id: int

    class Config:
        from_attributes = True

# API Routes for Projects
@app.get("/projects", response_model=List[Project])
async def get_projects():
    return projects

@app.get("/projects/{project_id}", response_model=Project)
async def get_project(project_id: int):
    project = next((p for p in projects if p["id"] == project_id), None)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@app.post("/projects", response_model=Project)
async def create_project(project: ProjectBase):
    new_id = max([p["id"] for p in projects]) + 1 if projects else 1
    new_project = {
        "id": new_id,
        "name": project.name,
        "description": project.description,
        "technologies": project.technologies,
        "github_url": project.github_url,
        "website_url": project.website_url
    }
    projects.append(new_project)
    return new_project

@app.put("/projects/{project_id}", response_model=Project)
async def update_project(project_id: int, project: ProjectBase):
    for i, p in enumerate(projects):
        if p["id"] == project_id:
            projects[i] = {
                "id": project_id,
                "name": project.name,
                "description": project.description,
                "technologies": project.technologies,
                "github_url": project.github_url,
                "website_url": project.website_url
            }
            return projects[i]
    raise HTTPException(status_code=404, detail="Project not found")

@app.delete("/projects/{project_id}")
async def delete_project(project_id: int):
    global projects
    projects = [p for p in projects if p["id"] != project_id]
    return {"message": "Project deleted successfully"}

# API Routes for Tasks
@app.get("/tasks", response_model=List[Task])
async def get_tasks():
    return tasks

@app.get("/tasks/{task_id}", response_model=Task)
async def get_task(task_id: int):
    task = next((t for t in tasks if t["id"] == task_id), None)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.post("/tasks", response_model=Task)
async def create_task(task: TaskBase):
    new_id = max([t["id"] for t in tasks]) + 1 if tasks else 1
    new_task = {
        "id": new_id,
        "name": task.name,
        "description": task.description,
        "status": task.status,
        "priority": task.priority
    }
    tasks.append(new_task)
    return new_task

@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(task_id: int, task: TaskBase):
    for i, t in enumerate(tasks):
        if t["id"] == task_id:
            tasks[i] = {
                "id": task_id,
                "name": task.name,
                "description": task.description,
                "status": task.status,
                "priority": task.priority
            }
            return tasks[i]
    raise HTTPException(status_code=404, detail="Task not found")

@app.delete("/tasks/{task_id}")
async def delete_task(task_id: int):
    global tasks
    tasks = [t for t in tasks if t["id"] != task_id]
    return {"message": "Task deleted successfully"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)