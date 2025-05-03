import io
import os
import time

import cv2
import libcamera
from picamera2 import MappedArray, Picamera2
from picamera2.encoders import MJPEGEncoder
from picamera2.outputs import FileOutput

from eliot import start_action
import threading

from app.constants import (RACE_DIRECTORY_BASE, STATIC_DIRECTORY,
                           TIMESTAMP_COLOUR, TIMESTAMP_FONT, TIMESTAMP_ORIGIN,
                           TIMESTAMP_SCALE, TIMESTAMP_THICKNESS)


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


class Camera:
    """
    Represents a camera used for recording races and capturing photos.
    """

    def __init__(self, frames_per_second=100, flip_image=False, resolution=(1332, 990)):
        """
        Initializes a Camera object.

        Args:
            frames_per_second (int): The desired frames per second for recording.
            flip_image (bool): Whether to flip the recorded image horizontally and vertically.
            resolution (tuple): The resolution of the recorded image (width, height).
        """
        self.picam2 = Picamera2()

        frame_duration_limit = int(1000000 / frames_per_second)

        video_config = self.picam2.create_video_configuration(
            transform=libcamera.Transform(hflip=flip_image, vflip=flip_image),
            main={"size": resolution, "format": "YUV420"},  # More efficient format for high FPS
            buffer_count=16,  # Further increased buffer count to handle frame processing
            encode="main",  # Encode from the main stream
            sensor={"output_size": resolution, "bit_depth": 8},  # Use 8-bit depth
            controls={
                "FrameDurationLimits": (frame_duration_limit, frame_duration_limit),
                "FrameRate": frames_per_second,
                "AeEnable": True,
                "AeExposureMode": libcamera.controls.AeExposureModeEnum.Short,
                "AeConstraintMode": libcamera.controls.AeConstraintModeEnum.Highlight,
                "AeFlickerMode": libcamera.controls.AeFlickerModeEnum.Off,
                "AeMeteringMode": libcamera.controls.AeMeteringModeEnum.CentreWeighted,
                "AwbEnable": True 
            },
            queue=8  # Further increased queue size for smoother processing
        )
        self.picam2.configure(video_config)
        self.picam2.start()

    def start_camera(self):
        """
        Start the camera.
        """
        self.picam2.start()

    def apply_timestamp(self, frame, race_start_time):
        """
        Apply a timestamp to the given frame based on the race start time.
        The timestamp is calculated as the difference between the current time and the race start time.

        Args:
            frame: The frame to apply the timestamp to.
            race_start_time: The start time of the race.
        """
        timestamp = f"{(time.monotonic_ns() - race_start_time)/1e9:0>5.2f}"
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

    def start_film(
        self,
        current_race,
        race_start_time,
        start_filming_after,
        stop_filming_after,
        callback_func,
    ):
        """
        Start recording the race and apply timestamps to the frames.
        The recording starts after the specified start_filming_after time
        and stops after the specified stop_filming_after time.

        Args:
            current_race: The current race object.
            race_start_time: The start time of the race.
            start_filming_after: The time to wait before starting the recording.
            stop_filming_after: The time to stop the recording after starting.
            callback_func: The callback function to be called after the recording stops.
        """
        with start_action(action_type="start_film") as action:
            self.picam2.pre_callback = lambda frame: self.apply_timestamp(
                frame, race_start_time
            )
            encoder = MJPEGEncoder(10000000)
            race_directory = (
                STATIC_DIRECTORY + RACE_DIRECTORY_BASE + current_race.start_time
            )
            os.makedirs(race_directory)
            output = SplitFrames(directory=race_directory)

            # race_start_time is a monotonic time
            start_delay = (time.monotonic_ns() - race_start_time)/1e9
            time.sleep(start_filming_after - start_delay)
            action.log(message_type="debug", message="Start recording")
            self.picam2.start_recording(encoder, FileOutput(output))
            time.sleep(stop_filming_after - start_delay)
            if self.picam2.started:
                callback_func(current_race)
                action.log(message_type="debug", message="Recording stopped")
            else:
                action.log(message_type="warn", message="Recording already stopped")

    def stop_film(self):
        """
        Stop the recording.
        """
        start_action(action_type="stop_film")
        self.picam2.stop_recording()
        self.picam2.pre_callback = None

    def get_video_stream(self):
        """
        Stream video from the camera.
        
        Returns:
            A generator that yields JPEG frames suitable for MJPEG streaming.
        """
        
        class StreamingOutput(io.BufferedIOBase):
            def __init__(self):
                self.frame = None
                self.condition = threading.Condition()
            
            def write(self, buf):
                if buf.startswith(b'\xff\xd8'):
                    with self.condition:
                        self.frame = buf
                        self.condition.notify_all()
                return len(buf)
        
        output = StreamingOutput()
        encoder = MJPEGEncoder(10000000)
        
        # Start recording to our streaming output
        self.picam2.start_recording(encoder, FileOutput(output))
        
        if not self.picam2.started:
            self.picam2.start()

        while True:
            with output.condition:
                output.condition.wait()
                time.sleep(0.04) # Add a delay between frames to slow down the stream
                if output.frame is None:
                    continue
                frame = output.frame
            
            # Yield in a format suitable for MJPEG streaming
            yield (b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    def flip_image(self, flip_image):
        """
        Flip the recorded image horizontally and vertically.

        Args:
            flip_image (bool): Whether to flip the image.
        """
        camera_config = self.picam2.camera_configuration()
        if camera_config["transform"].hflip != flip_image:
            camera_config["transform"] = libcamera.Transform(
                hflip=flip_image, vflip=flip_image
            )
            self.picam2.stop()
            self.picam2.configure(camera_config)
            self.picam2.start()