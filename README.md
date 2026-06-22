# Model Context Protocol (MCP) Repository

This repository provides an introduction and practical examples of using the Model Context Protocol (MCP) with Large Language Models (LLMs). MCP enables seamless integration between LLMs and external tools, allowing for more powerful and interactive AI applications.


## Repository Structure

### Main Files

- **`1_intro_to_MCP.ipynb`**: Introduction to Model Context Protocol, demonstrating basic usage with LLMs like Llama 3.2 models via Ollama.

- **`2_MCP_local_server.ipynb`**: Advanced usage showing how to run local MCP servers, chain tools (e.g., reading files and executing Python code), and use Chain of Thought prompting.

- **`mcp_servers/`**: Folder containing MCP server implementations:
  - `the_math_server.py`: Math-related MCP server.
  - `mcp_http_server.py`: HTTP-based MCP server with tools for reading local files and executing Python code.
  - `mcp_tools_server.py`: Additional MCP tools server.
  
## Usage

1. Set up your environment as described below.
2. Start with `1_intro_to_MCP.ipynb` to understand basic MCP concepts.
3. Proceed to `2_MCP_local_server.ipynb` for advanced server-based implementations.
4. Explore the `mcp_servers/` folder to understand and modify server implementations.

--- 

## Prerequisites

You will need a local LLM setup using Ollama:
```bash
brew install ollama
ollama pull llama3.2:1b
ollama pull llama3.2:3b
```

You can also use other LLMs for this repository, such as those from Groq. Get your [Groq API Key](https://console.groq.com/playground) for free.

## Environment Setup

### macOS
```bash
pyenv local 3.11.3
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Windows
For PowerShell:
```powershell
pyenv local 3.11.3
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

For Git-Bash:
```bash
pyenv local 3.11.3
python -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

