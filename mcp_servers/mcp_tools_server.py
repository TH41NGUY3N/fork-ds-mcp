import os
from mcp.server.fastmcp import FastMCP
from duckduckgo_search import DDGS


mcp: FastMCP = FastMCP("SuperServer")

@mcp.tool()
def search_web(query: str) -> str:
    """Searches the web for current information using DuckDuckGo."""
    print(f"DEBUG: Searching web for {query}") # FastMCP redirects prints safely
    with DDGS() as ddgs:
        results = [r['body'] for r in ddgs.text(query, max_results=3)]
        return "\n---\n".join(results) if results else "No results found."

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

    
if __name__ == "__main__":
    mcp.run()