from django.urls import path
from . import views

urlpatterns = [
    # Property Listing
    path('properties/create/', views.create_property_post, name='create_property'),
    path('properties/', views.list_properties, name='list_properties'),
    path('properties/<int:property_id>/', views.get_property_detail, name='property_detail'),
    path('properties/my-posts/', views.my_properties, name='my_properties'),
    path('properties/<int:property_id>/delete/', views.delete_property, name='delete_property'),
    
    # Property Inquiries
    path('properties/<int:property_id>/inquire/', views.create_property_inquiry, name='create_inquiry'),
    path('inquiries/my-inquiries/', views.get_my_inquiries, name='get_my_inquiries'),
    path('properties/<int:property_id>/inquiries/', views.get_property_inquiries, name='get_property_inquiries'),
    path('inquiries/<int:inquiry_id>/update-status/', views.update_inquiry_status, name='update_inquiry_status'),
    
    # Admin Property Approval/Rejection
    path('admin/properties/<int:property_id>/approve/', views.approve_property, name='approve_property'),
    path('admin/properties/<int:property_id>/reject/', views.reject_property, name='reject_property'),
]