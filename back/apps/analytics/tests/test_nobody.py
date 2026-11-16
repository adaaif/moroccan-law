"""What no table of the measures may hold (the analytics review, 15 Nov 2026): a row describes a task, never a person.
A column for who did it (an account, an address or part of one, a visitor's key even one that changes each day, a
User-Agent, a country, a city) would let the rows be put together into people, and their minutes be matched to the web
server's log. A change that adds one fails here, and must answer to the review first."""
from django.apps import apps
from django.db import models

from apps.analytics.models import DayCount, Event


def names(model) -> set[str]:
    return {f.name for f in model._meta.get_fields()}


def test_an_event_holds_what_happened_and_where_in_the_app_and_nothing_of_who():
    assert names(Event) == {'id', 'hour', 'name', 'kind', 'path', 'flow', 'props', 'lang', 'screen', 'build'}


def test_a_day_count_holds_a_day_a_metric_a_key_and_a_number():
    assert names(DayCount) == {'id', 'day', 'metric', 'key', 'count'}


def test_no_table_of_the_measures_points_at_an_account_or_any_other_row():
    for model in apps.get_app_config('analytics').get_models():
        assert not [f for f in model._meta.get_fields() if f.is_relation], model


def test_an_events_time_is_a_datetime_cut_to_the_hour_by_the_door():
    assert isinstance(Event._meta.get_field('hour'), models.DateTimeField)
    assert not any(isinstance(f, models.DateTimeField) and f.name != 'hour' for f in Event._meta.get_fields())
