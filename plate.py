"""
Michael duPont - michael@mdupont.com
plate.py - Display ICAO METAR weather data with a Raspberry Pi and Adafruit LCD plate

Use plate keypad to select ICAO station/airport ident to display METAR data
  Left/Right - Choose position
  Up/Down    - Choose character A-9
  Select     - Confirm station ident
LCD panel displays current METAR data
  Line1      - IDEN HHMMZ FTRL
  Line2      - Rest of METAR report
LCD backlight indicates current Flight Rules
  Green      - VFR
  Blue       - MVFR
  Red        - IFR
  Violet     - LIFR
While on the main display
  Holding select button displays ident selection screen
While on the main and station selection display
  Holding left and right buttons gives option to quit or shutdown the Pi

Uses Adafruit RGB Negative 16x2 LCD - https://www.adafruit.com/product/1110
"""

# stdlib
import os
import sys
from time import sleep
from typing import Callable

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


FR_COLORS = {
    "VFR": (0, 255, 0),
    "MVFR": (0, 0, 255),
    "IFR": (255, 0, 0),
    "LIFR": (255, 0, 255),
}


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
        self.clear()

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

    @property
    def pressed_select(self):
        return self.lcd.is_pressed(LCD.SELECT)

    @property
    def pressed_shutdown(self):
        return self.lcd.is_pressed(LCD.LEFT) and self.lcd.is_pressed(LCD.RIGHT)

    def clear(self, reset_backlight: bool = True):
        """
        Resets the display and backlight color
        """
        if reset_backlight:
            self.lcd.set_backlight(1)
        self.lcd.clear()
        self.lcd.set_cursor(0, 0)

    def __handle_select(self):
        """
        Select METAR station
        Use LCD to update 'ident' values
        """
        cursorPos = 0
        selected = False
        self.clear()
        self.lcd.message("4-Digit METAR")
        # Display default ident
        for row in range(4):
            self.lcd.set_cursor(row, 1)
            self.lcd.message(IDENT_CHARS[self.ident[row]])
        self.lcd.set_cursor(0, 1)
        self.lcd.show_cursor(True)
        # Allow finger to be lifted from select button
        sleep(1)
        # Selection loop
        while not selected:
            # Shutdown option
            if self.pressed_shutdown:
                self.lcd_shutdown()
                self.lcd_select()
                return
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
            # Confirm ident
            elif self.pressed_select:
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
        self.export_session()
        self.metar = avwx.Metar(self.station)
        self.clear()
        self.lcd.message(f"{self.station} selected")

    def lcd_timeout(self):
        """
        Display timeout message and sleep
        """
        logger.warning("Connection Timeout")
        self.clear(True)
        self.lcd.message("No connection\nCheck back soon")
        sleep(cfg.timeout_interval)

    def lcd_bad_station(self):
        self.clear()
        self.lcd.message(f"No Weather Data\nFor {self.station}")
        sleep(3)
        self.lcd_select()

    def lcd_shutdown(self):
        """
        Display shutdown options
        """
        selection = False
        selected = False
        self.clear()
        msg = "Shutdown the Pi" if cfg.shutdown_on_exit else "Quit the program"
        self.lcd.message(f"{msg}?\nY N")
        self.lcd.set_cursor(2, 1)
        self.lcd.show_cursor(True)
        # Allow finger to be lifted from LR buttons
        sleep(1)
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
            elif self.pressed_select:
                selected = True
            sleep(cfg.button_interval)
        self.lcd.show_cursor(False)
        if not selection:
            return None
        self.clear(False)
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
        line1 = f"{data.station} {data.time.repr[2:]} {data.flight_rules}"
        line2 = data.raw.split(" ", 2)[-1]
        if not cfg.include_remarks:
            line2 = line2.replace(data.remarks, "").strip()
        for src, rep in replacements:
            line2 = line2.replace(src, rep).strip()
        return line1, line2, FR_COLORS.get(data.flight_rules)

    def __scroll_button_check(self) -> bool:
        """
        Handles any pressed buttons during main display
        """
        # Go to selection screen if select button pressed
        if self.pressed_select:
            self.lcd_select()
            return True
        # Go to shutdown screen if left and right buttons pressed
        elif self.pressed_shutdown:
            self.lcd_shutdown()
            return True
        return False

    @staticmethod
    def __sleep_with_input(
        up_to: int, handler: Callable, step: float = cfg.button_interval
    ) -> float:
        """
        Sleep for a certain amount while checking an input handler

        Returns the elapsed time or None if interrupted
        """
        elapsed = 0
        for _ in range(int(up_to / step)):
            sleep(step)
            elapsed += step
            if handler():
                return
        return elapsed

    def scroll_line(self, line: str, handler: Callable, row: int = 1) -> (float, bool):
        """
        Scroll a line on the display

        Must be given a function to handle button presses

        Returns approximate time elapsed and main refresh boolean
        """
        elapsed = 0
        if len(line) <= self.cols:
            self.lcd.set_cursor(0, row)
            self.lcd.message(line)
        else:
            self.lcd.set_cursor(0, row)
            self.lcd.message(line[: self.cols])
            try:
                elapsed += self.__sleep_with_input(2, handler)
            except TypeError:
                return elapsed, True
            for i in range(1, len(line) - (self.cols - 1)):
                self.lcd.set_cursor(0, row)
                self.lcd.message(line[i : i + self.cols])
                sleep(cfg.scroll_interval)
                elapsed += cfg.scroll_interval
                if handler():
                    return elapsed, True
        try:
            elapsed += self.__sleep_with_input(2, handler)
        except TypeError:
            return elapsed, True
        return elapsed, False

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
            logger.exception("Report Update Error")
            return False
        return True

    def lcd_main(self):
        """
        Display data until the elapsed time exceeds the update interval
        """
        line1, line2, color = self.create_display_data()
        logger.info("\t%s\n\t%s", line1, line2)
        self.clear()
        # Set LCD color to match current flight rules
        self.lcd.set_color(*color) if color else self.lcd.set_backlight(1)
        elapsed = 0
        self.lcd.message(line1)
        # Scroll line2 until update interval exceeded
        while elapsed < cfg.update_interval:
            step, refresh = self.scroll_line(line2, handler=self.__scroll_button_check)
            if refresh:
                return
            elapsed += step


def main() -> int:
    logger.debug("Booting")
    plate = METARPlate.from_session(common.load_session())
    while True:
        if not plate.update_metar():
            return 1
        logger.info(plate.metar.raw)
        plate.lcd_main()
    return 0


if __name__ == "__main__":
    main()
