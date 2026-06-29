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
    

# Add this tool to your mcp_http_server.py
@mcp.tool()
def fetch_smart_meter_data(customer_id: str, month: str) -> str:
    """
    Fetches the daily electricity consumption (in kWh) for a specific customer.
    Use this to help customers understand their energy bill.
    """
    # In a real Enercity system, this would query an SQL database or SAP system.
    # For your portfolio, we use mock data.
    mock_database = {
        "CUST-8472": {
            "January": {"total_kwh": 450, "peak_usage_appliance": "Heat Pump", "peak_time": "18:00 - 21:00"},
            "February": {"total_kwh": 380, "peak_usage_appliance": "Electric Vehicle Charger", "peak_time": "23:00 - 05:00"}
        }
    }
    
    data = mock_database.get(customer_id, {}).get(month)
    if not data:
        return f"Error: No smart meter data found for customer {customer_id} in {month}."
    
    return (
        f"Data for {customer_id} in {month}:\n"
        f"- Total Consumption: {data['total_kwh']} kWh\n"
        f"- Main Driver: {data['peak_usage_appliance']}\n"
        f"- Peak Hours: {data['peak_time']}"
    )

# Add this tool to your mcp_http_server.py
@mcp.tool()
def predict_solar_yield(city: str, panel_capacity_kwp: float) -> str:
    """
    Calculates the expected solar energy generation (in kWh) for the next day.
    Requires the city name and the size of the customer's solar installation in kWp.
    """
    # Mocking a weather API call (e.g., OpenWeatherMap)
    weather_conditions = {
        "Hannover": {"sun_hours": 3.5, "condition": "Cloudy"},
        "Munich": {"sun_hours": 8.0, "condition": "Sunny"}
    }
    
    forecast = weather_conditions.get(city, {"sun_hours": 5.0, "condition": "Partly Cloudy"})
    
    # Simple physics estimation: Capacity * Sun Hours * 0.75 (Efficiency Loss)
    estimated_kwh = panel_capacity_kwp * forecast["sun_hours"] * 0.75
    
    return (
        f"Tomorrow's forecast for {city}: {forecast['condition']} ({forecast['sun_hours']} sun hours).\n"
        f"A {panel_capacity_kwp} kWp system is expected to generate approximately {estimated_kwh:.2f} kWh tomorrow."
    )


if __name__ == "__main__":
    # Just specify the transport here
    mcp.run(transport="sse")