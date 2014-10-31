METAR-RasPi
===========

####Display ICAO METAR weather data with a Raspberry Pi and Adafruit displays

Michael duPont - [https://mdupont.com](https://mdupont.com)

Python 3.2.3 - Raspberry Pi (Raspbian)

Download: `git clone https://github.com/flyinactor91/METAR-RasPi`

-----------

Program auto-updates METAR data for selected station

Option to log all displayed METAR data for further optimization

* Launch at start-up using "sudo python /home/pi/(path)/mscreen.py >> /home/pi/(path)/METARlog.txt 2>> /home/pi/(path)/METARerror.txt"

Optimized for US, Canada, Bahamas, and Mexico reporting stations

Settings for both screen and plate can be found in mlogic.py  
Screen and plate specific settings found in their own files

Note for Class D airports with regular towered hours:  
"Most Recent" data older than six hours is returned as "No data" by the server. While a running program will continue to show the last available METAR, a first run will not be able to use that station until a new report is issued.

-----------

####METAR Screen

METAR Screen Demonstration - Soon to come

Designed for the Adafruit 320x240 2.8" TFT+Touchscreen for Raspberry Pi - [http://www.adafruit.com/products/1601](http://www.adafruit.com/products/1601).  
However, the program can be run on any screen or computer in its own 320x240 window.

Tutorial for screen drivers and/or Raspian distro - [https://learn.adafruit.com/adafruit-pitft-28-inch-resistive-touchscreen-display-raspberry-pi](https://learn.adafruit.com/adafruit-pitft-28-inch-resistive-touchscreen-display-raspberry-pi)

On the main display, pressing the RMK, WX, WX/RMK displays more METAR information. Pressing the gear displays more options.

Options to shutdown on exit and start in dark-mode

-----------

####METAR Plate

METAR Plate Demonstration - [http://youtu.be/Pni-CPXJ2RM](http://youtu.be/Pni-CPXJ2RM)

Uses Adafruit RGB Negative 16x2 LCD - [https://www.adafruit.com/product/1110](https://www.adafruit.com/product/1110)

Software library for Adafruit LCD Plate - [https://github.com/adafruit/Adafruit-Raspberry-Pi-Python-Code/](https://github.com/adafruit/Adafruit-Raspberry-Pi-Python-Code/)

You might need this tutorial to unlock your Pi's i2c and smbus - [https://learn.adafruit.com/adafruits-raspberry-pi-lesson-4-gpio-setup](https://learn.adafruit.com/adafruits-raspberry-pi-lesson-4-gpio-setup)

Use plate keypad to select ICAO station/airport iden to display METAR data

* Left/Right - Choose position

* Up/Down - Choose character A-9

* Select - Confirm station iden

LCD panel now displays current METAR data (pulled from aviationweather.gov)

* Line1 - IDEN HHMMZ BA.RO

* Line2 - Rest of METAR report

LCD backlight indicates current Flight Rules

* Green - VFR

* Blue - MVFR

* Red - IFR

* Violet - LIFR

At the end of a line scroll:

* Holding select button displays iden selection screen

* Holding left and right buttons gives option to shutdown the Pi

* Shutdown option also available during station selection
