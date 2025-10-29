"""Display ICAO METAR weather data with a Raspberry Pi and touchscreen."""

import asyncio as aio
import math
import sys
import time
from collections.abc import Callable, Coroutine
from copy import copy
from datetime import UTC, datetime
from os import system
from typing import Any, Self

import pygame
from avwx import Metar, Station
from avwx.exceptions import BadStation, InvalidRequest, SourceError
from avwx.structs import Cloud, MetarData, Number, Units
from dateutil.tz import tzlocal

import metar_raspi.config as cfg
from metar_raspi import common
from metar_raspi.common import IDENT_CHARS, logger
from metar_raspi.layout import Color, Coord, Layout, SpChar

LAYOUT = Layout.from_file(cfg.layout_path)


# Init pygame and fonts
pygame.init()
ICON_PATH = cfg.LOC / "icons"
FONT_PATH = str(ICON_PATH / "DejaVuSans.ttf")

FONT_S1 = pygame.font.Font(FONT_PATH, LAYOUT.fonts.s1)
FONT_S2 = pygame.font.Font(FONT_PATH, LAYOUT.fonts.s2)
FONT_S3 = pygame.font.Font(FONT_PATH, LAYOUT.fonts.s3)
FONT_M1 = pygame.font.Font(FONT_PATH, LAYOUT.fonts.m1)
FONT_M2 = pygame.font.Font(FONT_PATH, LAYOUT.fonts.m2)
FONT_L1 = pygame.font.Font(FONT_PATH, LAYOUT.fonts.l1)
if LAYOUT.fonts.l2:
    FONT_L2 = pygame.font.Font(FONT_PATH, LAYOUT.fonts.l2)


