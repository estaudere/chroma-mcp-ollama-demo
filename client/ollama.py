from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import AsyncExitStack

from ollama import Client

class OllamaMCPClient():
    def __init__(self, model="llama3.1"):
        # Initialize session and client objects
        super().__init__()

        self.client = Client(
            host="http://localhost:11434"
        )
        self.model = model
        self.tools = []

        self.exit_stack = AsyncExitStack()


    async def connect_to_server(self, command: str, args: list):
        """Connect to an MCP server

        Args:
            command: The command to run the server
            args: The arguments to pass to the server
        """
        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=None
        )

        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        await self.session.initialize()

        # List available tools
        response = await self.session.list_tools()
        self.tools = [{
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema
                    },
                } for tool in response.tools]
        print("\nConnected to server with tools:", [tool["function"]["name"] for tool in self.tools])


    async def process_query(self, query: str) -> str:
        """Process a query using LLM and available tools"""
        messages = [
            {
                "role": "user",
                "content": query
            }
        ]

        response = self.client.chat(
            model=self.model,
            messages=messages,
            tools=self.tools,
        )

        # Process response and handle tool calls
        tool_results = []
        final_text = []

        if response.message.content:
            final_text.append(response.message.content)
        elif response.message.tool_calls:
            for tool in response.message.tool_calls:
                tool_name = tool.function.name
                tool_args = tool.function.arguments

                # Execute tool call
                result = await self.session.call_tool(tool_name, dict(tool_args))
                tool_results.append({"call": tool_name, "result": result})
                final_text.append(f"[Calling tool {tool_name} with args {tool_args}]")

                # Continue conversation with tool results
                messages.append({
                    "role": "user",
                    "content": result.content[0].text
                })

                response = self.client.chat(
                    model="llama3.1",
                    messages=messages,
                )

                final_text.append(response.message.content)

        return "\n".join(final_text)

    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")

        while True:
            try:
                query = input("\nQuery: ").strip()

                if query.lower() == 'quit':
                    break

                response = await self.process_query(query)
                print("\n" + response)

            except Exception as e:
                print(f"\nError: {str(e)}")

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()