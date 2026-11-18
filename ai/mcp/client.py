from langchain_mcp_adapters.client import MultiServerMCPClient

client = MultiServerMCPClient({
    "playwright": {
        "transport": "stdio",
        "command": "npx",
        # Attach to the user's running Chrome instead of launching a separate
        # automation profile. Chrome must allow remote debugging.
        "args": ["-y", "@playwright/mcp@latest", "--cdp-endpoint=chrome"],
    }
})

