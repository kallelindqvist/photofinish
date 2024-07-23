"""
This module contains the views for the Flask application.
"""

import datetime as dt
import fnmatch
import io
import os
import shutil
import time

import cv2
import flask_socketio
import libcamera
import pigpio
from flask import render_template, request, send_file, url_for
from picamera2 import MappedArray
from picamera2.encoders import MJPEGEncoder
from picamera2.outputs import FileOutput
from sqlalchemy import desc

from app import app, db, models, picam2, socketio, pi
from app.constants import (BUTTON_PIN, RACE_DIRECTORY_BASE,
                           STATIC_DIRECTORY, TIMESTAMP_COLOUR, TIMESTAMP_FONT,
                           TIMESTAMP_ORIGIN, TIMESTAMP_SCALE,
                           TIMESTAMP_THICKNESS, WEBSOCKET_ROOM)


def update_cage_status(_, level, tick):
    """
    Update the status of the cage based on the button state.
    If the button is pressed, the cage is considered closed.
    If the button is not pressed, the cage is considered open.
    """
    current_tick = pi.get_current_tick()
    race_start_time = dt.datetime.now() - dt.timedelta(microseconds=pigpio.tickDiff(tick, current_tick))
    button_state = level
    if not button_state:
        # Cage is closed
        with app.test_request_context("/"):
            flask_socketio.emit("cage", "Stängd", namespace="/", room=WEBSOCKET_ROOM)
    else:
        with app.test_request_context("/"):
            flask_socketio.emit("cage", "Öppen", namespace="/", room=WEBSOCKET_ROOM)
        with app.app_context():
            current_race = models.Race.query.filter_by(running=True).first()
            if current_race is not None:
                config = models.Config.query.first()
                current_race.started = True
                db.session.commit()
                socketio.emit("race", "Pågår", namespace="/", room=WEBSOCKET_ROOM)
                start_film(
                    current_race, race_start_time, config.start_filming_after, config.stop_filming_after
                )

pi.callback(BUTTON_PIN, pigpio.EITHER_EDGE, update_cage_status)

class SplitFrames(io.BufferedIOBase):
    """
    Splits a stream of MJPG bytes into separate jpeg frames.
    """

    def __init__(self, directory=None):
        self.directory = directory
        self.frame_num = 0
        self.output = None

    def write(self, buf):
        if buf.startswith(b"\xff\xd8"):
            # Start of new frame; close the old one (if any) and
            # open a new output
            if self.output:
                self.output.close()
            self.frame_num += 1
            self.output = io.open(
                f"{self.directory}/image_{self.frame_num:04d}.jpg", "wb"
            )
        self.output.write(buf)


def apply_timestamp(frame, race_start_time):
    """
    Apply a timestamp to the given frame based on the race start time.
    The timestamp is calculated as the difference between the current time and the race start time.
    """
    timestamp = f"{(dt.datetime.now() - race_start_time).total_seconds():0>5.2f}"
    with MappedArray(frame, "main") as m:
        cv2.putText(
            m.array,
            timestamp,
            TIMESTAMP_ORIGIN,
            TIMESTAMP_FONT,
            TIMESTAMP_SCALE,
            TIMESTAMP_COLOUR,
            TIMESTAMP_THICKNESS,
        )


def start_film(current_race, race_start_time, start_filming_after, stop_filming_after):
    """
    Start recording the race and apply timestamps to the frames.
    The recording starts after the specified start_filming_after time
    and stops after the specified stop_filming_after time.
    """
    picam2.pre_callback = lambda frame: apply_timestamp(frame, race_start_time)
    encoder = MJPEGEncoder(10000000)
    race_directory = STATIC_DIRECTORY + RACE_DIRECTORY_BASE + current_race.start_time
    os.makedirs(race_directory)
    output = SplitFrames(directory=race_directory)

    time.sleep(start_filming_after)
    picam2.start_recording(encoder, FileOutput(output))
    time.sleep(stop_filming_after - start_filming_after)
    if picam2.started:
        stop_race_actions(current_race)


def cage_status():
    """
    Get the status of the cage.
    If the button is pressed, the cage is considered closed.
    If the button is not pressed, the cage is considered open.
    """
    button_state = pi.read(BUTTON_PIN)
    if not button_state:
        return "Stängd"
    else:
        return "Öppen"


