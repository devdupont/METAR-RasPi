"""
Michael duPont - michael@mdupont.com
config.py - Shared METAR display settings
"""

import logging

# Screen size (width, height) in pixels
size = (320, 240) # Adafruit 2.8" screen
# size = (1, 1) # Pi Foundation 7" screen

# Seconds between server pings
update_interval = 600

# Seconds between connection retries
timeout_interval = 60

# Set log level - CRITICAL, ERROR, WARNING, INFO, DEBUG
log_level = logging.DEBUG

# Send METAR Pi logs to a file
log_file = None

# Set to True to shutdown the Pi when exiting the program
shutdown_on_exit = False

#------- Plate Settings -------#

# Seconds between plate button reads
button_interval = 0.2

# Seconds between row 2 char scroll
scroll_interval = 0.5     

# Replace row 1 altimeter with NOSIG if present in report
display_nosig = False

# Remarks section in scroll line
include_remarks = False

#------- Screen Settings ------#

#Set to False if not running on a RasPi. Changes env settings
on_pi = False
