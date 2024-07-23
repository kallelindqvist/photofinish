"""
This module contains the views for the Flask application.
"""

import datetime as dt
import fnmatch
import os
import shutil

import flask_socketio
import pigpio
from flask import render_template, request, send_file, url_for
from sqlalchemy import desc

from app import app, camera, db, models, pi, socketio
from app.constants import (BUTTON_PIN, RACE_DIRECTORY_BASE, STATIC_DIRECTORY,
                           WEBSOCKET_ROOM)


def update_cage_status(_, level, tick):
    """
    Update the status of the cage based on the button state.
    If the button is pressed, the cage is considered closed.
    If the button is not pressed, the cage is considered open.
    """
    current_tick = pi.get_current_tick()
    race_start_time = dt.datetime.now() - dt.timedelta(
        microseconds=pigpio.tickDiff(tick, current_tick)
    )
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
                camera.start_film(
                    current_race,
                    race_start_time,
                    config.start_filming_after,
                    config.stop_filming_after,
                    stop_race_actions,
                )


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
        camera.flip_image(config.flip_image)

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
    camera.stop_film()
    current_race.running = False
    db.session.commit()
    flask_socketio.emit("race", "Inte redo", namespace="/", room=WEBSOCKET_ROOM)


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

    return send_file(camera.take_photo(), mimetype="image/jpeg")


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
