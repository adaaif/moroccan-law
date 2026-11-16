"""The sign-in assistants use to read the site with a person's account (MC5–MC8 of the MCP review, 3 Nov 2026).

The site is its own OAuth 2.1 authorization server for one resource, the MCP server at MCP_RESOURCE. No token, code or
request id is stored as given: each is a SHA-256 digest, like the open data's API keys."""
from django.conf import settings
from django.db import models


class Client(models.Model):
    """An assistant as it identified itself: by the URL of its metadata document (CIMD: Claude, ChatGPT), or by a
    registration (DCR: the MCP Inspector, Cursor, VS Code). Its name is what it says of itself, except for the assistants
    the site knows by their domain (clients.KNOWN)."""

    class Kind(models.TextChoices):
        CIMD = 'cimd', 'Client ID metadata document'
        DCR = 'dcr', 'Dynamic registration'

    client_id = models.CharField(max_length=500, unique=True)
    kind = models.CharField(max_length=4, choices=Kind.choices)
    name = models.CharField(max_length=120, blank=True, default='', db_default='')
    # Where its redirects go: the domain the consent page shows large.
    domain = models.CharField(max_length=255, blank=True, default='', db_default='')
    redirect_uris = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    # A metadata document is read again after a day (CIMD_KEEP_SECONDS).
    fetched_at = models.DateTimeField(null=True, blank=True)
    # A registered client never used is removed after a week (prune_oauth).
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'oauth_client'

    def __str__(self):
        return self.name or self.client_id


class AuthRequest(models.Model):
    """An authorization asked for and waiting for the person's answer on /connect: ten minutes at most."""

    digest = models.CharField(max_length=64, unique=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='+')
    redirect_uri = models.CharField(max_length=2000)
    state = models.CharField(max_length=1000, blank=True, default='')
    code_challenge = models.CharField(max_length=128)
    scope = models.CharField(max_length=200)
    resource = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'oauth_request'


class Grant(models.Model):
    """A connection: one assistant reading the site with one person's account. Its tokens die with it."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='oauth_grants')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='grants')
    scope = models.CharField(max_length=200)
    resource = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'oauth_grant'
        indexes = [models.Index(fields=['user', 'revoked_at'], name='oauth_grant_user_idx')]


class Code(models.Model):
    """An authorization code: sixty seconds, once, for the redirect and the PKCE challenge it was issued with."""

    digest = models.CharField(max_length=64, unique=True)
    grant = models.ForeignKey(Grant, on_delete=models.CASCADE, related_name='+')
    redirect_uri = models.CharField(max_length=2000)
    code_challenge = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'oauth_code'


class Token(models.Model):
    """An access token (an hour) or a refresh token (60 days, replaced on each use: one used twice ends its grant)."""

    class Kind(models.TextChoices):
        ACCESS = 'access', 'Access'
        REFRESH = 'refresh', 'Refresh'

    digest = models.CharField(max_length=64, unique=True)
    kind = models.CharField(max_length=8, choices=Kind.choices)
    grant = models.ForeignKey(Grant, on_delete=models.CASCADE, related_name='tokens')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    replaced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'oauth_token'


class Day(models.Model):
    """What a connection did in a Casablanca day: calls by tool and the article bodies it was served (MC17, MC18).
    Counts only: never what was asked."""

    grant = models.ForeignKey(Grant, on_delete=models.CASCADE, related_name='days')
    day = models.DateField()
    calls = models.PositiveIntegerField(default=0, db_default=0)
    articles = models.PositiveIntegerField(default=0, db_default=0)
    tools = models.JSONField(default=dict)

    class Meta:
        db_table = 'oauth_day'
        constraints = [models.UniqueConstraint(fields=['grant', 'day'], name='oauth_day_unique')]
