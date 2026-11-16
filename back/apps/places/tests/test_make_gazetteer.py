"""`make_gazetteer` (PL1): the places' list written from what is kept under CORPUS_DIR/sources/places (the UN's M49 page,
Natural Earth's label points, GeoNames MA and EH), the census decree's tables as read on its pages, and what a person
adds in curated.yaml. Each source here is a few rows in its real format; the curated list and the list written sit in a
folder of the test's own, never in the repository's data/."""
import io
import json
import zipfile
from datetime import date

import pytest
import yaml
from django.core.management import call_command
from django.utils import timezone

from apps.corpus.models import Text
from apps.places.management.commands import make_gazetteer
from apps.sources.models import Document, Edition, Issue, Page

pytestmark = pytest.mark.django_db

M49_HEAD = ('Global Code', 'Global Name', 'Region Code', 'Region Name', 'Sub-region Code', 'Sub-region Name',
            'Intermediate Region Code', 'Intermediate Region Name', 'Country or Area', 'M49 Code', 'ISO-alpha2 Code',
            'ISO-alpha3 Code', 'Least Developed Countries (LDC)', 'Land Locked Developing Countries (LLDC)',
            'Small Island Developing States (SIDS)')
# ISO3 (empty for an area the UN gives none), region, sub-region, intermediate region, then the name in EN, FR, AR.
STATES = [
    ('DZA', 'Africa', 'Northern Africa', '', 'Algeria', 'Alg&eacute;rie', 'الجزائر'),
    ('BOL', 'Americas', 'Latin America and the Caribbean', 'South America', 'Bolivia (Plurinational State of)',
     'Bolivie (État plurinational de)', 'بوليفيا (دولة - المتعددة القوميات)'),
    ('COD', 'Africa', 'Sub-Saharan Africa', 'Middle Africa', 'Democratic Republic of the Congo',
     'République démocratique du Congo', 'جمهورية الكونغو الديمقراطية'),
    ('CZE', 'Europe', 'Eastern Europe', '', 'Czechia', 'Tchéquie', 'تشيكيا'),
    ('FRA', 'Europe', 'Western Europe', '', 'France', 'France', 'فرنسا'),
    ('ISR', 'Asia', 'Western Asia', '', 'Israel', 'Israël', 'إسرائيل'),
    ('MAR', 'Africa', 'Northern Africa', '', 'Morocco', 'Maroc', 'المغرب'),
    ('QAT', 'Asia', 'Western Asia', '', 'Qatar', 'Qatar', 'قطر'),
    ('', 'Europe', 'Northern Europe', 'Channel Islands', 'Sark', 'Sercq', 'سارك'),
]


# The regions as the French and Arabic tables name them (the list keeps the English).
REGIONS = {'Africa': ('Afrique', 'أفريقيا'), 'Northern Africa': ('Afrique du Nord', 'شمال أفريقيا'),
           'Americas': ('Amériques', 'الأمريكتان'), 'Latin America and the Caribbean': ('Amérique latine et Caraïbes', 'أمريكا اللاتينية'),
           'South America': ('Amérique du Sud', 'أمريكا الجنوبية'), 'Sub-Saharan Africa': ('Afrique subsaharienne', 'أفريقيا جنوب الصحراء'),
           'Middle Africa': ('Afrique centrale', 'وسط أفريقيا'), 'Europe': ('Europe', 'أوروبا'),
           'Eastern Europe': ('Europe orientale', 'أوروبا الشرقية'), 'Western Europe': ('Europe occidentale', 'أوروبا الغربية'),
           'Asia': ('Asie', 'آسيا'), 'Western Asia': ('Asie occidentale', 'غرب آسيا'),
           'Northern Europe': ('Europe septentrionale', 'شمال أوروبا'), 'Channel Islands': ('Îles Anglo-Normandes', 'جزر القنال'), '': ('', '')}


def m49_page() -> str:
    """The UN's overview page as kept: one table a language, its ISO-alpha3 code in the twelfth cell."""
    tables = []
    for k, lang in enumerate(('EN', 'FR', 'AR')):
        head = ''.join(f'<td>{h}</td>' for h in M49_HEAD)
        said = dict(zip(REGIONS, REGIONS)) if k == 0 else {r: words[k - 1] for r, words in REGIONS.items()}
        rows = ''.join('<tr>\n' + ''.join(f'  <td>{c}</td>\n' for c in (
            '001', 'World', '', said[region], '', said[sub], '', said[middle], names[k], '', '', iso, '', '', '')) +
            '<!--<td><code>Developed</code></td>--></tr>' for iso, region, sub, middle, *names in STATES)
        tables.append(f'<table id = "downloadTable{lang}" class="compact"><thead><tr>{head}</tr></thead>'
                      f'<tbody>{rows}</tbody></table>')
    return '<html><body>' + '\n'.join(tables) + '</body></html>'


