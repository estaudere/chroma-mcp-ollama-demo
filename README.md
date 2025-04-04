# chroma-mcp-ollama-demo

This is a demo app for a simple memory MCP with Chroma and an Ollama client. Run an AI chat with memory locally!

## Quick Start

Make sure you have [uv](https://docs.astral.sh/uv/#installation) installed and run `uv install` at the project root. When you have [Ollama](https://ollama.com/) installed, ensure it is running and then start both the client and MCP server with `uv run main.py`.

```
> What did I eat for breakfast today?

I'm sorry but I don't have any information about what you had for breakfast. Would you like 
to tell me so I can remember it?

> I had scrambled eggs!

I've got that down. You had scrambled eggs for breakfast. Would you like to talk about      
what's next?
```

## Configuration

I've created a new simplified memory MCP that works better with smaller local models of the 7B-8B parameter range (like LLama 3.1 8B), since saving memories is standardized to one collection and filtering is simple. You can use chroma-mcp, a more full-fledged MCP server, by running `git clone https://github.com/chroma-core/chroma-mcp.git servers/chroma-mcp`, then changing the chroma configuration in [config.json](./config.json) to

```json
"chroma": {
    "command": "uvx",
    "args": [
        "chroma-mcp"
    ]
}
```

with whatever other arguments you would like according to the chroma-mcp [docs](https://github.com/chroma-core/chroma-mcp/tree/main#usage-with-claude-desktop).

Otherwise, those same configurations also work with the simplified MCP server that is shipped with this repo, the default configuration of which is

```json
"chroma": {
    "command": "python",
    "args": [
        "servers/chroma-memory-mcp/src/chroma_mcp/server.py"
    ]
}
```

### Before and after hooks

I've added a "hooks" capability to the client as well. You can control this with

```json
"ollama": {
    "model": "llama3.1:8b-instruct-q4_0",
    "system_prompt": "...",
    "before_hook": {
        "prompt": "Find if there is anything to recall to supply as context to future assistant generations from the below user message.\n\n{user_message}"
    },
    "after_hook": {
        "prompt": "Store any important information in an organized way from the below user message and assistant message.\n\n---\nUser: {user_message}\nAssistant: {assistant_message}\n---\n"
    }
}
```

This was an attempt to make the small LLMs on Ollama interpret user queries better with the original Chroma MCP server (by having an intervention before or after that encourages the LLM to save/recall information), but I found that just simplifying the tool calling worked way better (plus it's faster!).

### More tool descriptions

The config also accepts more tool descriptions, to provide further hints (beyond the descriptions given in by the MCP server) to the client LLM on which tools to use when. These descriptions are inserted in the system prompt. Here's an example of the config:

```json
"chroma": {
    "command": "python",
    "args": [
        "servers/chroma-memory-mcp/src/chroma_mcp/server.py"
    ],
    "tool_descriptions": {
        "add_documents": "Use this tool to save memories/facts/thoughts.",
        "add_collection": "Organize memories/facts/thoughts by collections, to help find them easier later."
    }
}
```

Just make sure those tools actually exist in the given server! This was also an attempt to force the client LLMs to understand which tools to call in response to user commands/queries, but once again I found ensuring the tools are simpler and natively easier to understand (conceptually, by application) worked better than this.

## Future Directions

- Further assistant integration, e.g. every 10 minutes checking to see if there's anything to recall and proactively alerting the user if so
- Using the Chroma MCP as a fuzzy API for Chroma Cloud, e.g. allowing users to filter their documents with natural language, or using Claude or Anthropic to view 
- Benchmarking recall for assistants, specifically for memory — do they remember the right things & know how to filter for them later? Beyond embedding-based RAG, but also Chroma specific (human-in-the-loop)