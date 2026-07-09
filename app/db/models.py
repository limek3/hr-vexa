from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255))
    subscription_plan: Mapped[str] = mapped_column(String(32), default="free")
    subscription_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    channel_reminder_sent_on: Mapped[date | None] = mapped_column(Date)

    searches: Mapped[list["Search"]] = relationship(back_populates="user")
    settings: Mapped["UserSettings | None"] = relationship(back_populates="user")


class UserSettings(Base, TimestampMixin):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    quiet_hours_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    quiet_hours_start: Mapped[str] = mapped_column(String(5), default="00:00")
    quiet_hours_end: Mapped[str] = mapped_column(String(5), default="07:00")
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Moscow")

    user: Mapped[User] = relationship(back_populates="settings")


class Search(Base, TimestampMixin):
    __tablename__ = "searches"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    user: Mapped[User] = relationship(back_populates="searches")
    keywords: Mapped[list["SearchKeyword"]] = relationship(
        back_populates="search",
        cascade="all, delete-orphan",
    )
    minus_words: Mapped[list["SearchMinusWord"]] = relationship(
        back_populates="search",
        cascade="all, delete-orphan",
    )
    sources: Mapped[list["SearchSource"]] = relationship(
        back_populates="search",
        cascade="all, delete-orphan",
    )


class SearchKeyword(Base):
    __tablename__ = "search_keywords"

    id: Mapped[int] = mapped_column(primary_key=True)
    search_id: Mapped[int] = mapped_column(ForeignKey("searches.id", ondelete="CASCADE"), index=True)
    value: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    search: Mapped[Search] = relationship(back_populates="keywords")


class SearchMinusWord(Base):
    __tablename__ = "search_minus_words"

    id: Mapped[int] = mapped_column(primary_key=True)
    search_id: Mapped[int] = mapped_column(ForeignKey("searches.id", ondelete="CASCADE"), index=True)
    value: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    search: Mapped[Search] = relationship(back_populates="minus_words")


class Source(Base, TimestampMixin):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    username: Mapped[str | None] = mapped_column(String(255), index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    type: Mapped[str] = mapped_column(String(32), default="unknown")
    input_ref: Mapped[str] = mapped_column(String(512), unique=True)
    access_status: Mapped[str] = mapped_column(String(32), default="pending", index=True)

    search_links: Mapped[list["SearchSource"]] = relationship(back_populates="source")
    messages: Mapped[list["Message"]] = relationship(back_populates="source")


class SearchSource(Base):
    __tablename__ = "search_sources"
    __table_args__ = (UniqueConstraint("search_id", "source_id", name="uq_search_sources_pair"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    search_id: Mapped[int] = mapped_column(ForeignKey("searches.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    search: Mapped[Search] = relationship(back_populates="sources")
    source: Mapped[Source] = relationship(back_populates="search_links")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("source_id", "telegram_message_id", name="uq_messages_source_message"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    telegram_message_id: Mapped[int] = mapped_column(Integer)
    telegram_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    text: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str | None] = mapped_column(String(1024))
    sender_username: Mapped[str | None] = mapped_column(String(255))
    sender_phone: Mapped[str | None] = mapped_column(String(64))
    sender_name: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    source: Mapped[Source] = relationship(back_populates="messages")


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (UniqueConstraint("search_id", "message_id", name="uq_matches_search_message"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    search_id: Mapped[int] = mapped_column(ForeignKey("searches.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    matched_keyword: Mapped[str | None] = mapped_column(String(255))
    match_score: Mapped[int | None] = mapped_column(Integer)
    match_reason: Mapped[str | None] = mapped_column(Text)


class NotificationDelivery(Base, TimestampMixin):
    __tablename__ = "notification_deliveries"
    __table_args__ = (UniqueConstraint("match_id", name="uq_notification_deliveries_match"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str] = mapped_column(Text, default="")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MatchFeedback(Base):
    __tablename__ = "match_feedback"
    __table_args__ = (UniqueConstraint("user_id", "match_id", name="uq_match_feedback_user_match"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    search_id: Mapped[int] = mapped_column(ForeignKey("searches.id", ondelete="CASCADE"), index=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), index=True)
    is_relevant: Mapped[bool] = mapped_column(Boolean)
    keyword_snapshot: Mapped[str] = mapped_column(Text, default="")
    minus_word_snapshot: Mapped[str] = mapped_column(Text, default="")
    message_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "match_id", name="uq_favorites_user_match"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DailyStats(Base):
    __tablename__ = "daily_stats"
    __table_args__ = (UniqueConstraint("user_id", "search_id", "date", name="uq_daily_stats_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    search_id: Mapped[int] = mapped_column(ForeignKey("searches.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    matches_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
