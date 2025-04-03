import asyncio
import sys
import json
from client import OllamaMCPClient

async def main():
    with open('config.json', 'r') as f:
        config = json.load(f)

    mcp_servers = config.get('mcpServers', {})

    model = config.get('ollama', {}).get('model', 'llama3.1:8b-instruct-q3_K_M')
    ollama_client = OllamaMCPClient(model)

    try: 
        for server_name, server_config in mcp_servers.items():
            await ollama_client.connect_to_server(server_config['command'], server_config['args'])
        await ollama_client.chat_loop()
    finally:
        await ollama_client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