def natural_earth() -> dict:
    """Natural Earth's Morocco edition: where each state's name sits (France's ISO_A3 is «-99», as Natural Earth prints it)."""
    def feature(adm, iso, eh, x, y):
        return {'type': 'Feature', 'geometry': None,
                'properties': {'ADM0_A3': adm, 'ISO_A3': iso, 'ISO_A3_EH': eh, 'LABEL_X': x, 'LABEL_Y': y}}
    return {'type': 'FeatureCollection', 'features': [
        feature('MAR', 'MAR', 'MAR', -7.18753, 31.65055), feature('DZA', 'DZA', 'DZA', 2.808241, 27.397406),
        feature('FRA', '-99', 'FRA', 2.552275, 46.696113), feature('CZE', 'CZE', 'CZE', 15.377555, 49.882364)]}


def geonames(name: str, rows: list[tuple]) -> bytes:
    """A GeoNames country file as downloaded: a zip holding the readme and <CC>.txt, nineteen tab-separated columns."""
    lines = []
    for geoid, title, ascii_, alternates, lat, lon, fclass, pop in rows:
        lines.append('\t'.join([str(geoid), title, ascii_, alternates, str(lat), str(lon), fclass, 'PPL', name, '', '01', '', '',
                                '', pop, '', '10', 'Africa/Casablanca', '2024-01-01']))
    lines.append('2530335\tTruncated line')          # a line cut short is read past
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as z:
        z.writestr('readme.txt', 'GeoNames, CC BY 4.0\tnot a row\n')
        z.writestr(f'{name}.txt', '\n'.join(lines) + '\n')
    return out.getvalue()


FORWARD = ('| Collectivités territoriales | المغاربة Marocains | الأجانب Étrangers | السكان Population | الأسر Ménages | '
           'الجماعات الترابية | الرمز الجغرافي Code géographique |\n|---|---|---|---|---|---|---|\n')
BACKWARD = ('| الرمز الجغرافي | الجماعات الترابية | الأسر | السكان | الأجانب | المغاربة |\n'
            '| Code géographique | Collectivités territoriales | Ménages | Population | Étrangers | Marocains |\n')
