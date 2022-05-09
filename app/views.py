from flask import render_template, send_file, request
import io
import time
import picamera

from app import app

rotation = 180


@app.route("/", methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        rotation = request.form.get('rotation')

    return render_template('index.html')


@app.route('/camera')
def take_photo():
    # Create an in-memory stream
    my_stream = io.BytesIO()
    with picamera.PiCamera() as camera:
        camera.start_preview()
        # Camera warm-up time
        time.sleep(2)
        camera.rotation = rotation
        camera.capture(my_stream, 'jpeg')

    my_stream.seek(0)
    return send_file(my_stream, mimetype='image/jpeg')


@app.route('/camera_settings', methods=['GET', 'POST'])
def camera_settings():
    if request.method == 'GET':
        return rotation
    if request.method == 'POST':
        rotation = request.form.get('rotation')
