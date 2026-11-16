from django.db import models


class Tally(models.Model):
    """What the MCP server did in a Casablanca day for one origin: a platform («claude», «chatgpt»), a direct caller by
    the product it names («direct:python-httpx»), or «accounts» for calls made with an account on the site (those also count on
    their connection, apps.oauth Day). Counts only: no address, no person, no question."""

    day = models.DateField()
    origin = models.CharField(max_length=60)
    calls = models.PositiveIntegerField(default=0, db_default=0)
    articles = models.PositiveIntegerField(default=0, db_default=0)
    tools = models.JSONField(default=dict)

    class Meta:
        db_table = 'mcp_tally'
        constraints = [models.UniqueConstraint(fields=['day', 'origin'], name='mcp_tally_unique')]


class Alert(models.Model):
    """A platform's share for the hour half spent (apps/mcp/services/quotas.py): one row each time, read in the admin.
    No letter is sent; the log says it too. Counts only: no address, no person."""

    at = models.DateTimeField(auto_now_add=True)
    origin = models.CharField(max_length=60)
    share = models.CharField(max_length=10)          # 'calls' or 'articles'
    period = models.CharField(max_length=4)          # 'hour' or 'day'
    limit = models.PositiveIntegerField()

    class Meta:
        db_table = 'mcp_alert'
        indexes = [models.Index(fields=['at'], name='mcp_alert_at_idx')]

    def __str__(self):
        return f'{self.origin}: half its {self.share} an {self.period} ({self.limit})'
