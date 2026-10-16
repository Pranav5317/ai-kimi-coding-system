#!/usr/bin/env python3
import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

try:
    from backend.database import engine, SessionLocal
    from backend.models.user import User
    from backend.auth.auth import get_password_hash
    
    # Create tables if they don't exist
    from backend.database import Base
    Base.metadata.create_all(bind=engine)
    
    # Create a session
    db = SessionLocal()
    
    # Check if test user exists
    test_user = db.query(User).filter(User.username == "testuser").first()
    
    if not test_user:
        # Create test user
        hashed_password = get_password_hash("testpass123")
        new_user = User(
            username="testuser",
            email="test@example.com",
            hashed_password=hashed_password
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        print(f"✓ Test user created successfully!")
        print(f"  Username: {new_user.username}")
        print(f"  Email: {new_user.email}")
        print(f"  ID: {new_user.id}")
    else:
        print("✓ Test user already exists")
        print(f"  Username: {test_user.username}")
        print(f"  Email: {test_user.email}")
    
    db.close()
    
except Exception as e:
    print(f"✗ Error initializing test user: {e}")
    import traceback
    traceback.print_exc()