#!/usr/bin/env python3
"""
Interactive test script for MCP Knowledge Server.
Demonstrates the correct sequence of MCP protocol calls.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

def send_request(proc, request):
    """Send a JSON-RPC request to the server process."""
    request_json = json.dumps(request)
    print(f"Sending: {request_json}")
    proc.stdin.write(request_json + '\n')
    proc.stdin.flush()
    
    # Read response
    response_line = proc.stdout.readline()
    if response_line:
        response = json.loads(response_line.strip())
        print(f"Received: {json.dumps(response, indent=2)}")
        return response
    return None

def main():
    """Run interactive MCP protocol test."""
    print("Starting interactive MCP test...")
    
    # Start the server process
    server_path = Path(__file__).parent / "mcp_knowledge_server.py"
    proc = subprocess.Popen(
        [sys.executable, str(server_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )
    
    # Give server time to start
    time.sleep(0.5)
    
    # Read initial stderr output
    while True:
        line = proc.stderr.readline()
        if not line:
            break
        if "Starting MCP Knowledge Server" in line:
            print(f"Server: {line.strip()}")
            break
    
    try:
        # 1. Initialize
        print("\n" + "="*60)
        print("Step 1: Initialize")
        print("="*60)
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
        init_response = send_request(proc, init_request)
        
        if not init_response or 'error' in init_response:
            print("Initialize failed!")
            return
        
        # 2. List tools
        print("\n" + "="*60)
        print("Step 2: List tools")
        print("="*60)
        tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        tools_response = send_request(proc, tools_request)
        
        if tools_response and 'result' in tools_response:
            tools = tools_response['result'].get('tools', [])
            print(f"\nAvailable tools: {[t['name'] for t in tools]}")
        
        # 3. Search articles
        print("\n" + "="*60)
        print("Step 3: Search articles")
        print("="*60)
        search_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "search_articles",
                "arguments": {
                    "keyword": "agent",
                    "limit": 3
                }
            }
        }
        search_response = send_request(proc, search_request)
        
        # 4. Get stats
        print("\n" + "="*60)
        print("Step 4: Get knowledge stats")
        print("="*60)
        stats_request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "knowledge_stats",
                "arguments": {}
            }
        }
        stats_response = send_request(proc, stats_request)
        
        # Try to get an article by ID if we have search results
        if search_response and 'result' in search_response:
            # Parse the search results from the response
            result_text = search_response['result']['content'][0]['text']
            search_results = json.loads(result_text)
            if search_results:
                article_id = search_results[0]['id']
                
                print("\n" + "="*60)
                print(f"Step 5: Get article by ID: {article_id}")
                print("="*60)
                get_article_request = {
                    "jsonrpc": "2.0",
                    "id": 5,
                    "method": "tools/call",
                    "params": {
                        "name": "get_article",
                        "arguments": {
                            "article_id": article_id
                        }
                    }
                }
                article_response = send_request(proc, get_article_request)
        
        print("\n" + "="*60)
        print("Test completed successfully!")
        print("="*60)
        
    except Exception as e:
        print(f"\nError during test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up
        proc.terminate()
        proc.wait()
        print("\nServer terminated.")

if __name__ == '__main__':
    main()