from langchain_mcp_adapters.client import MultiServerMCPClient 

client = MultiServerMCPClient({
    "filesystem": {
    "transport": "stdio",
    "command": "npx",
    "args": [
        "-y", "@modelcontextprotocol/server-filesystem",
        "/Users/suchayjoshi/Documents",
        "/Users/suchayjoshi/Downloads",
        "/Users/suchayjoshi/Desktop",
    ],
},
}

)

async def get_tools():
    tools = await client.get_tools()
    return tools 
