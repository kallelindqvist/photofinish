import os

from flask import Flask

# create and configure the app
app = Flask(__name__)

# Import views
from app import views
