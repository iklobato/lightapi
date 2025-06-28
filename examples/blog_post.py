from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from lightapi import LightApi, RestEndpoint
from lightapi.database import Base


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

    def get(self, post_id: int):
        return {"status": "ok"}, 200

    def post(self, data: dict):
        return {"status": "ok"}, 200


if __name__ == "__main__":
    app = LightApi()
    app.register(BlogPost)
    app.register(Comment)
    app.register(Endpoint)

    app.run(host="0.0.0.0", port=8000)