PAGES = [
    # The decree's own words: a table on a page without the census's header is not read.
    'مرسوم رقم 2.24.1009 صادر في 25 من جمادى الأولى 1446\n| جهة الداخلة-وادي الذهب | 12 |\n',
    # The regions and the prefectures and provinces, French first (as BO 7356 prints them from page 8447).
    FORWARD +
    '| Ensemble du territoire national | 36,680,178 | 148,152 | 36,828,330 | 9,275,038 | مجموع التراب الوطني | |\n'
    '| Région de Tanger-Tétouan-Al Hoceima | 4,020,545 | 9,677 | 4,030,222 | 1,048,860 | جهة طنجة-تطوان-الحسيمة | 01 |\n'
    '| Préfecture de Tanger-Assilah | 1,487,175 | 7,238 | 1,494,413 | 418,844 | عمالة طنجة-أصيلة | 01.511 |\n'
    '| Commune de Tanjer | 1,268,512 | 6,916 | 1,275,428 | 362,062 | جماعة طنجة | 01.511.01.0 |\n'
    '| Arrondissement de Mghogha | 251,850 | 806 | 252,656 | 70,679 | مقاطعة مغوغة | 01.511.01.05 |\n'
    '| Commune de Bni Said | 9,100 | 4 | 9,104 | 2,000 | جماعة بني سعيد | 01.511.03.07 |\n'
    '| Commune de Bni Harchen | 9,000 | 2 | 9,002 | 2,000 | | 01.511.03.05 |\n'                  # its Arabic cell not read
    '| Province de Tétouan | 610,757 | 1,171 | 611,928 | 157,384 | إقليم تطوان | 01.571 |\n'
    # A commune's urban count, its Arabic cell read without «(الوسط الحضري)», before its own row.
    '| Commune de Tétouan (milieu urbain) | 379,000 | 1,170 | 380,170 | 97,000 | جماعة تطوات | 01.571.01.01 |\n'
    '| Commune de Tétouan | 379,616 | 1,171 | 380,787 | 98,000 | جماعة تطوات | 01.571.01.01 |\n'
    '| Commune de Ben Karrich | 30,410 | 12 | 30,422 | 7,500 | جماعة بن  قريش | 01.571.03.05 |\n'
    '| Commune de Bni Said | 12,890 | 3 | 12,893 | 3,100 | جماعة بني سعيد | 01.571.03.07 |\n'
    '| Préfecture de M\'diq-Fnideq | 253,388 | 676 | 254,064 | 67,797 | عمالة المضيق-الفنيدق | 01.573 |\n'
    '| Province d\'Al Hoceima | 371,391 | 136 | 371,527 | 89,181 | إقليم الحسيمة | 01.051 |\n'
    '| Région de Laâyoune-Sakia El Hamra | 451,028 | 2,000 | 453,028 | 110,000 | جهة العيون-الساقية الحمراء | 11 |\n',
    # A province's urban count comes before its own row, its French cell read without «(milieu urbain)».
    FORWARD +
    '| Province de Laâyoune | 238,000 | 1,050 | 239,050 | 58,000 | إقليم العيون (الوسط الحضري) | 11.321 |\n'
    '| Province de Laâyoune | 250,000 | 1,100 | 251,100 | 62,000 | إقليم العيون | 11.321 |\n'
    '| Commune de Laâyoune | 239,000 | 1,050 | 240,050 | 59,000 | جماعة العيون | 11.321.01.01 |\n',
    # The communes, Arabic first, no French column (the numbers printed from the other side).
    BACKWARD +
    '| 11 | جهة العيون-الساقية الحمراء | 110,000 | 453,028 | 2,000 | 451,028 |\n'
    '| 01.511.03 | دائرة أصيلة | 7,896 | 33,463 | 29 | 33,434 |\n'
    '| 01.511.03.03 | جماعة أقواس بريش | 1,190 | 4,981 | 15 | 4,966 |\n'
    '| 01.511.03.15 | جماعة حد الغربية | 3,084 | 12,838 | 6 | 12,382 |\n'
    '| 01.573 | عمالة المضيق-الفنيدق | 67,797 | 254,064 | 676 | 253,388 |\n'
    '| 01.573.01.03 | جماعة مرتيل | 26,886 | 95,896 | 416 | 95,480 |\n'
    '| 01.573.01.05 | جماعة المضيق | 17,498 | 67,599 | 100 | 67,499 |\n'
    '| 11.321.03.03 | جماعة المرسى | 3,000 | 12,000 | 10 | 11,990 |\n'
    # A commune whose code was not read: the two digits at its end are no region's code.
    '|  | جماعة سيدي لحسن | 9 | 38 | 0 | 38 |\n',
]

CURATED = {
    'countries': {
        'forms': {'FRA': ['الجمهورية الفرنسية', 'فرانسا'], 'QAT': ['دولة قطر']},
        'ctx': ['ISR'],
        'needs': {'ISR': ['اسرائيل']},
        'since': {'ISR': date(1948, 5, 14)},
        'slugs': {'COD': 'dr-congo'},
        'latin': {'FRA': ['francia']},
        'extra': {'TWN': {'slug': 'taiwan', 'ar': 'تايوان', 'fr': 'Taïwan', 'en': 'Taiwan', 'forms': ['تايوان', 'طايوان'],
                          'region': ['Asia', 'Eastern Asia', '']}},
        'skip': ['MAR', 'ESH'],
        'gone': {
            'czechoslovakia': {'ar': 'تشيكوسلوفاكيا', 'en': 'Czechoslovakia', 'fr': 'Tchécoslovaquie', 'successor': 'CZE',
                               'forms': ['تشيكوسلوفاكيا']},
            'zaire': {'ar': 'زائير', 'en': 'Zaire', 'fr': 'Zaïre', 'successor': 'COD', 'forms': ['زائير', 'الزايير'],
                      'since': date(1971, 10, 27)}},
    },
    'morocco': {
        'fix': {'تطوات': 'تطوان', 'commune de tanjer': 'Commune de Tanger'},
        'forms': {'مرتيل': ['مارتيل']},
        'ctx': ['المضيق', 'مليلية', 'مليلة'],
        'old': {'تطوان': ['تطاوين']},
        'since': {'العيون': date(1976, 1, 1), 'المرسى': date(1976, 1, 1)},
        'latin': {'طنجة': ['tanger', 'tangier', 'tanja']},
        'names': {'مرتيل': 'Martil', 'المضيق': "M'diq", 'المرسى': 'El Marsa'},
        'positions': {'مرتيل': [35.62, -5.27]},
        'extra': [{'slug': 'sebta', 'kind': 'city', 'ar': 'سبتة', 'fr': 'Sebta', 'en': 'Ceuta', 'forms': ['سبتة'],
                   'lat': 35.889, 'lon': -5.319},
                  {'slug': 'melilla', 'kind': 'city', 'ar': 'مليلية', 'fr': 'Melilla', 'en': 'Melilla', 'forms': ['مليلية', 'مليلة'],
                   'lat': 35.292, 'lon': -2.938}],
    },
}


