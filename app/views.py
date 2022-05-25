
from flask import render_template, send_file, request
import datetime as dt
import io
import time
import picamera
import RPi.GPIO as GPIO
import ffmpeg

from app import app

rotation = 180
start_filming_after = 2
stop_filming_after = 5
fps = 60

GPIO.setmode(GPIO.BOARD)
ledPin = 12
buttonPin = 16
GPIO.setup(ledPin, GPIO.OUT)
GPIO.setup(buttonPin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def start_film(channel):
    buttonState = GPIO.input(buttonPin)
    if buttonState == False:
        GPIO.output(ledPin, GPIO.HIGH)
        return

    GPIO.remove_event_detect(channel)
    GPIO.output(ledPin, GPIO.LOW)

    video_filename= dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with picamera.PiCamera(resolution=(640, 480), framerate=200, sensor_mode=7) as camera:
        camera.exposure_mode='off'
        camera.rotation=rotation
        camera.start_preview()
        time.sleep(start_filming_after)
        camera.annotate_frame_num = True
        camera.annotate_background = picamera.Color('black')
        camera.annotate_text = dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        camera.start_recording(video_filename+".h264")
        start = dt.datetime.now()
        while (dt.datetime.now() - start).seconds < stop_filming_after:
            camera.annotate_text = str(dt.datetime.now() - start)
            camera.wait_recording(0.001)
        camera.stop_recording()
        pass
        
    (
        ffmpeg
        .input(video_filename+".h264")
        .filter('fps', fps=fps, round='up')
        .output("app/static/video.mp4")
        .run(overwrite_output=True)
    )

    GPIO.add_event_detect(buttonPin, GPIO.BOTH, callback=start_film, bouncetime=200)
    return "aspa"


GPIO.add_event_detect(buttonPin, GPIO.BOTH, callback=start_film, bouncetime=200)
def cage_status():
    buttonState = GPIO.input(buttonPin)
    if buttonState == False:
        GPIO.output(ledPin, GPIO.HIGH)
        return "Stängd"
    else:
        GPIO.output(ledPin, GPIO.LOW)
        return "Öppen"
        

@app.route("/", methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        rotation = request.form.get('rotation')
    #cage_status = cage_status()
    return render_template('index.html', cage_status=cage_status())


@app.route("/video")
def video():
    return render_template('video.html')


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
        pass
    my_stream.seek(0)
    return send_file(my_stream, mimetype='image/jpeg')

@app.route('/camera_settings', methods=['GET', 'POST'])
def camera_settings():
    if request.method == 'GET':
        return rotation
    if request.method == 'POST':
        rotation = request.form.get('rotation')
