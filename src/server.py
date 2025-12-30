"""
CoinMarketCap MCP Server - Multi-Chain 

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
    format_market_cap,
)
from .utils.validators import (
    validate_symbol,
    validate_symbols,
    validate_limit,
    validate_timeframe,
    ValidationError,
)
from .utils.chains import (
    CHAINS,
    get_chain,
    get_chain_by_id,
    list_supported_chains,
    validate_chain,
)


load_dotenv()

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("coinmarketcap-mcp")

server = Server("coinmarketcap-mcp")
api_client: CoinMarketCapClient = None


# ============================================================================
# TOOL DEFINITIONS 
# ============================================================================

@server.list_tools()
async def list_tools() -> list[Tool]:
    """Define all 8 multi-chain tools."""
    
    
    supported_chains = ", ".join(list_supported_chains())
    
    return [
        
        Tool(
            name="get_token_info",
            description=f"""Get information about a cryptocurrency token.
            
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Token symbol",
                    },
                    "chain": {
                        "type": "string",
                        "description": f"Optional: Blockchain name ({supported_chains})",
                    },
                },
                "required": ["symbol"],
            },
        ),
        
        
        Tool(
            name="list_tokens",
            description=f"""List top cryptocurrency tokens on any blockchain network.
            
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "chain": {
                        "type": "string",
                        "description": f"Blockchain name ({supported_chains})",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of tokens (1-100, default: 20)",
                        "default": 20,
                    },
                    "sort_by": {
                        "type": "string",
                        "description": "Sort field",
                        "default": "volume_24h",
                        "enum": ["volume_24h", "market_cap"],
                    },
                },
                "required": ["chain"],
            },
        ),
        
        
        Tool(
            name="get_market_metrics",
            description=f"""Fetch market metrics for one or more tokens.
            
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
                    "chain": {
                        "type": "string",
                        "description": f"Optional: Filter by chain ({supported_chains})",
                    },
                },
                "required": ["symbols"],
            },
        ),
        
        
        Tool(
            name="get_token_analytics",
            description=f"""Get analytical insights about a token's performance.
            
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
                    "chain": {
                        "type": "string",
                        "description": f"Optional: Blockchain name ({supported_chains})",
                    },
                },
                "required": ["symbol"],
            },
        ),
        
        
        Tool(
            name="compare_tokens",
            description=f"""Compare multiple tokens side-by-side.
            
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
                    "chain": {
                        "type": "string",
                        "description": f"Optional: Filter by chain ({supported_chains})",
                    },
                },
                "required": ["symbols"],
            },
        ),
        
        
        Tool(
            name="list_chains",
            description="""List all supported blockchain networks.
            
            Returns information about each chain:
            - Chain name and native token
            - CoinMarketCap platform ID
            - Block explorer URL
            
            Use this to discover available chains.""",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        
        
        Tool(
            name="compare_chains",
            description="""Compare token ecosystems across multiple blockchains.
            
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "chains": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": f"2-5 chain names ({supported_chains})",
                        "minItems": 2,
                        "maxItems": 5,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Tokens per chain to analyze (default: 10)",
                        "default": 10,
                    },
                },
                "required": ["chains"],
            },
        ),
        
        
        Tool(
            name="search_token_across_chains",
            description="""Search for a token across all supported blockchains.
            
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Token symbol to search for",
                    },
                },
                "required": ["symbol"],
            },
        ),
    ]

# ============================================================================
# TOOL CALL ROUTER
# ============================================================================

