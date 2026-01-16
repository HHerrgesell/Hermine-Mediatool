"""Data models for Hermine API."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List


@dataclass
class Channel:
    """Channel model"""
    id: str
    name: str
    description: Optional[str] = None
    member_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class Message:
    """Message model"""
    id: str
    channel_id: str
    sender_id: Optional[str] = None
    sender_name: Optional[str] = None
    content: str = ""
    created_at: Optional[datetime] = None
    attachments: List[str] = field(default_factory=list)


@dataclass
class MediaFile:
    """Media file model"""
    id: str
    filename: str
    size: int
    mimetype: str
    url: str
    message_id: str
    channel_id: str
    sender_id: Optional[str] = None
    sender_name: Optional[str] = None
    created_at: Optional[datetime] = None
    checksum: Optional[str] = None
