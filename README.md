# METAR-RasPi

Display ICAO METAR weather data with a Raspberry Pi

## Basic Setup

This project requires Python 3.6+ to run the `avwx` library. Run these commands to see if you have it already. Whichever one prints 3.6+, use that.

```bash
python -V
python3 -V
python3.6 -V
```

If you're running this on a Raspberry Pi that does not yet have 3.6+ on it, you can find [instructions here](https://gist.github.com/dschep/24aa61672a2092246eaca2824400d37f).

## Screen

This version runs the METAR program on a touchscreen display.

Supported displays:

- Adafruit 320x240 2.8" TFT+Touchscreen - [Demo](http://youtu.be/tn1fOuBUiiI) / [Product](http://www.adafruit.com/products/1601) / [Guide](https://learn.adafruit.com/adafruit-pitft-28-inch-resistive-touchscreen-display-raspberry-pi)

However, the program can be run on any screen or computer in its own window for development purposes.

### Running

Install the dependancies using the Python version from above.

```bash
python3.6 -m pip install avwx-engine~=0.11.6 pygame~=1.9.3
```

Then just run the screen file to boot the display.

```bash
python3.6 screen.py
```

On the main display, pressing the RMK, WX, WX/RMK displays more METAR information. Pressing the gear displays more options.
