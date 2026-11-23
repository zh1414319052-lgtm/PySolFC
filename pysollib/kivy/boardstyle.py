"""Shared card-table styles for the Kivy interface."""

from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.utils import get_color_from_hex

CHROME = "#102D28"
FELT = "#124A3B"
SHEET = "#F7F3E9"
PAPER = "#FFFDF6"
INK = "#19342D"
MUTED = "#52655C"
DIVIDER = "#DADFD2"
MINT = "#DCEEDC"
GOLD = "#D6AD6A"
NAV_MUTED = "#BDCEBE"
PANEL_ENTER = 0.16


def rgba(color):
    return get_color_from_hex(color)


def backing(widget, color):
    with widget.canvas.before:
        Color(*rgba(color))
        shape = Rectangle(pos=widget.pos, size=widget.size)

    def update(*args):
        shape.pos = widget.pos
        shape.size = widget.size

    widget.bind(pos=update, size=update)


def menu_icon(widget, color):
    from kivy.graphics import Line

    with widget.canvas.after:
        Color(*rgba(color))
        lines = [Line(width=dp(1.3), cap="round") for _ in range(3)]

    def update(*args):
        x, y = widget.center
        for i, line in enumerate(lines):
            height = y + dp((i - 1) * 6)
            line.points = (x - dp(9), height, x + dp(9), height)

    widget.bind(pos=update, size=update)
    update()
