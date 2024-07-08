from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app import db


class Config(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    flip_image: Mapped[bool] = mapped_column(default=False)
    frames_per_second: Mapped[int] = mapped_column(default=100)
    resolution_width: Mapped[int] = mapped_column(default='640')
    resolution_height: Mapped[int] = mapped_column(default='480')
    rotation: Mapped[int] = mapped_column(default=0)
    start_filming_after: Mapped[int] = mapped_column(default=7)
    stop_filming_after: Mapped[int] = mapped_column(default=25)
