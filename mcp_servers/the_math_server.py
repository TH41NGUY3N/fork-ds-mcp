from mcp.server.fastmcp import FastMCP

# Define a host and port
mcp: FastMCP = FastMCP(
    "MathServer", 
    host="127.0.0.1", 
    port=54321
)

@mcp.tool()
def add_numbers(a: int, b: int) -> int:
    """Adds two numbers together."""
    return a + b

if __name__ == "__main__":
    # Force SSE transport to bypass Windows stdio pipe limits
    print("🚀 Starting Math Server on http://127.0.0.1:54321...")
    mcp.run(transport="sse")