from django.urls import path
from . import views

urlpatterns = [
    # Create a new job post
    path('jobs/create/', views.create_job_post, name='create_job'),
    
    # Get job details
    path('jobs/<int:job_id>/', views.get_job_detail, name='job_detail'),
    
    # List all approved jobs
    path('jobs/', views.list_jobs, name='list_jobs'),
    
    # Get current logged-in user's jobs
    path('jobs/my-posts/', views.my_jobs, name='my_jobs'),
    
    # Get jobs by specific user ID
    path('jobs/user/<int:user_id>/', views.get_user_jobs, name='user_jobs'),
    
    # Apply to a job
    path('jobs/<int:job_id>/apply/', views.apply_to_job, name='apply_to_job'),
    path("jobs/<int:job_id>/applications/", views.get_job_applications),
    
    path("jobs/applications/my/", views.get_my_applications),
    path("applications/<int:application_id>/delete/", views.delete_application),
    path("applications/<int:application_id>/", views.get_application_detail),
    path("jobs/<int:job_id>/delete/", views.delete_job),

    # ===== NEW ADMIN ENDPOINTS =====
    # Admin job approval/rejection
    path('admin/jobs/<int:job_id>/approve/', views.approve_job, name='approve_job'),
    path('admin/jobs/<int:job_id>/reject/', views.reject_job, name='reject_job'),
]