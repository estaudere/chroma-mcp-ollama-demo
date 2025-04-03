from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import requests
from rich import print as rprint
from rich.markdown import Markdown
from rich.prompt import Confirm, Prompt
from rich.status import Status
import traceback

import ollama
from ollama import Client

class OllamaMCPClient():
    def __init__(self, model="llama3.1", system_prompt="", before_hook=None, after_hook=None):
        # Initialize session and client objects
        super().__init__()

        self.client = Client(
            host="http://localhost:11434"
        )

        # check that ollama is running
        response = requests.get("http://localhost:11434")
        if response.status_code != 200:
            raise ValueError("Ollama is not running. Try running `ollama run` or opening the application.")
        

        # check that the model is loaded, or ask the user to download it if not
        models = [m['model'] for m in ollama.list().models]
        if model not in models:
            load_model = Confirm.ask(f"Model {model} is not loaded. Download it now?")
            if load_model:
                ollama.pull(model)
            else:
                raise ValueError(f"Model {model} is not loaded")
            
        self.model = model
        self.system_prompt = system_prompt
        rprint(f"[green]Started ollama chat client with model {model}[/green]")

        self.tools = []
        self.exit_stack = AsyncExitStack()

        self.before_hook = before_hook
        self.after_hook = after_hook


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

        # list available tools
        response = await self.session.list_tools()
        self.tools = [{
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema
                    },
                } for tool in response.tools]
        fmt_tools = '\n\t'.join([tool['function']['name'] for tool in self.tools])
        rprint(f"[green]Connected to server with tools[/green]\n\t{fmt_tools}")


    async def process_query(self, messages: list) -> str:
        """Process a list of messages using an LLM and available tools. 
        Returns a list of all messages with the assistant's response and tool calls."""
        
        # continue conversation until no more tool calls
        while True:
            response = self.client.chat(
                model=self.model,
                messages=messages,
                tools=self.tools,
            )

            rprint(f"[dim][bold]Response:[/bold] {response.message.content}[/dim]")
            rprint(f"[dim][bold]Tool calls:[/bold] {response.message.tool_calls}[/dim]")

            messages.append({
                "role": "assistant",
                "content": response.message.content,
                "tool_calls": response.message.tool_calls if response.message.tool_calls else None
            })

            if not response.message.tool_calls:
                break
            
            # process each tool call
            for tool in response.message.tool_calls:
                tool_name = tool.function.name
                tool_args = tool.function.arguments
                
                # execute tool call
                rprint(f"[dim bold]Executing tool {tool_name} with args {tool_args}[/]")
                result = await self.session.call_tool(tool_name, dict(tool_args))
                
                # add tool response to messages for context
                messages.append({
                    "role": "tool",
                    "name": tool_name,
                    "content": result.content[0].text
                })
                
                # debug info only printed to console, not returned to user
                if response.message.content:
                    rprint(f"[dim]response content: {response.message.content}[/dim]")
                rprint(f"[dim]tool result: {result.content[0].text}[/dim]")

        return messages

    async def chat_loop(self):
        """Run an interactive chat loop"""
        rprint("[green bold]MCP Client Started![/]")
        rprint("[dim]Type your queries or 'quit' to exit.[/dim]")

        if self.system_prompt:
            messages = [
                {
                    "role": "system",
                    "content": self.system_prompt
                }
            ]
        else:
            messages = []

        while True:
            try:
                query = Prompt.ask("> ")

                if query.strip().lower() == 'quit':
                    break

                # run before hook
                if self.before_hook:
                    before_hook_response = await self._before_hook(query)
                    if before_hook_response:
                        messages.append({
                            "role": "assistant",
                            "content": before_hook_response
                        })

                messages.append({
                    "role": "user",
                    "content": query
                })

                # with Status("Thinking...", spinner="dots") as status:
                response = await self.process_query(messages)
                rprint(Markdown(response[-1]['content']))
                messages = response

                # run after hook
                if self.after_hook:
                    after_hook_response = await self._after_hook(query, response[-1]['content'])
                    if after_hook_response:
                        messages.append({
                            "role": "assistant",
                            "content": after_hook_response
                        })

            except Exception as e:
                rprint(f"[red bold]Error:[/red bold] {str(e)}")
                traceback.print_exc()

    async def _before_hook(self, user_query: str):
        """Run a hook before the response is generated"""
        response = self.client.chat(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": self.before_hook['prompt'].format(user_message=user_query)
                }
            ],
            tools=self.tools,
        )

        rprint(f"[dim][bold]Before hook response:[/bold] {response.message.content}[/dim]")
        
        # run the tools if there are any
        if response.message.tool_calls:
            for tool in response.message.tool_calls:
                tool_name = tool.function.name
                tool_args = tool.function.arguments
                result = await self.session.call_tool(tool_name, dict(tool_args))
                rprint(f"[dim]tool result: {result.content[0].text}[/dim]")
                
                return result.content[0].text
        return None
        
    async def _after_hook(self, user_query: str, assistant_response: str):
        """Run a hook after the response is generated"""
        response = self.client.chat(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": self.after_hook['prompt'].format(user_message=user_query, assistant_message=assistant_response)
                }
            ],
            tools=self.tools,
        )

        rprint(f"[dim][bold]After hook response:[/bold] {response.message.content}[/dim]")

        # run the tools if there are any
        if response.message.tool_calls:
            for tool in response.message.tool_calls:
                tool_name = tool.function.name
                tool_args = tool.function.arguments
                result = await self.session.call_tool(tool_name, dict(tool_args))
                rprint(f"[dim]tool result: {result.content[0].text}[/dim]")

                return result.content[0].text
        return None

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()