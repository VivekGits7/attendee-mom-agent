from django.conf import settings


def email_delivery(request):
    return {
        "email_is_logged": settings.EMAIL_BACKEND
        == "django.core.mail.backends.console.EmailBackend"
    }
