"""Screen layout definitions and loading."""

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Self, TypeAlias

Coord: TypeAlias = tuple[int, int]
ColorT: TypeAlias = tuple[int, int, int]


class SpChar(StrEnum):
    """Special Characters."""

    CANCEL = "\u2715"
    CHECKMARK = "\u2713"
    DEGREES = "\u00b0"
    DOWN_TRIANGLE = "\u25bc"
    INFO = "\u2139"
    MOON = "\u263e"
    RELOAD = "\u21ba"
    SETTINGS = "\u2699"
    SUN = "\u2600"
    UP_TRIANGLE = "\u25b2"


# Because we swap black/white values for invert, we can't use enum here
class Color:
    """RGB color values."""

    WHITE: ColorT = 255, 255, 255
    BLACK: ColorT = 0, 0, 0
    RED: ColorT = 255, 0, 0
    GREEN: ColorT = 0, 255, 0
    BLUE: ColorT = 0, 0, 255
    PURPLE: ColorT = 150, 0, 255
    GRAY: ColorT = 60, 60, 60

    def __getitem__(self, key: str) -> ColorT:
        try:
            color: ColorT = getattr(self, key)
        except AttributeError as exc:
            msg = f"{key} is not a set color"
            raise KeyError(msg) from exc
        else:
            return color


@dataclass
class FontSize:
    """Font sizes for various text elements."""

    s1: int
    s2: int
    s3: int
    m1: int
    m2: int
    l1: int
    l2: int | None

    @classmethod
    def from_dict(cls, data: dict[str, int]) -> Self:
        """Load font sizes from a dictionary."""
        return cls(
            s1=data["s1"],
            s2=data["s2"],
            s3=data["s3"],
            m1=data["m1"],
            m2=data["m2"],
            l1=data["l1"],
            l2=data.get("l2"),
        )


@dataclass
class ButtonLayout:
    """Button layout settings."""

    radius: int
    outline: int

    @classmethod
    def from_dict(cls, data: dict[str, int]) -> Self:
        """Load button layout settings from a dictionary."""
        return cls(
            radius=data["radius"],
            outline=data["outline"],
        )


@dataclass
class FlightRulesLayout:
    """Flight rules layout settings."""

    vfr: tuple[ColorT, int]
    mvfr: tuple[ColorT, int]
    ifr: tuple[ColorT, int]
    lifr: tuple[ColorT, int]
    na: tuple[ColorT, int]

    def __getitem__(self, key: str) -> tuple[ColorT, int]:
        return getattr(self, key, self.na)

    @classmethod
    def from_dict(cls, data: dict[str, int]) -> Self:
        """Load flight rules layout settings from a dictionary."""
        return cls(
            vfr=(Color.GREEN, data["VFR"]),
            mvfr=(Color.BLUE, data["MVFR"]),
            ifr=(Color.RED, data["IFR"]),
            lifr=(Color.PURPLE, data["LIFR"]),
            na=(Color.BLACK, data["N/A"]),
        )


def as_tuple(data: Any) -> Coord:
    """Convert input data to a 2D coordinate tuple."""
    if data is None:
        msg = "Expected coordinate data, got None"
        raise ValueError(msg)
    if not isinstance(data, list | tuple) or len(data) != 2:
        msg = f"Expected coordinate data, got {data!r}"
        raise ValueError(msg)
    return tuple(data)


def opt_tuple(data: Any) -> Coord | None:
    """Convert input data to a 2D coordinate tuple or return None."""
    if data is None:
        return None
    return as_tuple(data)


@dataclass
class MainLayout:
    """Main layout settings."""

    title: Coord | None
    clock: Coord | None
    clock_label: Coord | None
    station: Coord | None
    timestamp: Coord | None
    timestamp_label: Coord | None
    flight_rules: Coord
    wind_compass: Coord
    wind_compass_radius: int
    wind_speed: Coord
    wind_gust: Coord
    temp: Coord
    temp_icon: Coord | None
    temp_stdv: Coord
    dew: Coord
    humid: Coord
    altim: Coord
    vis: Coord
    cloud_graph: tuple[Coord, Coord]
    wxrmk: tuple[int, int, int, int]
    util_spacing: int
    util_back: Coord

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        """Load main layout settings from a dictionary."""
        radius: int = data["wind-compass-radius"]
        util_spacing: int = data["util-spacing"]
        clouds = tuple(as_tuple(c) for c in data["cloud-graph"])
        cloud_graph = (clouds[0], clouds[1])
        wxrmk: tuple[int, int, int, int] = tuple(data["wxrmk"])
        return cls(
            title=opt_tuple(data.get("title")),
            clock=opt_tuple(data.get("clock")),
            clock_label=opt_tuple(data.get("clock-label")),
            station=opt_tuple(data.get("station")),
            timestamp=opt_tuple(data.get("timestamp")),
            timestamp_label=opt_tuple(data.get("timestamp-label")),
            flight_rules=as_tuple(data["flight-rules"]),
            wind_compass=as_tuple(data["wind-compass"]),
            wind_compass_radius=radius,
            wind_speed=as_tuple(data["wind-speed"]),
            wind_gust=as_tuple(data["wind-gust"]),
            temp=as_tuple(data["temp"]),
            temp_icon=opt_tuple(data.get("temp-icon")),
            temp_stdv=as_tuple(data["temp-stdv"]),
            dew=as_tuple(data["dew"]),
            humid=as_tuple(data["humid"]),
            altim=as_tuple(data["altim"]),
            vis=as_tuple(data["vis"]),
            cloud_graph=cloud_graph,
            wxrmk=wxrmk,
            util_spacing=util_spacing,
            util_back=as_tuple(data["util-back"]),
        )


