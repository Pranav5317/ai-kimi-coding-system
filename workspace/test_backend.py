#!/usr/bin/env python3
import sys
import os

# Add the backend directory to Python path
sys.path.insert(0, 'backend')

try:
    from fastapi import FastAPI
    print("✓ FastAPI imported successfully")
    
    # Try importing our main module
    import backend.main
    print("✓ Backend main module imported successfully")
    
    print("Backend appears to be working correctly!")
    
except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"✗ Other error: {e}")
    sys.exit(1)