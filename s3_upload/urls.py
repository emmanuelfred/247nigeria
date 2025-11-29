
from django.urls import path
from users.views import *

urlpatterns = [
    path('', upload_file, name="upload"),
    path('delete/', delete_image, name="delete_image"),

]
