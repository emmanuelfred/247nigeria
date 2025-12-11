from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction
from accounts.models import Job, JobImage, User, JobApplication, IdentityVerification
from s3_upload.utils import upload_file_to_s3
from django.conf import settings
from datetime import datetime, timezone
from django.utils.timesince import timesince
from .email_utils import (
    send_job_posted_email,
    send_job_approved_email,
    send_job_rejected_email,
    send_application_confirmation_to_applicant,
    send_application_notification_to_employer
)

# ✅ Add these constants
BUCKET = settings.AWS_STORAGE_BUCKET_NAME
REGION = settings.AWS_S3_REGION_NAME

def humanize_time(dt):
    """Convert datetime to '2 days ago' format."""
    if not dt:
        return None
    now = datetime.now(timezone.utc)
    return timesince(dt, now) + " ago"


def clean_label(val):
    """Convert 'per_month' → 'Per month', 'part_time' → 'Part time'."""
    if not val:
        return val
    return val.replace("_", " ").title()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_job_post(request):
    """
    Create a new job posting with multiple images
    Requires email verification and identity verification
    """
    user = request.user

    # 1. CHECK EMAIL VERIFICATION
    if not user.email_verified:
        return Response(
            {'error': 'Please verify your email before posting a job.'},
            status=status.HTTP_403_FORBIDDEN
        )

    # 2. CHECK IDENTITY VERIFICATION
    try:
        identity = IdentityVerification.objects.get(user=user)
        if not identity.verified:
            return Response(
                {'error': 'Your identity verification has not been approved yet.'},
                status=status.HTTP_403_FORBIDDEN
            )
    except IdentityVerification.DoesNotExist:
        return Response(
            {'error': 'Please submit your identity verification before posting a job.'},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        data = request.data
        files = request.FILES
        
        # Validate required fields
        required_fields = [
            'job_title', 'company_name', 'category', 'job_type',
            'full_address', 'state', 'city', 'job_description',
            'requirements', 'experience_years', 'education',
            'minimum_salary', 'maximum_salary', 'salary_period',
            'application_method'
        ]
        
        for field in required_fields:
            if field not in data or not data[field]:
                return Response(
                    {'error': f'{field} is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Use transaction to ensure all or nothing
        with transaction.atomic():
            # Create the job
            job = Job.objects.create(
                # Basic Information
                job_title=data['job_title'],
                company_name=data['company_name'],
                category=data['category'],
                job_type=data['job_type'],
                full_address=data['full_address'],
                state=data['state'],
                city=data['city'],
                
                # Job Details
                job_description=data['job_description'],
                requirements=data['requirements'],
                key_responsibilities=data.get('key_responsibilities', ''),
                benefits=data.get('benefits', ''),
                experience_years=int(data['experience_years']),
                education=data['education'],
                
                # Salary
                minimum_salary=float(data['minimum_salary']),
                maximum_salary=float(data['maximum_salary']),
                salary_period=data['salary_period'],
                
                # Contact
                application_method=data['application_method'],
                external_link=data.get('external_link', ''),
                
                # Metadata
                posted_by=request.user,
                status='pending'
            )
            
            # Handle multiple image uploads
            uploaded_images = []
            thumbnail_index = data.get('thumbnail_index', 0)
            
            # Get all image files from the request
            image_files = []
            for key in files:
                if key.startswith('image'):
                    image_files.append(files[key])
            
            # Upload each image to S3 and save to database
            for index, image_file in enumerate(image_files):
                # Upload to S3
                image_url, file_key = upload_file_to_s3(
                    image_file,
                    folder='job-images',
                    content_type=image_file.content_type
                )
                
                # Create JobImage record
                job_image = JobImage.objects.create(
                    job=job,
                    image_url=image_url,
                    is_thumbnail=(index == int(thumbnail_index)),
                    order=index,
                    caption=data.get(f'caption_{index}', '')
                )
                
                uploaded_images.append({
                    'id': job_image.id,
                    'url': image_url,
                    'is_thumbnail': job_image.is_thumbnail
                })
            
            # Send confirmation email
            send_job_posted_email(user, job)
            
            # Prepare response
            response_data = {
                'message': 'Job posted successfully! It will be reviewed within 24 hours.',
                'job': {
                    'id': job.id,
                    'job_title': job.job_title,
                    'company_name': job.company_name,
                    'category': job.category,
                    'job_type': job.job_type,
                    'full_address': job.full_address,
                    'state': job.state,
                    'city': job.city,
                    'job_description': job.job_description,
                    'requirements': job.requirements,
                    'key_responsibilities': job.key_responsibilities,
                    'benefits': job.benefits,
                    'experience_years': job.experience_years,
                    'education': job.education,
                    'minimum_salary': str(job.minimum_salary),
                    'maximum_salary': str(job.maximum_salary),
                    'salary_period': job.salary_period,
                    'application_method': job.application_method,
                    'external_link': job.external_link,
                    'status': job.status,
                    'created_at': job.created_at,
                    'applicant_count': job.applicant_count,
                    'posted_by': {
                        'id': job.posted_by.id,
                        'user_id': job.posted_by.id,  # ✅ Include user ID
                        'email': job.posted_by.email,
                        'first_name': job.posted_by.first_name,
                        'last_name': job.posted_by.last_name,
                        'surname': job.posted_by.surname,
                        'profile_photo': job.posted_by.profile_photo,
                    },
                    'images': uploaded_images
                }
            }
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def get_job_detail(request, job_id):
    """
    Get job details with all images and poster info
    """
    try:
        job = Job.objects.select_related('posted_by').get(id=job_id)
        
        # Get all images for this job
        images = job.images.all()
        
        response_data = {
            'id': job.id,
            'job_title': job.job_title,
            'company_name': job.company_name,
            'category': job.category,
            'job_type': job.job_type,
            'full_address': job.full_address,
            'state': job.state,
            'city': job.city,
            'job_description': job.job_description,
            'requirements': job.requirements,
            'key_responsibilities': job.key_responsibilities,
            'benefits': job.benefits,
            'experience_years': job.experience_years,
            'education': job.education,
            'minimum_salary': str(job.minimum_salary),
            'maximum_salary': str(job.maximum_salary),
            'salary_period': job.salary_period,
            'application_method': job.application_method,
            'external_link': job.external_link,
            'status': job.status,
            'applicant_count': job.applicant_count,
            'created_at': job.created_at,
            'updated_at': job.updated_at,
            'posted_by': {
                'id': job.posted_by.id,
                'user_id': job.posted_by.id,  # ✅ Include user ID
                'email': job.posted_by.email,
                'first_name': job.posted_by.first_name,
                'last_name': job.posted_by.last_name,
                'surname': job.posted_by.surname,
                'phone_number': job.posted_by.phone_number,
                'location': job.posted_by.location,
                'profile_photo': job.posted_by.profile_photo,
            },
            'images': [
                {
                    'id': img.id,
                    'url': img.image_url,
                    'is_thumbnail': img.is_thumbnail,
                    'caption': img.caption,
                    'order': img.order
                }
                for img in images
            ]
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Job.DoesNotExist:
        return Response(
            {'error': 'Job not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
def list_jobs(request):
    """
    List all approved jobs with poster info and thumbnail
    """
    jobs = Job.objects.filter(
        status='pending',#approved
        is_active=True
    ).select_related('posted_by').prefetch_related('images').order_by('-created_at')
    
    jobs_data = []
    for job in jobs:
        # Get thumbnail image
        thumbnail = job.images.filter(is_thumbnail=True).first()
        
        jobs_data.append({
            'id': job.id,
            'job_title': job.job_title,
            'company_name': job.company_name,
            'category': job.category,
            'job_type': job.job_type,
            'city': job.city,
            'state': job.state,
            'minimum_salary': clean_label(str(job.minimum_salary)),
            'maximum_salary': clean_label(str(job.maximum_salary)),
            'salary_period': job.salary_period,
            'applicant_count': job.applicant_count,
            'created_at': humanize_time(job.created_at),
            'thumbnail': thumbnail.image_url if thumbnail else None,
            'posted_by': {
                'id': job.posted_by.id,
                'user_id': job.posted_by.id,  # ✅ Include user ID
                'first_name': job.posted_by.first_name,
                'last_name': job.posted_by.last_name,
                'surname': job.posted_by.surname,
                'profile_photo': job.posted_by.profile_photo,
            }
        })
    
    return Response(jobs_data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_jobs(request):
    """
    Get all jobs posted by the current user
    Uses request.user to automatically filter by logged-in user
    """
    jobs = Job.objects.filter(
        posted_by=request.user
    ).prefetch_related('images').order_by('-created_at')
    
    jobs_data = []
    for job in jobs:
        thumbnail = job.images.filter(is_thumbnail=True).first()
        
        jobs_data.append({
            'id': job.id,
            'job_title': job.job_title,
            'company_name': job.company_name,
            'category': job.category,
            'job_type': job.job_type,
            'city': job.city,
            'state': job.state,
            'status': job.status,
            'applicant_count': job.applicant_count,
            'created_at': job.created_at,
            'updated_at': job.updated_at,
            'approval_date': job.approval_date,
            'rejection_reason': job.rejection_reason,
            'thumbnail': thumbnail.image_url if thumbnail else None,
            'minimum_salary': str(job.minimum_salary),
            'maximum_salary': str(job.maximum_salary),
            'salary_period': job.salary_period,
        })
    
    return Response(jobs_data, status=status.HTTP_200_OK)


@api_view(['GET'])
def get_user_jobs(request, user_id):
    """
    Get all approved jobs posted by a specific user (by user ID)
    Useful for viewing another user's public job listings
    """
    try:
        user = User.objects.get(id=user_id)
        
        jobs = Job.objects.filter(
            posted_by=user,
            status='approved',
            is_active=True
        ).prefetch_related('images').order_by('-created_at')
        
        jobs_data = []
        for job in jobs:
            thumbnail = job.images.filter(is_thumbnail=True).first()
            
            jobs_data.append({
                'id': job.id,
                'job_title': job.job_title,
                'company_name': job.company_name,
                'category': job.category,
                'job_type': job.job_type,
                'city': job.city,
                'state': job.state,
                'status': job.status,
                'applicant_count': job.applicant_count,
                'created_at': job.created_at,
                'thumbnail': thumbnail.image_url if thumbnail else None,
                'minimum_salary': str(job.minimum_salary),
                'maximum_salary': str(job.maximum_salary),
                'salary_period': job.salary_period,
            })
        
        response_data = {
            'user': {
                'id': user.id,
                'user_id': user.id,  # ✅ Include user ID
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'surname': user.surname,
                'profile_photo': user.profile_photo,
                'location': user.location,
            },
            'jobs': jobs_data,
            'total_jobs': len(jobs_data)
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except User.DoesNotExist:
        return Response(
            {'error': 'User not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def apply_to_job(request, job_id):
    """
    Apply for a job with CV upload to S3
    Requires email verification and identity verification
    """
    user = request.user
    
    # 1. CHECK EMAIL VERIFICATION
    if not user.email_verified:
        return Response(
            {'error': 'Please verify your email before applying for a job.'},
            status=status.HTTP_403_FORBIDDEN
        )

    # 2. CHECK IDENTITY VERIFICATION
    try:
        identity = IdentityVerification.objects.get(user=user)
        if not identity.verified:
            return Response(
                {'error': 'Your identity verification has not been approved yet.'},
                status=status.HTTP_403_FORBIDDEN
            )
    except IdentityVerification.DoesNotExist:
        return Response(
            {'error': 'Please submit your identity verification before applying.'},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        data = request.data
        files = request.FILES

        # 3. Check job exists + is approved
        try:
            job = Job.objects.get(id=job_id, status='approved')
        except Job.DoesNotExist:
            return Response(
                {'error': 'Job not found or not open for applications.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # 4. Extract fields
        full_name = data.get('full_name')
        email = data.get('email')
        phone_number = data.get('phone_number')
        expected_salary = data.get('expected_salary')
        portfolio_website = data.get('portfolio_website', '')
        cover_letter = data.get('cover_letter')

        # 5. Check required fields
        required_fields = [
            full_name, email, phone_number,
            expected_salary, cover_letter
        ]

        if any(field is None or field == '' for field in required_fields):
            return Response(
                {'error': 'All fields except portfolio_website are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 6. CV Upload Handling
        cv_url = None
        if 'cv_file' in files:
            cv_file = files['cv_file']

            # Upload to S3 using your helper
            cv_url, file_key = upload_file_to_s3(
                cv_file,
                folder='job-applications',
                content_type=cv_file.content_type
            )
        else:
            # fallback: maybe passed URL instead
            cv_url = data.get('cv_url')

        if not cv_url:
            return Response(
                {'error': 'Please upload your CV or provide a CV URL.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 7. Prevent duplicate applications
        if JobApplication.objects.filter(job=job, applicant=request.user).exists():
            return Response(
                {'error': 'You have already applied for this job.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 8. Save application
        application = JobApplication.objects.create(
            job=job,
            applicant=request.user,
            full_name=full_name,
            email=email,
            phone_number=phone_number,
            cv_url=cv_url,
            expected_salary=expected_salary,
            portfolio_website=portfolio_website,
            cover_letter=cover_letter,
            status='pending'
        )
        
        # 9. INCREMENT APPLICANT COUNT
        job.increment_applicant_count()

        # 10. Send confirmation emails
        # To applicant
        send_application_confirmation_to_applicant(request.user, job, application)
        # To employer
        send_application_notification_to_employer(job.posted_by, job, application, request.user)

        # 11. Response
        return Response(
            {
                'message': 'Application submitted successfully!',
                'application': {
                    'id': application.id,
                    'applicant_id': request.user.id,  # ✅ Include user ID
                    'full_name': application.full_name,
                    'email': application.email,
                    'cv_url': application.cv_url,
                    'expected_salary': str(application.expected_salary),
                    'status': application.status,
                    'created_at': application.applied_at,
                    'job': {
                        'id': job.id,
                        'title': job.job_title,
                        'company': job.company_name,
                        'applicant_count': job.applicant_count,
                    }
                }
            },
            status=status.HTTP_201_CREATED
        )

    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_applications(request):
    """
    Get all applications submitted by the current user
    """
    user = request.user

    applications = JobApplication.objects.filter(applicant=user).select_related('job')
    images = JobImage.objects.filter(job__in=[app.job for app in applications], is_thumbnail=True)

    data = []

    for app in applications:
        data.append({
            "application_id": app.id,
            "applicant_id": user.id,  # ✅ Include user ID
            "status": app.status,
            "cv_url": app.cv_url,
            "expected_salary": str(app.expected_salary),
            "portfolio_website": app.portfolio_website,
            "cover_letter": app.cover_letter,
            "applied_at": humanize_time(app.applied_at),

            "job": {
                "id": app.job.id,
                "title": app.job.job_title,
                "company": app.job.company_name,
                "city": app.job.city,
                "state": app.job.state,
                "minimum_salary": str(app.job.minimum_salary),
                "maximum_salary": str(app.job.maximum_salary),
                "salary_period": clean_label(app.job.salary_period),
                "job_type": clean_label(app.job.job_type),
                "applicant_count": app.job.applicant_count or 0,
                "thumbnail": next((img.image_url for img in images if img.job_id == app.job.id), None)
            }
        })

    return Response({"applications": data}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_job_applications(request, job_id):
    """
    Get all applications made to a specific job.
    Only the job owner (posted_by) should be allowed to view this.
    """
    try:
        # Confirm job exists
        try:
            job = Job.objects.get(id=job_id)
        except Job.DoesNotExist:
            return Response(
                {"error": "Job not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Optional: Ensure only job owner can view the applications
        if job.posted_by != request.user:
            return Response(
                {"error": "You are not allowed to view applications for this job."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get all applications for this job
        applications = JobApplication.objects.filter(job=job).select_related("applicant")

        data = []

        for app in applications:
            data.append({
                "application_id": app.id,
                "applicant_id": app.applicant.id,  # ✅ Include user ID
                "full_name": app.full_name,
                "email": app.email,
                "phone_number": app.phone_number,
                "cv_url": app.cv_url,
                "expected_salary": str(app.expected_salary),
                "portfolio_website": app.portfolio_website,
                "cover_letter": app.cover_letter,
                "status": app.status,
                "applied_at": app.applied_at,

                # Applicant details
                "applicant": {
                    "id": app.applicant.id,
                    "user_id": app.applicant.id,  # ✅ Include user ID
                    "email": app.applicant.email,
                    "surname": app.applicant.surname,
                    "phone_number": app.applicant.phone_number,
                    "profile_photo": app.applicant.profile_photo,
                }
            })

        return Response(
            {
                "job_title": job.job_title,
                "company": job.company_name,
                "applicant_count": job.applicant_count,
                "applications": data
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_application(request, application_id):
    """
    Delete a job application.
    Only the applicant who submitted it can delete it.
    """
    try:
        # Get the application
        try:
            application = JobApplication.objects.get(id=application_id)
        except JobApplication.DoesNotExist:
            return Response(
                {"error": "Application not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Ensure the user removing it is the applicant
        if application.applicant != request.user:
            return Response(
                {"error": "You are not allowed to delete this application."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Decrement applicant count before deleting
        job = application.job
        if job.applicant_count > 0:
            job.applicant_count -= 1
            job.save(update_fields=['applicant_count'])

        application.delete()

        return Response(
            {"message": "Application deleted successfully."},
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_application_detail(request, application_id):
    """
    Get detailed information about a specific application
    Only the applicant or job owner can view
    """
    try:
        # Get the application with related job and applicant data
        try:
            application = JobApplication.objects.select_related(
                'job', 
                'applicant',
                'job__posted_by'
            ).prefetch_related('job__images').get(id=application_id)
        except JobApplication.DoesNotExist:
            return Response(
                {"error": "Application not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check permissions: only applicant or job owner can view
        if application.applicant != request.user and application.job.posted_by != request.user:
            return Response(
                {"error": "You are not allowed to view this application."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get job thumbnail
        thumbnail = application.job.images.filter(is_thumbnail=True).first()

        # Build response data
        response_data = {
            "application_id": application.id,
            "status": application.status,
            "applied_at": application.applied_at,
            "updated_at": application.updated_at,
            
            # Application Details
            "full_name": application.full_name,
            "email": application.email,
            "phone_number": application.phone_number,
            "cv_url": application.cv_url,
            "expected_salary": str(application.expected_salary),
            "portfolio_website": application.portfolio_website,
            "cover_letter": application.cover_letter,
            
            # Job Details
            "job": {
                "id": application.job.id,
                "title": application.job.job_title,
                "company": application.job.company_name,
                "city": application.job.city,
                "state": application.job.state,
                "full_address": application.job.full_address,
                "category": application.job.category,
                "job_type": clean_label(application.job.job_type),
                "minimum_salary": str(application.job.minimum_salary),
                "maximum_salary": str(application.job.maximum_salary),
                "salary_period": clean_label(application.job.salary_period),
                "job_description": application.job.job_description,
                "requirements": application.job.requirements,
                "key_responsibilities": application.job.key_responsibilities,
                "benefits": application.job.benefits,
                "experience_years": application.job.experience_years,
                "education": application.job.education,
                "application_method": application.job.application_method,
                "applicant_count": application.job.applicant_count,
                "thumbnail": thumbnail.image_url if thumbnail else None,
                
                # Job Poster Details
                "posted_by": {
                    "id": application.job.posted_by.id,
                    "user_id": application.job.posted_by.id,
                    "email": application.job.posted_by.email,
                    "first_name": application.job.posted_by.first_name,
                    "last_name": application.job.posted_by.last_name,
                    "surname": application.job.posted_by.surname,
                    "phone_number": application.job.posted_by.phone_number,
                    "location": application.job.posted_by.location,
                    "profile_photo": application.job.posted_by.profile_photo,
                }
            },
            
            # Applicant Details
            "applicant": {
                "id": application.applicant.id,
                "user_id": application.applicant.id,
                "email": application.applicant.email,
                "first_name": application.applicant.first_name,
                "last_name": application.applicant.last_name,
                "surname": application.applicant.surname,
                "phone_number": application.applicant.phone_number,
                "location": application.applicant.location,
                "profile_photo": application.applicant.profile_photo,
            }
        }

        return Response(response_data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_job(request, job_id):
    """
    Delete a job.
    Only the user who posted the job can delete it.
    """
    try:
        # Get the job
        try:
            job = Job.objects.get(id=job_id)
        except Job.DoesNotExist:
            return Response(
                {"error": "Job not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Ensure the user is the creator
        if job.posted_by != request.user:
            return Response(
                {"error": "You are not allowed to delete this job."},
                status=status.HTTP_403_FORBIDDEN
            )

        job.delete()

        return Response(
            {"message": "Job deleted successfully."},
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ====== ADMIN ENDPOINTS FOR APPROVING/REJECTING JOBS ======

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def approve_job(request, job_id):
    """
    Approve a job posting (Admin only)
    """
    # Check if user is admin/staff
    if not request.user.is_staff:
        return Response(
            {"error": "Only administrators can approve jobs."},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        job = Job.objects.get(id=job_id)
        
        if job.status == 'approved':
            return Response(
                {"error": "Job is already approved."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Approve the job
        job.approve(request.user)
        
        # Send approval email to job poster
        send_job_approved_email(job.posted_by, job)
        
        return Response(
            {
                "message": "Job approved successfully.",
                "job": {
                    "id": job.id,
                    "title": job.job_title,
                    "status": job.status,
                    "approved_by": request.user.email,
                    "approval_date": job.approval_date
                }
            },
            status=status.HTTP_200_OK
        )
        
    except Job.DoesNotExist:
        return Response(
            {"error": "Job not found."},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reject_job(request, job_id):
    """
    Reject a job posting (Admin only)
    """
    # Check if user is admin/staff
    if not request.user.is_staff:
        return Response(
            {"error": "Only administrators can reject jobs."},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        job = Job.objects.get(id=job_id)
        
        if job.status == 'rejected':
            return Response(
                {"error": "Job is already rejected."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reason = request.data.get('reason', '')
        
        # Reject the job
        job.reject(request.user, reason)
        
        # Send rejection email to job poster
        send_job_rejected_email(job.posted_by, job)
        
        return Response(
            {
                "message": "Job rejected successfully.",
                "job": {
                    "id": job.id,
                    "title": job.job_title,
                    "status": job.status,
                    "rejected_by": request.user.email,
                    "rejection_reason": job.rejection_reason,
                    "approval_date": job.approval_date
                }
            },
            status=status.HTTP_200_OK
        )
        
    except Job.DoesNotExist:
        return Response(
            {"error": "Job not found."},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_application_status(request, application_id):
    """
    Update application status (reviewed, shortlisted, rejected, accepted)
    Only job owner can update
    """
    try:
        application = JobApplication.objects.get(id=application_id)
        
        # Check if user is job owner
        if application.job.posted_by != request.user:
            return Response({"error": "Unauthorized"}, status=403)
        
        new_status = request.data.get('status')
        application.status = new_status
        application.save()
        
        # TODO: Send email notification to applicant
        
        return Response({"message": "Status updated"}, status=200)
    except:
        return Response({"error": "Failed"}, status=400)