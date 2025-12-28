"""
CoinMarketCap MCP Server

Architecture:
- Registers 5 tools that Claude can call
- Routes tool calls to appropriate handlers
- Coordinates between API client, validators, and formatters
- Manages server lifecycle 

"""

import asyncio
import logging
import os
from typing import Any
from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from .api.coinmarketcap import CoinMarketCapClient, CoinMarketCapAPIError
from .utils.formatters import (
    format_token_info,
    format_token_list,
    format_comparison,
    format_analytics,
)
from .utils.validators import (
    validate_symbol,
    validate_symbols,
    validate_limit,
    validate_timeframe,
    ValidationError,
)




load_dotenv()


logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("coinmarketcap-mcp")

# Initialize MCP server
server = Server("coinmarketcap-mcp")


api_client: CoinMarketCapClient = None


# ============================================================================
# TOOL DEFINITIONS
# ============================================================================

@server.list_tools()
async def list_tools() -> list[Tool]:
    """
    Define all tools available to Claude.
    
    Each tool has:
    - name: Unique identifier (used when calling the tool)
    - description: What the tool does (helps Claude decide when to use it)
    - inputSchema: JSON Schema defining required/optional parameters
    
    """
    return [
        
        Tool(
            name="get_token_info",
            description="""Get comprehensive information about a cryptocurrency token.

            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Token symbol",
                    },
                    "platform_id": {
                        "type": "integer",
                        "description": "Optional: Platform ID ",
                    },
                },
                "required": ["symbol"],  
            },
        ),
        
       
        Tool(
            name="list_base_tokens",
            description="""List top cryptocurrency tokens on the Base network.
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of tokens to return (1-500, default: 50)",
                        "default": 50,
                        "minimum": 1,
                        "maximum": 500,
                    },
                    "sort_by": {
                        "type": "string",
                        "description": "Sort field",
                        "default": "volume_24h",
                        "enum": ["volume_24h", "market_cap"],
                    },
                },
            },
        ),
        
        
        Tool(
            name="get_market_metrics",
            description="""Fetch specific market metrics for one or more tokens.
            
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "symbols": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of token symbols",
                        "minItems": 1,
                        "maxItems": 20,
                    },
                    "platform_id": {
                        "type": "integer",
                        "description": "Optional: Platform ID",
                    },
                },
                "required": ["symbols"],
            },
        ),
        
        
        Tool(
            name="get_token_analytics",
            description="""Get analytical insights about a token's performance.
            
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Token symbol to analyze",
                    },
                    "timeframe": {
                        "type": "string",
                        "description": "Analysis period",
                        "enum": ["1h", "24h", "7d", "30d"],
                        "default": "24h",
                    },
                    "platform_id": {
                        "type": "integer",
                        "description": "Optional: Platform ID",
                    },
                },
                "required": ["symbol"],
            },
        ),
        
        
        Tool(
            name="compare_tokens",
            description="""Compare multiple tokens side-by-side.
            
           """,
            inputSchema={
                "type": "object",
                "properties": {
                    "symbols": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "2-10 token symbols to compare",
                        "minItems": 2,
                        "maxItems": 10,
                    },
                    "platform_id": {
                        "type": "integer",
                        "description": "Optional: Platform ID ",
                    },
                },
                "required": ["symbols"],
            },
        ),
    ]


# ============================================================================
# TOOL CALL ROUTER
# ============================================================================

