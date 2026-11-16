"""How the counts' report writes its figures (templates/admin/analytics/report.html): Western digits with a comma every
three, a share with its sign on the right, a change with its sign, and «fewer than 5» as it is."""
from django import template

register = template.Library()


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


@register.filter
def num(value):
    """1,234; «—» for none; words (FEWER) as they are."""
    if value is None:
        return '—'
    return f'{value:,}' if _number(value) else value


@register.filter
def pct(value):
    """12.5%."""
    if value is None:
        return '—'
    return f'{value}%' if _number(value) else value


@register.filter
def change(value):
    """+12% or -3%; nothing when there is no change to say (nothing before, or a group too small to show)."""
    return f'{value:+d}%' if _number(value) else ''


@register.filter
def points(value):
    """+2.5 pts: a share's change."""
    return f'{value:+} pts' if _number(value) else ''


@register.filter
def width(value):
    """A share as a bar's width in % for a style attribute (a point, never the language's comma); 0 for a share not
    shown."""
    return f'{min(100, max(0, value)):g}' if _number(value) else '0'
