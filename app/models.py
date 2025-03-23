"""
This module contains the models for the application.
"""

from sqlalchemy.orm import Mapped, mapped_column

from app import db


class Race(db.Model):
    """
    Represents a race in the application.
    """

    id: Mapped[int] = mapped_column(primary_key=True)
    start_time: Mapped[str] = mapped_column()
    running: Mapped[bool] = mapped_column(default=False)
    started: Mapped[bool] = mapped_column(default=False)
    eliot_task_id: Mapped[str] = mapped_column()


class Config(db.Model):
    """
    Represents the configuration settings in the application.
    """

    id: Mapped[int] = mapped_column(primary_key=True)
    flip_image: Mapped[bool] = mapped_column(default=False)
    frames_per_second: Mapped[int] = mapped_column(default=100)
    resolution_width: Mapped[int] = mapped_column(default="1332")
    resolution_height: Mapped[int] = mapped_column(default="990")
    rotation: Mapped[int] = mapped_column(default=0)
    start_filming_after: Mapped[int] = mapped_column(default=7)
    stop_filming_after: Mapped[int] = mapped_column(default=25)
