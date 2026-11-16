"""The counts' report in the admin (/admin/analytics/, the analytics review, 15 Nov 2026): every figure of
services/report.py for the last 7 complete days, or the last 28 (?days=28), beside the days before. Read only, for staff
with the view right on the day counts (analytics.view_daycount; a superuser has every right): config.admin.Site gives
it its address behind the admin's sign-in and lists it on the index. No model is registered: the counts are read
here, never listed row by row."""
from django.conf import settings
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse

from apps.analytics.services import report as figures
from config.admin import REPORT


def report(request):
    if not request.user.has_perm(REPORT['right']):
        raise PermissionDenied
    asked = request.GET.get('days', '')
    days = int(asked) if asked in {str(d) for d in figures.DAYS} else figures.DAYS[0]
    return TemplateResponse(request, 'admin/analytics/report.html', {
        **admin.site.each_context(request), 'title': 'What readers do', 'r': figures.build(days),
        'choices': figures.DAYS, 'fewer': figures.FEWER, 'thresholds': figures.THRESHOLDS,
        'site': settings.SITE_URL.rstrip('/')})
