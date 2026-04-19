"""
Wrapper script to run deepseek_mcp_server from any directory.
This script ensures the working directory is set correctly.
"""
import os
import sys
from pathlib import Path

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent.resolve()

# Change working directory to script location
os.chdir(SCRIPT_DIR)

# Add script directory to Python path
sys.path.insert(0, str(SCRIPT_DIR))

# Now import and run the actual server
import deepseek_mcp_server

if __name__ == "__main__":
    deepseek_mcp_server.mcp.run()