@server.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Route tool calls to handlers."""
    try:
        logger.info(f"Tool called: {name}")
        
        if name == "get_token_info":
            result = await handle_get_token_info(arguments)
        elif name == "list_tokens":
            result = await handle_list_tokens(arguments)
        elif name == "get_market_metrics":
            result = await handle_get_market_metrics(arguments)
        elif name == "get_token_analytics":
            result = await handle_get_token_analytics(arguments)
        elif name == "compare_tokens":
            result = await handle_compare_tokens(arguments)
        elif name == "list_chains":
            result = await handle_list_chains(arguments)
        elif name == "compare_chains":
            result = await handle_compare_chains(arguments)
        elif name == "search_token_across_chains":
            result = await handle_search_token_across_chains(arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")
        
        return [TextContent(type="text", text=result)]
        
    except (ValidationError, ValueError) as e:
        logger.warning(f"Validation error in {name}: {e}")
        return [TextContent(type="text", text=f"Invalid input: {str(e)}")]
    except CoinMarketCapAPIError as e:
        logger.error(f"API error in {name}: {e}")
        return [TextContent(type="text", text=f"API error: {str(e)}")]
    except Exception as e:
        logger.error(f"Unexpected error in {name}: {e}", exc_info=True)
        return [TextContent(type="text", text=f"An error occurred: {str(e)}")]


# ============================================================================
# TOOL HANDLERS
# ============================================================================

async def handle_get_token_info(args: dict) -> str:
    """Get token info - supports multi-chain."""
    symbol = validate_symbol(args["symbol"])
    
    
    platform_id = None
    chain_name = None
    if "chain" in args:
        chain_name = validate_chain(args["chain"])
        chain = get_chain(chain_name)
        platform_id = chain.id
    
    token = await api_client.get_token_by_symbol(symbol, platform_id)
    
    if not token:
        chain_msg = f" on {chain_name}" if chain_name else ""
        return f"Token '{symbol}' not found{chain_msg}. Try a different chain or check the symbol."
    
    info = format_token_info(token)
    
    
    chain_display = ""
    if chain_name:
        chain = get_chain(chain_name)
        chain_display = f"\n**Chain:** {chain.name} ({chain.symbol})\n**Explorer:** {chain.explorer}"
    
    return f"""# {info['name']} ({info['symbol']}){chain_display}

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


async def handle_list_tokens(args: dict) -> str:
    """List tokens on specified chain."""
    chain_name = validate_chain(args["chain"])
    limit = validate_limit(args.get("limit", 20), max_val=100)
    sort_by = args.get("sort_by", "volume_24h")
    
    chain = get_chain(chain_name)
    
    tokens = await api_client.get_cryptocurrency_listing(
        limit=limit,
        sort_by=sort_by,
        platform_id=chain.id
    )
    
    if not tokens:
        return f"No tokens found on {chain.name}."
    
    formatted = format_token_list(tokens)
    
    result = f"# Top {len(formatted)} Tokens on {chain.name}\n\n"
    result += f"**Chain:** {chain.name} ({chain.symbol})\n"
    result += f"**Explorer:** {chain.explorer}\n"
    result += f"**Sorted by:** {sort_by}\n\n"
    result += "| Rank | Symbol | Name | Price | 24h Change | Volume | Market Cap |\n"
    result += "|------|--------|------|-------|------------|--------|------------|\n"
    
    for token in formatted:
        result += (
            f"| {token['rank']} | {token['symbol']} | {token['name']} | "
            f"{token['price']} | {token['change_24h']} | "
            f"{token['volume_24h']} | {token['market_cap']} |\n"
        )
    
    return result


async def handle_get_market_metrics(args: dict) -> str:
    """Get metrics for multiple tokens."""
    symbols = validate_symbols(args["symbols"])
    
    platform_id = None
    chain_name = None
    if "chain" in args:
        chain_name = validate_chain(args["chain"])
        chain = get_chain(chain_name)
        platform_id = chain.id
    
    tokens = await api_client.get_multiple_tokens(symbols, platform_id)
    
    if not tokens:
        return f"No tokens found for: {', '.join(symbols)}"
    
    chain_display = f" on {chain_name}" if chain_name else ""
    result = f"# Market Metrics{chain_display}\n\n"
    
    for token in tokens:
        info = format_token_info(token)
        result += f"## {info['symbol']}\n"
        result += f"- **Price:** {info['price']} ({info['change_24h']} 24h)\n"
        result += f"- **Market Cap:** {info['market_cap']}\n"
        result += f"- **Volume 24h:** {info['volume_24h']}\n\n"
    
    return result


