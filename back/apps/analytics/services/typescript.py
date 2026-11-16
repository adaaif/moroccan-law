"""The registry written for the web (`manage.py write_measure_types`): web/src/shared/analytics/measures.ts holds the
measures' names, each one's properties as TypeScript types, the kinds of page, the languages and screens, the door's
limits and every property's rule, so the beacon is written against what the door accepts. The file is committed; a
test holds it equal to what this module writes from the registry."""
import json

from django.conf import settings

from apps.analytics import registry

TARGET = settings.BASE_DIR.parent / 'web' / 'src' / 'shared' / 'analytics' / 'measures.ts'
HEADER = ('// Written by `manage.py write_measure_types` from back/apps/analytics/registry.py: do not edit it by hand.'
          '\n'
          '// Change the registry, run the command and commit both; a backend test fails while they differ.\n')


def _s(value: str) -> str:
    return registry.quoted(value)


def _list(values) -> str:
    return '[' + ', '.join(_s(v) for v in values) + ']'


def _number(value) -> str:
    return json.dumps(value)


def _comment(rule) -> str:
    if isinstance(rule, registry.Number):
        return f'from {_number(rule.lo)} to {_number(rule.hi)}, rounded to {_number(rule.step)}'
    if isinstance(rule, registry.Pattern):
        return f'{rule.regex}, at most {rule.max_len} characters' + (', lowercased' if rule.lower else '')
    return ''


def _rule(rule) -> str:
    out = rule.rule()
    parts = []
    for key, value in out.items():
        if isinstance(value, str):
            parts.append(f'{key}: {_s(value)}')
        elif isinstance(value, bool):
            parts.append(f'{key}: {"true" if value else "false"}')
        elif isinstance(value, list):
            parts.append(f'{key}: {_list(value)}')
        else:
            parts.append(f'{key}: {_number(value)}')
    return '{ ' + ', '.join(parts) + ' }'


def render() -> str:
    names = list(registry.MEASURES)
    out = [HEADER]
    out.append('/** The kinds of page an event is shown on (registry.KINDS says which addresses each holds). */')
    out.append(f'export const KINDS = {_list(registry.KINDS)} as const;')
    out.append('export type Kind = (typeof KINDS)[number];')
    out.append(f'export const LANGS = {_list(registry.LANGS)} as const;')
    out.append('export type Lang = (typeof LANGS)[number];')
    out.append('/** The width the browser saw: under 640 px, under 1024 px, wider. */')
    out.append(f'export const SCREENS = {_list(registry.SCREENS)} as const;')
    out.append('export type Screen = (typeof SCREENS)[number];')
    out.append('')
    out.append('/** The door: events a batch, bytes a body, an address without its query, a build, a flow. */')
    out.append(f'export const MOST_EVENTS = {registry.MOST_EVENTS};')
    out.append(f'export const MOST_BYTES = {registry.MOST_BYTES};')
    out.append(f'export const PATH = {_s(registry.PATH)};')
    out.append(f'export const BUILD = {_s(registry.BUILD)};')
    out.append(f'export const FLOW_MOST = {registry.FLOW_MOST};')
    out.append("/** page.shown's properties that only a visit's first page carries. */")
    out.append(f'export const ENTRY_ONLY = {_list(registry.ENTRY_ONLY)} as const;')
    out.append('')
    out.append('/** Each measure\'s properties, every one optional. */')
    out.append('export interface Props {')
    for name, measure in registry.MEASURES.items():
        out.append(f'  {_s(name)}: {{')
        for prop, rule in measure.props.items():
            if comment := _comment(rule):
                out.append(f'    /** {comment.replace("*/", "*\\/")} */')
            out.append(f'    {prop}?: {rule.ts()};')
        out.append('  };')
    out.append('}')
    out.append('export type MeasureName = keyof Props;')
    out.append(f'export const MEASURES: readonly MeasureName[] = {_list(names)};')
    out.append('export type MeasureEvent = {')
    out.append('  [N in MeasureName]: { name: N; kind: Kind; path: string; flow?: number; props?: Props[N] };')
    out.append('}[MeasureName];')
    out.append('export interface Batch {')
    out.append('  lang: Lang;')
    out.append('  screen: Screen;')
    out.append('  build: string;')
    out.append('  events: MeasureEvent[];')
    out.append('}')
    out.append('')
    out.append('/** Each property\'s rule as the door checks it; a pattern is a regular expression\'s source. */')
    out.append('export const RULES = {')
    for name, measure in registry.MEASURES.items():
        out.append(f'  {_s(name)}: {{')
        for prop, rule in measure.props.items():
            out.append(f'    {prop}: {_rule(rule)},')
        out.append('  },')
    out.append('} as const;')
    return '\n'.join(out) + '\n'


def write() -> None:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(render(), encoding='utf-8')
