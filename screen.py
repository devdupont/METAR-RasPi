"""
Michael duPont - michael@mdupont.com
screen.py - Display ICAO METAR weather data with a Raspberry Pi and touchscreen
"""

# pylint: disable=E1101

# stdlib
import asyncio as aio
import math
import sys
import time
from copy import copy
from datetime import datetime
from os import system
from typing import Callable

# library
import avwx
import pygame

# module
import common
import config as cfg
from common import IDENT_CHARS, logger


class SpChar:
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


class Color:
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
ICON_PATH = cfg.LOC / "icons"
FONT_PATH = str(ICON_PATH / "DejaVuSans.ttf")

FONT_S1 = pygame.font.Font(FONT_PATH, cfg.layout["fonts"]["s1"])
FONT_S2 = pygame.font.Font(FONT_PATH, cfg.layout["fonts"]["s2"])
FONT_S3 = pygame.font.Font(FONT_PATH, cfg.layout["fonts"]["s3"])
FONT_M1 = pygame.font.Font(FONT_PATH, cfg.layout["fonts"]["m1"])
FONT_M2 = pygame.font.Font(FONT_PATH, cfg.layout["fonts"]["m2"])
FONT_L1 = pygame.font.Font(FONT_PATH, cfg.layout["fonts"]["l1"])
try:
    FONT_L2 = pygame.font.Font(FONT_PATH, cfg.layout["fonts"]["l2"])
except KeyError:
    pass


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
    degree %= 360
    x = center[0] + radius * math.cos((degree - 90) * math.pi / 180)
    y = center[1] + radius * math.sin((degree - 90) * math.pi / 180)
    return x, y


def hide_mouse():
    """
    This makes the mouse transparent
    """
    pygame.mouse.set_cursor(
        (8, 8), (0, 0), (0, 0, 0, 0, 0, 0, 0, 0), (0, 0, 0, 0, 0, 0, 0, 0)
    )


class Button:
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
        fontsize: int = cfg.layout["fonts"]["s3"],
        fontcolor: str = "Black",
        thickness: int = cfg.layout["button"]["outline"],
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

    def __init__(
        self,
        center: (int, int),
        action: Callable,
        radius: int = cfg.layout["button"]["radius"],
    ):
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
    fill: str = "WHITE"
    fontcolor: str = "BLACK"
    fontsize: int = cfg.layout["fonts"]["l1"]
    radius: int = cfg.layout["button"]["radius"]

    def __init__(
        self,
        center: (int, int) = None,
        action: Callable = None,
        icon: str = None,
        fontcolor: str = None,
        fill: str = None,
        radius: int = None,
        fontsize: int = None,
    ):
        if center:
            self.center = center
        if radius:
            self.radius = radius
        if action:
            self.onclick = action
        if icon:
            self.icon = icon
        if fontsize:
            self.fontsize = fontsize
        if fontcolor:
            self.fontcolor = fontcolor
        if fill:
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


class SelectionButton(RoundButton):
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
        font = FONT_S3 if cfg.layout["large-display"] else FONT_M1
        for char, direction in ((SpChar.UP_TRIANGLE, -1), (SpChar.DOWN_TRIANGLE, 1)):
            tri = font.render(char, 1, color[self.fontcolor])
            topleft = list(centered(tri, self.center))
            topleft[1] += int(self.radius * 0.5) * direction - 3
            win.blit(tri, topleft)


