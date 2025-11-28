from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator

def send_verification_email(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    link = f"http://localhost:3000/verify-email/{uid}/{token}/"

    send_mail(
        'Verify Your Email',
        f"Click the link to verify your email: {link} \n Link will expire in 3 days.",
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )
def send_otp_email(user,otp):
    send_mail(
            "Your Password Reset Code",
            f"Hello {user.surname}\nYour password reset code is:\n {otp}",
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )