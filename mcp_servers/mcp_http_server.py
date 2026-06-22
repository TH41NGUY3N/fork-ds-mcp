import sys
import subprocess
import os
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

# Initialize with security settings that allow local development
mcp: FastMCP = FastMCP(
    "SuperServer", 
    host="127.0.0.1", 
    port=8000,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False
    )
)


@mcp.tool()
def read_local_file(file_path: str) -> str:
    """Reads the content of a local text file. Provide the full path."""
    if not os.path.exists(file_path):
        return f"Error: File at {file_path} not found."
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

@mcp.tool()
def execute_python_code(
    code: str | None = None, 
    file_path: str | None = None, 
    script_name: str | None = None
) -> str:
    """
    Executes Python code or a script. 
    Accepts 'code' (string), 'file_path' (path), or 'script_name' (filename).
    """
    scripts_dir = os.path.abspath("scripts")
    
    # 1. Resolve which input the model actually gave us
    # This catches cases where the LLM hallucinates the parameter name
    input_content = code or file_path or script_name
    
    if not input_content:
        return "Error: No code or filename provided. Please provide the 'code' parameter."

    # Setup environment
    env = os.environ.copy()
    env["PYTHONPATH"] = scripts_dir
    
    # 2. Check if the resolved input is a file on disk
    potential_file = os.path.join(scripts_dir, os.path.basename(input_content.strip()))
    
    try:
        if input_content.strip().endswith(".py") and os.path.exists(potential_file):
            # CASE A: Run existing file
            command = [sys.executable, potential_file]
        else:
            # CASE B: Execute raw string
            # If the model passed a file path but it didn't exist, we treat the path 
            # as the code string (which will likely fail, but it's the safest fallback)
            command = [sys.executable, "-c", input_content]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=scripts_dir,
            env=env 
        )
        
        if result.stderr:
            return f"Execution Error:\n{result.stderr}"
        return f"Output:\n{result.stdout}" if result.stdout else "Success (No output)."
        
    except Exception as e:
        return f"Error: {str(e)}"


if __name__ == "__main__":
    # Just specify the transport here
    mcp.run(transport="sse")