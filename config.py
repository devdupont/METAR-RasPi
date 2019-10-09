"""
Michael duPont - michael@mdupont.com
config.py - Shared METAR display settings
"""

import json
import logging
from os import path
from pathlib import Path

# Size of the screen. Loads the layout from "./screen_settings"
layout = "320x240"

LOC = Path(path.abspath(path.dirname(__file__)))
layout = LOC / "screen_settings" / f"{layout}.json"
layout = json.load(layout.open())

# Seconds between server pings
update_interval = 600

# Seconds between connection retries
timeout_interval = 60

# Set log level - CRITICAL, ERROR, WARNING, INFO, DEBUG
log_level = logging.DEBUG

# Send METAR Pi logs to a file. Ex: "output.log"
log_file = None

# Set to True to shutdown the Pi when exiting the program
shutdown_on_exit = False

# ------- Plate Settings ------- #

# Seconds between plate button reads
button_interval = 0.2

# Seconds between row 2 char scroll
scroll_interval = 0.5

# Remarks section in scroll line
include_remarks = False

# ------- Screen Settings ------ #

# Run the program fullscreen or windowed
fullscreen = True

# Hide the mouse on a touchscreen
hide_mouse = True

# Clock displays UTC or local time
clock_utc = True
