#!/usr/bin/env python3
import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

try:
    from backend.database import engine, Base
    print("✓ Database setup imported successfully")
    
    # Try to create tables
    Base.metadata.create_all(bind=engine)
    print("✓ Database tables created successfully")
    
    print("Database setup is working!")
    
except Exception as e:
    print(f"✗ Error in database setup: {e}")
    import traceback
    traceback.print_exc()