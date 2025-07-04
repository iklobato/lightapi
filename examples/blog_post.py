from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from lightapi import LightApi
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


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True)
    content = Column(String(1000), nullable=False)
    author = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)

    post = relationship("BlogPost", back_populates="comments")


class Endpoint(RestEndpoint):
    __tablename__ = "asdasd"

    def get(self, post_id: int):
        return {"status": "ok"}, 200

    def post(self, data: dict):
        return {"status": "ok"}, 200


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

    app.run(host="0.0.0.0", port=8000)
