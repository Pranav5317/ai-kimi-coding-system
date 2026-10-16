import os
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.database import engine, Base
from backend.routers import projects, tasks, auth

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Portfolio Task Tracker API",
    description="API for managing projects and tasks in a portfolio",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(projects.router)
app.include_router(tasks.router)
app.include_router(auth.router)

@app.get("/")
async def root():
    return {"message": "Portfolio Task Tracker API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}