#!/usr/bin/env python3
"""
Test script for MCP Knowledge Server.
This script tests the server functionality directly without going through stdio.
"""

import json
import sys
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from mcp_knowledge_server import KnowledgeBase

def test_knowledge_base():
    """Test the KnowledgeBase class directly."""
    print("Testing KnowledgeBase class...")
    
    kb = KnowledgeBase()
    
    print(f"Loaded {len(kb.articles)} articles")
    
    # Test search
    print("\n1. Testing search for 'agent':")
    results = kb.search_articles("agent", limit=3)
    for i, article in enumerate(results, 1):
        print(f"  {i}. {article['title']} (score: {article['score']})")
        print(f"     Tags: {article['tags']}")
        print(f"     Summary: {article['summary'][:100]}...")
    
    # Test search for 'rag'
    print("\n2. Testing search for 'rag':")
    results = kb.search_articles("rag", limit=2)
    for i, article in enumerate(results, 1):
        print(f"  {i}. {article['title']} (score: {article['score']})")
    
    # Test get_article if we have articles
    if kb.articles:
        first_id = kb.articles[0].get('id')
        if first_id:
            print(f"\n3. Testing get_article for ID: {first_id}")
            article = kb.get_article(first_id)
            if article:
                print(f"   Title: {article.get('title')}")
                print(f"   Source: {article.get('source_type')}")
                print(f"   URL: {article.get('source_url')}")
    
    # Test stats
    print("\n4. Testing knowledge_stats:")
    stats = kb.get_stats()
    print(f"   Total articles: {stats['total_articles']}")
    print(f"   Sources: {stats['sources']}")
    print(f"   Top 3 tags: {stats['top_tags'][:3]}")
    
    print("\nKnowledgeBase tests completed successfully!")

def test_mcp_protocol():
    """Test MCP protocol messages."""
    print("\n" + "="*60)
    print("Testing MCP Protocol Messages")
    print("="*60)
    
    from mcp_knowledge_server import MCPServer
    
    server = MCPServer()
    
    # Test initialize
    print("\n1. Testing initialize:")
    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            }
        }
    }
    
    response = server.handle_request(init_request)
    print(f"   Response: {json.dumps(response, indent=2)}")
    
    # Test tools/list
    print("\n2. Testing tools/list:")
    tools_request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list"
    }
    
    response = server.handle_request(tools_request)
    print(f"   Response has tools: {'tools' in response.get('result', {})}")
    if 'result' in response and 'tools' in response['result']:
        print(f"   Available tools: {[t['name'] for t in response['result']['tools']]}")
    
    # Test tools/call - search_articles
    print("\n3. Testing tools/call - search_articles:")
    search_request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "search_articles",
            "arguments": {
                "keyword": "agent",
                "limit": 2
            }
        }
    }
    
    response = server.handle_request(search_request)
    if 'result' in response:
        print(f"   Search successful, response contains content")
    else:
        print(f"   Error: {response.get('error', {})}")
    
    # Test tools/call - knowledge_stats
    print("\n4. Testing tools/call - knowledge_stats:")
    stats_request = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "knowledge_stats",
            "arguments": {}
        }
    }
    
    response = server.handle_request(stats_request)
    if 'result' in response:
        print(f"   Stats request successful")
    else:
        print(f"   Error: {response.get('error', {})}")
    
    print("\nMCP protocol tests completed!")

def main():
    """Run all tests."""
    print("Starting MCP Knowledge Server Tests")
    print("="*60)
    
    try:
        test_knowledge_base()
        test_mcp_protocol()
        
        print("\n" + "="*60)
        print("All tests completed successfully!")
        print("\nTo run the MCP server:")
        print("  python mcp_knowledge_server.py")
        print("\nThe server will communicate via stdio using JSON-RPC 2.0 protocol.")
        
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()