@pytest.fixture
def kept(settings, tmp_path, monkeypatch):
    """The kept sources under CORPUS_DIR, the census decree's pages in the database, and the curated list in a folder
    of the test's own, where the command also writes places.json."""
    settings.CORPUS_DIR = tmp_path / 'corpus'
    folder = tmp_path / 'corpus' / 'sources' / 'places'
    folder.mkdir(parents=True)
    (folder / 'm49_overview.html').write_text(m49_page(), encoding='utf-8')
    (folder / 'naturalearth_ne_10m_admin_0_countries_mar.geojson').write_text(json.dumps(natural_earth()))
    (folder / 'geonames_MA.zip').write_bytes(geonames('MA', [
        (2530335, 'Tangier', 'Tangier', 'Tanger,Tanja,طنجة', 35.76727, -5.79973, 'P', '688356'),
        (2530336, 'Tanja', 'Tanja', 'طنجة', 34.5, -6.1, 'P', ''),              # a hamlet of the same name, smaller
        (2528910, 'Tetouan', 'Tetouan', 'Tetuan,Tétouan', 35.57843, -5.36837, 'P', '380787'),
        (2561668, 'Aqouâss Briech', 'Aqouass Briech', 'أقواس بريش', 35.4, -6.0, 'P', '4981'),
        (2550001, 'Ain Had el Gharbia', 'Ain Had el Gharbia', 'حد الغربية', 35.6, -5.9, 'H', '0'),   # a spring: no place
    ]))
    (folder / 'geonames_EH.zip').write_bytes(geonames('EH', [
        (2462881, 'Laayoune', 'Laayoune', 'El Aaiun,Laâyoune,العيون', 27.1536, -13.2033, 'P', '217732'),
    ]))
    document = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256='7356'.ljust(64, '0'), path='BO_7356_ar.pdf',
                                       mime='application/pdf', language='ar', bytes=1, fetched_at=timezone.now())
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=7356, date=date(2024, 11, 28), document=document)
    Text.objects.create(akn_uri=make_gazetteer.CENSUS, type='decree', number='2-24-1009', title_ar='مرسوم رقم 2.24.1009',
                        first_published_in=issue)
    Page.objects.bulk_create([Page(document=document, index=i, printed_number=8446 + i, kind='scan', text=t)
                              for i, t in enumerate(PAGES)])
    data = tmp_path / 'data'
    data.mkdir()
    monkeypatch.setattr(make_gazetteer, 'DATA', data)

    def write(curated=CURATED):
        (data / 'curated.yaml').write_text(yaml.safe_dump(curated, allow_unicode=True), encoding='utf-8')
        return data / 'places.json'
    return write


def run() -> str:
    out = io.StringIO()
    call_command('make_gazetteer', stdout=out)
    return out.getvalue()


