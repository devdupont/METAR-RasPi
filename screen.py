"""
Michael duPont - michael@mdupont.com
screen.py - Display ICAO METAR weather data with a Raspberry Pi and touchscreen
"""

# pylint: disable=E1101

# stdlib
import asyncio
import math
import sys
import time
from copy import copy
from os import path, putenv, system
from typing import Callable

# library
import avwx
import pygame

# module
import common
import config as cfg
from common import IDENT_CHARS, logger


class SpChar(object):
    """
    Special Characters
    """

    CANCEL = "\u2715"
    CHECKMARK = "\u2713"
    DEGREES = "\u00B0"
    DOWN_TRIANGLE = "\u25bc"
    INFO = "\u2139"
    MOON = "\u263E"
    RELOAD = "\u21ba"
    SETTINGS = "\u2699"
    SUN = "\u2600"
    UP_TRIANGLE = "\u25b2"


class Color(object):
    """
    RGB color values
    """

    WHITE = 255, 255, 255
    BLACK = 0, 0, 0
    RED = 255, 0, 0
    GREEN = 0, 255, 0
    BLUE = 0, 0, 255
    PURPLE = 150, 0, 255
    GRAY = 60, 60, 60

    def __getitem__(self, key: str) -> (int, int, int):
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(f"{key} is not a set color: {self.__slots__}")


# Init pygame and fonts
pygame.init()
LOC = path.abspath(path.dirname(__file__))
FONT_PATH = path.join(LOC, "icons", "DejaVuSans.ttf")
FONT12 = pygame.font.Font(FONT_PATH, 12)
FONT16 = pygame.font.Font(FONT_PATH, 16)
FONT18 = pygame.font.Font(FONT_PATH, 18)
FONT26 = pygame.font.Font(FONT_PATH, 26)
FONT32 = pygame.font.Font(FONT_PATH, 32)
FONT48 = pygame.font.Font(FONT_PATH, 48)

fr_display = {
    "VFR": (Color.GREEN, (263, 5)),
    "MVFR": (Color.BLUE, (241, 5)),
    "IFR": (Color.RED, (273, 5)),
    "LIFR": (Color.PURPLE, (258, 5)),
    "N/A": (Color.BLACK, (269, 5)),
}


