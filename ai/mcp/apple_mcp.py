from langchain_mcp_adapters.client import MultiServerMCPClient 
client =MultiServerMCPClient(
    {
        "apple" : {
            "command":"bunx",
            "args":[
                "--no-cache",
                "apple-mcp@latest"
            ],
            "transport":"stdio",
        }
    }
)

async def get_apple_tools():
    tools = await client.get_tools()
    return tools 
