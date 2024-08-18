from .logger import logger
from .common_utils import *


import os

if not os.path.exists(path="sessions"):
    os.mkdir(path="sessions")