def test_the_list_is_written_from_the_kept_sources(kept):
    written = kept()
    said = run()
    places = json.loads(written.read_text(encoding='utf-8'))
    assert '"ar": "الجزائر"' in written.read_text(encoding='utf-8')      # the letters as they are, a reader can diff them
    by = {p['slug']: p for p in places}
    assert said == ("30 places: {'country': 8, 'gone': 2, 'region': 2, 'province': 5, 'city': 7, 'commune': 6}; "
                    'without a position: 6\n')
    # Morocco and Sark (no ISO code) are no states here; Taiwan comes from the curated list.
    assert [p['slug'] for p in places if p['kind'] == 'country'] == [
        'bolivia', 'dr-congo', 'czechia', 'algeria', 'france', 'israel', 'qatar', 'taiwan']
    assert by['algeria'] == {
        'slug': 'algeria', 'kind': 'country', 'code': 'DZA', 'ar': 'الجزائر', 'fr': 'Algérie', 'en': 'Algeria',
        'region': 'Africa/Northern Africa', 'forms': ['الجزائر'], 'ctx': False, 'needs': [], 'latin': ['algeria', 'algerie'],
        'lat': 27.397, 'lon': 2.808}
    assert by['bolivia']['en'] == 'Bolivia' and by['bolivia']['region'] == 'Americas/Latin America and the Caribbean/South America'
    # A state word in front gives the name alone; a name that is also a word («قطر», a diameter) is never a form alone.
    assert by['dr-congo']['forms'] == ['جمهوريه الكونغو الديمقراطيه', 'الكونغو الديمقراطيه']
    assert by['qatar']['forms'] == ['دوله قطر'] and by['qatar']['lat'] is None
    assert by['france']['forms'] == ['فرنسا', 'الجمهوريه الفرنسيه', 'فرانسا']
    assert by['france']['latin'] == ['france', 'francia'] and (by['france']['lat'], by['france']['lon']) == (46.696, 2.552)
    assert (by['israel']['ctx'], by['israel']['needs'], by['israel']['since']) == (True, ['اسرائيل'], '1948-05-14')
    assert by['taiwan']['region'] == 'Asia/Eastern Asia' and by['taiwan']['forms'] == ['تايوان', 'طايوان']
    # A gone state points to its successor's slug and sits where it sits; one counted from a day says so.
    assert by['czechoslovakia'] == {
        'slug': 'czechoslovakia', 'kind': 'gone', 'code': '', 'ar': 'تشيكوسلوفاكيا', 'fr': 'Tchécoslovaquie',
        'en': 'Czechoslovakia', 'region': '', 'forms': ['تشيكوسلوفاكيا'], 'ctx': False, 'successor': 'czechia',
        'latin': ['czechoslovakia', 'tchecoslovaquie'], 'lat': 49.882, 'lon': 15.378}
    assert (by['zaire']['successor'], by['zaire']['since'], by['zaire']['lat']) == ('dr-congo', '1971-10-27', None)
    assert (by['zaire']['forms'], by['zaire']['latin']) == (['زائير', 'الزايير'], ['zaire'])


