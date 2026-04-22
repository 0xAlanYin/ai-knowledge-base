#!/usr/bin/env python3
"""
MCP Server for AI Knowledge Base Search

This server provides tools to search and query the local knowledge base
containing AI/LLM/Agent related articles from GitHub Trending and other sources.

Protocol: JSON-RPC 2.0 over stdio
Dependencies: Python standard library only
"""

import json
import sys
import os
import glob
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
import re
from collections import Counter
import traceback

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent
ARTICLES_DIR = PROJECT_ROOT / "knowledge" / "articles" / "processed"

# ---------------------------------------------------------------------------
# Knowledge Base Loader
# ---------------------------------------------------------------------------

class KnowledgeBase:
    """Loads and manages the knowledge base from JSON files."""
    
    def __init__(self, articles_dir: Path = ARTICLES_DIR):
        self.articles_dir = articles_dir
        self.articles: List[Dict[str, Any]] = []
        self.articles_by_id: Dict[str, Dict[str, Any]] = {}
        self._load_articles()
    
    def _load_articles(self) -> None:
        """Load all JSON articles from the processed directory."""
        if not self.articles_dir.exists():
            print(f"Warning: Articles directory not found: {self.articles_dir}", file=sys.stderr)
            return
        
        json_files = glob.glob(str(self.articles_dir / "*.json"))
        print(f"Loading {len(json_files)} articles from {self.articles_dir}", file=sys.stderr)
        
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    article = json.load(f)
                    self.articles.append(article)
                    article_id = article.get('id')
                    if article_id:
                        self.articles_by_id[article_id] = article
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading {json_file}: {e}", file=sys.stderr)
        
        print(f"Successfully loaded {len(self.articles)} articles", file=sys.stderr)
    
    def search_articles(self, keyword: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search articles by keyword in title, summary, and tags.
        
        Args:
            keyword: Search keyword (case-insensitive)
            limit: Maximum number of results to return
            
        Returns:
            List of matching articles with simplified format
        """
        if not keyword:
            return []
        
        keyword_lower = keyword.lower()
        results = []
        
        for article in self.articles:
            score = 0
            
            # Search in title
            title = article.get('title', '')
            if keyword_lower in title.lower():
                score += 3
            
            # Search in summary
            summary = article.get('content', {}).get('summary', '')
            if keyword_lower in summary.lower():
                score += 2
            
            # Search in tags
            tags = article.get('analysis', {}).get('tags', [])
            for tag in tags:
                if keyword_lower in tag.lower():
                    score += 1
            
            # Search in source metadata description
            source_desc = article.get('source_metadata', {}).get('description', '')
            if keyword_lower in source_desc.lower():
                score += 1
            
            if score > 0:
                # Create simplified result format
                simplified = {
                    'id': article.get('id', ''),
                    'title': title,
                    'source': article.get('source_type', ''),
                    'summary': summary[:200] + '...' if len(summary) > 200 else summary,
                    'score': score,
                    'tags': tags[:5],  # Limit tags for display
                    'source_url': article.get('source_url', ''),
                    'language': article.get('source_metadata', {}).get('language', ''),
                    'stars': article.get('source_metadata', {}).get('stars', 0)
                }
                results.append((score, simplified))
        
        # Sort by score (descending) and limit results
        results.sort(key=lambda x: x[0], reverse=True)
        return [result[1] for result in results[:limit]]
    
    def get_article(self, article_id: str) -> Optional[Dict[str, Any]]:
        """
        Get full article content by ID.
        
        Args:
            article_id: Article ID to retrieve
            
        Returns:
            Full article data or None if not found
        """
        return self.articles_by_id.get(article_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get knowledge base statistics.
        
        Returns:
            Dictionary with statistics
        """
        if not self.articles:
            return {
                'total_articles': 0,
                'sources': {},
                'top_tags': [],
                'languages': {},
                'recent_articles': []
            }
        
        # Source distribution
        sources = Counter()
        languages = Counter()
        all_tags = []
        
        for article in self.articles:
            source_type = article.get('source_type', 'unknown')
            sources[source_type] += 1
            
            # Language distribution
            lang = article.get('source_metadata', {}).get('language', 'unknown')
            languages[lang] += 1
            
            # Collect tags
            tags = article.get('analysis', {}).get('tags', [])
            all_tags.extend(tags)
        
        # Top tags
        tag_counter = Counter(all_tags)
        top_tags = tag_counter.most_common(10)
        
        # Recent articles (last 5)
        recent = []
        for article in self.articles[-5:]:
            recent.append({
                'id': article.get('id', ''),
                'title': article.get('title', ''),
                'source': article.get('source_type', ''),
                'collected_at': article.get('timestamps', {}).get('collected_at', '')
            })
        
        return {
            'total_articles': len(self.articles),
            'sources': dict(sources),
            'top_tags': [{'tag': tag, 'count': count} for tag, count in top_tags],
            'languages': dict(languages),
            'recent_articles': recent
        }

# ---------------------------------------------------------------------------
# MCP Server Implementation
# ---------------------------------------------------------------------------

class MCPServer:
    """MCP Server implementing JSON-RPC 2.0 over stdio."""
    
    def __init__(self):
        self.kb = KnowledgeBase()
        self.initialized = False
        
        # Define available tools
        self.tools = {
            'search_articles': {
                'name': 'search_articles',
                'description': 'Search articles in the knowledge base by keyword',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'keyword': {
                            'type': 'string',
                            'description': 'Search keyword (searches in title, summary, and tags)'
                        },
                        'limit': {
                            'type': 'integer',
                            'description': 'Maximum number of results (default: 5)',
                            'default': 5,
                            'minimum': 1,
                            'maximum': 20
                        }
                    },
                    'required': ['keyword']
                }
            },
            'get_article': {
                'name': 'get_article',
                'description': 'Get full article content by ID',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'article_id': {
                            'type': 'string',
                            'description': 'Article ID to retrieve'
                        }
                    },
                    'required': ['article_id']
                }
            },
            'knowledge_stats': {
                'name': 'knowledge_stats',
                'description': 'Get knowledge base statistics',
                'inputSchema': {
                    'type': 'object',
                    'properties': {}
                }
            }
        }
    
    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a JSON-RPC request."""
        try:
            method = request.get('method')
            request_id = request.get('id')
            
            if method == 'initialize':
                return self._handle_initialize(request, request_id)
            elif method == 'tools/list':
                return self._handle_tools_list(request, request_id)
            elif method == 'tools/call':
                return self._handle_tools_call(request, request_id)
            else:
                return self._create_error_response(
                    request_id, 
                    -32601, 
                    f"Method not found: {method}"
                )
        except Exception as e:
            return self._create_error_response(
                request.get('id'),
                -32603,
                f"Internal error: {str(e)}"
            )
    
    def _handle_initialize(self, request: Dict[str, Any], request_id: Any) -> Dict[str, Any]:
        """Handle initialize request."""
        self.initialized = True
        return {
            'jsonrpc': '2.0',
            'id': request_id,
            'result': {
                'protocolVersion': '2024-11-05',
                'capabilities': {
                    'tools': {}
                },
                'serverInfo': {
                    'name': 'ai-knowledge-base-mcp-server',
                    'version': '1.0.0'
                }
            }
        }
    
    def _handle_tools_list(self, request: Dict[str, Any], request_id: Any) -> Dict[str, Any]:
        """Handle tools/list request."""
        if not self.initialized:
            return self._create_error_response(
                request_id,
                -32000,
                "Server not initialized"
            )
        
        return {
            'jsonrpc': '2.0',
            'id': request_id,
            'result': {
                'tools': list(self.tools.values())
            }
        }
    
    def _handle_tools_call(self, request: Dict[str, Any], request_id: Any) -> Dict[str, Any]:
        """Handle tools/call request."""
        if not self.initialized:
            return self._create_error_response(
                request_id,
                -32000,
                "Server not initialized"
            )
        
        params = request.get('params', {})
        tool_name = params.get('name')
        arguments = params.get('arguments', {})
        
        if tool_name not in self.tools:
            return self._create_error_response(
                request_id,
                -32601,
                f"Tool not found: {tool_name}"
            )
        
        try:
            if tool_name == 'search_articles':
                result = self.kb.search_articles(
                    keyword=arguments.get('keyword', ''),
                    limit=arguments.get('limit', 5)
                )
            elif tool_name == 'get_article':
                result = self.kb.get_article(arguments.get('article_id', ''))
                if result is None:
                    return self._create_error_response(
                        request_id,
                        -32001,
                        f"Article not found: {arguments.get('article_id')}"
                    )
            elif tool_name == 'knowledge_stats':
                result = self.kb.get_stats()
            else:
                return self._create_error_response(
                    request_id,
                    -32601,
                    f"Tool not implemented: {tool_name}"
                )
            
            return {
                'jsonrpc': '2.0',
                'id': request_id,
                'result': {
                    'content': [
                        {
                            'type': 'text',
                            'text': json.dumps(result, ensure_ascii=False, indent=2)
                        }
                    ]
                }
            }
            
        except Exception as e:
            print(f"Error executing tool {tool_name}: {traceback.format_exc()}", file=sys.stderr)
            return self._create_error_response(
                request_id,
                -32603,
                f"Tool execution error: {str(e)}"
            )
    
    def _create_error_response(self, request_id: Any, code: int, message: str) -> Dict[str, Any]:
        """Create an error response."""
        return {
            'jsonrpc': '2.0',
            'id': request_id,
            'error': {
                'code': code,
                'message': message
            }
        }
    
    def run(self):
        """Run the MCP server, reading from stdin and writing to stdout."""
        print("Starting MCP Knowledge Server...", file=sys.stderr)
        
        while True:
            try:
                # Read line from stdin
                line = sys.stdin.readline()
                if not line:
                    break
                
                line = line.strip()
                if not line:
                    continue
                
                # Parse JSON-RPC request
                request = json.loads(line)
                
                # Handle request
                response = self.handle_request(request)
                
                # Send response
                if response:
                    response_json = json.dumps(response, ensure_ascii=False)
                    sys.stdout.write(response_json + '\n')
                    sys.stdout.flush()
                    
            except json.JSONDecodeError as e:
                error_response = self._create_error_response(
                    None,
                    -32700,
                    f"Parse error: {str(e)}"
                )
                sys.stdout.write(json.dumps(error_response) + '\n')
                sys.stdout.flush()
            except KeyboardInterrupt:
                print("\nShutting down MCP server...", file=sys.stderr)
                break
            except Exception as e:
                print(f"Unexpected error: {traceback.format_exc()}", file=sys.stderr)
                error_response = self._create_error_response(
                    None,
                    -32603,
                    f"Internal error: {str(e)}"
                )
                sys.stdout.write(json.dumps(error_response) + '\n')
                sys.stdout.flush()

# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

def main():
    """Main entry point for the MCP server."""
    server = MCPServer()
    server.run()

if __name__ == '__main__':
    main()