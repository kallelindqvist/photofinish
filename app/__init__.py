"""
This module initializes the Flask application 
and sets up the necessary configurations and dependencies.
"""
import atexit

import lgpio
from flask import Flask
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy

from app.camera import Camera
from app.constants import BUTTON_PIN

from eliot import to_file, Action, start_action, add_global_fields
import sys

add_global_fields(process="server")
to_file(sys.stdout)

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

handle = lgpio.gpiochip_open(4)
err = lgpio.gpio_claim_alert(handle, BUTTON_PIN, lgpio.BOTH_EDGES, lgpio.SET_PULL_UP)
if err != 0:
    print(f"Error: {lgpio.error_text(err)}")
    exit(1)

# Register cleanup function for normal exit
atexit.register(lgpio.gpio_free, handle, BUTTON_PIN)

# Import views
from app import views

lgpio.callback(handle, BUTTON_PIN, lgpio.BOTH_EDGES, views.update_cage_status)
