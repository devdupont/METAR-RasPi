"""
Michael duPont - michael@mdupont.com
plate.py - Display ICAO METAR weather data with a Raspberry Pi and Adafruit LCD plate

Use plate keypad to select ICAO station/airport ident to display METAR data
  Left/Right - Choose position
  Up/Down    - Choose character A-9
  Select     - Confirm station ident
LCD panel now displays current METAR data (pulled from aviationweather.gov)
  Line1      - IDEN HHMMZ FTRL
  Line2      - Rest of METAR report
LCD backlight indicates current Flight Rules
  Green      - VFR
  Blue       - MVFR
  Red        - IFR
  Violet     - LIFR
At the end of a line scroll:
  Holding select button displays ident selection screen
  Holding left and right buttons gives option to shutdown the Pi

Uses Adafruit RGB Negative 16x2 LCD - https://www.adafruit.com/product/1110
Software library for LCD plate - https://github.com/adafruit/Adafruit-Raspberry-Pi-Python-Code
"""

# stdlib
import os
import sys
from time import sleep

# library
import avwx
import Adafruit_CharLCD as LCD

# module
import common
import config as cfg
from common import IDENT_CHARS, logger

# String replacement for Line2 (scrolling data)
replacements = [
    ["00000KT", "CALM"],
    ["00000MPS", "CALM"],
    ["10SM", "UNLM"],
    ["9999", "UNLM"],
]


FR_COLORS = {"VFR": (0, 255, 0), "MVFR": (0, 0, 255), "IFR": (255, 0, 0), "LIFR": (255, 0, 255)}


