
from flask import render_template, send_file, request
import datetime as dt
import io
import time
import picamera
import RPi.GPIO as GPIO
import ffmpeg

from app import app

rotation = 180
start_filming_after = 7
stop_filming_after = 20
fps = 200

# GPIO.setmode(GPIO.BOARD)
# ledPin = 12
# buttonPin = 16
# GPIO.setup(ledPin, GPIO.OUT)
# GPIO.setup(buttonPin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def start_film(channel):
    #buttonState = GPIO.input(buttonPin)
    #if buttonState == False:
    #    GPIO.output(ledPin, GPIO.HIGH)
    #    return

    #GPIO.remove_event_detect(channel)
    #GPIO.output(ledPin, GPIO.LOW)

    video_filename= 'app/static/' + dt.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    with picamera.PiCamera(resolution=(640, 480), framerate=fps, sensor_mode=7) as camera:
        camera.exposure_mode='off'
        camera.rotation=rotation
        camera.start_preview()
        start = dt.datetime.now()
        time.sleep(start_filming_after)
        camera.annotate_frame_num = True
        camera.annotate_background = picamera.Color('black')
        camera.start_recording(PtsOutput(camera, video_filename + ".h264", 'pts.txt'), format='h264')
        camera.wait_recording(stop_filming_after - start_filming_after)
        camera.stop_recording()
        pass
        
    (
        ffmpeg
        .input(video_filename+".h264")
        .output("app/static/race/"+video_filename+"_%04d.png")
        .run(overwrite_output=True)
    )

    #GPIO.add_event_detect(buttonPin, GPIO.BOTH, callback=start_film, bouncetime=200)
    return video_filename[4:]


class PtsOutput(object):
    def __init__(self, camera, video_filename, pts_filename):
        self.camera = camera
        self.video_output = io.open(video_filename, 'wb')
        self.pts_output = io.open(pts_filename, 'w')
        self.start_time = None

    def write(self, buf):
        self.video_output.write(buf)
        if self.camera.frame.complete and self.camera.frame.timestamp:
            if self.start_time is None:
                self.start_time = self.camera.frame.timestamp
                self.pts_output.write('# timecode format v2\n')
                print(buf)
            self.pts_output.write('%f\n' % ((self.camera.frame.timestamp - self.start_time) / 1000000.0))

        
        def flush(self):    
            self.video_output.flush()
            self.pts_output.flush()
            
        def close(self):
            self.video_output.close()
            self.pts_output.close()    

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
    return '<html><body><a href="' + start_film(20) + '">Ladda ner video</a></body></html>'
    #return index()

@app.route('/camera')
def take_photo():
    # Create an in-memory stream
    my_stream = io.BytesIO()
    with picamera.PiCamera() as camera:
        camera.start_preview()
        # Camera warm-up time
        time.sleep(2)
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
