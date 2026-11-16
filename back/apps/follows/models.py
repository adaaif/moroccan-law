"""What an account follows (R13 of the for-everyone review): a law, an article or a life topic, for a letter when it
changes. A reader without an account follows on their device; this row is what a letter needs. Following a
discussion stays apps.discussion's."""
from django.conf import settings
from django.db import models


class Follow(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    path = models.CharField(max_length=300, help_text='/ma/loi/2013/67-12, /ma/loi/2013/67-12/art_34, /topics/housing')
    created_at = models.DateTimeField(auto_now_add=True)
    # The changes already known (services.news keys): what stood when one began to follow, then what a letter told.
    told = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = 'follows_follow'
        constraints = [models.UniqueConstraint(fields=['user', 'path'], name='follows_follow_once')]

    def __str__(self):
        return f'{self.user_id} follows {self.path}'
