from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

from apps.accounts.services import brake
from apps.accounts.services.accounts import find_login_user


class UsernameOrEmailBackend(ModelBackend):
    """Sign in with the username or the email address, in any letter case.

    The brake on wrong passwords lives here, so every door that checks a password through Django shares it: the API's
    sign-in and the admin's form alike. A wrong password counts; while the brake holds, no password is checked, the
    right one included, and the door refuses as it refuses a wrong one (the admin's form with Django's own words; the
    API's sign-in reads `brake.held` to say the minutes, or to ask for Turnstile, whose token lets the password be
    judged)."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or password is None:
            return None
        user = find_login_user(username)
        if user is None or not self.user_can_authenticate(user):
            # Hash anyway: a missing or switched-off account takes as long as a wrong password.
            get_user_model()().set_password(password)
            return None
        brake.mark(request, known=True)
        ip = brake.address(request) if request is not None else '-'
        # Held, unless the person passed Turnstile (brake.py): then the password is judged, and counts if wrong.
        if (wait := brake.wait(user, ip)) and not brake.passed(request):
            brake.mark(request, wait=wait)
            return None
        if not user.check_password(password):
            brake.mark(request, wait=brake.failed(user, ip))
            return None
        brake.clear(user, ip)
        return user