@app.route("/", methods=["GET", "POST"])
def index():
    """
    Render the index page and handle form submissions.
    """
    config = models.Config.query.first()
    current_race = models.Race.query.filter_by(running=True).first()
    if request.method == "POST":
        if bool(request.form.get("reset_everything")):
            db.session.delete(config)
            models.Race.query.delete()
            db.session.commit()
            db.session.add(models.Config())
            db.session.commit()
            shutil.rmtree(STATIC_DIRECTORY + RACE_DIRECTORY_BASE)
            os.makedirs(STATIC_DIRECTORY + RACE_DIRECTORY_BASE)
        else:
            config.flip_image = bool(request.form.get("flip_image"))
            config.start_filming_after = request.form.get("start_filming_after")
            config.stop_filming_after = request.form.get("stop_filming_after")
            db.session.commit()
        camera_config = picam2.camera_configuration()
        if camera_config["transform"].hflip != config.flip_image:
            camera_config["transform"] = libcamera.Transform(
                hflip=config.flip_image, vflip=config.flip_image
            )
            picam2.stop()
            picam2.configure(camera_config)
            picam2.start()

    race_status = "Inte redo"
    races = (
        models.Race.query.filter_by(running=False, started=True)
        .order_by(desc(models.Race.start_time))
        .all()
    )
    image_count_max = 1
    if current_race is not None and current_race.running:
        if current_race.started:
            race_status = "Pågår"
        else:
            race_status = "Redo för start"
        image_src = url_for("static", filename="active_race.png")
    else:
        if races is not None and len(races) > 0:
            image_count_max = image_count(races[0].start_time)
            image_src = url_for(
                "static",
                filename=RACE_DIRECTORY_BASE + races[0].start_time + "/image_0001.jpg",
            )
        else:
            image_src = url_for("take_photo")
    return render_template(
        "index.html",
        cage_status=cage_status(),
        flip_image=config.flip_image,
        max=image_count_max,
        image_src=image_src,
        race_status=race_status,
        races=races,
        start_filming_after=config.start_filming_after,
        stop_filming_after=config.stop_filming_after,
    )


@app.route("/start_race", methods=["POST"])
def start_race():
    """
    Start a new race.
    """
    current_race = models.Race.query.filter_by(running=True).first()
    if current_race is not None:
        print("Race is already running")
    else:
        current_race = models.Race()
        current_race.start_time = dt.datetime.now().replace(microsecond=0).isoformat()
        current_race.running = True
        db.session.add(current_race)
        db.session.commit()
        race_status = "Redo för start"
        if current_race.started:
            race_status = "Pågår"
        flask_socketio.emit("race", race_status, namespace="/", room=WEBSOCKET_ROOM)
    return "OK"


@app.route("/stop_race", methods=["POST"])
def stop_race():
    """
    Stop the current race.
    """
    current_race = models.Race.query.filter_by(running=True).first()

    if current_race is None:
        print("No race is running")
    else:
        stop_race_actions(current_race)
    return "OK"

def stop_race_actions(current_race):
    """
    Stops recording, update the race in database, informs liteners and remove the timestamp callback.

    Args:
        current_race: The current race object.
    """
    picam2.stop_recording()
    current_race.running = False
    db.session.commit()
    flask_socketio.emit("race", "Inte redo", namespace="/", room=WEBSOCKET_ROOM)
    picam2.pre_callback = None



def image_count(race):
    """
    Get the number of images in the specified race directory.
    """
    return len(
        fnmatch.filter(
            os.listdir(STATIC_DIRECTORY + RACE_DIRECTORY_BASE + race), "image*.jpg"
        )
    )


@app.route("/image_count")
def get_image_count():
    """
    Get the number of images in a race directory.
    """
    return str(image_count(request.args.get("race")))


@app.route("/camera")
def take_photo():
    """
    Take a photo using the camera and return it as a response.
    """
    current_race = models.Race.query.filter_by(running=True).first()
    if current_race is not None:
        return send_file("static/active_race.png", mimetype="image/png")
    picam2.start()
    # Create an in-memory stream
    my_stream = io.BytesIO()
    picam2.capture_file(my_stream, format="jpeg")
    my_stream.seek(0)
    return send_file(my_stream, mimetype="image/jpeg")

@app.route("/reload")
def reload():
    """
    Reload gunicorn.
    """
    os.system("pkill -HUP gunicorn")
    return "OK"


@socketio.on("connect")
def websocket_connect():
    """
    Handle WebSocket connection event.
    """
    flask_socketio.join_room(WEBSOCKET_ROOM)


@socketio.on("disconnect")
def websocket_disconnect():
    """
    Handle WebSocket disconnection event.
    """
    flask_socketio.leave_room(WEBSOCKET_ROOM)


@app.errorhandler(404)
def not_found(_):
    """
    Handle 404 Not Found error.
    """
    if request.path.endswith(".jpg"):
        return send_file("static/404.png", mimetype="image/png"), 404
    return "Not found", 404
