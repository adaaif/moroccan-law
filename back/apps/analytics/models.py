"""What the site counts (the analytics review, 15 Nov 2026): tasks, never people. A row is a page shown, a tool's step,
a page's speed or an error, with the hour it happened in; no table holds a visitor. There is no address or part of one,
no visitor's key (not even one that changes each day), no account, no User-Agent, no place and no words a reader typed,
and the hour is never a minute, so a row cannot be matched to a line of the web server's log. Every name and property
is declared in registry.py, and the door (services/record.py) writes nothing else.

Event rows are kept ANALYTICS_DAYS days; each night `fold_events` turns the day's rows into DayCount rows, kept for
good, which count events and describe nobody."""
from django.db import models


class Event(models.Model):
    hour = models.DateTimeField(help_text='When it happened, cut to the hour.')
    name = models.CharField(max_length=24, help_text="A measure's name in the registry («page.shown»).")
    kind = models.CharField(max_length=12, help_text="The page's kind (registry.KINDS).")
    path = models.CharField(max_length=200, help_text='The address, without its query or fragment.')
    flow = models.BigIntegerField(null=True, blank=True,
                                  help_text='One opening of a tool: a random number the browser drew in memory.')
    props = models.JSONField(default=dict, db_default={}, blank=True,
                             help_text='Only the properties the registry allows for the name.')
    lang = models.CharField(max_length=2)
    screen = models.CharField(max_length=6, help_text='phone, tablet or desk, from the width the browser saw.')
    build = models.CharField(max_length=8, help_text="The web build's short id.")

    class Meta:
        db_table = 'analytics_event'
        indexes = [models.Index(fields=['hour'], name='analytics_event_hour_idx'),
                   models.Index(fields=['name', 'hour'], name='analytics_event_name_idx')]


class DayCount(models.Model):
    """A day's count of one thing (a metric and its key: «page.path» and an address, «visit.country» and a country), in
    Morocco's day. Each writer owns its metrics and replaces or adds to those alone:
    - the night's fold (services/fold.py `owns`): the registry's names and every `<name>.…`, `page.path`, `visits`,
      `visits.nostore`, `readers.…`, `speed.…`; it deletes and writes them again for each day it folds;
    - the door (services/record.py): `visit.country`, added to as visits come;
    - the night's count of machines: `machine.…`;
    - the import of the counts kept before this app: `past.…`.
    A new writer takes a prefix of its own and says it here."""
    day = models.DateField()
    metric = models.CharField(max_length=48)
    key = models.CharField(max_length=255, blank=True, default='', db_default='')
    count = models.PositiveIntegerField(default=0, db_default=0)

    class Meta:
        db_table = 'analytics_daycount'
        constraints = [models.UniqueConstraint(fields=['day', 'metric', 'key'], name='analytics_daycount_unique')]