def midpoint(p1: (int, int), p2: (int, int)) -> (int, int):
    """
    Returns the midpoint between two points
    """
    return (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2


def centered(rendered_text, around: (int, int)) -> (int, int):
    """
    Returns the top left point for rendered text at a center point
    """
    width, height = rendered_text.get_size()
    return around[0] - width / 2 + 1, around[1] - height / 2 + 1


def radius_point(degree: int, center: (int, int), radius: int) -> (int, int):
    """
    Returns the degree point on the circumference of a circle
    """
    x = center[0] + radius * math.cos((degree - 90) * math.pi / 180)
    y = center[1] + radius * math.sin((degree - 90) * math.pi / 180)
    return x, y


class Button(object):
    """
    Base button class

    Runs a function when clicked
    """

    # Function to run when clicked. Cannot accept args
    onclick: Callable
    # Text settings
    text: str
    fontsize: int
    # Color strings must match Color.attr names
    fontcolor: str

    def draw(self, win: pygame.Surface, color: Color):
        """
        Draw the button on the window with the current color palette
        """
        raise NotImplementedError()

    def is_clicked(self, pos: (int, int)) -> bool:
        """
        Returns True if the position is within the button bounds
        """
        raise NotImplementedError()


class RectButton(Button):
    """
    Rectangular buttons can contain text
    """

    # Top left
    x1: int
    y1: int
    # Bottom right
    x2: int
    y2: int

    width: int
    height: int

    # Box outline thickness
    thickness: int

    def __init__(
        self,
        bounds: [int],
        action: Callable,
        text: str = None,
        fontsize: int = None,
        fontcolor: str = "Black",
        thickness: int = None,
    ):
        self.x1, self.y1, self.width, self.height = bounds
        self.x2 = self.x1 + self.width
        self.y2 = self.y1 + self.height
        self.onclick = action
        self.text = text
        self.fontsize = fontsize
        self.fontcolor = fontcolor
        self.thickness = thickness

    def __repr__(self) -> str:
        return f'<RectButton "{self.text}" at ({self.x1}, {self.y1}), ({self.x2}, {self.y2})>'

    def draw(self, win: pygame.Surface, color: Color):
        """
        Draw the button on the window with the current color palette
        """
        if self.width is not None:
            bounds = ((self.x1, self.y1), (self.width, self.height))
            pygame.draw.rect(win, color[self.fontcolor], bounds, self.thickness)
        if self.text is not None:
            font = pygame.font.Font(FONT_PATH, self.fontsize)
            rendered = font.render(self.text, 1, color[self.fontcolor])
            rwidth, rheight = rendered.get_size()
            x = self.x1 + (self.width - rwidth) / 2
            y = self.y1 + (self.height - rheight) / 2 + 1
            win.blit(rendered, (x, y))

    def is_clicked(self, pos: (int, int)) -> bool:
        """
        Returns True if the position is within the button bounds
        """
        return self.x1 < pos[0] < self.x2 and self.y1 < pos[1] < self.y2


class RoundButton(Button):
    """
    Round buttons 
    """

    # Center pixel and radius
    x: int
    y: int
    radius: int

    def __init__(self, center: (int, int), radius: int, action: Callable):
        self.center = center
        self.radius = radius
        self.onclick = action

    def is_clicked(self, pos: (int, int)) -> bool:
        """
        Returns True if the position is within the button bounds
        """
        x, y = self.center
        return self.radius > math.hypot(x - pos[0], y - pos[1])


class IconButton(RoundButton):
    """
    Round button which contain a letter or symbol
    """

    # Fill color
    fill: str

    def __init__(
        self,
        center: (int, int),
        radius: int,
        action: Callable,
        icon: str = None,
        fontsize: int = None,
        fontcolor: str = None,
        fill: str = None,
    ):
        self.center = center
        self.radius = radius
        self.onclick = action
        self.icon = icon
        self.fontsize = fontsize
        self.fontcolor = fontcolor
        self.fill = fill

    def __repr__(self) -> str:
        return f"<IconButton at {self.center} rad {self.radius}>"

    def draw(self, win: pygame.Surface, color: Color):
        """
        Draw the button on the window with the current color palette
        """
        if self.fill is not None:
            pygame.draw.circle(win, color[self.fill], self.center, self.radius)
        if self.icon is not None:
            font = pygame.font.Font(FONT_PATH, self.fontsize)
            rendered = font.render(self.icon, 1, color[self.fontcolor])
            win.blit(rendered, centered(rendered, self.center))


class ShutdownButton(RoundButton):
    """
    Round button with a drawn shutdown symbol
    """

    fontcolor: str = "WHITE"
    fill: str = "RED"

    def draw(self, win: pygame.Surface, color: Color):
        """
        Draw the button on the window with the current color palette
        """
        pygame.draw.circle(win, color[self.fill], self.center, self.radius)
        pygame.draw.circle(win, color[self.fontcolor], self.center, self.radius - 6)
        pygame.draw.circle(win, color[self.fill], self.center, self.radius - 9)
        rect = ((self.center[0] - 2, self.center[1] - 10), (4, 20))
        pygame.draw.rect(win, color[self.fontcolor], rect)


class SelectionButton(ShutdownButton):
    """
    Round button with icons resembling selection screen
    """

    fontcolor: str = "WHITE"
    fill: str = "GREEN"

    def draw(self, win: pygame.Surface, color: Color):
        """
        Draw the button on the window with the current color palette
        """
        pygame.draw.circle(win, color[self.fill], self.center, self.radius)
        for char, direction in ((SpChar.UP_TRIANGLE, -1), (SpChar.DOWN_TRIANGLE, 1)):
            tri = FONT26.render(char, 1, color[self.fontcolor])
            topleft = list(centered(tri, self.center))
            topleft[1] += int(self.radius * 0.5) * direction - 3
            win.blit(tri, topleft)


def draw_func(func):
    """
    Decorator wraps drawing functions with common commands
    """

    def wrapper(screen):
        screen.on_main = False
        screen.buttons = []
        func(screen)
        screen.draw_buttons()
        pygame.display.flip()
        # This line is a hack to force the screen to redraw
        pygame.event.get()

    return wrapper


class METARScreen:
    """
    Controls and draws UI elements
    """

    ident: [str]
    old_ident: [str]
    width: int
    height: int
    win: pygame.Surface
    c: Color
    inverted: bool
    update_time: float
    buttons: [Button]

    on_main: bool = False

    def __init__(self, station: str, size: (int, int), inverted: bool):
        logger.debug("Running init")
        try:
            self.metar = avwx.Metar(station)
        except avwx.exceptions.BadStation:
            self.metar = avwx.Metar("KJFK")
        self.ident = common.station_to_ident(station)
        self.old_ident = copy(self.ident)
        self.width, self.height = size
        self.win = pygame.display.set_mode(size)
        self.c = Color()
        self.inverted = inverted
        if inverted:
            self.c.BLACK, self.c.WHITE = self.c.WHITE, self.c.BLACK
        # Hide mouse for touchscreen input/Disable if test non touchscreen
        if cfg.on_pi:
            pygame.mouse.set_visible(False)
        self.reset_update_time()
        self.buttons = []
        logger.debug("Finished running init")

    @property
    def station(self) -> str:
        """
        The current station
        """
        return common.ident_to_station(self.ident)

    @classmethod
    def from_session(cls, session: dict, size: (int, int)):
        """
        Returns a new Screen from a saved session
        """
        station = session.get("station", "KJFK")
        inverted = session.get("inverted", True)
        return cls(station, size, inverted)

    def export_session(self, save: bool = True):
        """
        Saves or returns a dictionary representing the session's state
        """
        session = {"station": self.station, "inverted": self.inverted}
        if save:
            common.save_session(session)
        return session

    def reset_update_time(self, interval: int = None):
        """
        Call to reset the update time to now plus the update interval
        """
        self.update_time = time.time() + (interval or cfg.update_interval)

    def refresh_data(self, force_main: bool = False):
        """
        Refresh existing station
        """
        try:
            updated = self.metar.update()
        except TimeoutError:
            self.error_connection()
        except avwx.exceptions.InvalidRequest:
            self.error_station()
        except Exception as exc:
            logger.error(f"An unknown error has occured: {exc}")
            self.error_unknown()
        else:
            logger.info(self.metar.raw)
            self.reset_update_time()
            if updated and (self.on_main or force_main):
                self.draw_main()

    @draw_func
    def new_station(self):
        """
        Update the current station from ident and display new main screen
        """
        try:
            station = avwx.station.Station.from_icao(self.station)
            if not station.sends_reports:
                return self.error_reporting()
        except avwx.exceptions.BadStation:
            return self.error_station()
        self.draw_loading_screen()
        new_metar = avwx.Metar(self.station)
        try:
            new_metar.update()
        except (TimeoutError, ConnectionError, avwx.exceptions.SourceError):
            self.error_connection()
        except avwx.exceptions.InvalidRequest:
            self.error_station()
        except Exception as exc:
            logger.error(f"An unknown error has occured: {exc}")
            self.error_unknown()
        else:
            logger.info(new_metar.raw)
            self.metar = new_metar
            self.old_ident = copy(self.ident)
            self.reset_update_time()
            self.export_session()
            self.draw_main()

    def cancel_station(self):
        """
        Revert ident and redraw main screen
        """
        self.ident = self.old_ident
        self.draw_main()

    def draw_buttons(self):
        """
        Draw all current buttons
        """
        for button in self.buttons:
            button.draw(self.win, self.c)

    @draw_func
    def draw_selection_screen(self):
        """
        Load selection screen elements
        """
        self.win.fill(self.c.WHITE)
        # Draw Selection Grid
        self.buttons = [
            IconButton(
                (275, 80), 25, self.new_station, SpChar.CHECKMARK, 48, "WHITE", "GREEN"
            ),
            IconButton(
                (275, 160), 25, self.cancel_station, SpChar.CANCEL, 48, "WHITE", "RED"
            ),
        ]
        for col in range(4):
            x = self.__selection_getx(col)
            self.buttons.append(
                IconButton(
                    (x, 42),
                    25,
                    self.__incr_ident(col, 1),
                    SpChar.UP_TRIANGLE,
                    48,
                    "BLACK",
                )
            )
            self.buttons.append(
                IconButton(
                    (x, 192),
                    25,
                    self.__incr_ident(col, 0),
                    SpChar.DOWN_TRIANGLE,
                    48,
                    "BLACK",
                )
            )
            rendered = FONT48.render(IDENT_CHARS[self.ident[col]], 1, self.c.BLACK)
            self.win.blit(rendered, centered(rendered, (x, 122)))

    @staticmethod
    def __selection_getx(col: int) -> int:
        """
        Returns the top left x pixel for a desired column
        """
        return 43 + col * 55

    def __incr_ident(self, pos: int, down: bool) -> Callable:
        """
        Returns a function to update and replace ident char on display
        
        pos: 0-3 column
        up: increment up
        """

        def update_func():
            # Update ident
            if down:
                if self.ident[pos] == 0:
                    self.ident[pos] = len(IDENT_CHARS)
                self.ident[pos] -= 1
            else:
                self.ident[pos] += 1
                if self.ident[pos] == len(IDENT_CHARS):
                    self.ident[pos] = 0
            # Update display
            rendered = FONT48.render(IDENT_CHARS[self.ident[pos]], 1, self.c.BLACK)
            x = self.__selection_getx(pos)
            region = (x - 25, 122 - 25, 55, 55)
            pygame.draw.rect(self.win, self.c.WHITE, region)
            self.win.blit(rendered, centered(rendered, (x, 122)))
            pygame.display.update(region)

        return update_func

    @draw_func
    def draw_loading_screen(self):
        """
        Display load screen
        """
        # Reset on_main because the main screen should always display on success
        self.on_main = True
        self.win.fill(self.c.WHITE)
        self.win.blit(FONT32.render("Fetching weather", 1, self.c.BLACK), (25, 70))
        self.win.blit(
            FONT32.render("data for " + self.station, 1, self.c.BLACK), (25, 120)
        )

    def __draw_wind_compass(
        self, data: avwx.structs.MetarData, center: [int], radius: int
    ):
        """
        Draw the wind direction compass
        """
        wdir = data.wind_direction
        speed = data.wind_speed
        var = data.wind_variable_direction
        pygame.draw.circle(self.win, self.c.GRAY, center, radius, 3)
        if not speed.value:
            text = FONT18.render("Calm", 1, self.c.BLACK)
        elif wdir and wdir.repr == "VRB":
            text = FONT18.render("VRB", 1, self.c.BLACK)
        elif wdir:
            text = FONT26.render(str(wdir.value), 1, self.c.BLACK)
            rad_point = radius_point(wdir.value, center, radius)
            pygame.draw.line(self.win, self.c.RED, center, rad_point, 2)
            if var:
                for point in var:
                    rad_point = radius_point(point.value, center, radius)
                    pygame.draw.line(self.win, self.c.BLUE, center, rad_point, 2)
        else:
            text = FONT48.render(SpChar.CANCEL, 1, self.c.RED)
        self.win.blit(text, centered(text, center))

    def __draw_wind(self, data: avwx.structs.MetarData, unit: str):
        """
        Draw the dynamic wind elements
        """
        speed, gust = data.wind_speed, data.wind_gust
        self.__draw_wind_compass(data, (40, 80), 35)
        if speed.value:
            self.win.blit(
                FONT18.render(f"{speed.value} {unit}", 1, self.c.BLACK), (17, 116)
            )
        gust_text = f"G: {gust.value}" if gust else "No Gust"
        self.win.blit(FONT18.render(gust_text, 1, self.c.BLACK), (5, 137))

    def __draw_temp_icon(self, temp: int, point: (int, int)):
        """
        Draw the temperature icon
        """
        therm_level = 0
        if temp:
            therm_level = temp // 12 + 2
            if therm_level < 0:
                therm_level = 0
        add_i = "I" if self.inverted else ""
        therm_icon = f"Therm{therm_level}{add_i}.png"
        self.win.blit(pygame.image.load(path.join(LOC, "icons", therm_icon)), point)

    def __draw_temp_dew_humidity(self, data: avwx.structs.MetarData):
        """
        Draw the dynamic temperature, dewpoint, and humidity elements
        """
        temp = data.temperature
        dew = data.dewpoint
        temp_text = "TMP: --"
        diff_text = "STD: --"
        dew_text = "DEW: --"
        # Dewpoint
        if dew:
            dew_text = f"DEW: {dew.value}{SpChar.DEGREES}"
        self.win.blit(FONT18.render(dew_text, 1, self.c.BLACK), (105, 114))
        # Temperature
        if temp:
            temp_text = f"TMP: {temp.value}{SpChar.DEGREES}"
            temp_diff = temp.value - 15
            diff_sign = "-" if temp_diff < 0 else "+"
            diff_text = f"STD: {diff_sign}{abs(temp_diff)}{SpChar.DEGREES}"
        self.win.blit(FONT18.render(temp_text, 1, self.c.BLACK), (110, 50))
        self.win.blit(FONT18.render(diff_text, 1, self.c.BLACK), (110, 82))
        self.__draw_temp_icon(temp.value, (60, 50))
        # Humidity
        hmd_text = "HMD: --"
        if isinstance(temp.value, int) and isinstance(dew.value, int):
            relHum = (
                (6.11 * 10.0 ** (7.5 * dew.value / (237.7 + dew.value)))
                / (6.11 * 10.0 ** (7.5 * temp.value / (237.7 + temp.value)))
                * 100
            )
            hmd_text = f"HMD: {int(relHum)}%"
        self.win.blit(FONT18.render(hmd_text, 1, self.c.BLACK), (90, 146))

    def __draw_cloud_graph(self, clouds: [avwx.structs.Cloud], tl: [int], br: [int]):
        """
        Draw cloud layers in chart

        Scales everything based on top left and bottom right points
        """
        tlx, tly = tl
        brx, bry = br
        header = FONT18.render("Clouds AGL", 1, self.c.BLACK)
        header_height = header.get_size()[1]
        header_point = midpoint(tl, (brx, tly + header_height))
        self.win.blit(header, centered(header, header_point))
        tly += header_height
        pygame.draw.lines(
            self.win, self.c.BLACK, False, ((tlx, tly), (tlx, bry), (brx, bry)), 3
        )
        if not clouds:
            text = FONT32.render("CLR", 1, self.c.BLUE)
            self.win.blit(text, centered(text, midpoint((tlx, tly), (brx, bry))))
            return
        top = 80
        LRBool = 1
        tlx += 5
        brx -= 5
        bry -= 10
        for cloud in clouds[::-1]:
            if cloud.base:
                if cloud.base > top:
                    top = cloud.base
                drawHeight = bry - (bry - tly) * cloud.base / top
                text = FONT12.render(cloud.repr, 1, self.c.BLUE)
                width, height = text.get_size()
                liney = drawHeight + height / 2
                if LRBool > 0:
                    self.win.blit(text, (tlx, drawHeight))
                    pygame.draw.line(
                        self.win, self.c.BLUE, (tlx + width + 2, liney), (brx, liney)
                    )
                else:
                    self.win.blit(text, (brx - width, drawHeight))
                    pygame.draw.line(
                        self.win, self.c.BLUE, (tlx, liney), (brx - width - 2, liney)
                    )
                LRBool *= -1

    def __main_draw_dynamic(
        self, data: avwx.structs.MetarData, units: avwx.structs.Units
    ) -> bool:
        """
        Load Main dynamic foreground elements

        Returns True if "Other-WX" or "Remarks" is not empty, else False
        """
        # Station and Time
        time_text = data.station + "  " + data.time.dt.strftime(r"%d-%H:%M")
        self.win.blit(FONT26.render(time_text, 1, self.c.BLACK), (5, 5))
        # Current Flight Rules
        fr = data.flight_rules or "N/A"
        fr_color, fr_loc = fr_display[fr]
        self.win.blit(FONT26.render(fr, 1, fr_color), fr_loc)
        # Wind
        self.__draw_wind(data, units.wind_speed)
        # Temperature / Dewpoint / Humidity
        self.__draw_temp_dew_humidity(data)
        # Altimeter
        altm = data.altimeter
        altm_text = "ALT: --"
        if altm:
            altm_text = f"ALT: {altm.value}"
        self.win.blit(FONT18.render(altm_text, 1, self.c.BLACK), (90, 178))
        # Visibility
        vis_text = "VIS: --"
        if data.visibility:
            vis_text = f"VIS: {data.visibility.value}{units.visibility}"
        self.win.blit(FONT18.render(vis_text, 1, self.c.BLACK), (90, 210))
        # Cloud Layers
        self.__draw_cloud_graph(data.clouds, (200, 35), (310, 230))
        pygame.display.flip()

    @draw_func
    def draw_rmk(self):
        """
        Display available Other Weather / Remarks and cancel button control
        """

        def getY(numHead: int, numLine: int) -> int:
            return 5 + 26 * numHead + 23 * numLine

        # Load
        self.win.fill(self.c.WHITE)
        numHead, numLine = 0, 0
        # Weather
        wxs = self.metar.data.other
        if wxs:
            self.win.blit(
                FONT18.render("Other Weather", 1, self.c.BLACK),
                (8, getY(numHead, numLine)),
            )
            numHead += 1
            offset = -75
            for wx in avwx.translate.other_list(wxs).split(", "):
                # Column overflow control
                if len(wx) > 17:
                    if offset > 0:
                        numLine += 1
                    offset = -75
                self.win.blit(
                    FONT16.render(wx, 1, self.c.BLACK),
                    (85 + offset, getY(numHead, numLine)),
                )
                if len(wx) > 17:
                    numLine += 1
                else:
                    if offset > 0:
                        numLine += 1
                    offset *= -1
            if offset > 0:
                numLine += 1
        # Remarks
        rmk = self.metar.data.remarks
        if rmk:
            self.win.blit(
                FONT18.render("Remarks", 1, self.c.BLACK), (8, getY(numHead, numLine))
            )
            numHead += 1
            # Line overflow control
            while len(rmk) > 28:
                cutPoint = rmk[:28].rfind(" ")
                self.win.blit(
                    FONT16.render(rmk[:cutPoint], 1, self.c.BLACK),
                    (10, getY(numHead, numLine)),
                )
                numLine += 1
                rmk = rmk[cutPoint + 1 :]
            self.win.blit(
                FONT16.render(rmk, 1, self.c.BLACK), (10, getY(numHead, numLine))
            )
            numLine += 1
        self.buttons = [
            IconButton(
                (40, 213), 24, self.draw_main, SpChar.CANCEL, 48, "WHITE", "GRAY"
            )
        ]

    @draw_func
    def draw_main(self):
        """
        Run main data display and options touch button control
        """
        self.win.fill(self.c.WHITE)
        self.__main_draw_dynamic(self.metar.data, self.metar.units)
        self.buttons = [
            IconButton(
                (40, 213),
                24,
                self.draw_options_bar,
                SpChar.SETTINGS,
                48,
                "WHITE",
                "GRAY",
            )
        ]
        wx = self.metar.data.other
        rmk = self.metar.data.remarks
        if wx or rmk:
            if wx and rmk:
                text, color = "WX/RMK", "PURPLE"
            elif wx:
                text, color = "WX", "RED"
            elif rmk:
                text, color = "RMK", "BLUE"
            self.buttons.append(
                RectButton((3, 159, 80, 27), self.draw_rmk, text, 18, color, 2)
            )
        self.on_main = True

    def invert_wb(self, redraw: bool = True):
        """
        Invert the black and white of the display
        """
        self.inverted = not self.inverted
        self.c.BLACK, self.c.WHITE = self.c.WHITE, self.c.BLACK
        self.export_session()
        if redraw:
            self.draw_main()

    @draw_func
    def draw_quit_screen(self) -> False:
        """
        Display Shutdown/Exit option and touch button control

        Returns False or exits program
        """
        self.win.fill(self.c.WHITE)
        if cfg.shutdown_on_exit:
            self.win.blit(FONT32.render("Shutdown the Pi?", 1, self.c.BLACK), (22, 70))
        else:
            self.win.blit(FONT32.render("Exit the program?", 1, self.c.BLACK), (18, 70))
        self.buttons = [
            IconButton((105, 150), 25, quit, SpChar.CHECKMARK, 48, "WHITE", "GREEN"),
            IconButton(
                (215, 150), 25, self.draw_main, SpChar.CANCEL, 48, "WHITE", "RED"
            ),
        ]

    @draw_func
    def draw_info_screen(self):
        """
        Display info screen and cancel touch button control
        """
        self.win.fill(self.c.WHITE)
        self.win.blit(FONT32.render("METAR-RasPi", 1, self.c.BLACK), (51, 40))
        self.win.blit(FONT18.render("Michael duPont", 1, self.c.BLACK), (85, 95))
        self.win.blit(FONT18.render("michael@mdupont.com", 1, self.c.BLACK), (50, 120))
        self.win.blit(
            FONT12.render("github.com/flyinactor91/METAR-RasPi", 1, self.c.BLACK),
            (40, 147),
        )
        self.buttons = [
            IconButton(
                (40, 213), 24, self.draw_main, SpChar.CANCEL, 48, "WHITE", "GRAY"
            )
        ]

    @draw_func
    def draw_options_bar(self) -> bool:
        """
        Draws options bar display
        """
        # Clear Option background
        pygame.draw.rect(self.win, self.c.WHITE, ((0, 190), (85, 50)))
        pygame.draw.rect(self.win, self.c.WHITE, ((85, 180), (335, 60)))
        invchar = SpChar.SUN if self.inverted else SpChar.MOON
        self.buttons = [
            IconButton(
                (40, 213), 24, self.draw_main, SpChar.CANCEL, 48, "WHITE", "GRAY"
            ),
            SelectionButton((100, 213), 24, self.draw_selection_screen),
            ShutdownButton((160, 213), 24, self.draw_quit_screen),
            IconButton((220, 213), 24, self.invert_wb, invchar, 48, "WHITE", "BLACK"),
            IconButton(
                (280, 213),
                24,
                self.draw_info_screen,
                SpChar.INFO,
                48,
                "WHITE",
                "PURPLE",
            ),
        ]

    @draw_func
    def error_station(self):
        """
        Display invalid station message and sleep
        """
        self.win.fill(self.c.WHITE)
        self.win.blit(
            FONT32.render(f"{self.station} is not", 1, self.c.BLACK), (25, 70)
        )
        self.win.blit(FONT32.render("a valid station", 1, self.c.BLACK), (25, 120))
        self.buttons = [
            IconButton(
                (40, 213),
                24,
                self.draw_selection_screen,
                SpChar.CANCEL,
                48,
                "WHITE",
                "GRAY",
            )
        ]

    @draw_func
    def error_reporting(self):
        """
        Display invalid station message and sleep
        """
        self.win.fill(self.c.WHITE)
        self.win.blit(FONT32.render(f"{self.station} does", 1, self.c.BLACK), (25, 70))
        self.win.blit(FONT32.render("not send METARs", 1, self.c.BLACK), (25, 120))
        self.buttons = [
            IconButton(
                (40, 213),
                24,
                self.draw_selection_screen,
                SpChar.CANCEL,
                48,
                "WHITE",
                "GRAY",
            )
        ]

    @draw_func
    def error_unknown(self):
        """
        Display invalid station message and sleep
        """
        self.win.fill(self.c.WHITE)
        self.win.blit(FONT32.render(f"There was an", 1, self.c.BLACK), (25, 70))
        self.win.blit(FONT32.render("unknown errer", 1, self.c.BLACK), (25, 120))
        self.buttons = [
            IconButton(
                (40, 213),
                24,
                self.draw_selection_screen,
                SpChar.CANCEL,
                48,
                "WHITE",
                "GRAY",
            )
        ]

    @draw_func
    def error_connection(self):
        """
        Display timeout message and sleep
        """
        logger.warning("Connection Timeout")
        self.win.fill(self.c.WHITE)
        self.win.blit(FONT32.render("Could not fetch", 1, self.c.BLACK), (25, 70))
        self.win.blit(FONT32.render("data from source", 1, self.c.BLACK), (25, 120))
        self.buttons = [
            IconButton(
                (40, 213), 24, self.draw_main, SpChar.CANCEL, 48, "WHITE", "GRAY"
            ),
            IconButton(
                (100, 213), 24, self.refresh_data, SpChar.RELOAD, 48, "WHITE", "GRAY"
            ),
        ]
        self.reset_update_time(cfg.timeout_interval)
        self.on_main = True


def quit():
    logger.debug("Quit")
    if cfg.shutdown_on_exit:
        system("shutdown -h now")
    sys.exit()


async def update_loop(screen: METARScreen):
    """
    Handles updating the METAR data in the background
    """
    while True:
        # logger.debug(f'{int(time.time())} {screen.update_time}')
        if time.time() >= screen.update_time:
            logger.debug("Auto update")
            screen.refresh_data()
        await asyncio.sleep(10)


async def input_loop(screen: METARScreen):
    """
    Handles user input and calling button functions when clicked
    """
    while True:
        for event in pygame.event.get():
            if event.type == pygame.MOUSEBUTTONDOWN:
                pos = pygame.mouse.get_pos()
                for button in screen.buttons:
                    if button.is_clicked(pos):
                        button.onclick()
                        break
        await asyncio.sleep(0.01)


def main():
    """
    Program main handles METAR data handling and user interaction flow
    """
    logger.debug("Booting")
    screen = METARScreen.from_session(common.load_session(), cfg.size)
    screen.draw_loading_screen()
    screen.refresh_data(force_main=True)
    loop = asyncio.get_event_loop()
    coros = [update_loop(screen), input_loop(screen)]
    logger.debug("Setup complete")
    loop.run_until_complete(asyncio.wait(coros, return_when=asyncio.FIRST_COMPLETED))


if __name__ == "__main__":
    if cfg.on_pi:
        putenv("SDL_FBDEV", "/dev/fb1")
        putenv("SDL_MOUSEDEV", "/dev/input/touchscreen")
        putenv("SDL_MOUSEDRV", "TSLIB")
        putenv("SDL_VIDEODRIVER", "fbcon")
    main()