async def handle_get_token_analytics(args: dict) -> str:
    """Get token analytics."""
    symbol = validate_symbol(args["symbol"])
    timeframe = validate_timeframe(args.get("timeframe", "24h"))
    
    platform_id = None
    chain_name = None
    if "chain" in args:
        chain_name = validate_chain(args["chain"])
        chain = get_chain(chain_name)
        platform_id = chain.id
    
    token = await api_client.get_token_by_symbol(symbol, platform_id)
    
    if not token:
        return f"Token '{symbol}' not found."
    
    analytics = format_analytics(token, timeframe)
    
    chain_display = ""
    if chain_name:
        chain = get_chain(chain_name)
        chain_display = f"\n**Chain:** {chain.name}"
    
    return f"""# {analytics['name']} ({analytics['symbol']}) Analytics{chain_display}

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
    """Compare multiple tokens."""
    symbols = validate_symbols(args["symbols"])
    
    if len(symbols) < 2:
        raise ValidationError("Need at least 2 tokens to compare")
    if len(symbols) > 10:
        raise ValidationError("Maximum 10 tokens allowed")
    
    platform_id = None
    chain_name = None
    if "chain" in args:
        chain_name = validate_chain(args["chain"])
        chain = get_chain(chain_name)
        platform_id = chain.id
    
    tokens = await api_client.get_multiple_tokens(symbols, platform_id)
    
    if not tokens:
        return f"No tokens found for: {', '.join(symbols)}"
    
    comparison = format_comparison(tokens)
    
    chain_display = f" on {chain_name}" if chain_name else ""
    result = f"# Token Comparison{chain_display}\n\n"
    result += "| Symbol | Name | Price | Market Cap | Volume 24h | Change 24h | Change 7d |\n"
    result += "|--------|------|-------|------------|------------|------------|----------|\n"
    
    for token in comparison['tokens']:
        result += (
            f"| {token['symbol']} | {token['name']} | {token['price']} | "
            f"{token['market_cap']} | {token['volume_24h']} | "
            f"{token['change_24h']} | {token['change_7d']} |\n"
        )
    
    result += f"\n## Summary\n"
    result += f"- **Combined Market Cap:** {comparison['summary']['total_market_cap']}\n"
    result += f"- **Combined Volume:** {comparison['summary']['total_volume_24h']}\n"
    result += f"- **Best Performer:** {comparison['summary']['best_performer']}\n"
    result += f"- **Worst Performer:** {comparison['summary']['worst_performer']}\n"
    
    return result


async def handle_list_chains(args: dict) -> str:
    """List all supported chains."""
    result = "# Supported Blockchain Networks\n\n"
    result += "| Chain | Native Token | Platform ID | Explorer |\n"
    result += "|-------|--------------|-------------|----------|\n"
    
    for chain_name in sorted(CHAINS.keys()):
        chain = CHAINS[chain_name]
        result += (
            f"| {chain.name} | {chain.symbol} | "
            f"{chain.id} | [Link]({chain.explorer}) |\n"
        )
    
    result += f"\n**Total Chains:** {len(CHAINS)}\n"
    result += f"\n**Available chains:** {', '.join(sorted(CHAINS.keys()))}\n"
    
    return result


async def handle_compare_chains(args: dict) -> str:
    """Compare multiple blockchain ecosystems."""
    chain_names = [validate_chain(c) for c in args["chains"]]
    
    if len(chain_names) < 2:
        raise ValidationError("Need at least 2 chains to compare")
    if len(chain_names) > 5:
        raise ValidationError("Maximum 5 chains allowed")
    
    limit = validate_limit(args.get("limit", 10), max_val=50)
    
    result = "# Blockchain Ecosystem Comparison\n\n"
    
    chain_stats = []
    
    for chain_name in chain_names:
        chain = get_chain(chain_name)
        
        tokens = await api_client.get_cryptocurrency_listing(
            limit=limit,
            platform_id=chain.id
        )
        
        if tokens:
            total_mcap = sum(
                t.get("quotes", [{}])[0].get("marketCap", 0) 
                for t in tokens
            )
            total_vol = sum(
                t.get("quotes", [{}])[0].get("volume24h", 0) 
                for t in tokens
            )
            top_token = tokens[0] if tokens else None
            
            chain_stats.append({
                "name": chain.name,
                "symbol": chain.symbol,
                "token_count": len(tokens),
                "total_mcap": format_market_cap(total_mcap),
                "total_vol": format_market_cap(total_vol),
                "top_token": top_token.get("symbol") if top_token else "N/A",
                "explorer": chain.explorer,
            })
    
    result += "| Chain | Native | Tokens | Total Market Cap | Total Volume | Top Token | Explorer |\n"
    result += "|-------|--------|--------|------------------|--------------|-----------|----------|\n"
    
    for stats in chain_stats:
        result += (
            f"| {stats['name']} | {stats['symbol']} | "
            f"{stats['token_count']} | {stats['total_mcap']} | "
            f"{stats['total_vol']} | {stats['top_token']} | "
            f"[Link]({stats['explorer']}) |\n"
        )
    
    return result


async def handle_search_token_across_chains(args: dict) -> str:
    """Search for a token across all chains."""
    symbol = validate_symbol(args["symbol"])
    
    result = f"# Cross-Chain Search: {symbol}\n\n"
    
    found_tokens = []
    
    for chain_name, chain in CHAINS.items():
        token = await api_client.get_token_by_symbol(symbol, chain.id)
        
        if token:
            info = format_token_info(token)
            found_tokens.append({
                "chain": chain.name,
                "chain_key": chain_name,
                "symbol": chain.symbol,
                "price": info['price'],
                "price_raw": info['price_raw'],
                "volume": info['volume_24h'],
                "market_cap": info['market_cap'],
                "explorer": chain.explorer,
            })
    
    if not found_tokens:
        return f"Token '{symbol}' not found on any supported chain."
    
    result += f"**Found on {len(found_tokens)} chain(s):**\n\n"
    result += "| Chain | Native | Price | Volume 24h | Market Cap | Explorer |\n"
    result += "|-------|--------|-------|------------|------------|----------|\n"
    
    for token in found_tokens:
        result += (
            f"| {token['chain']} | {token['symbol']} | "
            f"{token['price']} | {token['volume']} | "
            f"{token['market_cap']} | [Link]({token['explorer']}) |\n"
        )
    
    
    if len(found_tokens) > 1:
        prices = [t['price_raw'] for t in found_tokens]
        highest = max(prices)
        lowest = min(prices)
        diff_pct = ((highest - lowest) / lowest) * 100 if lowest > 0 else 0
        
        result += f"\n## Price Analysis\n"
        result += f"- **Highest Price:** ${highest:,.6f}\n"
        result += f"- **Lowest Price:** ${lowest:,.6f}\n"
        result += f"- **Price Difference:** {diff_pct:.2f}%\n"
    
    return result


# ============================================================================
# SERVER LIFECYCLE
# ============================================================================

async def main():
    """Main entry point."""
    global api_client
    
    api_client = CoinMarketCapClient(
        base_url=os.getenv("API_BASE_URL", "https://api.coinmarketcap.com/data-api/v3"),
        timeout=int(os.getenv("API_TIMEOUT", "30"))
    )
    
    logger.info("=" * 60)
    logger.info("CoinMarketCap MCP Server (Multi-Chain Edition)")
    logger.info(f"Supported Chains: {', '.join(sorted(CHAINS.keys()))}")
    logger.info(f"Total Tools: 8")
    logger.info("=" * 60)
    
    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options()
            )
    finally:
        await api_client.close()
        logger.info("Server shutdown")


if __name__ == "__main__":
    asyncio.run(main())