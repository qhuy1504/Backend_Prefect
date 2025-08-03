import requests

MCP_API_TOOL = 'http://mcp_tools:5001/search'

def ask_llama_via_mcp(prompt):
    try:
        response = requests.post(MCP_API_TOOL, json={'prompt': prompt})
        response.raise_for_status()
        return response.json().get('response', '')
    except requests.RequestException as e:
        print('MCP error:', str(e))
        raise e
