import uuid
from typing import Optional, TYPE_CHECKING
from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class ToolExecutionLog(Base, TimestampMixin):
    """
    Audit and Telemetry Log for D2C AI Tool Executions.
    """
    __tablename__ = "tool_execution_logs"

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
    tool_name: Mapped[str] = mapped_column(
        String(100),
        index=True,
        nullable=False
    )
    provider: Mapped[str] = mapped_column(
        String(50),
        default="gemini",
        nullable=False
    )
    model_used: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="success",
        nullable=False
    )
    latency_ms: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False
    )
    tokens_used: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="tool_logs"
    )