def test_the_census_gives_the_regions_provinces_and_communes(kept):
    written = kept()
    run()
    places = json.loads(written.read_text(encoding='utf-8'))
    by = {p['slug']: p for p in places}
    # Only the census's tables are read, each code once, its first row kept; two digits ending a commune's row are no region.
    assert [p['slug'] for p in places if p['kind'] == 'region'] == ['region-tanger-tetouan-al-hoceima',
                                                                    'region-laayoune-sakia-el-hamra']
    assert by['region-tanger-tetouan-al-hoceima'] == {
        'slug': 'region-tanger-tetouan-al-hoceima', 'kind': 'region', 'code': '01', 'ar': 'طنجة-تطوان-الحسيمة',
        'fr': 'Tanger-Tétouan-Al Hoceima', 'pop': 4030222, 'forms': ['طنجه تطوان الحسيمه'], 'ctx': True,
        'latin': ['tanger tetouan al hoceima']}
    assert [p['slug'] for p in places if p['kind'] == 'province'] == [
        'prefecture-tanger-assilah', 'province-tetouan', 'prefecture-mdiq-fnideq', 'province-al-hoceima', 'province-laayoune']
    assert (by['province-al-hoceima']['fr'], by['province-al-hoceima']['word'], by['province-al-hoceima']['town']) == (
        'Al Hoceima', 'إقليم', '')
    assert by['prefecture-mdiq-fnideq'] == {
        'slug': 'prefecture-mdiq-fnideq', 'kind': 'province', 'code': '01.573', 'ar': 'المضيق-الفنيدق', 'fr': "M'diq-Fnideq",
        'word': 'عمالة', 'pop': 254064, 'foreign': 676, 'parent': 'region-tanger-tetouan-al-hoceima',
        'forms': ['المضيق الفنيدق'], 'ctx': True, 'latin': ['mdiq fnideq'], 'town': ''}
    # A province named after its city points to the city; its urban count is not its population.
    assert (by['province-tetouan']['town'], by['province-laayoune']['town']) == ('tetouan', 'laayoune')
    assert (by['province-laayoune']['pop'], by['province-laayoune']['foreign']) == (251100, 1100)
    # The cities, biggest first, then the rural communes; a row with no Arabic name is no commune.
    assert [p['slug'] for p in places if p['kind'] in ('city', 'commune')] == [
        'tanger', 'tetouan', 'laayoune', 'martil', 'mdiq', 'ben-karrich', 'bni-said', 'el-marsa', 'bni-said-tanger-assilah',
        'aqouass-briech', 'commune-01-511-03-15', 'sebta', 'melilla']
    assert by['tanger'] == {
        'slug': 'tanger', 'kind': 'city', 'code': '01.511.01.0', 'ar': 'طنجة', 'fr': 'Tanger', 'needs': [],
        'parent': 'prefecture-tanger-assilah', 'pop': 1275428, 'foreign': 6916, 'forms': ['طنجه'], 'old': [], 'ctx': False,
        'latin': ['tanger', 'tangier', 'tanja'], 'lat': 35.7673, 'lon': -5.7997}
    # A reading slip is fixed in the cell; the old name counts for the city; GeoNames found it by its Latin name; its
    # urban count is not its population.
    assert (by['tetouan']['ar'], by['tetouan']['old'], by['tetouan']['lat']) == ('تطوان', ['تطاوين'], 35.5784)
    assert (by['tetouan']['pop'], by['tetouan']['foreign']) == (380787, 1171)
    # Counted from a day; found in GeoNames' Sahara file by its Arabic name.
    assert (by['laayoune']['since'], by['laayoune']['lat'], by['laayoune']['lon']) == ('1976-01-01', 27.1536, -13.2033)
    # A rural commune named like a city counted from a day is not given the day.
    assert 'since' not in by['el-marsa'] and (by['el-marsa']['pop'], by['el-marsa']['foreign']) == (12000, 10)
    # No French cell read: the curated French name, a position by hand, a form more; a word of the language needs context.
    assert (by['martil']['fr'], by['martil']['lat'], by['martil']['lon']) == ('Martil', 35.62, -5.27)
    assert by['martil']['forms'] == ['مرتيل', 'مارتيل'] and by['martil']['ctx'] is False
    assert (by['mdiq']['fr'], by['mdiq']['ctx'], by['mdiq']['lat']) == ("M'diq", True, None)
    # A rural commune needs context; a name like a man's needs a place word.
    assert (by['ben-karrich']['ar'], by['ben-karrich']['ctx'], by['ben-karrich']['needs']) == ('بن قريش', True, ['بن قريش'])
    # Two communes of one French name: the smaller is told by its province.
    assert (by['bni-said']['parent'], by['bni-said-tanger-assilah']['parent']) == ('province-tetouan', 'prefecture-tanger-assilah')
    # GeoNames names a commune whose French cell was not read; a spring of the same name is no place.
    assert (by['aqouass-briech']['fr'], by['aqouass-briech']['pop'], by['aqouass-briech']['foreign']) == ('Aqouass Briech', 4981, 15)
    assert by['commune-01-511-03-15'] == {
        'slug': 'commune-01-511-03-15', 'kind': 'commune', 'code': '01.511.03.15', 'ar': 'حد الغربية', 'fr': 'حد الغربية',
        'needs': [], 'parent': 'prefecture-tanger-assilah', 'pop': None, 'foreign': None, 'forms': ['حد الغربيه'], 'old': [],
        'ctx': True, 'latin': [''], 'lat': None, 'lon': None}
    assert by['melilla'] == {
        'slug': 'melilla', 'kind': 'city', 'ar': 'مليلية', 'fr': 'Melilla', 'en': 'Melilla', 'lat': 35.292, 'lon': -2.938,
        'code': '', 'forms': ['مليليه', 'مليله'], 'ctx': True, 'old': [], 'latin': ['melilla', 'melilla'], 'parent': ''}
    assert by['sebta']['ctx'] is False and by['sebta']['latin'] == ['sebta', 'ceuta']


def test_a_slug_given_twice_writes_nothing(kept):
    curated = {**CURATED, 'morocco': {**CURATED['morocco'], 'extra': [
        *CURATED['morocco']['extra'], {'slug': 'france', 'kind': 'city', 'ar': 'فرنسا', 'fr': 'France', 'en': 'France',
                                       'forms': ['فرنسا']}]}}
    written = kept(curated)
    with pytest.raises(SystemExit, match=r"slugs twice: \['france'\]"):
        run()
    assert not written.exists()
