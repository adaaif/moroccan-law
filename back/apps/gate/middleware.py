from django.http import HttpResponseRedirect, JsonResponse
from django.utils.http import urlencode

from apps.gate.services import gate


class GateMiddleware:
    """While the gate is on: nothing but the gate without its cookie (an API call gets the one error shape, a page the
    gate), and every answer asks search engines to stay away."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not gate.on():
            return self.get_response(request)
        # The assistants' sign-in carries its own authorization (apps.oauth): never behind the gate.
        open_paths = ('/gate/', '/oauth/', '/.well-known/')
        if not request.path.startswith(open_paths) and not gate.admitted(request):
            if request.path.startswith('/api/'):
                response = JsonResponse({'errors': [{'field': 'gate', 'code': 'locked'}]}, status=401)
            else:
                response = HttpResponseRedirect('/gate/?' + urlencode({'next': request.get_full_path()}))
        else:
            response = self.get_response(request)
        response['X-Robots-Tag'] = 'noindex, nofollow'
        return response
