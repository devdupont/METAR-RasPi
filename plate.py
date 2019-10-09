"""
Michael duPont - michael@mdupont.com
plate.py - Display ICAO METAR weather data with a Raspberry Pi and Adafruit LCD plate

Use plate keypad to select ICAO station/airport iden to display METAR data
  Left/Right - Choose position
  Up/Down    - Choose character A-9
  Select     - Confirm station iden
LCD panel now displays current METAR data (pulled from aviationweather.gov)
  Line1      - IDEN HHMMZ BA.RO   or   IDEN HHMMZ NOSIG
  Line2      - Rest of METAR report
LCD backlight indicates current Flight Rules
  Green      - VFR
  Blue       - MVFR
  Red        - IFR
  Violet     - LIFR
At the end of a line scroll:
  Holding select button displays iden selection screen
  Holding left and right buttons gives option to shutdown the Pi

Uses Adafruit RGB Negative 16x2 LCD - https://www.adafruit.com/product/1110
Software library for LCD plate - https://github.com/adafruit/Adafruit-Raspberry-Pi-Python-Code
"""

# stdlib
import os
import sys
from copy import copy
from time import sleep

# library
import avwx
from Adafruit_CharLCDPlate import Adafruit_CharLCDPlate

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


FR_COLORS = {"VFR": "GREEN", "MVFR": "BLUE", "IFR": "RED", "LIFR": "VIOLET"}


class METARPlate:
    """
    """

    metar: avwx.Metar
    ident: [str]
    old_ident: [str]
    lcd: Adafruit_CharLCDPlate
    num_cols: int = 16
    num_rows: int = 2

    def __init__(self, station: str, size: (int, int) = None):
        logger.debug("Running init")
        try:
            self.metar = avwx.Metar(station)
        except avwx.exceptions.BadStation:
            self.metar = avwx.Metar("KJFK")
        self.ident = common.station_to_ident(station)
        self.old_ident = copy(self.ident)
        if size:
            self.num_cols, self.num_rows = size
        self.lcd = Adafruit_CharLCDPlate()
        self.lcd.begin(self.num_cols, self.num_rows)
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
        self.lcd.setCursor(0, 0)
        self.lcd.message("4-Digit METAR")
        # Display default iden
        for row in range(4):
            self.lcd.setCursor(row, 1)
            self.lcd.message(IDENT_CHARS[self.ident[row]])
        self.lcd.setCursor(0, 1)
        self.lcd.cursor()
        sleep(1)  # Allow finger to be lifted from select button
        # Selection loop
        while not selected:
            # Shutdown option
            if self.lcd.buttonPressed(self.lcd.LEFT) and self.lcd.buttonPressed(
                self.lcd.RIGHT
            ):
                self.lcd_shutdown()
                self.lcd.clear()  # If no, reset screen
                self.lcd.setCursor(0, 0)
                self.lcd.message("4-Digit METAR")
                for row in range(4):
                    self.lcd.setCursor(row, 1)
                    self.lcd.message(IDENT_CHARS[self.ident[row]])
                self.lcd.setCursor(0, 1)
                self.lcd.cursor()
                sleep(1)
            # Previous char
            elif self.lcd.buttonPressed(self.lcd.UP):
                curNum = self.ident[cursorPos]
                if curNum == 0:
                    curNum = len(IDENT_CHARS)
                self.ident[cursorPos] = curNum - 1
                self.lcd.message(IDENT_CHARS[self.ident[cursorPos]])
            # Next char
            elif self.lcd.buttonPressed(self.lcd.DOWN):
                newNum = self.ident[cursorPos] + 1
                if newNum == len(IDENT_CHARS):
                    newNum = 0
                self.ident[cursorPos] = newNum
                self.lcd.message(IDENT_CHARS[self.ident[cursorPos]])
            # Move cursor right
            elif self.lcd.buttonPressed(self.lcd.RIGHT):
                if cursorPos < 3:
                    cursorPos += 1
            # Move cursor left
            elif self.lcd.buttonPressed(self.lcd.LEFT):
                if cursorPos > 0:
                    cursorPos -= 1
            # Confirm iden
            elif self.lcd.buttonPressed(self.lcd.SELECT):
                selected = True
            self.lcd.setCursor(cursorPos, 1)
            sleep(cfg.button_interval)
        self.lcd.noCursor()

    def lcd_select(self):
        """
        Display METAR selection screen on LCD
        """
        self.lcd.backlight(self.lcd.ON)
        self.__handle_select()
        self.lcd.clear()
        self.lcd.message(
            common.ident_to_station(self.ident) + " selected\nFetching METAR"
        )

    def lcdTimeout(self):
        """
        Display timeout message and sleep
        """
        logger.warning("Connection Timeout")
        self.lcd.backlight(self.lcd.ON)
        self.lcd.clear()
        self.lcd.setCursor(0, 0)
        self.lcd.message("No connection\nCheck back soon")
        sleep(cfg.timeout_interval)

    def lcdBadStation(self):
        self.lcd.clear()
        self.lcd.setCursor(0, 0)
        self.lcd.message("No Weather Data\nFor " + common.ident_to_station(self.ident))
        sleep(3)
        self.lcd_select()

    def lcd_shutdown(self):
        """
        Display shutdown options
        """
        selection = False
        selected = False
        self.lcd.backlight(self.lcd.ON)
        self.lcd.clear()
        self.lcd.setCursor(0, 0)
        if cfg.shutdown_on_exit:
            self.lcd.message("Shutdown the Pi?\nY N")
        else:
            self.lcd.message("Quit the program?\nY N")
        self.lcd.setCursor(2, 1)
        self.lcd.cursor()
        sleep(1)  # Allow finger to be lifted from LR buttons
        # Selection loop
        while not selected:
            # Move cursor right
            if self.lcd.buttonPressed(self.lcd.RIGHT) and selection:
                self.lcd.setCursor(2, 1)
                selection = False
            # Move cursor left
            elif self.lcd.buttonPressed(self.lcd.LEFT) and not selection:
                self.lcd.setCursor(0, 1)
                selection = True
            # Confirm selection
            elif self.lcd.buttonPressed(self.lcd.SELECT):
                selected = True
            sleep(cfg.button_interval)
        self.lcd.noCursor()
        if not selection:
            return None
        self.lcd.clear()
        self.lcd.backlight(self.lcd.OFF)
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
        return line1, line2, FR_COLORS.get(data.flight_rules, "ON")