@server.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """
    Route tool calls to appropriate handlers.
    
    This is the main entry point for all tool calls from Claude.
    
    Args:
        name: Tool name 
        arguments: Tool arguments as dictionary
        
    Returns:
        List of TextContent responses (MCP standard format)
        
    """
    try:
        logger.info(f"Tool called: {name} with args: {arguments}")
        
       
        if name == "get_token_info":
            result = await handle_get_token_info(arguments)
        elif name == "list_base_tokens":
            result = await handle_list_base_tokens(arguments)
        elif name == "get_market_metrics":
            result = await handle_get_market_metrics(arguments)
        elif name == "get_token_analytics":
            result = await handle_get_token_analytics(arguments)
        elif name == "compare_tokens":
            result = await handle_compare_tokens(arguments)
        else:
            
            raise ValueError(f"Unknown tool: {name}")
        
        
        return [TextContent(type="text", text=result)]
        
    except ValidationError as e:
        
        logger.warning(f"Validation error in {name}: {e}")
        return [TextContent(
            type="text",
            text=f"Invalid input: {str(e)}"
        )]
        
    except CoinMarketCapAPIError as e:
        
        logger.error(f"API error in {name}: {e}")
        return [TextContent(
            type="text",
            text=f"API error: {str(e)}. Please try again in a moment."
        )]
        
    except Exception as e:
        
        logger.error(f"Unexpected error in {name}: {e}", exc_info=True)
        return [TextContent(
            type="text",
            text=f"An unexpected error occurred. Please try again."
        )]


# ============================================================================
# TOOL HANDLERS 
# ============================================================================

async def handle_get_token_info(args: dict) -> str:
    """
    Handle get_token_info tool call.
    
    """
    
    symbol = validate_symbol(args["symbol"])
    platform_id = args.get("platform_id")  
    
   
    token = await api_client.get_token_by_symbol(symbol, platform_id)
    
    
    if not token:
        return f"Token '{symbol}' not found. Please check the symbol and try again."
    
    
    info = format_token_info(token)
    
    
    return f"""# {info['name']} ({info['symbol']})

**Rank:** #{info['rank']}

## Current Price
- **Price:** {info['price']}
- **24h High:** {info['high_24h']}
- **24h Low:** {info['low_24h']}
- **All-Time High:** {info['ath']}
- **All-Time Low:** {info['atl']}

## Market Data
- **Market Cap:** {info['market_cap']}
- **Volume 24h:** {info['volume_24h']}
- **Volume 7d:** {info['volume_7d']}

## Price Changes
- **1 Hour:** {info['change_1h']}
- **24 Hours:** {info['change_24h']}
- **7 Days:** {info['change_7d']}
- **30 Days:** {info['change_30d']}

## Supply
- **Circulating:** {info['circulating_supply']}
- **Total:** {info['total_supply']}
- **Max:** {info['max_supply']}
"""


async def handle_list_base_tokens(args: dict) -> str:
    """
    Handle list_base_tokens tool call.
    
    """
    
    limit = validate_limit(args.get("limit", 50), max_val=500)
    sort_by = args.get("sort_by", "volume_24h")
    
    
    tokens = await api_client.get_cryptocurrency_listing(
        limit=limit,
        sort_by=sort_by,
        platform_id=199  
    )
    
    
    if not tokens:
        return "No tokens found on Base network."
    
    
    formatted = format_token_list(tokens)
    
    
    result = f"# Top {len(formatted)} Tokens on Base Network\n\n"
    result += f"**Sorted by:** {sort_by}\n\n"
    
   
    result += "| Rank | Symbol | Name | Price | 24h Change | Volume | Market Cap |\n"
    result += "|------|--------|------|-------|------------|--------|------------|\n"
    
    
    for token in formatted:
        result += (
            f"| {token['rank']} "
            f"| {token['symbol']} "
            f"| {token['name']} "
            f"| {token['price']} "
            f"| {token['change_24h']} "
            f"| {token['volume_24h']} "
            f"| {token['market_cap']} |\n"
        )
    
    return result


async def handle_get_market_metrics(args: dict) -> str:
    """
    Handle get_market_metrics tool call.
    
    """
    
    symbols = validate_symbols(args["symbols"])
    platform_id = args.get("platform_id")
    
    
    tokens = await api_client.get_multiple_tokens(symbols, platform_id)
    
    
    if not tokens:
        return f"No tokens found for: {', '.join(symbols)}"
    
    
    result = "# Market Metrics\n\n"
    
    for token in tokens:
        info = format_token_info(token)
        result += f"## {info['symbol']}\n"
        result += f"- **Price:** {info['price']} ({info['change_24h']} 24h)\n"
        result += f"- **Market Cap:** {info['market_cap']}\n"
        result += f"- **Volume 24h:** {info['volume_24h']}\n\n"
    
    return result


