#!/usr/bin/env python3
"""
LightAPI Search Functionality Example

This example demonstrates search capabilities in LightAPI.
It shows full-text search, fuzzy matching, multi-field search,
and search result ranking.

Features demonstrated:
- Full-text search
- Fuzzy matching
- Multi-field search
- Search result ranking
- Search suggestions
- Search filters
"""

import re
from datetime import datetime
from difflib import SequenceMatcher
from sqlalchemy import Column, Integer, String, Text, Float, DateTime
from sqlalchemy import or_, and_, func
from lightapi import LightApi, Response
from lightapi.models import Base
from lightapi.rest import RestEndpoint


class Article(Base, RestEndpoint):
    """Article model for search functionality demo."""
    __tablename__ = "search_articles"
    __table_args__ = {"extend_existing": True}
    
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    author = Column(String(100), nullable=False)
    category = Column(String(50))
    tags = Column(String(500))  # Comma-separated tags
    published_at = Column(DateTime, default=datetime.utcnow)
    views = Column(Integer, default=0)
    rating = Column(Float, default=0.0)


class SearchService(Base, RestEndpoint):
    """Search service for articles."""
    __tablename__ = "search_service"
    __table_args__ = {"extend_existing": True}
    
    id = Column(Integer, primary_key=True)
    
    def get(self, request):
        """Search articles with various search methods."""
        try:
            query = request.query_params.get('q', '').strip()
            search_type = request.query_params.get('type', 'fulltext')
            category = request.query_params.get('category')
            limit = int(request.query_params.get('limit', 10))
            offset = int(request.query_params.get('offset', 0))
            
            if not query:
                return Response(
                    body={"error": "Search query is required"},
                    status_code=400
                )
            
            if search_type == 'fulltext':
                results = self._fulltext_search(query, category, limit, offset)
            elif search_type == 'fuzzy':
                results = self._fuzzy_search(query, category, limit, offset)
            elif search_type == 'multifield':
                results = self._multifield_search(query, category, limit, offset)
            elif search_type == 'exact':
                results = self._exact_search(query, category, limit, offset)
            else:
                return Response(
                    body={"error": "Invalid search type. Use: fulltext, fuzzy, multifield, or exact"},
                    status_code=400
                )
            
            return Response(
                body={
                    "query": query,
                    "search_type": search_type,
                    "results": results['articles'],
                    "total_results": results['total'],
                    "limit": limit,
                    "offset": offset,
                    "has_more": results['has_more']
                },
                status_code=200
            )
            
        except ValueError as e:
            return Response(
                body={"error": "Invalid parameters"},
                status_code=400
            )
        except Exception as e:
            return Response(
                body={"error": "Search failed"},
                status_code=500
            )
    
    def _fulltext_search(self, query, category, limit, offset):
        """Full-text search using SQL LIKE patterns."""
        base_query = self.db.query(Article)
        
        # Apply category filter if specified
        if category:
            base_query = base_query.filter(Article.category == category)
        
        # Split query into words for better matching
        words = query.lower().split()
        
        # Build search conditions
        conditions = []
        for word in words:
            word_pattern = f"%{word}%"
            conditions.append(
                or_(
                    Article.title.ilike(word_pattern),
                    Article.content.ilike(word_pattern),
                    Article.author.ilike(word_pattern),
                    Article.tags.ilike(word_pattern)
                )
            )
        
        # Combine conditions with AND
        if conditions:
            base_query = base_query.filter(and_(*conditions))
        
        # Get total count
        total = base_query.count()
        
        # Apply pagination and ordering
        articles = base_query.order_by(Article.rating.desc(), Article.views.desc())\
                           .offset(offset)\
                           .limit(limit)\
                           .all()
        
        return {
            'articles': [self._format_article(article, query) for article in articles],
            'total': total,
            'has_more': offset + limit < total
        }
    
    def _fuzzy_search(self, query, category, limit, offset):
        """Fuzzy search using similarity matching."""
        base_query = self.db.query(Article)
        
        if category:
            base_query = base_query.filter(Article.category == category)
        
        # Get all articles for fuzzy matching
        all_articles = base_query.all()
        
        # Calculate similarity scores
        scored_articles = []
        query_lower = query.lower()
        
        for article in all_articles:
            # Calculate similarity for different fields
            title_sim = self._calculate_similarity(query_lower, article.title.lower())
            content_sim = self._calculate_similarity(query_lower, article.content.lower())
            author_sim = self._calculate_similarity(query_lower, article.author.lower())
            
            # Weighted similarity score
            similarity = (title_sim * 0.5 + content_sim * 0.3 + author_sim * 0.2)
            
            if similarity > 0.3:  # Threshold for fuzzy matching
                scored_articles.append((article, similarity))
        
        # Sort by similarity score
        scored_articles.sort(key=lambda x: x[1], reverse=True)
        
        # Apply pagination
        total = len(scored_articles)
        paginated = scored_articles[offset:offset + limit]
        
        return {
            'articles': [self._format_article(article, query, similarity) for article, similarity in paginated],
            'total': total,
            'has_more': offset + limit < total
        }
    
    def _multifield_search(self, query, category, limit, offset):
        """Multi-field search with field-specific matching."""
        base_query = self.db.query(Article)
        
        if category:
            base_query = base_query.filter(Article.category == category)
        
        # Split query into words
        words = query.lower().split()
        
        # Build field-specific conditions
        title_conditions = [Article.title.ilike(f"%{word}%") for word in words]
        content_conditions = [Article.content.ilike(f"%{word}%") for word in words]
        author_conditions = [Article.author.ilike(f"%{word}%") for word in words]
        tag_conditions = [Article.tags.ilike(f"%{word}%") for word in words]
        
        # Combine with OR to match any field
        all_conditions = []
        if title_conditions:
            all_conditions.append(and_(*title_conditions))
        if content_conditions:
            all_conditions.append(and_(*content_conditions))
        if author_conditions:
            all_conditions.append(and_(*author_conditions))
        if tag_conditions:
            all_conditions.append(and_(*tag_conditions))
        
        if all_conditions:
            base_query = base_query.filter(or_(*all_conditions))
        
        total = base_query.count()
        articles = base_query.order_by(Article.rating.desc())\
                           .offset(offset)\
                           .limit(limit)\
                           .all()
        
        return {
            'articles': [self._format_article(article, query) for article in articles],
            'total': total,
            'has_more': offset + limit < total
        }
    
    def _exact_search(self, query, category, limit, offset):
        """Exact phrase search."""
        base_query = self.db.query(Article)
        
        if category:
            base_query = base_query.filter(Article.category == category)
        
        # Search for exact phrase in title or content
        phrase_pattern = f"%{query}%"
        base_query = base_query.filter(
            or_(
                Article.title.ilike(phrase_pattern),
                Article.content.ilike(phrase_pattern)
            )
        )
        
        total = base_query.count()
        articles = base_query.order_by(Article.rating.desc())\
                           .offset(offset)\
                           .limit(limit)\
                           .all()
        
        return {
            'articles': [self._format_article(article, query) for article in articles],
            'total': total,
            'has_more': offset + limit < total
        }
    
    def _calculate_similarity(self, a, b):
        """Calculate similarity between two strings."""
        return SequenceMatcher(None, a, b).ratio()
    
    def _format_article(self, article, query, similarity=None):
        """Format article for search results."""
        result = {
            "id": article.id,
            "title": article.title,
            "content": article.content[:200] + "..." if len(article.content) > 200 else article.content,
            "author": article.author,
            "category": article.category,
            "tags": article.tags.split(',') if article.tags else [],
            "published_at": article.published_at.isoformat(),
            "views": article.views,
            "rating": article.rating
        }
        
        if similarity is not None:
            result["similarity_score"] = round(similarity, 3)
        
        # Highlight matching text
        result["highlighted_title"] = self._highlight_text(article.title, query)
        
        return result
    
    def _highlight_text(self, text, query):
        """Highlight matching text in search results."""
        words = query.lower().split()
        highlighted = text
        
        for word in words:
            pattern = re.compile(re.escape(word), re.IGNORECASE)
            highlighted = pattern.sub(f"<mark>{word}</mark>", highlighted)
        
        return highlighted
    
    def post(self, request):
        """Get search suggestions."""
        try:
            data = request.json()
            partial_query = data.get('query', '').strip()
            
            if len(partial_query) < 2:
                return Response(
                    body={"suggestions": []},
                    status_code=200
                )
            
            # Get suggestions from titles and tags
            suggestions = set()
            
            # Search in titles
            title_matches = self.db.query(Article.title)\
                                 .filter(Article.title.ilike(f"%{partial_query}%"))\
                                 .limit(5)\
                                 .all()
            
            for title, in title_matches:
                words = title.split()
                for word in words:
                    if word.lower().startswith(partial_query.lower()):
                        suggestions.add(word)
            
            # Search in tags
            tag_matches = self.db.query(Article.tags)\
                               .filter(Article.tags.ilike(f"%{partial_query}%"))\
                               .limit(5)\
                               .all()
            
            for tags, in tag_matches:
                if tags:
                    for tag in tags.split(','):
                        tag = tag.strip()
                        if tag.lower().startswith(partial_query.lower()):
                            suggestions.add(tag)
            
            return Response(
                body={
                    "suggestions": sorted(list(suggestions))[:10]
                },
                status_code=200
            )
            
        except Exception as e:
            return Response(
                body={"error": "Failed to get suggestions"},
                status_code=500
            )


