import os
from picamera2 import Picamera2
import libcamera

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# create and configure the app
app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
db = SQLAlchemy(app)

# Import models 
from app.models import Config

with app.app_context():
    #Create the database
    db.create_all()
    if Config.query.first() is None:
        db.session.add(Config())
        db.session.commit()
    # Get values from database
    config = Config.query.first()
    rotation = config.rotation
    resolution = (config.resolution_width, config.resolution_height)

    picam2 = Picamera2()

    frame_duration_limit = int(1000000 / config.frames_per_second)


    video_config = picam2.create_video_configuration(
        transform=libcamera.Transform(hflip=config.flip_image, vflip=config.flip_image),
        main={"size": resolution},
        sensor={'output_size': resolution, 'bit_depth': 10},
        controls={"FrameDurationLimits": (frame_duration_limit, frame_duration_limit)}
    )
    picam2.configure(video_config)
    picam2.start()

# Import views
from app import views
