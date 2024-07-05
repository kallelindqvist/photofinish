
from flask import render_template, send_file, request
import datetime as dt
import io
import time
import RPi.GPIO as GPIO
import fnmatch
import os
import glob
import cv2
from picamera2.encoders import MJPEGEncoder
from picamera2 import MappedArray
from picamera2.outputs import FileOutput

from app import app, picam2, models, db

# GPIO.setmode(GPIO.BOARD)
# ledPin = 12
# buttonPin = 16
# GPIO.setup(ledPin, GPIO.OUT)
# GPIO.setup(buttonPin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

startiest_time = dt.datetime.now()
colour = (255, 255, 255)
origin = (0, 30)
font = cv2.FONT_HERSHEY_PLAIN
scale = 2
thickness = 2 

class SplitFrames(io.BufferedIOBase):
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

def apply_timestamp(request):
    timestamp = str(dt.datetime.now() - startiest_time)
    with MappedArray(request, "main") as m:
        cv2.putText(m.array, timestamp, origin, font, scale, colour, thickness)


def start_film(channel):
    #buttonState = GPIO.input(buttonPin)
    #if buttonState == False:
    #    GPIO.output(ledPin, GPIO.HIGH)
    #    return

    #GPIO.remove_event_detect(channel)
    #GPIO.output(ledPin, GPIO.LOW)
    
    for f in glob.glob("app/static/race/image_*.jpg"):
        os.remove(f)

    picam2.pre_callback = apply_timestamp
    encoder = MJPEGEncoder(10000000)
    output = SplitFrames()
    startiest_time = dt.datetime.now()
    picam2.start_recording(encoder, FileOutput(output))
    time.sleep(5)
    picam2.stop_recording()
    #GPIO.add_event_detect(buttonPin, GPIO.BOTH, callback=start_film, bouncetime=200)

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
    config = models.Config.query.first()
    if request.method == 'POST':
        config.rotation=request.form.get('rotation')
        config.start_filming_after=request.form.get('start_filming_after')
        config.stop_filming_after=request.form.get('stop_filming_after')
        config.frames_per_second=request.form.get('frames_per_second')
        db.session.commit()
    #cage_status = cage_status()
    return render_template('index.html', cage_status=cage_status(), start_filming_after=config.start_filming_after, stop_filming_after=config.stop_filming_after)

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
    picam2.capture_file(my_stream, format='jpeg')
    my_stream.seek(0)
    return send_file(my_stream, mimetype='image/jpeg')
