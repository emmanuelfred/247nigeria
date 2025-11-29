from django.urls import path
from .views import upload_cover_photo, upload_profile_photo,signup,verify_identity, verify_email, login_view,update_profile,request_password_reset,verify_otp,reset_password ,resend_verification,update_password,update_email

urlpatterns = [
    path('auth/signup/', signup),
    path('auth/identity/<int:user_id>/', verify_identity),
    path('auth/verify-email/<uid>/<token>/', verify_email),
    path("auth/login/", login_view, name="login"),
    path("auth/update-profile/", update_profile),
    path('auth/forgot-password/', request_password_reset, name='forgot-password'),
    path('auth/verify-otp/', verify_otp, name='verify-otp'),
    path('auth/reset-password/', reset_password, name='reset-password'),
    path('auth/resend-verification/', resend_verification, name='resend-verification'),
    path("auth/update-password/<int:user_id>/", update_password, name="update-password"),
    path("auth/update-email/<int:user_id>/", update_email, name="update-email"),
    path('auth/upload-cover-photo/<int:user_id>/', upload_cover_photo, name='upload_cover_photo'),
    path('auth/upload-profile-photo/<int:user_id>/', upload_profile_photo, name='upload_profile_photo'),


    
]