async def handle_get_token_analytics(args: dict) -> str:
    """
    Handle get_token_analytics tool call.
    
    """
    
    symbol = validate_symbol(args["symbol"])
    timeframe = validate_timeframe(args.get("timeframe", "24h"))
    platform_id = args.get("platform_id")
    
    
    token = await api_client.get_token_by_symbol(symbol, platform_id)
    
    if not token:
        return f"Token '{symbol}' not found."
    
    
    analytics = format_analytics(token, timeframe)
    
    
    return f"""# {analytics['name']} ({analytics['symbol']}) Analytics

**Analysis Period:** {analytics['timeframe']}

## Performance
- **Price Change:** {analytics['price_change']}
- **Current Price:** {analytics['current_price']}
- **All-Time High:** {analytics['ath']}
- **Distance from ATH:** {analytics['distance_from_ath']}

## Volume
- **24h Volume:** {analytics['volume_24h']}
- **7d Volume:** {analytics['volume_7d']}

## Market Position
- **CMC Rank:** #{analytics['rank']}
- **Market Cap:** {analytics['market_cap']}
"""


async def handle_compare_tokens(args: dict) -> str:
    """
    Handle compare_tokens tool call.

    """
    
    symbols = validate_symbols(args["symbols"])
    
    
    if len(symbols) < 2:
        raise ValidationError("Need at least 2 tokens to compare")
    if len(symbols) > 10:
        raise ValidationError("Maximum 10 tokens allowed for comparison")
    
    platform_id = args.get("platform_id")
    
    
    tokens = await api_client.get_multiple_tokens(symbols, platform_id)
    
    if not tokens:
        return f"No tokens found for: {', '.join(symbols)}"
    
    
    comparison = format_comparison(tokens)
    
    
    result = "# Token Comparison\n\n"
    
    
    result += "| Symbol | Name | Price | Market Cap | Volume 24h | Change 24h | Change 7d |\n"
    result += "|--------|------|-------|------------|------------|------------|----------|\n"
    
    for token in comparison['tokens']:
        result += (
            f"| {token['symbol']} "
            f"| {token['name']} "
            f"| {token['price']} "
            f"| {token['market_cap']} "
            f"| {token['volume_24h']} "
            f"| {token['change_24h']} "
            f"| {token['change_7d']} |\n"
        )
    
    
    result += "\n## Summary\n"
    result += f"- **Combined Market Cap:** {comparison['summary']['total_market_cap']}\n"
    result += f"- **Combined Volume 24h:** {comparison['summary']['total_volume_24h']}\n"
    result += f"- **Best 24h Performer:** {comparison['summary']['best_performer']}\n"
    result += f"- **Worst 24h Performer:** {comparison['summary']['worst_performer']}\n"
    
    return result


# ============================================================================
# SERVER LIFECYCLE
# ============================================================================

async def main():
    """
    Main entry point - manages server lifecycle.

    """
    global api_client
    
   
    api_base_url = os.getenv(
        "API_BASE_URL",
        "https://api.coinmarketcap.com/data-api/v3"
    )
    api_timeout = int(os.getenv("API_TIMEOUT", "30"))
    
    api_client = CoinMarketCapClient(
        base_url=api_base_url,
        timeout=api_timeout
    )
    
    logger.info("=" * 60)
    logger.info("CoinMarketCap MCP Server starting...")
    logger.info(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
    logger.info(f"API Base URL: {api_base_url}")
    logger.info("=" * 60)
    
    try:
        # Run MCP server with stdio transport
        # stdio = standard input/output (how Claude communicates)
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options()
            )
    finally:
        
        await api_client.close()
        logger.info("Server shutdown complete")


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    """
    Script entry point.
    
    """
    asyncio.run(main())