from langchain_mcp_adapters.client import MultiServerMCPClient

client = MultiServerMCPClient({
    "playwright": {
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@playwright/mcp@latest"],
    }
})

