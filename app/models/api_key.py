import uuid
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class UserApiKey(Base, TimestampMixin):
    """
    Bring Your Own Key (BYOK) Model.
    Securely stores encrypted third-party AI keys for a given user.
    """
    __tablename__ = "user_api_keys"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_user_provider_key"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )
    provider: Mapped[str] = mapped_column(
        String(50),
        default="gemini",
        index=True,
        nullable=False
    )
    encrypted_key: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    key_hint: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="api_keys"
    )