# Display METAR data on LCD plate
# Returns approx time elapsed (float)
def displayMETAR(line1, line2, lcdLight):
    lcd.clear()
    # Set LCD color to match current flight rules
    lcd.backlight(lcdColors[lcdLight])
    # Write row 1
    lcd.setCursor(0, 0)
    lcd.message(line1)
    # Scroll row 2
    timeElapsed = 0.0
    if line2 <= numCols:  # No need to scroll line
        lcd.setCursor(0, 1)
        lcd.message(line2, lcd.TRUNCATE)
    else:
        lcd.setCursor(0, 1)
        lcd.message(line2[:numCols], lcd.TRUNCATE)
        sleep(2)  # Pause to read line start
        timeElapsed += 2
        for i in range(1, len(line2) - (numCols - 1)):
            lcd.setCursor(0, 1)
            lcd.message(line2[i : i + numCols], lcd.TRUNCATE)
            sleep(scrollInterval)
            timeElapsed += scrollInterval
    sleep(2)  # Pause to read line / line end
    return timeElapsed + 2


# Program Main
# Returns 1 if error, else 0
def lcd_main():
    lastMETAR = ""
    userSelected = True
    setup()  # Initial Setup
    lcdSelect()  # Show Ident Selection
    while True:
        METARtxt = getMETAR(ident_to_station(ident))  # Fetch current METAR
        while type(METARtxt) == int:  # Fetch data until success
            if METARtxt == 0:
                lcdTimeout()  # Bad Connection
            elif METARtxt == 1:
                if userSelected:
                    lcdBadStation()  # Invalid Station
                else:
                    logger.info("Ignoring non-user generated selection")
                    METARtxt = copy(lastMETAR)  # Server data lookup error
                    break
            else:
                return 1  # Code error
            METARtxt = getMETAR(ident_to_station(ident))
        userSelected = False
        lastMETAR = copy(METARtxt)
        logger.info(METARtxt)
        L1, L2, FR = createDisplayData(METARtxt)  # Create display data
        logger.info("\t" + L1 + "\n\t" + L2)  # Log METAR data
        totalTime = 0.0
        while totalTime < updateInterval:  # Loop until program fetches new data
            totalTime += displayMETAR(
                L1, L2, FR
            )  # Cycle display one loop. Add elapsed time to total time
            if lcd.buttonPressed(
                lcd.SELECT
            ):  # If select button pressed at end of a cycle
                lcdSelect()  # Show Ident Selection
                userSelected = True
                break  # Break to fetch new METAR
            elif lcd.buttonPressed(lcd.LEFT) and lcd.buttonPressed(
                lcd.RIGHT
            ):  # If right and left
                lcdShutdown()  # Shutdown option

    return 0


def main() -> int:
    """
    """
    plate = METARPlate.from_session(common.load_session())
    return 0


if __name__ == "__main__":
    main()