def midpoint(p1: Coord, p2: Coord) -> Coord:
    """Returns the midpoint between two points."""
    return (p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2


def centered(rendered_text: pygame.Surface, around: Coord) -> Coord:
    """Returns the top left point for rendered text at a center point."""
    width, height = rendered_text.get_size()
    return around[0] - width // 2 + 1, around[1] - height // 2 + 1


def radius_point(degree: int, center: Coord, radius: int) -> Coord:
    """Returns the degree point on the circumference of a circle."""
    degree %= 360
    x = center[0] + radius * math.cos((degree - 90) * math.pi / 180)
    y = center[1] + radius * math.sin((degree - 90) * math.pi / 180)
    return int(x), int(y)


def hide_mouse() -> None:
    """This makes the mouse transparent."""
    pygame.mouse.set_cursor((8, 8), (0, 0), (0, 0, 0, 0, 0, 0, 0, 0), (0, 0, 0, 0, 0, 0, 0, 0))


class Button:
    """Base button class.

    Runs a function when clicked
    """

    # Function to run when clicked. Cannot accept args
    onclick: Callable
    # Text settings
    text: str
    fontsize: int
    # Color strings must match Color.attr names
    fontcolor: str

    def draw(self, win: pygame.Surface, color: Color) -> None:
        """Draw the button on the window with the current color palette."""
        raise NotImplementedError

    def is_clicked(self, pos: Coord) -> bool:
        """Returns True if the position is within the button bounds."""
        raise NotImplementedError


class RectButton(Button):
    """Rectangular buttons can contain text."""

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
        bounds: tuple[int, int, int, int],
        action: Callable,
        text: str,
        fontsize: int = LAYOUT.fonts.s3,
        fontcolor: str = "Black",
        thickness: int = LAYOUT.button.outline,
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

    def draw(self, win: pygame.Surface, color: Color) -> None:
        """Draw the button on the window with the current color palette."""
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

    def is_clicked(self, pos: Coord) -> bool:
        """Returns True if the position is within the button bounds."""
        return self.x1 < pos[0] < self.x2 and self.y1 < pos[1] < self.y2


class RoundButton(Button):
    """Round buttons."""

    # Center pixel and radius
    x: int
    y: int
    radius: int

    def __init__(
        self,
        center: Coord,
        action: Callable,
        radius: int = LAYOUT.button.radius,
    ):
        self.center = center
        self.radius = radius
        self.onclick = action

    def is_clicked(self, pos: Coord) -> bool:
        """Returns True if the position is within the button bounds."""
        x, y = self.center
        return self.radius > math.hypot(x - pos[0], y - pos[1])


class IconButton(RoundButton):
    """Round button which contain a letter or symbol."""

    # Fill color
    fill: str = "WHITE"
    fontcolor: str = "BLACK"
    fontsize: int = LAYOUT.fonts.l1
    radius: int = LAYOUT.button.radius

    def __init__(
        self,
        center: Coord | None = None,
        action: Callable | None = None,
        icon: str | None = None,
        fontcolor: str | None = None,
        fill: str | None = None,
        radius: int | None = None,
        fontsize: int | None = None,
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

    def draw(self, win: pygame.Surface, color: Color) -> None:
        """Draw the button on the window with the current color palette."""
        if self.fill is not None:
            pygame.draw.circle(win, color[self.fill], self.center, self.radius)
        if self.icon is not None:
            font = pygame.font.Font(FONT_PATH, self.fontsize)
            rendered = font.render(self.icon, 1, color[self.fontcolor])
            win.blit(rendered, centered(rendered, self.center))


class ShutdownButton(RoundButton):
    """Round button with a drawn shutdown symbol."""

    fontcolor: str = "WHITE"
    fill: str = "RED"

    def draw(self, win: pygame.Surface, color: Color) -> None:
        """Draw the button on the window with the current color palette."""
        pygame.draw.circle(win, color[self.fill], self.center, self.radius)
        pygame.draw.circle(win, color[self.fontcolor], self.center, self.radius - 6)
        pygame.draw.circle(win, color[self.fill], self.center, self.radius - 9)
        rect = ((self.center[0] - 2, self.center[1] - 10), (4, 20))
        pygame.draw.rect(win, color[self.fontcolor], rect)


class SelectionButton(RoundButton):
    """Round button with icons resembling selection screen."""

    fontcolor: str = "WHITE"
    fill: str = "GREEN"

    def draw(self, win: pygame.Surface, color: Color) -> None:
        """Draw the button on the window with the current color palette."""
        pygame.draw.circle(win, color[self.fill], self.center, self.radius)
        font = FONT_S3 if LAYOUT.large_display else FONT_M1
        for char, direction in ((SpChar.UP_TRIANGLE, -1), (SpChar.DOWN_TRIANGLE, 1)):
            tri = font.render(char, 1, color[self.fontcolor])
            topleft = list(centered(tri, self.center))
            topleft[1] += int(self.radius * 0.5) * direction - 3
            win.blit(tri, topleft)


class CancelButton(IconButton):
    center: Coord = LAYOUT.util_pos
    icon: str = SpChar.CANCEL
    fontcolor: str = "WHITE"
    fill: str = "GRAY"


def draw_func(func: Callable[["METARScreen"], None]) -> Callable[["METARScreen"], None]:
    """Decorator wraps drawing functions with common commands."""

    def wrapper(screen: "METARScreen") -> None:
        screen.on_main = False
        screen.buttons = []
        func(screen)
        screen.draw_buttons()
        pygame.display.flip()
        # This line is a hack to force the screen to redraw
        pygame.event.get()

    return wrapper


class METARScreen:
    """Controls and draws UI elements."""

    ident: list[int]
    old_ident: list[int]
    width: int
    height: int
    win: pygame.Surface
    c: Color
    inverted: bool
    update_time: float
    buttons: list[Button]
    layout: Layout
    is_large: bool

    on_main: bool = False

    def __init__(self, station: str, size: Coord, *, inverted: bool):
        logger.debug("Running init")
        try:
            self.metar = Metar(station)
        except BadStation:
            self.metar = Metar("KJFK")
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
        self.layout = LAYOUT
        self.is_large = self.layout.large_display
        logger.debug("Finished running init")

    @property
    def station(self) -> str:
        """The current station."""
        return common.ident_to_station(self.ident)

    @classmethod
    def from_session(cls, session: dict, size: Coord) -> Self:
        """Returns a new Screen from a saved session."""
        station = session.get("station", "KJFK")
        inverted = session.get("inverted", True)
        return cls(station, size, inverted=inverted)

    def export_session(self, *, save: bool = True) -> dict:
        """Saves or returns a dictionary representing the session's state."""
        session = {"station": self.station, "inverted": self.inverted}
        if save:
            common.save_session(session)
        return session

    def reset_update_time(self, interval: int | None = None) -> None:
        """Call to reset the update time to now plus the update interval."""
        self.update_time = time.time() + (interval or cfg.update_interval)

    async def refresh_data(self, *, force_main: bool = False, ignore_updated: bool = False) -> None:
        """Refresh existing station data."""
        logger.info("Calling refresh update")
        try:
            updated = await self.metar.async_update()
        except ConnectionError:
            await self.wait_for_network()
        except (TimeoutError, SourceError):
            self.error_connection()
        except InvalidRequest:
            self.error_station()
        except Exception as exc:  # noqa: BLE001
            logger.exception(f"An unknown error has occurred: {exc}")
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

    async def new_station(self) -> None:
        """Update the current station from ident and display new main screen."""
        logger.info("Calling new update")
        self.draw_loading_screen()
        new_metar = Metar(self.station)
        try:
            if not await new_metar.async_update():
                self.error_no_data()
                return
        except (TimeoutError, ConnectionError, SourceError):
            self.error_connection()
        except InvalidRequest:
            self.error_station()
        except Exception as exc:  # noqa: BLE001
            logger.exception(f"An unknown error has occurred: {exc}")
            self.error_unknown()
        else:
            logger.info(new_metar.raw)
            self.metar = new_metar
            self.old_ident = copy(self.ident)
            self.reset_update_time()
            self.export_session()
            self.draw_main()

    async def verify_station(self) -> None:
        """Verifies the station value before calling new data."""
        try:
            station = Station.from_icao(self.station)
            if not station.sends_reports:
                self.error_reporting()
                return
        except BadStation:
            self.error_station()
        else:
            await self.new_station()

    def cancel_station(self) -> None:
        """Revert ident and redraw main screen."""
        self.ident = self.old_ident
        if self.metar.data is None:
            self.error_no_data()
        else:
            self.draw_main()

    def draw_buttons(self) -> None:
        """Draw all current buttons."""
        for button in self.buttons:
            button.draw(self.win, self.c)

    @draw_func
    def draw_selection_screen(self) -> None:
        """Load selection screen elements."""
        self.win.fill(self.c.WHITE)
        # Draw Selection Grid
        yes, no = self.layout.select.yes, self.layout.select.no
        self.buttons = [
            IconButton(yes, self.verify_station, SpChar.CHECKMARK, "WHITE", "GREEN"),
            CancelButton(no, self.cancel_station, fill="RED"),
        ]
        upy = self.layout.select.row_up
        chary = self.layout.select.row_char
        downy = self.layout.select.row_down
        for col in range(4):
            x = self.__selection_get_x(col)
            self.buttons.append(IconButton((x, upy), self.__incr_ident(col, down=True), SpChar.UP_TRIANGLE))
            self.buttons.append(IconButton((x, downy), self.__incr_ident(col, down=False), SpChar.DOWN_TRIANGLE))
            rendered = FONT_L1.render(IDENT_CHARS[self.ident[col]], 1, self.c.BLACK)
            self.win.blit(rendered, centered(rendered, (x, chary)))

    def __selection_get_x(self, col: int) -> int:
        """Returns the top left x pixel for a desired column."""
        offset = self.layout.select.col_offset
        spacing = self.layout.select.col_spacing
        return offset + col * spacing

    def __incr_ident(self, pos: int, *, down: bool) -> Callable:
        """Returns a function to update and replace ident char on display.

        pos: 0-3 column
        down: increment/decrement counter
        """

        def update_func() -> None:
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
            x = self.__selection_get_x(pos)
            chary = self.layout.select.row_char
            spacing = self.layout.select.col_spacing
            region = (x - spacing / 2, chary - spacing / 2, spacing, spacing)
            pygame.draw.rect(self.win, self.c.WHITE, region)
            self.win.blit(rendered, centered(rendered, (x, chary)))
            pygame.display.update(region)

        return update_func

    @draw_func
    def draw_loading_screen(self) -> None:
        """Display load screen."""
        # Reset on_main because the main screen should always display on success
        self.on_main = True
        self.win.fill(self.c.WHITE)
        point = self.layout.error.line1
        self.win.blit(FONT_M2.render("Fetching weather", 1, self.c.BLACK), point)
        point = self.layout.error.line2
        self.win.blit(FONT_M2.render("data for " + self.station, 1, self.c.BLACK), point)

    def __draw_clock(self) -> None:
        """Draw the clock components."""
        if not (self.layout.main.clock and self.layout.main.clock_label):
            return
        now = datetime.now(UTC) if cfg.clock_utc else datetime.now(tzlocal())
        label = now.tzname() or "UTC"
        clock_font = globals().get("FONT_L2") or FONT_L1
        clock_text = clock_font.render(now.strftime(cfg.clock_format), 1, self.c.BLACK)
        x, y = self.layout.main.clock
        w, h = clock_text.get_size()
        pygame.draw.rect(self.win, self.c.WHITE, ((x, y), (x + w, (y + h) * 0.9)))
        self.win.blit(clock_text, (x, y))
        label_font = FONT_M1 if self.is_large else FONT_S3
        point = self.layout.main.clock_label
        self.win.blit(label_font.render(label, 1, self.c.BLACK), point)

    def __draw_wind_compass(self, data: MetarData, center: Coord, radius: int) -> None:
        """Draw the wind direction compass."""
        wdir = data.wind_direction
        var = data.wind_variable_direction
        pygame.draw.circle(self.win, self.c.GRAY, center, radius, 3)
        if data.wind_speed and not data.wind_speed.value:
            text = FONT_S3.render("Calm", 1, self.c.BLACK)
        elif wdir and wdir.repr == "VRB":
            text = FONT_S3.render("VRB", 1, self.c.BLACK)
        elif wdir and (wdir_value := wdir.value):
            text = FONT_M1.render(str(wdir_value).zfill(3), 1, self.c.BLACK)
            rad_point = radius_point(int(wdir_value), center, radius)
            width = 4 if self.is_large else 2
            pygame.draw.line(self.win, self.c.RED, center, rad_point, width)
            if var:
                for point in var:
                    if point.value is not None:
                        rad_point = radius_point(int(point.value), center, radius)
                        pygame.draw.line(self.win, self.c.BLUE, center, rad_point, width)
        else:
            text = FONT_L1.render(SpChar.CANCEL, 1, self.c.RED)
        self.win.blit(text, centered(text, center))

    def __draw_wind(self, data: MetarData, unit: str) -> None:
        """Draw the dynamic wind elements."""
        speed, gust = data.wind_speed, data.wind_gust
        point = self.layout.main.wind_compass
        radius = self.layout.main.wind_compass_radius
        self.__draw_wind_compass(data, point, radius)
        if speed and speed.value:
            rendered = FONT_S3.render(f"{speed.value} {unit}", 1, self.c.BLACK)
            point = self.layout.main.wind_speed
            self.win.blit(rendered, centered(rendered, point))
        text = f"G: {gust.value}" if gust else "No Gust"
        rendered = FONT_S3.render(text, 1, self.c.BLACK)
        self.win.blit(rendered, centered(rendered, self.layout.main.wind_gust))

    def __draw_temp_icon(self, temp: int) -> None:
        """Draw the temperature icon."""
        if not self.layout.main.temp_icon:
            return
        therm_level = 0
        if temp:
            therm_level = temp // 12 + 2
            if therm_level < 0:
                therm_level = 0
        add_i = "I" if self.inverted else ""
        therm_icon = f"Therm{therm_level}{add_i}.png"
        point = self.layout.main.temp_icon
        self.win.blit(pygame.image.load(str(ICON_PATH / therm_icon)), point)

    def __draw_temp_dew_humidity(self, data: MetarData) -> None:
        """Draw the dynamic temperature, dewpoint, and humidity elements."""
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
        point = self.layout.main.dew
        self.win.blit(FONT_S3.render(dew_text, 1, self.c.BLACK), point)
        # Temperature
        if temp and temp.value is not None:
            temp_text += f"{temp.value}{SpChar.DEGREES}"
            if self.is_large and self.metar.units:
                temp_text += self.metar.units.temperature
            temp_diff = temp.value - 15
            diff_sign = "-" if temp_diff < 0 else "+"
            diff_text += f"{diff_sign}{abs(temp_diff)}{SpChar.DEGREES}"
        else:
            temp_text += "--"
            diff_text += "--"
        point = self.layout.main.temp
        self.win.blit(FONT_S3.render(temp_text, 1, self.c.BLACK), point)
        point = self.layout.main.temp_stdv
        self.win.blit(FONT_S3.render(diff_text, 1, self.c.BLACK), point)
        if temp and temp.value is not None and self.layout.main.temp_icon:
            self.__draw_temp_icon(int(temp.value))
        # Humidity
        if temp and dew and isinstance(temp.value, int) and isinstance(dew.value, int):
            rel_humidity = (
                (6.11 * 10.0 ** (7.5 * dew.value / (237.7 + dew.value)))
                / (6.11 * 10.0 ** (7.5 * temp.value / (237.7 + temp.value)))
                * 100
            )
            hmd_text += f"{int(rel_humidity)}%"
        else:
            hmd_text += "--"
        point = self.layout.main.humid
        self.win.blit(FONT_S3.render(hmd_text, 1, self.c.BLACK), point)

    def __draw_cloud_graph(self, clouds: list[Cloud], tl: Coord, br: Coord) -> None:
        """Draw cloud layers in chart.

        Scales everything based on top left and bottom right points
        """
        tlx, tly = tl
        brx, bry = br
        header = FONT_S3.render("Clouds AGL", 1, self.c.BLACK)
        header_height = header.get_size()[1]
        header_point = midpoint(tl, (brx, tly + header_height))
        self.win.blit(header, centered(header, header_point))
        tly += header_height
        pygame.draw.lines(self.win, self.c.BLACK, False, ((tlx, tly), (tlx, bry), (brx, bry)), 3)
        if not clouds:
            text = FONT_M2.render("CLR", 1, self.c.BLUE)
            self.win.blit(text, centered(text, midpoint((tlx, tly), (brx, bry))))
            return
        top = 80
        left_side = True
        tlx += 5
        brx -= 5
        bry -= 10
        for cloud in clouds[::-1]:
            if cloud.base:
                if cloud.base > top:
                    top = cloud.base
                draw_height = bry - (bry - tly) * cloud.base / top
                text = FONT_S1.render(cloud.repr, 1, self.c.BLUE)
                width, height = text.get_size()
                liney = draw_height + height / 2
                if left_side:
                    self.win.blit(text, (tlx, draw_height))
                    pygame.draw.line(self.win, self.c.BLUE, (tlx + width + 2, liney), (brx, liney))
                else:
                    self.win.blit(text, (brx - width, draw_height))
                    pygame.draw.line(self.win, self.c.BLUE, (tlx, liney), (brx - width - 2, liney))
                left_side = not left_side

    def __draw_wx_raw(self) -> None:
        """Draw wx and raw report."""
        if not (self.layout.wx_raw and self.metar.data and self.metar.data.raw):
            return
        x, y = self.layout.wx_raw.start
        spacing = self.layout.wx_raw.line_space
        raw_key = "large"
        wxs = [c.value for c in self.metar.data.wx_codes]
        wxs.sort(key=lambda x: len(x))
        if wxs:
            wx_length = self.layout.wx_raw.wx_length
            y = self.__draw_text_lines(wxs, (x, y), wx_length, spacing)
            raw_key = "small"
        raw_font, raw_length, raw_padding = getattr(self.layout.wx_raw, raw_key)
        y += raw_padding
        self.__draw_text_lines(self.metar.data.raw, (x, y), raw_length, spacing, fontsize=raw_font)

    def get_timestamp(self, data: MetarData) -> str:
        """"""
        if not (data.time and data.time.dt):
            return "---"
        tstamp = data.time.dt
        if not cfg.clock_utc:
            tstamp = tstamp.astimezone(tzlocal())
        return tstamp.strftime(cfg.timestamp_format)

    def __draw_station_and_timestamp(self, data: MetarData) -> None:
        """Draw station identifier and timestamp."""
        station = data.station or "----"
        tstamp = self.get_timestamp(data)
        if point := self.layout.main.title:
            time_text = station + "  " + tstamp
            self.win.blit(FONT_M1.render(time_text, 1, self.c.BLACK), point)
        elif point := self.layout.main.station:
            self.win.blit(FONT_M1.render(station, 1, self.c.BLACK), point)
            if self.is_large and (point := self.layout.main.timestamp_label):
                self.win.blit(FONT_S3.render("Updated", 1, self.c.BLACK), point)
            else:
                tstamp = "TS: " + tstamp
            if point := self.layout.main.timestamp:
                self.win.blit(FONT_S3.render(tstamp, 1, self.c.BLACK), point)

    def __draw_flight_rules(self, flight_rules: str) -> None:
        """Draw the current flight rules."""
        fr_color, fr_x_offset = self.layout.flight_rules[flight_rules]
        point = list(self.layout.main.flight_rules)
        point[0] += fr_x_offset
        self.win.blit(FONT_M1.render(flight_rules, 1, fr_color), point)

    def __draw_altimeter(self, altim: Number | None) -> None:
        """Draw the altimeter setting."""
        text = "Altm " if self.is_large else "ALT: "
        text += str(altim.value) if altim else "--"
        point = self.layout.main.altim
        self.win.blit(FONT_S3.render(text, 1, self.c.BLACK), point)

    def __draw_visibility(self, vis: Number | None) -> None:
        """Draw the visibility."""
        text = "Visb " if self.is_large else "VIS: "
        text += str(vis.value) if vis else "--"
        point = self.layout.main.vis
        self.win.blit(FONT_S3.render(text, 1, self.c.BLACK), point)

    def __main_draw_dynamic(self, data: MetarData, units: Units) -> None:
        """Load Main dynamic foreground elements.

        Returns True if "Other-WX" or "Remarks" is not empty, else False
        """
        self.__draw_station_and_timestamp(data)
        self.__draw_flight_rules(data.flight_rules or "N/A")
        self.__draw_wind(data, units.wind_speed)
        self.__draw_temp_dew_humidity(data)
        self.__draw_altimeter(data.altimeter)
        self.__draw_visibility(data.visibility)
        top_left, bottom_right = self.layout.main.cloud_graph
        self.__draw_cloud_graph(data.clouds, top_left, bottom_right)

    def __draw_text_lines(
        self,
        items: str | list[str],
        left_point: Coord,
        length: int,
        space: int,
        header: str | None = None,
        right_x: int | None = None,
        fontsize: int | None = None,
    ) -> int:
        """Draw lines of text with header, columns, and line wrapping."""
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
            if right_x is not None and len(item) > length and not left:
                y += space
                left = not left
            x = left_x if left else right_x
            if x is None:
                msg = "Text line x coordinate cannot be None"
                raise ValueError(msg)
            # Line overflow control
            if right_x is None:
                while len(item) > length:
                    cut_point = item[:length].rfind(" ")
                    text = font.render(item[:cut_point], 1, self.c.BLACK)
                    self.win.blit(text, (x, y))
                    y += text.get_size()[1] + space
                    item = item[cut_point + 1 :]  # noqa: PLW2901
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
    def draw_rmk(self) -> None:
        """Display available Other Weather / Remarks and cancel button control."""
        if not self.metar.data:
            self.error_no_data()
            return
        if self.layout.wx_rmk is None:
            return
        left = self.layout.wx_rmk.col1
        right = self.layout.wx_rmk.col2
        y = self.layout.wx_rmk.padding
        line_space = self.layout.wx_rmk.line_space
        self.win.fill(self.c.WHITE)
        # Weather
        wxs = [c.value for c in self.metar.data.wx_codes]
        wxs.sort(key=lambda x: len(x))
        if wxs:
            wx_length = self.layout.wx_rmk.wx_length
            y = self.__draw_text_lines(
                wxs,
                (left, y),
                wx_length,
                line_space,
                header="Other Weather",
                right_x=right,
            )
        # Remarks
        rmk = self.metar.data.remarks
        if rmk:
            rmk_length = self.layout.wx_rmk.rmk_length
            self.__draw_text_lines(rmk, (left, y), rmk_length, line_space, header="Remarks")
        self.buttons = [CancelButton(action=self.draw_main)]

    @draw_func
    def draw_main(self) -> None:
        """Run main data display and options touch button control."""
        if not (self.metar.data and self.metar.units):
            self.error_no_data()
            return
        self.win.fill(self.c.WHITE)
        self.__main_draw_dynamic(self.metar.data, self.metar.units)
        self.buttons = [
            IconButton(
                self.layout.util_pos,
                self.draw_options_bar,
                SpChar.SETTINGS,
                "WHITE",
                "GRAY",
            )
        ]
        if self.is_large:
            self.__draw_wx_raw()
        else:
            wx = self.metar.data.wx_codes
            rmk = self.metar.data.remarks
            if wx or rmk:
                if wx and rmk:
                    text, color = "WX/RMK", "PURPLE"
                elif wx:
                    text, color = "WX", "RED"
                elif rmk:
                    text, color = "RMK", "BLUE"
                rect = self.layout.main.wxrmk
                self.buttons.append(RectButton(rect, self.draw_rmk, text, fontcolor=color))
        self.__draw_clock()
        self.on_main = True

    def invert_wb(self, *, redraw: bool = True) -> None:
        """Invert the black and white of the display."""
        self.inverted = not self.inverted
        self.c.BLACK, self.c.WHITE = self.c.WHITE, self.c.BLACK
        self.export_session()
        if redraw:
            self.draw_main()

    @draw_func
    def draw_quit_screen(self) -> None:
        """Display Shutdown/Exit option and touch button control.

        Returns False or exits program
        """
        self.win.fill(self.c.WHITE)
        text = "Shutdown the Pi?" if cfg.shutdown_on_exit else "Exit the program?"
        rendered = FONT_M2.render(text, 1, self.c.BLACK)
        point = self.width // 2, self.layout.quit.text_y
        self.win.blit(rendered, centered(rendered, point))
        pointy, pointn = self.layout.quit.yes, self.layout.quit.no
        self.buttons = [
            IconButton(pointy, quit, SpChar.CHECKMARK, "WHITE", "GREEN"),
            CancelButton(pointn, self.draw_main, fill="RED"),
        ]

    @draw_func
    def draw_info_screen(self) -> None:
        """Display info screen and cancel touch button control."""
        self.win.fill(self.c.WHITE)
        for text, key, font in (
            ("METAR-RasPi", "title", FONT_M2),
            ("Michael duPont", "name", FONT_S3),
            ("michael@mdupont.com", "email", FONT_S3),
            ("github.com/devdupont/METAR-RasPi", "url", FONT_S1),
        ):
            point = self.width // 2, getattr(self.layout.info, key + "_y")
            rendered = font.render(text, 1, self.c.BLACK)
            self.win.blit(rendered, centered(rendered, point))
        self.buttons = [CancelButton(action=self.draw_main)]

    @draw_func
    def draw_options_bar(self) -> None:
        """Draws options bar display."""
        # Clear Option background
        height, width = self.layout.main.util_back
        pygame.draw.rect(self.win, self.c.WHITE, ((0, height), (width, self.height)))
        invchar = SpChar.SUN if self.inverted else SpChar.MOON
        btnx, btny = self.layout.util_pos
        spacing = self.layout.main.util_spacing

        def get_x(n: int) -> int:
            return btnx + spacing * n

        self.buttons = [
            CancelButton((get_x(0), btny), self.draw_main),
            SelectionButton((get_x(1), btny), self.draw_selection_screen),
            ShutdownButton((get_x(2), btny), self.draw_quit_screen),
            IconButton((get_x(3), btny), self.invert_wb, invchar, "WHITE", "BLACK"),
            IconButton((get_x(4), btny), self.draw_info_screen, SpChar.INFO, "WHITE", "PURPLE"),
        ]

    def update_clock(self) -> None:
        """Update just the clock on the screen."""
        self.__draw_clock()
        pygame.display.flip()
        # This line is a hack to force the screen to redraw
        pygame.event.get()

    @draw_func
    def draw_no_network(self) -> None:
        """Display no network connection."""
        self.win.fill(self.c.WHITE)
        self.win.blit(FONT_M2.render("Waiting for a", 1, self.c.BLACK), (25, 70))
        self.win.blit(FONT_M2.render("network conn", 1, self.c.BLACK), (25, 120))
        self.buttons = [ShutdownButton(self.layout.util_pos, quit)]

    async def wait_for_network(self) -> None:
        """Sleep while waiting for a missing network."""
        logger.info("No network")
        self.draw_no_network()
        await aio.sleep(5)
        self.on_main = True
        await self.refresh_data(ignore_updated=True)

    def __error_msg(self, line1: str, line2: str, btnf: Callable) -> None:
        """Display an error message and cancel button."""
        self.win.fill(self.c.WHITE)
        point = self.layout.error.line1
        self.win.blit(FONT_M2.render(line1, 1, self.c.BLACK), point)
        point = self.layout.error.line2
        self.win.blit(FONT_M2.render(line2, 1, self.c.BLACK), point)
        self.buttons = [CancelButton(action=btnf)]

    @draw_func
    def error_no_data(self) -> None:
        """Display unavailable report message."""
        self.__error_msg(f"{self.station} has no", "current METAR", self.draw_selection_screen)

    @draw_func
    def error_station(self) -> None:
        """Display invalid station message."""
        self.__error_msg(f"{self.station} is not", "a valid station", self.draw_selection_screen)

    @draw_func
    def error_reporting(self) -> None:
        """Display non-reporting station message."""
        self.__error_msg(f"{self.station} does", "not send METARs", self.draw_selection_screen)

    @draw_func
    def error_unknown(self) -> None:
        """Display unknown error message."""
        logger.exception("Unknown error")
        self.__error_msg("There was an", "unknown error", self.draw_selection_screen)

    @draw_func
    def error_connection(self) -> None:
        """Display timeout message and sleep."""
        logger.warning("Connection Timeout")
        self.__error_msg("Could not fetch", "data from source", self.draw_main)
        point = self.layout.error.refresh
        self.buttons.append(IconButton(point, self.refresh_data, SpChar.RELOAD, "WHITE", "GRAY"))
        self.reset_update_time(cfg.timeout_interval)
        self.on_main = True


def shutdown() -> None:
    """Shutdown the program and optionally the system."""
    logger.debug("Quit")
    if cfg.shutdown_on_exit:
        system("shutdown -h now")  # noqa: S605,S607
    sys.exit(0)


async def update_loop(screen: METARScreen) -> None:
    """Handles updating the METAR data in the background."""
    while True:
        if time.time() >= screen.update_time:
            logger.debug("Auto update")
            await screen.refresh_data()
        await aio.sleep(10)


async def input_loop(screen: METARScreen) -> None:
    """Handles user input and calling button functions when clicked."""
    while True:
        for event in pygame.event.get():
            if event.type == pygame.MOUSEBUTTONDOWN:
                pos = pygame.mouse.get_pos()
                if cfg.hide_mouse:
                    hide_mouse()
                for button in screen.buttons:
                    if button.is_clicked(pos):
                        if aio.iscoroutinefunction(button.onclick):
                            await button.onclick()
                        else:
                            button.onclick()
                        break
        await aio.sleep(0.01)


async def clock_loop(screen: METARScreen) -> None:
    """Handles updating the clock while on the main screen."""
    while True:
        if screen.on_main:
            screen.update_clock()
        await aio.sleep(1)


def run_with_touch_input(screen: METARScreen, *tasks: Coroutine[Any, Any, None]) -> None:
    """Runs an async screen function with touch input enabled."""
    coros = [*tasks, input_loop(screen)]

    async def run_tasks() -> None:
        await aio.wait((aio.create_task(coro) for coro in coros), return_when=aio.FIRST_COMPLETED)

    aio.run(run_tasks())


def main() -> None:
    """Program main handles METAR data handling and user interaction flow."""
    logger.debug("Booting")
    screen = METARScreen.from_session(common.load_session(), LAYOUT.size)
    screen.draw_loading_screen()
    run_with_touch_input(screen, screen.refresh_data(force_main=True))
    logger.debug("Setup complete")
    coros = [update_loop(screen)]
    if screen.layout.main.clock:
        coros.append(clock_loop(screen))
    run_with_touch_input(screen, *coros)


if __name__ == "__main__":
    main()
