"""
Import helper for the demo notebook
This module handles the relative import issues by running from the correct directory
"""

import sys
import os
from pathlib import Path

# Add the parent directory to the path so we can import src as a package
notebook_dir = Path(__file__).parent
project_root = notebook_dir.parent
src_path = project_root / "src"

# Add project root to Python path
sys.path.insert(0, str(project_root))

# Change to project root directory to make relative imports work
original_cwd = os.getcwd()
os.chdir(project_root)

try:
    # Now we can import the modules properly
    from src.graph import run_market_research, create_workflow
    from src.state import WorkflowState
    from src.observability import (
        setup_langsmith, 
        create_tracer, 
        metrics_collector,
        export_trace_to_json,
        create_sample_trace,
        generate_metrics_summary
    )
    from src.fallbacks import create_fallback_response
    
    # Change back to original directory
    os.chdir(original_cwd)
    
    print("✅ All workflow modules imported successfully!")
    
except Exception as e:
    # Change back to original directory even if import fails
    os.chdir(original_cwd)
    print(f"❌ Import failed: {e}")
    raise