if __name__ == "__main__":
    print("🔍 LightAPI Search Functionality Example")
    print("=" * 50)
    
    # Initialize the API
    app = LightApi(
        database_url="sqlite:///search_example.db",
        swagger_title="Search Functionality API",
        swagger_version="1.0.0",
        swagger_description="Demonstrates various search capabilities",
        enable_swagger=True
    )
    
    # Register endpoints
    app.register(Article)
    app.register(SearchService)
    
    print("Server running at http://localhost:8000")
    print("API documentation at http://localhost:8000/docs")
    print()
    print("Test search functionality:")
    print("  # Create sample articles")
    print("  curl -X POST http://localhost:8000/article/ -H 'Content-Type: application/json' -d '{\"title\": \"Python Programming Guide\", \"content\": \"Learn Python programming from basics to advanced topics\", \"author\": \"John Doe\", \"category\": \"Programming\", \"tags\": \"python,programming,tutorial\"}'")
    print()
    print("  # Full-text search")
    print("  curl http://localhost:8000/searchservice/?q=python&type=fulltext")
    print()
    print("  # Fuzzy search")
    print("  curl http://localhost:8000/searchservice/?q=pyton&type=fuzzy")
    print()
    print("  # Multi-field search")
    print("  curl http://localhost:8000/searchservice/?q=programming&type=multifield")
    print()
    print("  # Exact phrase search")
    print("  curl http://localhost:8000/searchservice/?q=Python Programming&type=exact")
    print()
    print("  # Search with category filter")
    print("  curl http://localhost:8000/searchservice/?q=programming&category=Programming")
    print()
    print("  # Get search suggestions")
    print("  curl -X POST http://localhost:8000/searchservice/ -H 'Content-Type: application/json' -d '{\"query\": \"py\"}'")
    
    # Run the server
    app.run(host="localhost", port=8000, debug=True)