@dataclass
class WxRmkLayout:
    """Weather remark layout settings."""

    padding: int
    line_space: int
    col1: int
    col2: int
    wx_length: int
    rmk_length: int

    @classmethod
    def from_dict(cls, data: dict[str, int] | None) -> Self | None:
        """Load weather remark layout settings from a dictionary."""
        if data is None:
            return None
        return cls(
            padding=data["padding"],
            line_space=data["line-space"],
            col1=data["col1"],
            col2=data["col2"],
            wx_length=data["wx-length"],
            rmk_length=data["rmk-length"],
        )


@dataclass
class WxRawLayout:
    """Weather raw layout settings."""

    start: Coord
    line_space: int
    wx_length: int
    small: tuple[int, int, int]
    large: tuple[int, int, int]

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Self | None:
        """Load weather raw layout settings from a dictionary."""
        if data is None:
            return None
        return cls(
            start=as_tuple(data["start"]),
            line_space=data["line-space"],
            wx_length=data["wx-length"],
            small=tuple(data["raw"]["small"]),
            large=tuple(data["raw"]["large"]),
        )


@dataclass
class SelectLayout:
    """Selection layout settings."""

    row_up: int
    row_char: int
    row_down: int
    col_offset: int
    col_spacing: int
    yes: Coord
    no: Coord

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        """Load selection layout settings from a dictionary."""
        return cls(
            row_up=data["row-up"],
            row_char=data["row-char"],
            row_down=data["row-down"],
            col_offset=data["col-offset"],
            col_spacing=data["col-spacing"],
            yes=as_tuple(data["yes"]),
            no=as_tuple(data["no"]),
        )


@dataclass
class InfoLayout:
    """Application information layout settings."""

    title_y: int
    name_y: int
    email_y: int
    url_y: int

    @classmethod
    def from_dict(cls, data: dict[str, int]) -> Self:
        """Load application information layout settings from a dictionary."""
        return cls(
            title_y=data["title-y"],
            name_y=data["name-y"],
            email_y=data["email-y"],
            url_y=data["url-y"],
        )


@dataclass
class QuitLayout:
    """Quit layout settings."""

    text_y: int
    yes: Coord
    no: Coord

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        """Load quit layout settings from a dictionary."""
        return cls(
            text_y=data["text-y"],
            yes=as_tuple(data["yes"]),
            no=as_tuple(data["no"]),
        )


@dataclass
class ErrorLayout:
    """Error layout settings."""

    line1: Coord
    line2: Coord
    refresh: Coord

    @classmethod
    def from_dict(cls, data: dict[str, int | Coord]) -> Self:
        """Load error layout settings from a dictionary."""
        return cls(
            line1=as_tuple(data["line1"]),
            line2=as_tuple(data["line2"]),
            refresh=as_tuple(data["refresh"]),
        )


@dataclass
class Layout:
    """Screen layout settings."""

    width: int
    height: int

    large_display: bool

    fonts: FontSize
    button: ButtonLayout
    flight_rules: FlightRulesLayout
    util_pos: Coord

    main: MainLayout
    wx_rmk: WxRmkLayout | None
    wx_raw: WxRawLayout | None
    select: SelectLayout
    info: InfoLayout
    quit: QuitLayout
    error: ErrorLayout

    @property
    def size(self) -> Coord:
        """Get the size of the screen."""
        return self.width, self.height

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Load screen layout settings from a dictionary."""
        wx_rmk = data.get("wxrmk")
        wx_raw = data.get("wxraw")
        return cls(
            width=data["width"],
            height=data["height"],
            large_display=data["large-display"],
            fonts=FontSize.from_dict(data["fonts"]),
            button=ButtonLayout.from_dict(data["button"]),
            flight_rules=FlightRulesLayout.from_dict(data["fr-display"]),
            util_pos=as_tuple(data["util"]),
            main=MainLayout.from_dict(data["main"]),
            wx_rmk=WxRmkLayout.from_dict(wx_rmk) if wx_rmk else None,
            wx_raw=WxRawLayout.from_dict(wx_raw) if wx_raw else None,
            select=SelectLayout.from_dict(data["select"]),
            info=InfoLayout.from_dict(data["info"]),
            quit=QuitLayout.from_dict(data["quit"]),
            error=ErrorLayout.from_dict(data["error"]),
        )

    @classmethod
    def from_file(cls, path: Path) -> Self:
        """Load screen layout settings from a JSON file."""
        with path.open() as fin:
            return cls.from_dict(json.load(fin))


if __name__ == "__main__":
    import metar_raspi.config as cfg

    for size in cfg.layout_path.parent.iterdir():
        layout = Layout.from_file(size)
