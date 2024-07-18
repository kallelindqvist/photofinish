"""
This module initializes the Flask application 
and sets up the necessary configurations and dependencies.
"""

import atexit

import libcamera
import RPi.GPIO as GPIO
from flask import Flask
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from picamera2 import Picamera2

from app.constants import BUTTON_PIN

def cleanup_gpio():
    """
    Cleans up the GPIO pins when the application exits.
    """
    print("Cleaning up GPIO")
    GPIO.cleanup(BUTTON_PIN)


# Register cleanup function for normal exit
atexit.register(cleanup_gpio)

# create and configure the app
app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///data.db"
socketio = SocketIO(app)
db = SQLAlchemy(app)

# Import models
from app.models import Config, Race

with app.app_context():
    # Create the database
    db.create_all()

    race = Race.query.filter_by(running=True).first()
    # Stop any race that is running
    if race is not None:
        race.running = False
        db.session.commit()

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
        sensor={"output_size": resolution, "bit_depth": 10},
        controls={"FrameDurationLimits": (frame_duration_limit, frame_duration_limit)},
    )
    picam2.configure(video_config)
    picam2.start()


GPIO.setmode(GPIO.BCM)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)


# Import views
from app import views
