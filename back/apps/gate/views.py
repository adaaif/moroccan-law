from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_exempt

from apps.gate.services import gate


def _next(request) -> str:
    target = request.POST.get('next') or request.GET.get('next') or '/'
    if not url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return '/'
    return target if target.startswith('/') and not target.startswith('/gate/') else '/'


@csrf_exempt            # a shared password, not an account: there is no session to ride on
def page(request):
    """The password page (GET), and the password (POST): the cookie and back to where the reader was going."""
    if request.method == 'POST':
        result = gate.attempt(request, request.POST.get('password', ''))
        if result == 'ok':
            response = HttpResponseRedirect(_next(request))
            response.set_cookie(gate.COOKIE, gate.ticket(), max_age=gate.DAYS * 86400, secure=request.is_secure(),
                                httponly=True, samesite='Lax')
            return response
        return render(request, 'gate/page.html', {'next': _next(request), 'error': result},
                      status=429 if result == 'wait' else 200)
    return render(request, 'gate/page.html', {'next': _next(request)})


def check(request):
    """nginx's auth_request: 204 when the reader came through the gate, else 401."""
    return HttpResponse(status=204 if not gate.on() or gate.admitted(request) else 401)
