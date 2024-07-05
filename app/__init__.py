import os
from picamera2 import Picamera2

from flask import Flask

# create and configure the app
app = Flask(__name__)

rotation = 180
start_filming_after = 7
stop_filming_after = 20
fps = 120
sensor_mode = 6
resolution= (640, 480)


picam2 = Picamera2()

video_config = picam2.create_video_configuration(
    main={"size": resolution},
    sensor={'output_size': resolution, 'bit_depth': 10},
    controls={"FrameDurationLimits": (5000,5000)}
    )
picam2.configure(video_config)
picam2.start()

# Import views
from app import views