class METARPlate:
    """
    Controls LCD plate display and buttons
    """

    metar: avwx.Metar
    ident: [str]
    lcd: LCD.Adafruit_CharLCDPlate
    cols: int = 16
    rows: int = 2

    def __init__(self, station: str, size: (int, int) = None):
        logger.debug("Running init")
        try:
            self.metar = avwx.Metar(station)
        except avwx.exceptions.BadStation:
            self.metar = avwx.Metar("KJFK")
        self.ident = common.station_to_ident(station)
        if size:
            self.cols, self.rows = size
        self.lcd = LCD.Adafruit_CharLCDPlate(cols=self.cols, lines=self.rows)
        self.lcd.clear()

    @property
    def station(self) -> str:
        """
        The current station
        """
        return common.ident_to_station(self.ident)

    @classmethod
    def from_session(cls, session: dict):
        """
        Returns a new Screen from a saved session
        """
        station = session.get("station", "KJFK")
        return cls(station)

    def export_session(self, save: bool = True):
        """
        Saves or returns a dictionary representing the session's state
        """
        session = {"station": self.station}
        if save:
            common.save_session(session)
        return session

    def __handle_select(self):
        """
        Select METAR station
        Use LCD to update 'ident' values
        """
        cursorPos = 0
        selected = False

        self.lcd.clear()
        self.lcd.set_cursor(0, 0)
        self.lcd.message("4-Digit METAR")
        # Display default iden
        for row in range(4):
            self.lcd.set_cursor(row, 1)
            self.lcd.message(IDENT_CHARS[self.ident[row]])
        self.lcd.set_cursor(0, 1)
        self.lcd.show_cursor(True)
        sleep(1)  # Allow finger to be lifted from select button
        # Selection loop
        while not selected:
            # Shutdown option
            if self.lcd.is_pressed(LCD.LEFT) and self.lcd.is_pressed(
                LCD.RIGHT
            ):
                self.lcd_shutdown()
                self.lcd.clear()  # If no, reset screen
                self.lcd.set_cursor(0, 0)
                self.lcd.message("4-Digit METAR")
                for row in range(4):
                    self.lcd.set_cursor(row, 1)
                    self.lcd.message(IDENT_CHARS[self.ident[row]])
                self.lcd.set_cursor(0, 1)
                self.lcd.show_cursor(True)
                sleep(1)
            # Previous char
            elif self.lcd.is_pressed(LCD.UP):
                curNum = self.ident[cursorPos]
                if curNum == 0:
                    curNum = len(IDENT_CHARS)
                self.ident[cursorPos] = curNum - 1
                self.lcd.message(IDENT_CHARS[self.ident[cursorPos]])
            # Next char
            elif self.lcd.is_pressed(LCD.DOWN):
                newNum = self.ident[cursorPos] + 1
                if newNum == len(IDENT_CHARS):
                    newNum = 0
                self.ident[cursorPos] = newNum
                self.lcd.message(IDENT_CHARS[self.ident[cursorPos]])
            # Move cursor right
            elif self.lcd.is_pressed(LCD.RIGHT):
                if cursorPos < 3:
                    cursorPos += 1
            # Move cursor left
            elif self.lcd.is_pressed(LCD.LEFT):
                if cursorPos > 0:
                    cursorPos -= 1
            # Confirm iden
            elif self.lcd.is_pressed(LCD.SELECT):
                selected = True
            self.lcd.set_cursor(cursorPos, 1)
            sleep(cfg.button_interval)
        self.lcd.show_cursor(0)

    def lcd_select(self):
        """
        Display METAR selection screen on LCD
        """
        self.lcd.set_backlight(1)
        self.__handle_select()
        self.lcd.clear()
        self.lcd.message(f"{common.ident_to_station(self.ident)} selected")

    def lcd_timeout(self):
        """
        Display timeout message and sleep
        """
        logger.warning("Connection Timeout")
        self.lcd.set_backlight(1)
        self.lcd.clear()
        self.lcd.set_cursor(0, 0)
        self.lcd.message("No connection\nCheck back soon")
        sleep(cfg.timeout_interval)

    def lcd_bad_station(self):
        self.lcd.clear()
        self.lcd.set_cursor(0, 0)
        self.lcd.message("No Weather Data\nFor " + common.ident_to_station(self.ident))
        sleep(3)
        self.lcd_select()

    def lcd_shutdown(self):
        """
        Display shutdown options
        """
        selection = False
        selected = False
        self.lcd.set_backlight(1)
        self.lcd.clear()
        self.lcd.set_cursor(0, 0)
        if cfg.shutdown_on_exit:
            self.lcd.message("Shutdown the Pi?\nY N")
        else:
            self.lcd.message("Quit the program?\nY N")
        self.lcd.set_cursor(2, 1)
        self.lcd.show_cursor(True)
        sleep(1)  # Allow finger to be lifted from LR buttons
        # Selection loop
        while not selected:
            # Move cursor right
            if self.lcd.is_pressed(LCD.RIGHT) and selection:
                self.lcd.set_cursor(2, 1)
                selection = False
            # Move cursor left
            elif self.lcd.is_pressed(LCD.LEFT) and not selection:
                self.lcd.set_cursor(0, 1)
                selection = True
            # Confirm selection
            elif self.lcd.is_pressed(LCD.SELECT):
                selected = True
            sleep(cfg.button_interval)
        self.lcd.show_cursor(False)
        if not selection:
            return None
        self.lcd.clear()
        self.lcd.set_backlight(0)
        if cfg.shutdown_on_exit:
            os.system("shutdown -h now")
        sys.exit()

    def create_display_data(self):
        """
        Returns tuple of display data
        Line1: IDEN HHMMZ FTRL
        Line2: Rest of METAR report
        BLInt: Flight rules backlight color
        """
        data = self.metar.data
        line1 = f"{data.station} {data.time.repr} {data.flight_rules}"
        line2 = data.raw.split(" ", 2)[-1]
        if not cfg.include_remarks:
            line2 = line2.replace(data.remarks, "").strip()
        for src, rep in replacements:
            line2 = line2.replace(src, rep).strip()
        return line1, line2, FR_COLORS.get(data.flight_rules)

    def display_metar(self, line1: str, line2: str) -> float:
        """
        Display METAR data on LCD plate
        Returns approx time elapsed
        """
        self.lcd.clear()
        # Write row 1
        self.lcd.set_cursor(0, 0)
        self.lcd.message(line1)
        # Scroll row 2
        timeElapsed = 0.0
        if line2 <= self.cols:  # No need to scroll line
            self.lcd.set_cursor(0, 1)
            self.lcd.message(line2)
        else:
            self.lcd.set_cursor(0, 1)
            self.lcd.message(line2[: self.cols])
            sleep(2)  # Pause to read line start
            timeElapsed += 2
            for i in range(1, len(line2) - (self.cols - 1)):
                self.lcd.set_cursor(0, 1)
                self.lcd.message(line2[i : i + self.cols])
                sleep(cfg.scroll_interval)
                timeElapsed += cfg.scroll_interval
        sleep(2)  # Pause to read line / line end
        return timeElapsed + 2

    def update_metar(self) -> bool:
        """
        Update the METAR data and handle any errors
        """
        try:
            self.metar.update()
        except avwx.exceptions.BadStation:
            self.lcd_bad_station()
        except ConnectionError:
            self.lcd_timeout()
        except:
            logger.exception()
            return False
        return True

    def lcd_main(self):
        """
        Display data until the elapsed time exceeds the update interval
        """
        line1, line2, color = self.create_display_data()
        logger.info("\t{}\n\t{}" % line1, line2)
        # Set LCD color to match current flight rules
        self.lcd.set_color(*color) if color else self.lcd.set_backlight(1)
        total_time = 0
        # Loop until program fetches new data
        while total_time < cfg.update_interval:
            # Cycle display one loop. Add elapsed time to total time
            total_time += self.display_metar(line1, line2)
            # Go to selection screen if select button pressed
            if self.lcd.is_pressed(LCD.SELECT):
                self.lcd_select()
                break
            # Go to shutdown screen if left and right buttons pressed
            elif self.lcd.is_pressed(LCD.LEFT) and self.lcd.is_pressed(LCD.RIGHT):
                self.lcd_shutdown()


def main() -> int:
    logger.debug("Booting")
    plate = METARPlate.from_session(common.load_session())
    # plate.lcd_select()
    while True:
        if not plate.update_metar():
            return 1
        logger.info(plate.metar.raw)
        plate.lcd_main()
    return 0


if __name__ == "__main__":
    main()
