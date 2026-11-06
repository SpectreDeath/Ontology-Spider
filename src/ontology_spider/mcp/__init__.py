"""Model Context Protocol (MCP) server package for Ontology-Spider."""

from ontology_spider.mcp.server import MCPServer
from ontology_spider.mcp.transport import StdioTransport

__all__ = ["MCPServer", "StdioTransport"]
