#!/usr/bin/env python3
import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

try:
    from backend.auth.auth import verify_password, get_password_hash
    print("✓ Authentication module imported successfully")
    
    # Test password hashing
    test_password = "test123"
    hashed = get_password_hash(test_password)
    print(f"✓ Password hashing works: {test_password} -> {hashed[:20]}...")
    
    # Test password verification
    is_valid = verify_password(test_password, hashed)
    print(f"✓ Password verification works: {is_valid}")
    
    print("Authentication system is working!")
    
except Exception as e:
    print(f"✗ Error in authentication test: {e}")
    import traceback
    traceback.print_exc()