#!/usr/bin/env python
"""
Run FastAPI app with proper Python path setup.
This ensures that the app modules can be imported correctly.
"""
import os
import sys

# Add the project root directory to the Python path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# Import after setting up the path
from app.main import run_api

if __name__ == "__main__":
    run_api()
