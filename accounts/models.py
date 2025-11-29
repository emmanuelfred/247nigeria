from django.db import models
from django.contrib.auth.models import AbstractUser
import random
from datetime import timedelta
from django.utils import timezone

class User(AbstractUser):
    username = None  # remove the default username field
    email = models.EmailField(unique=True)  # email as unique identifier
    surname = models.CharField(max_length=100)
    email_verified = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    cover_photo = models.URLField(
        blank=True, 
        null=True,
        default='https://247nigeria.s3.eu-north-1.amazonaws.com/cover-photo.jpg'
    )
    profile_photo = models.URLField(blank=True, null=True)  # ✅ Add blank=True, null=True

    USERNAME_FIELD = "email"  # make email the login field
    REQUIRED_FIELDS = ["surname", "first_name", "last_name"]
    
class IdentityVerification(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    id_document = models.URLField() 
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=10)
    address = models.CharField(max_length=255)
    verified = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(auto_now_add=True)



class PasswordResetOTP(models.Model):
    user = models.ForeignKey("User", on_delete=models.CASCADE)
    code = models.CharField(max_length=4)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = f"{random.randint(1000, 9999)}"
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=15)  # OTP valid for 15 mins
        super().save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() > self.expires_at
class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=32, unique=True)
    expires_at = models.DateTimeField()
