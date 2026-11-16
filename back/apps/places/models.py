from django.db import models


class Place(models.Model):
    """A state, a gone state, or a Moroccan region, province, city or commune (PL1 of the places review), as
    data/places.json lists it; `build_places` writes them all again, with what the count found."""

    class Kind(models.TextChoices):
        COUNTRY = 'country'
        GONE = 'gone'
        REGION = 'region'
        PROVINCE = 'province'
        CITY = 'city'
        COMMUNE = 'commune'

    slug = models.SlugField(max_length=90, unique=True)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    name_ar = models.CharField(max_length=160)
    name_fr = models.CharField(max_length=160, blank=True, default='')
    name_en = models.CharField(max_length=160, blank=True, default='')
    code = models.CharField(max_length=20, blank=True, default='', help_text='ISO 3166 alpha-3, or the census code.')
    region = models.CharField(max_length=80, blank=True, default='', help_text='A state\'s UN region.')
    parent = models.CharField(max_length=90, blank=True, default='', help_text='The province or region it is in.')
    town = models.CharField(max_length=90, blank=True, default='', help_text='A province named after its city: the city.')
    successor = models.CharField(max_length=90, blank=True, default='', help_text='A gone state\'s successor.')
    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)
    population = models.PositiveIntegerField(null=True, blank=True, help_text='The 2024 census decree\'s legal population.')
    foreigners = models.PositiveIntegerField(null=True, blank=True)
    forms = models.JSONField(default=list, help_text='Folded names the count looks for.')
    old = models.JSONField(default=list, help_text='Folded old names, counted for this place.')
    latin = models.JSONField(default=list, help_text='What a reader types in Latin letters.')
    texts = models.PositiveIntegerField(default=0, help_text='Texts naming it, any version.')
    first = models.JSONField(null=True, blank=True, help_text='Its first mention in a text as printed.')
    spellings = models.JSONField(default=list, help_text='The forms it was printed in: form, texts, first and last year.')

    class Meta:
        db_table = 'places_place'
        indexes = [models.Index(fields=['kind', '-texts'])]


class Mention(models.Model):
    """A place named in an article (or a text's title, eid ''), first time in it; keyed by the article's address,
    never a foreign key to the corpus, so a reload means a new build."""

    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name='mentions')
    uri = models.CharField(max_length=200)
    eid = models.CharField(max_length=120, blank=True, default='')
    order = models.IntegerField(default=-1, help_text='The article\'s order in its text; -1 the title.')
    date = models.DateField(help_text='The issue that first published the text.')
    issue = models.CharField(max_length=20)
    edition = models.CharField(max_length=20)
    page = models.PositiveIntegerField(null=True, blank=True)
    text_type = models.CharField(max_length=20)
    kind = models.CharField(max_length=12, help_text='What the text is, by its title (names.kind_of).')
    form = models.CharField(max_length=120, help_text='The name as printed.')
    at = models.PositiveIntegerField(default=0, help_text='Where it is printed in the article (or the title).')
    printed = models.BooleanField(default=True, help_text='Read in the text as published (else its newest version).')
    old = models.BooleanField(default=False)

    class Meta:
        db_table = 'places_mention'
        indexes = [models.Index(fields=['place', '-date', 'uri', 'order'], name='places_mention_list'),
                   models.Index(fields=['place', 'uri'], name='places_mention_text')]


class PlaceYear(models.Model):
    """The texts as printed that name a place, a year: their number and their kinds."""

    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name='years')
    year = models.PositiveSmallIntegerField()
    texts = models.PositiveIntegerField()
    kinds = models.JSONField(default=dict)

    class Meta:
        db_table = 'places_year'
        constraints = [models.UniqueConstraint(fields=['place', 'year'], name='places_year_once')]


class Year(models.Model):
    """A year's texts as printed (the shares' denominator, PL4) and those naming any foreign state."""

    year = models.PositiveSmallIntegerField(unique=True)
    texts = models.PositiveIntegerField()
    foreign = models.PositiveIntegerField()

    class Meta:
        db_table = 'places_total'
