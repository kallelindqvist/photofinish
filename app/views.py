
from flask import render_template, send_file, request, url_for
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
import libcamera 

from app import app, picam2, models, db

STATIC_DIRECTORY = 'app/static/'
RACE_DIRECTORY_BASE = 'race/'
RACE_DIRECTORY_LATEST = STATIC_DIRECTORY + RACE_DIRECTORY_BASE + 'latest'

GPIO.setmode(GPIO.BCM)
ledPin = 18
buttonPin = 13
GPIO.setup(ledPin, GPIO.OUT)
GPIO.setup(buttonPin, GPIO.IN, pull_up_down=GPIO.PUD_UP)


def update_cage_status(pin):
    buttonState = GPIO.input(buttonPin)
    if buttonState == False:
        # Cage is closed
        GPIO.output(ledPin, GPIO.HIGH)
        
    #Cage is open
    GPIO.output(ledPin, GPIO.LOW)
    with app.app_context():
        current_race = models.Race.query.filter_by(running=True).first()
        config = models.Config.query.first()
        if current_race is not None:
            start_film(current_race, config.start_filming_after, config.stop_filming_after)
        return


GPIO.add_event_detect(buttonPin, GPIO.BOTH, callback=update_cage_status, bouncetime=200)

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
            self.output = io.open(RACE_DIRECTORY_LATEST + '/image_%04d.jpg' % self.frame_num, 'wb')
        self.output.write(buf)

def apply_timestamp(request):
    timestamp = str(dt.datetime.now() - race_start_time)
    with MappedArray(request, "main") as m:
        cv2.putText(m.array, timestamp, origin, font, scale, colour, thickness)


def start_film(current_race, start_filming_after, stop_filming_after):
    global race_start_time
    race_start_time = dt.datetime.now()

    picam2.pre_callback = apply_timestamp
    encoder = MJPEGEncoder(10000000)
    output = SplitFrames()

    time.sleep(start_filming_after)
    picam2.start_recording(encoder, FileOutput(output))
    time.sleep(stop_filming_after)
    picam2.stop_recording() 

    # Wait a while to make sure the recording is stopped
    time.sleep(2)
    if current_race is not None:
        current_race_directory = STATIC_DIRECTORY + RACE_DIRECTORY_BASE + current_race.start_time
        os.rename(RACE_DIRECTORY_LATEST, current_race_directory)
        current_race.running = False
        db.session.commit()
    

def cage_status():
    buttonState = GPIO.input(buttonPin)
    if buttonState == False:
        return "Stängd"
    else:
        return "Öppen"
        

@app.route("/", methods=['GET', 'POST'])
def index():
    config = models.Config.query.first()
    current_race = models.Race.query.filter_by(running=True).first()
    if request.method == 'POST':
        if bool(request.form.get('reset_settings')) == True:
            db.session.delete(config)
            db.session.commit()
            db.session.add(models.Config())
            db.session.commit()
        elif bool(request.form.get('start_race')) == True:
            if current_race is not None:
                print("Race is already running")
            else:
                current_race = models.Race()
                current_race.start_time = dt.datetime.now().replace(microsecond=0).isoformat()
                current_race.running = True
                db.session.add(current_race)
                db.session.commit()

        elif bool(request.form.get('stop_race')) == True:
            if current_race is None:
                print("No race is running")
            else:
                current_race.running = False
                db.session.commit()
        else:
            config.flip_image = bool(request.form.get('flip_image'))
            config.start_filming_after=request.form.get('start_filming_after')
            config.stop_filming_after=request.form.get('stop_filming_after')
            db.session.commit()
            camera_config = picam2.camera_configuration()
            if camera_config['transform'].hflip != config.flip_image:
                camera_config['transform'] = libcamera.Transform(hflip=config.flip_image, vflip=config.flip_image)
                picam2.stop()
                picam2.configure(camera_config)
                picam2.start()

    race_active = "Nej"
    races = models.Race.query.filter_by(running=False).all()
    if current_race is not None and current_race.running:
        race_active = "Ja"
        image_src = url_for('static', filename='active_race.png')
    else:
        if races is not None and len(races) > 0:
            image_src = url_for('static', filename=RACE_DIRECTORY_BASE + races[0].start_time + '/image_0001.jpg')
        else:
            image_src = url_for("take_photo")
    return render_template('index.html', cage_status=cage_status(), flip_image=config.flip_image, image_src=image_src, race_active=race_active, races=races, start_filming_after=config.start_filming_after, stop_filming_after=config.stop_filming_after)

@app.route("/start")
def start():
    start_film(None, 0, 10)
    return images()

@app.route("/images")
def images():
    file_count = len(fnmatch.filter(os.listdir('app/static/race'), 'image*.jpg'))
    return render_template('images.html', max=file_count)

@app.route('/camera')
def take_photo():
    # Create an in-memory stream
    my_stream = io.BytesIO()
    picam2.capture_file(my_stream, format='jpeg')
    my_stream.seek(0)
    return send_file(my_stream, mimetype='image/jpeg')
