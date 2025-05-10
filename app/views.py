"""
This module contains the views for the Flask application.
"""

import fnmatch
import os
import shutil
import time

import flask_socketio
import lgpio
from flask import render_template, request, send_file, url_for, Response
from sqlalchemy import desc

from eliot import start_action, Action

from app import app, camera, db, handle, models, socketio
from app.constants import (BUTTON_PIN, RACE_DIRECTORY_BASE, STATIC_DIRECTORY,
                           WEBSOCKET_ROOM)


def update_cage_status(_, __, level, race_start_time):
    """
    Update the status of the cage based on the button state.
    If the button is pressed, the cage is considered closed.
    If the button is not pressed, the cage is considered open.
    """
    button_state = level
    if not button_state:
        # Cage is closed
        with app.test_request_context("/"):
            flask_socketio.emit("cage", "🟢 Stängd", namespace="/", room=WEBSOCKET_ROOM)
    else:
        with app.test_request_context("/"):
            flask_socketio.emit("cage", "🟡 Öppen", namespace="/", room=WEBSOCKET_ROOM)
        with app.app_context():
            current_race = models.Race.query.filter_by(running=True).first()
            if current_race is not None:
                with Action.continue_task(task_id=current_race.eliot_task_id, action_type="update_cage_status") as action:
                    config = models.Config.query.first()
                    current_race.started = True
                    db.session.commit()
                    socketio.emit("race", "🔴 Pågår", namespace="/", room=WEBSOCKET_ROOM)
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
    button_state = lgpio.gpio_read(handle, BUTTON_PIN)
    if not button_state:
        return "🟢 Stängd"
    else:
        return "🟡 Öppen"

@app.route("/", methods=["GET", "POST"])
def index():
    """
    Render the index page and handle form submissions.
    """
    config = models.Config.query.first()
    current_race = models.Race.query.filter_by(running=True).first()
    if request.method == "POST":
        raceNameToDelete = request.form.get("deleteRace")
        if bool(request.form.get("reset_everything")):
            start_action(action_type="reset")
            db.session.delete(config)
            models.Race.query.delete()
            db.session.commit()
            db.session.add(models.Config())
            db.session.commit()
            shutil.rmtree(STATIC_DIRECTORY + RACE_DIRECTORY_BASE)
            os.makedirs(STATIC_DIRECTORY + RACE_DIRECTORY_BASE)
        if raceNameToDelete is not None:
            if raceNameToDelete != "undefined":
                models.Race.query.filter_by(start_time=raceNameToDelete).delete()
                db.session.commit()
        else:
            start_action(action_type="update_config")
            config.flip_image = bool(request.form.get("flip_image"))
            config.start_filming_after = request.form.get("start_filming_after")
            config.stop_filming_after = request.form.get("stop_filming_after")
            db.session.commit()
        camera.flip_image(config.flip_image)

    race_status = "🟡 Inte redo"
    races = (
        models.Race.query.filter_by(running=False, started=True)
        .order_by(desc(models.Race.start_time))
        .all()
    )
    image_count_max = 1
    start_race_button_disabled = False
    stop_race_button_disabled = True
    if current_race is not None and current_race.running:
        if current_race.started:
            race_status = "🔴 Pågår"
            image_src = url_for("static", filename="active_race.png")
            start_race_button_disabled = True
        else:
            race_status = "🟢 Redo för start"
            image_src = url_for("static", filename="ready_for_race.png")
            start_race_button_disabled = True
            stop_race_button_disabled = False
    else:
        if races is not None and len(races) > 0:
            image_count_max = image_count(races[0].start_time)
            image_src = url_for(
                "static",
                filename=RACE_DIRECTORY_BASE + races[0].start_time + "/image_0001.jpg",
            )
        else:
            image_src = url_for("video_stream")
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
        start_race_button_disabled=start_race_button_disabled,
        stop_race_button_disabled=stop_race_button_disabled
    )


@app.route("/start_race", methods=["POST"])
def start_race():
    """
    Start a new race.
    """
    current_race = models.Race.query.filter_by(running=True).first()
    if current_race is not None:
        with start_action(action_type="start_race") as action:
            action.log(message_type="warn", message="Race is already running")
    else:
        with start_action(action_type="start_race") as action:
            current_race = models.Race()
            current_race.start_time = time.strftime("%Y%m%d-%H%M%S")
            current_race.running = True
            current_race.eliot_task_id = action.serialize_task_id()

            db.session.add(current_race)
            db.session.commit()
            #Make sure the camera is not filming
            camera.stop_film()
            # Start the camera to warm it up
            camera.start_camera()

            if current_race.started:
                action.log(message_type="debug", message="Race started")
                race_status = "🔴 Pågår"
            else:
                action.log(message_type="debug", message="Race ready to start")
                race_status = "🟢 Redo för start"
            flask_socketio.emit("race", race_status, namespace="/", room=WEBSOCKET_ROOM)
    return "OK"


@app.route("/stop_race", methods=["POST"])
def stop_race():
    """
    Stop the current race.
    """
    with start_action(action_type="stop_race") as action:
        current_race = models.Race.query.filter_by(running=True).first()
        if current_race is None:
            action.log(message_type="warn", message="No race is running")
        else:
            action.log(message_type="warn", message="Stopping race early")
            stop_race_actions(current_race)
    return "OK"


def stop_race_actions(current_race):
    """
    Stops recording, update the race in database, informs liteners and remove the timestamp callback.

    Args:
        current_race: The current race object.
    """
    with start_action(action_type="stop_race_actions") as action:
        camera.stop_film()
        current_race.running = False
        db.session.commit()
        flask_socketio.emit("race", "🟡 Inte redo", namespace="/", room=WEBSOCKET_ROOM)


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

@app.route("/video_stream")
def video_stream():
    """
    Stream video from the camera.
    """
    
    def generate():
        for frame in camera.get_video_stream():
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
    
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route("/reload")
def reload():
    """
    Reload gunicorn.
    """
    start_action(action_type="reload_gunicorn")
    os.system("pkill -HUP gunicorn")
    return "OK"


@socketio.on("connect")
def websocket_connect():
    """
    Handle WebSocket connection event.
    """
    start_action(action_type="websocket_connect")
    flask_socketio.join_room(WEBSOCKET_ROOM)


@socketio.on("disconnect")
def websocket_disconnect():
    """
    Handle WebSocket disconnection event.
    """
    start_action(action_type="websocket_disconnect")
    flask_socketio.leave_room(WEBSOCKET_ROOM)


@app.errorhandler(404)
def not_found(_):
    """
    Handle 404 Not Found error.
    """
    if request.path.endswith(".jpg"):
        return send_file("static/404.png", mimetype="image/png"), 404
    return "Not found", 404
