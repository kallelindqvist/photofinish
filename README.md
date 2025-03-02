# photofinish

## Requirements

python3
python3-libcamera

## Install
python3 -m venv venv
source --system-site-packages venv/bin/venv
pip install -r requirements.txt

## Run
gunicorn --threads 3 -b 0.0.0.0:5000 app:app

## Run on start up
sudo cp system/systemd/photofinish.service /lib/systemd/system/photofinish.service
sudo chmod 644 /lib/systemd/system/photofinish.service
sudo systemctl enable photofinish

Install nginx and add system/nginx/photofinish to /etc/nginx/available-site