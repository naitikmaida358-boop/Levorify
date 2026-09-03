import uuid
from typing import List, TYPE_CHECKING
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.api_key import UserApiKey
    from app.models.tool_log import ToolExecutionLog


class User(Base, TimestampMixin):
    """
    User Node representing a D2C Merchant or Brand Operator on Levorify.
    """
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=True
    )
    brand_name: Mapped[str] = mapped_column(
        String(255),
        nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )
    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    # Relationships
    api_keys: Mapped[List["UserApiKey"]] = relationship(
        "UserApiKey",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    tool_logs: Mapped[List["ToolExecutionLog"]] = relationship(
        "ToolExecutionLog",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
