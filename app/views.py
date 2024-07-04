
from flask import render_template, send_file, request
import datetime as dt
import io
import time
import picamera
import RPi.GPIO as GPIO
import fnmatch
import os
import glob

from app import app

rotation = 180
start_filming_after = 7
stop_filming_after = 20
fps = 120
sensor_mode = 6
resolution= (640, 480)

# GPIO.setmode(GPIO.BOARD)
# ledPin = 12
# buttonPin = 16
# GPIO.setup(ledPin, GPIO.OUT)
# GPIO.setup(buttonPin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

class SplitFrames(object):
    def __init__(self):
        self.frame_num = 0
        self.output = None

    def write(self, buf):
        if buf.startswith(b'\xff\xd8'):
            # Start of new frame; close the old one (if any) and
            # open a new output
            if self.output:
                self.output.close()
            self.frame_num += 1
            self.output = io.open('app/static/race/image_%04d.jpg' % self.frame_num, 'wb')
        self.output.write(buf)


def start_film(channel):
    #buttonState = GPIO.input(buttonPin)
    #if buttonState == False:
    #    GPIO.output(ledPin, GPIO.HIGH)
    #    return

    #GPIO.remove_event_detect(channel)
    #GPIO.output(ledPin, GPIO.LOW)
    
    for f in glob.glob("app/static/race/image_*.jpg"):
        os.remove(f)

    filename = dt.datetime.now().strftime('%Y-%m-%dT%H%M%S')
    video_filename= 'app/static/' + filename + ".mjpeg"
    with picamera.PiCamera(resolution=resolution, framerate=fps, sensor_mode=sensor_mode) as camera:
        camera.exposure_mode='off'
        camera.rotation=rotation
        camera.start_preview()
        time.sleep(start_filming_after)
        output = SplitFrames()
        start = dt.datetime.now()
        camera.annotate_background = picamera.Color('black')
        camera.annotate_text = str(dt.datetime.now() - start)
        camera.start_recording(output, format='mjpeg')
        while (dt.datetime.now() - start).seconds < (stop_filming_after - start_filming_after):
            camera.annotate_text = str(dt.datetime.now() - start)
            camera.wait_recording(0.001)
        camera.stop_recording()
        finish = dt.datetime.now()
        print('Captured %d frames at %.2ffps' % (
            output.frame_num,
            output.frame_num / (finish - start).total_seconds()))


    #GPIO.add_event_detect(buttonPin, GPIO.BOTH, callback=start_film, bouncetime=200)
    return video_filename[4:]


# GPIO.add_event_detect(buttonPin, GPIO.BOTH, callback=start_film, bouncetime=200)
def cage_status():
    #buttonState = GPIO.input(buttonPin)
    buttonState = False
    if buttonState == False:
        #GPIO.output(ledPin, GPIO.HIGH)
        return "Stängd"
    else:
        #GPIO.output(ledPin, GPIO.LOW)
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

@app.route("/start")
def start():
    start_film(20)
    return images()

@app.route("/images")
def images():
    print(os.listdir('.'))
    file_count = len(fnmatch.filter(os.listdir('app/static/race'), 'image*.jpg'))
    return render_template('images.html', max=file_count)

@app.route('/camera')
def take_photo():
    # Create an in-memory stream
    my_stream = io.BytesIO()
    with picamera.PiCamera() as camera:
        camera.start_preview()
        # Camera warm-up time
        time.sleep(2)
        camera.resolution=resolution
        camera.sensor_mode = sensor_mode
        camera.rotation = rotation
        camera.capture(my_stream, format='jpeg', use_video_port=True)
        pass
    my_stream.seek(0)
    return send_file(my_stream, mimetype='image/jpeg')

@app.route('/camera_settings', methods=['GET', 'POST'])
def camera_settings():
    if request.method == 'GET':
        return rotation
    if request.method == 'POST':
        rotation = request.form.get('rotation')
