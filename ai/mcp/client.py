from langchain_mcp_adapters.client import MultiServerMCPClient

client = MultiServerMCPClient({
    "playwright": {
        "transport": "stdio",
        "command": "npx",
        # Start with an empty profile each time Max starts a browser session.
        "args": ["-y", "@playwright/mcp@latest", "--browser", "chrome", "--isolated"],
    }
})