class CancelButton(IconButton):

    center: (int, int) = cfg.layout["util"]
    icon: str = SpChar.CANCEL
    fontcolor: str = "WHITE"
    fill: str = "GRAY"


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
    layout: dict
    is_large: bool

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
        if cfg.fullscreen:
            self.win = pygame.display.set_mode(size, pygame.FULLSCREEN)
        else:
            self.win = pygame.display.set_mode(size)
        self.c = Color()
        self.inverted = inverted
        if inverted:
            self.c.BLACK, self.c.WHITE = self.c.WHITE, self.c.BLACK
        if cfg.hide_mouse:
            hide_mouse()
        self.reset_update_time()
        self.buttons = []
        self.layout = cfg.layout
        self.is_large = self.layout["large-display"]
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

    async def refresh_data(
        self, force_main: bool = False, ignore_updated: bool = False
    ):
        """
        Refresh existing station
        """
        logger.info("Calling refresh update")
        try:
            updated = await self.metar.async_update()
        except ConnectionError:
            await self.wait_for_network()
        except (TimeoutError, avwx.exceptions.SourceError):
            self.error_connection()
        except avwx.exceptions.InvalidRequest:
            self.error_station()
        except Exception as exc:
            logger.exception(f"An unknown error has occured: {exc}")
            self.error_unknown()
        else:
            logger.info(self.metar.raw)
            self.reset_update_time()
            if ignore_updated:
                updated = True
            if updated and (self.on_main or force_main):
                self.draw_main()
            elif force_main and not updated:
                self.error_no_data()

    def new_station(self):
        """
        Update the current station from ident and display new main screen
        """
        logger.info("Calling new update")
        self.draw_loading_screen()
        new_metar = avwx.Metar(self.station)
        try:
            if not new_metar.update():
                return self.error_no_data()
        except (TimeoutError, ConnectionError, avwx.exceptions.SourceError):
            self.error_connection()
        except avwx.exceptions.InvalidRequest:
            self.error_station()
        except Exception as exc:
            logger.exception(f"An unknown error has occured: {exc}")
            self.error_unknown()
        else:
            logger.info(new_metar.raw)
            self.metar = new_metar
            self.old_ident = copy(self.ident)
            self.reset_update_time()
            self.export_session()
            self.draw_main()

    def verify_station(self):
        """
        Verifies the station value before calling new data
        """
        try:
            station = avwx.station.Station.from_icao(self.station)
            if not station.sends_reports:
                return self.error_reporting()
        except avwx.exceptions.BadStation:
            return self.error_station()
        return self.new_station()

    def cancel_station(self):
        """
        Revert ident and redraw main screen
        """
        self.ident = self.old_ident
        if self.metar.data is None:
            return self.error_no_data()
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
        yes, no = self.layout["select"]["yes"], self.layout["select"]["no"]
        self.buttons = [
            IconButton(yes, self.verify_station, SpChar.CHECKMARK, "WHITE", "GREEN"),
            CancelButton(no, self.cancel_station, fill="RED"),
        ]
        upy = self.layout["select"]["row-up"]
        chary = self.layout["select"]["row-char"]
        downy = self.layout["select"]["row-down"]
        for col in range(4):
            x = self.__selection_getx(col)
            self.buttons.append(
                IconButton((x, upy), self.__incr_ident(col, 1), SpChar.UP_TRIANGLE)
            )
            self.buttons.append(
                IconButton((x, downy), self.__incr_ident(col, 0), SpChar.DOWN_TRIANGLE)
            )
            rendered = FONT_L1.render(IDENT_CHARS[self.ident[col]], 1, self.c.BLACK)
            self.win.blit(rendered, centered(rendered, (x, chary)))

    def __selection_getx(self, col: int) -> int:
        """
        Returns the top left x pixel for a desired column
        """
        offset = self.layout["select"]["col-offset"]
        spacing = self.layout["select"]["col-spacing"]
        return offset + col * spacing

    def __incr_ident(self, pos: int, down: bool) -> Callable:
        """
        Returns a function to update and replace ident char on display

        pos: 0-3 column
        down: increment/decrement counter
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
            rendered = FONT_L1.render(IDENT_CHARS[self.ident[pos]], 1, self.c.BLACK)
            x = self.__selection_getx(pos)
            chary = self.layout["select"]["row-char"]
            spacing = self.layout["select"]["col-spacing"]
            region = (x - spacing / 2, chary - spacing / 2, spacing, spacing)
            pygame.draw.rect(self.win, self.c.WHITE, region)
            self.win.blit(rendered, centered(rendered, (x, chary)))
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
        point = self.layout["error"]["line1"]
        self.win.blit(FONT_M2.render("Fetching weather", 1, self.c.BLACK), point)
        point = self.layout["error"]["line2"]
        self.win.blit(
            FONT_M2.render("data for " + self.station, 1, self.c.BLACK), point
        )

    def __draw_clock(self):
        """
        Draw the clock components
        """
        now = datetime.utcnow().strftime(r"%H:%M")
        clock_font = globals().get("FONT_L2") or FONT_L1
        clock_text = clock_font.render(now, 1, self.c.BLACK)
        x, y = self.layout["main"]["clock"]
        w, h = clock_text.get_size()
        pygame.draw.rect(self.win, self.c.WHITE, ((x, y), (x + w, (y + h) * 0.9)))
        self.win.blit(clock_text, (x, y))
        label_font = FONT_M1 if self.is_large else FONT_S3
        point = self.layout["main"]["clock-label"]
        self.win.blit(label_font.render("UTC", 1, self.c.BLACK), point)

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
            text = FONT_S3.render("Calm", 1, self.c.BLACK)
        elif wdir and wdir.repr == "VRB":
            text = FONT_S3.render("VRB", 1, self.c.BLACK)
        elif wdir:
            text = FONT_M1.render(str(wdir.value).zfill(3), 1, self.c.BLACK)
            rad_point = radius_point(wdir.value, center, radius)
            width = 4 if self.is_large else 2
            pygame.draw.line(self.win, self.c.RED, center, rad_point, width)
            if var:
                for point in var:
                    rad_point = radius_point(point.value, center, radius)
                    pygame.draw.line(self.win, self.c.BLUE, center, rad_point, width)
        else:
            text = FONT_L1.render(SpChar.CANCEL, 1, self.c.RED)
        self.win.blit(text, centered(text, center))

    def __draw_wind(self, data: avwx.structs.MetarData, unit: str):
        """
        Draw the dynamic wind elements
        """
        speed, gust = data.wind_speed, data.wind_gust
        point = self.layout["main"]["wind-compass"]
        radius = self.layout["main"]["wind-compass-radius"]
        self.__draw_wind_compass(data, point, radius)
        if speed.value:
            text = FONT_S3.render(f"{speed.value} {unit}", 1, self.c.BLACK)
            point = self.layout["main"]["wind-speed"]
            self.win.blit(text, centered(text, point))
        text = f"G: {gust.value}" if gust else "No Gust"
        text = FONT_S3.render(text, 1, self.c.BLACK)
        self.win.blit(text, centered(text, self.layout["main"]["wind-gust"]))

    def __draw_temp_icon(self, temp: int):
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
        point = self.layout["main"]["temp-icon"]
        self.win.blit(pygame.image.load(str(ICON_PATH / therm_icon)), point)

    def __draw_temp_dew_humidity(self, data: avwx.structs.MetarData):
        """
        Draw the dynamic temperature, dewpoint, and humidity elements
        """
        temp = data.temperature
        dew = data.dewpoint
        if self.is_large:
            temp_text = "Temp "
            diff_text = "Std Dev "
            dew_text = "Dewpoint "
            hmd_text = "Humidity "
        else:
            temp_text = "TMP: "
            diff_text = "STD: "
            dew_text = "DEW: "
            hmd_text = "HMD: "
        # Dewpoint
        dew_text += f"{dew.value}{SpChar.DEGREES}" if dew else "--"
        point = self.layout["main"]["dew"]
        self.win.blit(FONT_S3.render(dew_text, 1, self.c.BLACK), point)
        # Temperature
        if temp:
            temp_text += f"{temp.value}{SpChar.DEGREES}"
            if self.is_large:
                temp_text += self.metar.units.temperature
            temp_diff = temp.value - 15
            diff_sign = "-" if temp_diff < 0 else "+"
            diff_text += f"{diff_sign}{abs(temp_diff)}{SpChar.DEGREES}"
        else:
            temp_text += "--"
            diff_text += "--"
        point = self.layout["main"]["temp"]
        self.win.blit(FONT_S3.render(temp_text, 1, self.c.BLACK), point)
        point = self.layout["main"]["temp-stdv"]
        self.win.blit(FONT_S3.render(diff_text, 1, self.c.BLACK), point)
        if "temp-icon" in self.layout["main"]:
            self.__draw_temp_icon(temp.value)
        # Humidity
        if isinstance(temp.value, int) and isinstance(dew.value, int):
            relHum = (
                (6.11 * 10.0 ** (7.5 * dew.value / (237.7 + dew.value)))
                / (6.11 * 10.0 ** (7.5 * temp.value / (237.7 + temp.value)))
                * 100
            )
            hmd_text += f"{int(relHum)}%"
        else:
            hmd_text += "--"
        point = self.layout["main"]["humid"]
        self.win.blit(FONT_S3.render(hmd_text, 1, self.c.BLACK), point)

    def __draw_cloud_graph(self, clouds: [avwx.structs.Cloud], tl: [int], br: [int]):
        """
        Draw cloud layers in chart

        Scales everything based on top left and bottom right points
        """
        tlx, tly = tl
        brx, bry = br
        header = FONT_S3.render("Clouds AGL", 1, self.c.BLACK)
        header_height = header.get_size()[1]
        header_point = midpoint(tl, (brx, tly + header_height))
        self.win.blit(header, centered(header, header_point))
        tly += header_height
        pygame.draw.lines(
            self.win, self.c.BLACK, False, ((tlx, tly), (tlx, bry), (brx, bry)), 3
        )
        if not clouds:
            text = FONT_M2.render("CLR", 1, self.c.BLUE)
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
                text = FONT_S1.render(cloud.repr, 1, self.c.BLUE)
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

    def __draw_wx_raw(self):
        """
        Draw wx and raw report
        """
        x, y = self.layout["wxraw"]["start"]
        spacing = self.layout["wxraw"]["line-space"]
        raw_key = "large"
        wxs = sorted(self.metar.translations.other, key=lambda x: len(x))
        if wxs:
            wx_length = self.layout["wxraw"]["wx-length"]
            y = self.__draw_text_lines(wxs, (x, y), wx_length, space=spacing)
            raw_key = "small"
        raw_font, raw_length, raw_padding = self.layout["wxraw"]["raw"][raw_key]
        y += raw_padding
        self.__draw_text_lines(
            self.metar.data.raw, (x, y), raw_length, space=spacing, fontsize=raw_font
        )

    def __main_draw_dynamic(
        self, data: avwx.structs.MetarData, units: avwx.structs.Units
    ) -> bool:
        """
        Load Main dynamic foreground elements

        Returns True if "Other-WX" or "Remarks" is not empty, else False
        """
        if self.is_large:
            altm_text = "Altm "
            vis_text = "Visb "
        else:
            altm_text = "ALT: "
            vis_text = "VIS: "
        tstamp = data.time.dt.strftime(r"%d-%H:%M")
        if "title" in cfg.layout["main"]:
            time_text = data.station + "  " + tstamp
            point = self.layout["main"]["title"]
            self.win.blit(FONT_M1.render(time_text, 1, self.c.BLACK), point)
        else:
            self.__draw_clock()
            point = self.layout["main"]["station"]
            self.win.blit(FONT_M1.render(data.station, 1, self.c.BLACK), point)
            if self.is_large:
                point = self.layout["main"]["timestamp-label"]
                self.win.blit(FONT_S3.render(f"Updated", 1, self.c.BLACK), point)
            else:
                tstamp = "TS: " + tstamp
            point = self.layout["main"]["timestamp"]
            self.win.blit(FONT_S3.render(tstamp, 1, self.c.BLACK), point)
        # Current Flight Rules
        fr = data.flight_rules or "N/A"
        fr_color, fr_x_offset = self.layout["fr-display"][fr]
        point = copy(self.layout["main"]["flight-rules"])
        point[0] += fr_x_offset
        self.win.blit(FONT_M1.render(fr, 1, getattr(self.c, fr_color.upper())), point)
        # Wind
        self.__draw_wind(data, units.wind_speed)
        # Temperature / Dewpoint / Humidity
        self.__draw_temp_dew_humidity(data)
        # Altimeter
        altm = data.altimeter
        altm_text += str(altm.value) if altm else "--"
        point = self.layout["main"]["altim"]
        self.win.blit(FONT_S3.render(altm_text, 1, self.c.BLACK), point)
        # Visibility
        vis = data.visibility
        vis_text += f"{vis.value}{units.visibility}" if vis else "--"
        point = self.layout["main"]["vis"]
        self.win.blit(FONT_S3.render(vis_text, 1, self.c.BLACK), point)
        # Cloud Layers
        points = self.layout["main"]["cloud-graph"]
        self.__draw_cloud_graph(data.clouds, *points)

    def __draw_text_lines(
        self,
        items: [str],
        left_point: (int, int),
        length: int,
        header: str = None,
        space: int = None,
        right_x: int = None,
        fontsize: int = None,
    ) -> int:
        """
        Draw lines of text with header, columns, and line wrapping
        """
        left_x, y = left_point
        font = pygame.font.Font(FONT_PATH, fontsize) if fontsize else FONT_S2
        if header:
            text = FONT_S3.render(header, 1, self.c.BLACK)
            self.win.blit(text, left_point)
            y += text.get_size()[1] + space
        left = True
        if not isinstance(items, list):
            items = [items]
        for item in items:
            # Column overflow control
            if right_x is not None and len(item) > length:
                if not left:
                    y += space
                    left = not left
            x = left_x if left else right_x
            # Line overflow control
            if right_x is None:
                while len(item) > length:
                    cutPoint = item[:length].rfind(" ")
                    text = font.render(item[:cutPoint], 1, self.c.BLACK)
                    self.win.blit(text, (x, y))
                    y += text.get_size()[1] + space
                    item = item[cutPoint + 1 :]
            text = font.render(item, 1, self.c.BLACK)
            self.win.blit(text, (x, y))
            if right_x is not None:
                if not left or len(item) > length:
                    y += text.get_size()[1] + space
                left = not left
            else:
                y += text.get_size()[1] + space
        # Don't add double new line
        if not (left or len(items[-1]) > length):
            y += text.get_size()[1] + space
        return y

    @draw_func
    def draw_rmk(self):
        """
        Display available Other Weather / Remarks and cancel button control
        """
        left = self.layout["wxrmk"]["col1"]
        right = self.layout["wxrmk"]["col2"]
        y = self.layout["wxrmk"]["padding"]
        line_space = self.layout["wxrmk"]["line-space"]
        self.win.fill(self.c.WHITE)
        # Weather
        wxs = sorted(self.metar.translations.other.split(", "), key=lambda x: len(x))
        if wxs:
            wx_length = self.layout["wxrmk"]["wx-length"]
            y = self.__draw_text_lines(
                wxs,
                (left, y),
                wx_length,
                header="Other Weather",
                space=line_space,
                right_x=right,
            )
        # Remarks
        rmk = self.metar.data.remarks
        if rmk:
            rmk_length = self.layout["wxrmk"]["rmk-length"]
            self.__draw_text_lines(
                rmk, (left, y), rmk_length, header="Remarks", space=line_space
            )
        self.buttons = [CancelButton(action=self.draw_main)]

    @draw_func
    def draw_main(self):
        """
        Run main data display and options touch button control
        """
        self.win.fill(self.c.WHITE)
        self.__main_draw_dynamic(self.metar.data, self.metar.units)
        self.buttons = [
            IconButton(
                self.layout["util"],
                self.draw_options_bar,
                SpChar.SETTINGS,
                "WHITE",
                "GRAY",
            )
        ]
        if self.is_large:
            self.__draw_wx_raw()
        else:
            wx = self.metar.data.other
            rmk = self.metar.data.remarks
            if wx or rmk:
                if wx and rmk:
                    text, color = "WX/RMK", "PURPLE"
                elif wx:
                    text, color = "WX", "RED"
                elif rmk:
                    text, color = "RMK", "BLUE"
                rect = self.layout["main"]["wxrmk"]
                self.buttons.append(
                    RectButton(rect, self.draw_rmk, text, fontcolor=color)
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
            text = "Shutdown the Pi?"
        else:
            text = "Exit the program?"
        text = FONT_M2.render(text, 1, self.c.BLACK)
        point = self.width / 2, self.layout["quit"]["text-y"]
        self.win.blit(text, centered(text, point))
        pointy, pointn = self.layout["quit"]["yes"], self.layout["quit"]["no"]
        self.buttons = [
            IconButton(pointy, quit, SpChar.CHECKMARK, "WHITE", "GREEN"),
            CancelButton(pointn, self.draw_main, fill="RED"),
        ]

    @draw_func
    def draw_info_screen(self):
        """
        Display info screen and cancel touch button control
        """
        self.win.fill(self.c.WHITE)
        for text, key, font in (
            ("METAR-RasPi", "title", FONT_M2),
            ("Michael duPont", "name", FONT_S3),
            ("michael@mdupont.com", "email", FONT_S3),
            ("github.com/flyinactor91/METAR-RasPi", "url", FONT_S1),
        ):
            point = self.width / 2, self.layout["info"][key + "-y"]
            text = font.render(text, 1, self.c.BLACK)
            self.win.blit(text, centered(text, point))
        self.buttons = [CancelButton(action=self.draw_main)]

    @draw_func
    def draw_options_bar(self) -> bool:
        """
        Draws options bar display
        """
        # Clear Option background
        height, width = self.layout["main"]["util-back"]
        pygame.draw.rect(self.win, self.c.WHITE, ((0, height), (width, self.height)))
        invchar = SpChar.SUN if self.inverted else SpChar.MOON
        btnx, btny = self.layout["util"]
        spacing = self.layout["main"]["util-spacing"]

        def getX(n: int) -> int:
            return btnx + spacing * n

        self.buttons = [
            CancelButton((getX(0), btny), self.draw_main),
            SelectionButton((getX(1), btny), self.draw_selection_screen),
            ShutdownButton((getX(2), btny), self.draw_quit_screen),
            IconButton((getX(3), btny), self.invert_wb, invchar, "WHITE", "BLACK"),
            IconButton(
                (getX(4), btny), self.draw_info_screen, SpChar.INFO, "WHITE", "PURPLE"
            ),
        ]

    def update_clock(self):
        """
        Update just the clock on the screen
        """
        self.__draw_clock()
        pygame.display.flip()
        # This line is a hack to force the screen to redraw
        pygame.event.get()

    @draw_func
    def draw_no_network(self):
        """
        Display no network connection
        """
        self.win.fill(self.c.WHITE)
        self.win.blit(FONT_M2.render("Waiting for a", 1, self.c.BLACK), (25, 70))
        self.win.blit(FONT_M2.render("network conn", 1, self.c.BLACK), (25, 120))
        self.buttons = [ShutdownButton(self.layout["util"], quit)]

    async def wait_for_network(self):
        """
        Sleep while waiting for a missing network 
        """
        logger.info("No network")
        self.draw_no_network()
        await aio.sleep(5)
        self.on_main = True
        await self.refresh_data(ignore_updated=True)

    def __error_msg(self, line1: str, line2: str, btnf: Callable):
        """
        Display an error message and cancel button
        """
        self.win.fill(self.c.WHITE)
        point = self.layout["error"]["line1"]
        self.win.blit(FONT_M2.render(line1, 1, self.c.BLACK), point)
        point = self.layout["error"]["line2"]
        self.win.blit(FONT_M2.render(line2, 1, self.c.BLACK), point)
        self.buttons = [CancelButton(action=btnf)]

    @draw_func
    def error_no_data(self):
        """
        Display unavailable report message
        """
        self.__error_msg(
            f"{self.station} has no", "current METAR", self.draw_selection_screen
        )

    @draw_func
    def error_station(self):
        """
        Display invalid station message
        """
        self.__error_msg(
            f"{self.station} is not", "a valid station", self.draw_selection_screen
        )

    @draw_func
    def error_reporting(self):
        """
        Display non-reporting station message
        """
        self.__error_msg(
            f"{self.station} does", "not send METARs", self.draw_selection_screen
        )

    @draw_func
    def error_unknown(self):
        """
        Display unknown error message
        """
        logger.exception("Unknown error")
        self.__error_msg("There was an", "unknown error", self.draw_selection_screen)

    @draw_func
    def error_connection(self):
        """
        Display timeout message and sleep
        """
        logger.warning("Connection Timeout")
        self.__error_msg("Could not fetch", "data from source", self.draw_main)
        point = self.layout["error"]["refresh"]
        self.buttons.append(
            IconButton(point, self.refresh_data, SpChar.RELOAD, "WHITE", "GRAY")
        )
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
        if time.time() >= screen.update_time:
            logger.debug("Auto update")
            await screen.refresh_data()
        await aio.sleep(10)


async def input_loop(screen: METARScreen):
    """
    Handles user input and calling button functions when clicked
    """
    while True:
        for event in pygame.event.get():
            if event.type == pygame.MOUSEBUTTONDOWN:
                pos = pygame.mouse.get_pos()
                if cfg.hide_mouse:
                    hide_mouse()
                for button in screen.buttons:
                    if button.is_clicked(pos):
                        button.onclick()
                        break
        await aio.sleep(0.01)


async def clock_loop(screen: METARScreen):
    """
    Handles updating the clock while on the main screen
    """
    while True:
        if screen.on_main:
            screen.update_clock()
        await aio.sleep(1)


def run_with_touch_input(screen: METARScreen, *coros: [Callable]):
    """
    Runs an async screen function with touch input enabled
    """
    coros = [*coros, input_loop(screen)]
    aio.run(aio.wait(coros, return_when=aio.FIRST_COMPLETED))


def main():
    """
    Program main handles METAR data handling and user interaction flow
    """
    logger.debug("Booting")
    screen = METARScreen.from_session(common.load_session(), cfg.layout["size"])
    screen.draw_loading_screen()
    run_with_touch_input(screen, screen.refresh_data(force_main=True))
    logger.debug("Setup complete")
    coros = [update_loop(screen)]
    if "clock" in screen.layout["main"]:
        coros.append(clock_loop(screen))
    run_with_touch_input(screen, *coros)


if __name__ == "__main__":
    main()
