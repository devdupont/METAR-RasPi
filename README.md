METAR-RasPi
===========

####Display ICAO METAR weather data with a Raspberry Pi and Adafruit LCD plate

Michael duPont - [https://mdupont.com](https://mdupont.com)

Python 3.2.3 - Raspberry Pi (Raspbian)

Download: `git clone https://github.com/flyinactor91/METAR-RasPi`

-----------

Demonstration on YouTube - [http://youtu.be/Pni-CPXJ2RM](http://youtu.be/Pni-CPXJ2RM)

Uses Adafruit RGB Negative 16x2 LCD - [https://www.adafruit.com/product/1110](https://www.adafruit.com/product/1110)

Software library for Adafruit LCD Plate - [https://github.com/adafruit/Adafruit-Raspberry-Pi-Python-Code/](https://github.com/adafruit/Adafruit-Raspberry-Pi-Python-Code/)

You might need this tutorial to unlock your Pi's i2c and smbus - [https://learn.adafruit.com/adafruits-raspberry-pi-lesson-4-gpio-setup](https://learn.adafruit.com/adafruits-raspberry-pi-lesson-4-gpio-setup)

Program auto-updates METAR data for selected station

Option to log all displayed METAR data for further optimization

Optimized for US, Canada, Bahamas, and Mexico reporting stations

-----------

####Instructions

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

Holding select button at the end of a line scroll displays iden selection screen
