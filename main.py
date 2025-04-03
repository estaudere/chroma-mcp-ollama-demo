import asyncio
import sys
import json
from client import OllamaMCPClient

async def main():
    with open('config.json', 'r') as f:
        config = json.load(f)

    mcp_servers = config.get('mcpServers', {})
    tool_descriptions = config.get('tool_descriptions', None)
    client_config = config.get('ollama', {})

    # add tool descriptions to system prompt
    if tool_descriptions:
        system_prompt = client_config.get('system_prompt', '')
        system_prompt += "\n\nHere are more usage details about common tools you may use:\n"
        for mcp_name, mcp_config in mcp_servers.items():
            for tool_name, tool_description in tool_descriptions[mcp_name].items():
                system_prompt += f"{mcp_name}_{tool_name}: {tool_description}\n"
        client_config['system_prompt'] = system_prompt

    ollama_client = OllamaMCPClient(**client_config)

    try: 
        for server_name, server_config in mcp_servers.items():
            await ollama_client.connect_to_server(server_config['command'], server_config['args'])
        await ollama_client.chat_loop()
    finally:
        await ollama_client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
