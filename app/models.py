from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.sql import func
from .db import Base

class Download(Base):
    __tablename__ = "downloads"
    id = Column(Integer, primary_key=True)
    source = Column(Text)          # magnet/url/filename
    engine = Column(String(20))    # aria2|transmission|qbit
    kind = Column(String(10))      # movie|tv
    status = Column(String(20), default="queued")
    progress = Column(Float, default=0.0)
    save_path = Column(Text, nullable=True)
    engine_id = Column(String(128), nullable=True)  # aria2 GID, torrent hash, etc.
    title = Column(String(256), nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())



