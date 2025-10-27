from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from lightapi import Base, LightApi
from lightapi.database import Base
from lightapi.rest import RestEndpoint

print(f"DEBUG: LightApi loaded from {LightApi.__module__}")


class BlogPost(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")

    def _serialize_post(self, post, include_comments=True):
        """Serialize post with optional comments."""
        result = {c.name: getattr(post, c.name) for c in post.__table__.columns}
        if result.get('created_at'):
            result['created_at'] = result['created_at'].isoformat()
        
        if include_comments:
            result['comments'] = [self._serialize_comment(c) for c in post.comments]
        else:
            result['comment_count'] = len(post.comments)
        return result

    def _serialize_comment(self, comment):
        """Serialize comment to dict."""
        result = {c.name: getattr(comment, c.name) for c in comment.__table__.columns}
        if result.get('created_at'):
            result['created_at'] = result['created_at'].isoformat()
        return result


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True)
    content = Column(String(1000), nullable=False)
    author = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)

    post = relationship("BlogPost", back_populates="comments")


class Endpoint(Base, RestEndpoint):
    __tablename__ = "asdasd"

    def get(self, post_id: int):
        return {"status": "ok"}, 200

    def post(self, data: dict):
        return {"status": "ok"}, 200


def _create_sample_posts(session):
    """Create sample blog posts."""
    posts = [
        BlogPost(title="Getting Started with LightAPI", content="This is a comprehensive guide to using LightAPI..."),
        BlogPost(title="Advanced Features", content="Learn about advanced features like caching and pagination..."),
        BlogPost(title="Best Practices", content="Follow these best practices for building robust APIs...")
    ]
    session.add_all(posts)
    return posts


def _print_usage():
    """Print usage instructions."""
    print("🚀 Blog Post API Started")
    print("Server running at http://localhost:8000")
    print("API documentation at http://localhost:8000/docs")
    print("\nTry these endpoints:")
    print("  curl http://localhost:8000/posts/")
    print("  curl http://localhost:8000/comments/")


if __name__ == "__main__":
    app = LightApi(
        enable_swagger=True,
        swagger_title="Blog Post API",
        swagger_version="1.0.0",
        swagger_description="API documentation for the Blog Post application",
    )
    app.register(BlogPost)
    app.register(Comment)
    app.register(Endpoint)

    _print_usage()
    app.run(host="0.0.0.0", port=8000)
