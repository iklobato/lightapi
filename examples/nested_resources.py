#!/usr/bin/env python3
"""
LightAPI Nested Resources Example

This example demonstrates nested resource patterns in LightAPI.
It shows how to create hierarchical API endpoints like /users/{id}/posts
and /posts/{id}/comments with proper relationships.

Features demonstrated:
- Nested resource endpoints
- Parent-child relationships
- Hierarchical URL patterns
- Relationship validation
- Cascading operations
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from lightapi import LightApi, Response
from lightapi.models import Base
from lightapi.rest import RestEndpoint


class NestedUser(Base, RestEndpoint):
    """User model for nested resources demo."""
    __tablename__ = "nested_users"
    __table_args__ = {"extend_existing": True}
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    
    # Relationships
    posts = relationship("NestedPost", back_populates="author", cascade="all, delete-orphan")


class NestedPost(Base, RestEndpoint):
    """Post model for nested resources demo."""
    __tablename__ = "nested_posts"
    __table_args__ = {"extend_existing": True}
    
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    author_id = Column(Integer, ForeignKey("nested_users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    author = relationship("NestedUser", back_populates="posts")
    comments = relationship("NestedComment", back_populates="post", cascade="all, delete-orphan")


class NestedComment(Base, RestEndpoint):
    """Comment model for nested resources demo."""
    __tablename__ = "nested_comments"
    __table_args__ = {"extend_existing": True}
    
    id = Column(Integer, primary_key=True)
    content = Column(Text, nullable=False)
    author_name = Column(String(100), nullable=False)
    post_id = Column(Integer, ForeignKey("nested_posts.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    post = relationship("NestedPost", back_populates="comments")


class UserPostsEndpoint(Base, RestEndpoint):
    """Endpoint for managing posts under a specific user."""
    __tablename__ = "user_posts_endpoint"
    __table_args__ = {"extend_existing": True}
    
    id = Column(Integer, primary_key=True)
    
    def _get_user(self, user_id):
        """Get user or raise ValueError."""
        user = self.db.query(NestedUser).filter(NestedUser.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")
        return user
    
    def _get_user_posts(self, user_id):
        """Get all posts for a user."""
        return self.db.query(NestedPost).filter(NestedPost.author_id == user_id).all()
    
    def _serialize_user(self, user):
        """Serialize user to dict."""
        return {c.name: getattr(user, c.name) for c in user.__table__.columns}
    
    def _validate_post_data(self, data):
        """Validate post data, raise ValueError on error."""
        if not data.get('title'):
            raise ValueError("Post title is required")
        if not data.get('content'):
            raise ValueError("Post content is required")
        return data
    
    def get(self, request):
        """Get all posts for a specific user."""
        try:
            user_id = int(request.path_params['user_id'])
            user = self._get_user(user_id)
            posts = self._get_user_posts(user_id)
            
            return Response(
                body={
                    "user": self._serialize_user(user),
                    "posts": [self._serialize_post(post) for post in posts],
                    "total_posts": len(posts)
                },
                status_code=200
            )
            
        except ValueError as e:
            return Response(body={"error": str(e)}, status_code=404)
        except Exception as e:
            return Response(body={"error": "Failed to retrieve posts"}, status_code=500)
    
    def post(self, request):
        """Create a new post for a specific user."""
        try:
            user_id = int(request.path_params['user_id'])
            data = self._validate_post_data(request.json())
            
            user = self._get_user(user_id)
            
            # Create post
            post = NestedPost(
                title=data['title'],
                content=data['content'],
                author_id=user_id
            )
            
            self.db.add(post)
            self.db.commit()
            
            return Response(
                body={
                    "message": "Post created successfully",
                    "post": self._serialize_post(post)
                },
                status_code=201
            )
            
        except ValueError as e:
            return Response(body={"error": str(e)}, status_code=400)
        except Exception as e:
            self.db.rollback()
            return Response(body={"error": "Failed to create post"}, status_code=500)


class PostCommentsEndpoint(Base, RestEndpoint):
    """Endpoint for managing comments under a specific post."""
    __tablename__ = "post_comments_endpoint"
    __table_args__ = {"extend_existing": True}
    
    id = Column(Integer, primary_key=True)
    
    def _get_post(self, post_id):
        """Get post or raise ValueError."""
        post = self.db.query(NestedPost).filter(NestedPost.id == post_id).first()
        if not post:
            raise ValueError(f"Post {post_id} not found")
        return post
    
    def _get_post_comments(self, post_id):
        """Get all comments for a post."""
        return self.db.query(NestedComment).filter(NestedComment.post_id == post_id).all()
    
    def _serialize_post_with_author(self, post):
        """Serialize post with author info."""
        return {
            "id": post.id,
            "title": post.title,
            "author": {
                "id": post.author.id,
                "name": post.author.name
            }
        }
    
    def _serialize_comment(self, comment):
        """Serialize comment to dict."""
        result = {c.name: getattr(comment, c.name) for c in comment.__table__.columns}
        if result.get('created_at'):
            result['created_at'] = result['created_at'].isoformat()
        return result
    
    def _validate_comment_data(self, data):
        """Validate comment data, raise ValueError on error."""
        if not data.get('content'):
            raise ValueError("Comment content is required")
        if not data.get('author_name'):
            raise ValueError("Author name is required")
        return data
    
    def get(self, request):
        """Get all comments for a specific post."""
        try:
            post_id = int(request.path_params['post_id'])
            post = self._get_post(post_id)
            comments = self._get_post_comments(post_id)
            
            return Response(
                body={
                    "post": self._serialize_post_with_author(post),
                    "comments": [self._serialize_comment(comment) for comment in comments],
                    "total_comments": len(comments)
                },
                status_code=200
            )
            
        except ValueError as e:
            return Response(body={"error": str(e)}, status_code=404)
        except Exception as e:
            return Response(body={"error": "Failed to retrieve comments"}, status_code=500)
    
    def post(self, request):
        """Create a new comment for a specific post."""
        try:
            post_id = int(request.path_params['post_id'])
            data = self._validate_comment_data(request.json())
            
            post = self._get_post(post_id)
            
            # Create comment
            comment = NestedComment(
                content=data['content'],
                author_name=data['author_name'],
                post_id=post_id
            )
            
            self.db.add(comment)
            self.db.commit()
            
            return Response(
                body={
                    "message": "Comment created successfully",
                    "comment": self._serialize_comment(comment)
                },
                status_code=201
            )
            
        except ValueError as e:
            return Response(body={"error": str(e)}, status_code=400)
        except Exception as e:
            self.db.rollback()
            return Response(body={"error": "Failed to create comment"}, status_code=500)


class UserCommentsEndpoint(Base, RestEndpoint):
    """Endpoint for getting all comments by posts of a specific user."""
    __tablename__ = "user_comments_endpoint"
    __table_args__ = {"extend_existing": True}
    
    id = Column(Integer, primary_key=True)
    
    def get(self, request):
        """Get all comments on posts by a specific user."""
        try:
            user_id = int(request.path_params['user_id'])
            
            # Verify user exists
            user = self.db.query(NestedUser).filter(NestedUser.id == user_id).first()
            if not user:
                return Response(
                    body={"error": f"User {user_id} not found"},
                    status_code=404
                )
            
            # Get all posts by the user
            user_posts = self.db.query(NestedPost).filter(NestedPost.author_id == user_id).all()
            post_ids = [post.id for post in user_posts]
            
            # Get all comments on those posts
            comments = self.db.query(NestedComment).filter(NestedComment.post_id.in_(post_ids)).all()
            
            # Group comments by post
            comments_by_post = {}
            for comment in comments:
                if comment.post_id not in comments_by_post:
                    comments_by_post[comment.post_id] = []
                comments_by_post[comment.post_id].append({
                    "id": comment.id,
                    "content": comment.content,
                    "author_name": comment.author_name,
                    "created_at": comment.created_at.isoformat()
                })
            
            return Response(
                body={
                    "user": {
                        "id": user.id,
                        "name": user.name,
                        "email": user.email
                    },
                    "posts_with_comments": [
                        {
                            "post_id": post.id,
                            "post_title": post.title,
                            "comments": comments_by_post.get(post.id, [])
                        }
                        for post in user_posts
                    ],
                    "total_comments": len(comments)
                },
                status_code=200
            )
            
        except ValueError:
            return Response(
                body={"error": "Invalid user ID"},
                status_code=400
            )
        except Exception as e:
            return Response(
                body={"error": "Failed to retrieve comments"},
                status_code=500
            )


def _print_usage():
    """Print usage instructions."""
    print("🚀 Nested Resources API Started")
    print("Server running at http://localhost:8000")
    print("API documentation at http://localhost:8000/docs")
    print()
    print("Test nested resources:")
    print()
    print("  # Create users")
    print("  curl -X POST http://localhost:8000/nestedusers/ -H 'Content-Type: application/json' -d '{\"name\": \"Alice\", \"email\": \"alice@example.com\"}'")
    print()
    print("  # Create posts for user 1")
    print("  curl -X POST http://localhost:8000/userpostsendpoint/1/ -H 'Content-Type: application/json' -d '{\"title\": \"My First Post\", \"content\": \"This is my first post!\"}'")
    print()
    print("  # Get all posts for user 1")
    print("  curl http://localhost:8000/userpostsendpoint/1/")
    print()
    print("  # Create comments for post 1")
    print("  curl -X POST http://localhost:8000/postcommentsendpoint/1/ -H 'Content-Type: application/json' -d '{\"content\": \"Great post!\", \"author_name\": \"Bob\"}'")
    print()
    print("  # Get all comments for post 1")
    print("  curl http://localhost:8000/postcommentsendpoint/1/")
    print()
    print("  # Get all comments on posts by user 1")
    print("  curl http://localhost:8000/usercommentsendpoint/1/")


if __name__ == "__main__":
    print("🔗 LightAPI Nested Resources Example")
    print("=" * 50)
    
    # Initialize the API
    app = LightApi(
        database_url="sqlite:///nested_resources_example.db",
        swagger_title="Nested Resources API",
        swagger_version="1.0.0",
        swagger_description="Demonstrates nested resource patterns",
        enable_swagger=True
    )
    
    # Register endpoints
    app.register(NestedUser)
    app.register(NestedPost)
    app.register(NestedComment)
    app.register(UserPostsEndpoint)
    app.register(PostCommentsEndpoint)
    app.register(UserCommentsEndpoint)
    
    _print_usage()
    
    # Run the server
    app.run(host="localhost", port=8000, debug=True)
