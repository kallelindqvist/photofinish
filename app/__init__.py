"""
This module initializes the Flask application 
and sets up the necessary configurations and dependencies.
"""

import atexit

from app.camera import Camera
import pigpio
from flask import Flask
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy

from app.constants import BUTTON_PIN





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

    camera = Camera(config.frames_per_second, config.flip_image, resolution)

pi = pigpio.pi()
# Register cleanup function for normal exit
atexit.register(pi.stop)
pi.set_mode(BUTTON_PIN, pigpio.INPUT)
pi.set_pull_up_down(BUTTON_PIN, pigpio.PUD_UP)

# Import views
from app import views
pi.callback(BUTTON_PIN, pigpio.EITHER_EDGE, views.update_cage_status)
