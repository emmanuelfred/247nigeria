from django.db import models
from django.contrib.auth.models import AbstractUser
import random
from datetime import timedelta
from django.utils import timezone
from django.db import models
from django.contrib.auth import get_user_model


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
    profile_photo = models.URLField(blank=True, null=True)

    USERNAME_FIELD = "email"
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
            self.expires_at = timezone.now() + timedelta(minutes=15)
        super().save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() > self.expires_at
        
class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=32, unique=True)
    expires_at = models.DateTimeField()


User = get_user_model()


class Job(models.Model):
    """Main job posting model"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    CATEGORY_CHOICES = [
        ('technology', 'Technology'),
        ('marketing', 'Marketing'),
        ('finance', 'Finance'),
        ('design', 'Design'),
        ('graphics', 'Graphics'),
        ('customer_service', 'Customer Service'),
        ('other', 'Other'),
    ]
    
    JOB_TYPE_CHOICES = [
        ('full_time', 'Full-time'),
        ('part_time', 'Part-time'),
        ('contract', 'Contract'),
        ('internship', 'Internship'),
    ]
    
    SALARY_PERIOD_CHOICES = [
        ('per_month', 'Per Month'),
        ('per_hour', 'Per Hour'),
        ('per_year', 'Per Year'),
    ]
    
    APPLICATION_METHOD_CHOICES = [
        ('phone', 'Via Phone Number'),
        ('email', 'Via Email'),
        ('external_link', 'External Link'),
        ('onsite', 'Apply on Site'),
    ]
    
    # Basic Information
    job_title = models.CharField(max_length=255)
    company_name = models.CharField(max_length=255)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    job_type = models.CharField(max_length=50, choices=JOB_TYPE_CHOICES)
    full_address = models.TextField()
    state = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    
    # Job Details
    job_description = models.TextField()
    requirements = models.TextField()
    key_responsibilities = models.TextField(blank=True, null=True)
    benefits = models.TextField(blank=True, null=True)
    experience_years = models.IntegerField(help_text="Required years of experience")
    education = models.CharField(max_length=255)
    
    # Salary & Media
    minimum_salary = models.DecimalField(max_digits=10, decimal_places=2)
    maximum_salary = models.DecimalField(max_digits=10, decimal_places=2)
    salary_period = models.CharField(max_length=20, choices=SALARY_PERIOD_CHOICES)
    
    # Contact Information
    application_method = models.CharField(max_length=20, choices=APPLICATION_METHOD_CHOICES)
    external_link = models.URLField(blank=True, null=True)
    
    # Admin approval fields
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    approved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='approved_jobs'
    )
    approval_date = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)
    
    # Metadata
    posted_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='posted_jobs'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    # Applicant counter
    applicant_count = models.PositiveIntegerField(default=0, help_text="Number of applicants")
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Job Posting'
        verbose_name_plural = 'Job Postings'
    
    def __str__(self):
        return f"{self.job_title} at {self.company_name}"
    
    def approve(self, admin_user):
        """Approve the job posting"""
        self.status = 'approved'
        self.approved_by = admin_user
        self.approval_date = timezone.now()
        self.save()
    
    def reject(self, admin_user, reason=None):
        """Reject the job posting"""
        self.status = 'rejected'
        self.approved_by = admin_user
        self.rejection_reason = reason
        self.approval_date = timezone.now()
        self.save()
    
    def increment_applicant_count(self):
        """Increment the applicant count"""
        self.applicant_count += 1
        self.save(update_fields=['applicant_count'])


class JobImage(models.Model):
    """Model to store multiple images for a job posting"""
    
    job = models.ForeignKey(
        Job, 
        on_delete=models.CASCADE, 
        related_name='images'
    )
    image_url = models.URLField(max_length=500)
    is_thumbnail = models.BooleanField(
        default=False,
        help_text="Mark as main thumbnail image"
    )
    caption = models.CharField(max_length=255, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    order = models.PositiveIntegerField(default=0, help_text="Display order")
    
    class Meta:
        ordering = ['order', '-is_thumbnail', 'uploaded_at']
        verbose_name = 'Job Image'
        verbose_name_plural = 'Job Images'
    
    def __str__(self):
        thumbnail_text = " (Thumbnail)" if self.is_thumbnail else ""
        return f"Image for {self.job.job_title}{thumbnail_text}"
    
    def save(self, *args, **kwargs):
        if self.is_thumbnail:
            JobImage.objects.filter(
                job=self.job, 
                is_thumbnail=True
            ).exclude(pk=self.pk).update(is_thumbnail=False)
        super().save(*args, **kwargs)


class JobApplication(models.Model):
    """Model to store job applications"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('reviewed', 'Reviewed'),
        ('shortlisted', 'Shortlisted'),
        ('rejected', 'Rejected'),
        ('accepted', 'Accepted'),
    ]
    
    job = models.ForeignKey(
        'Job', 
        on_delete=models.CASCADE, 
        related_name='applications'
    )
    applicant = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='job_applications'
    )
    
    # Basic Information
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20)
    
    # Application Details
    cv_url = models.URLField(max_length=500, help_text="S3 URL for CV/Resume")
    expected_salary = models.DecimalField(max_digits=10, decimal_places=2)
    portfolio_website = models.URLField(blank=True, null=True)
    cover_letter = models.TextField()
    
    # Application Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Metadata
    applied_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-applied_at']
        verbose_name = 'Job Application'
        verbose_name_plural = 'Job Applications'
        unique_together = ['job', 'applicant']
    
    def __str__(self):
        return f"{self.full_name} - {self.job.job_title} ({self.status})"
    
    
    
class Property(models.Model):
    """Main property listing model"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    PROPERTY_TYPE_CHOICES = [
        ('apartment', 'Apartment'),
        ('house', 'House'),
        ('land', 'Land'),
        ('commercial_building', 'Commercial Building'),
        ('office_space', 'Office Space'),
    ]
    
    LISTING_TYPE_CHOICES = [
        ('for_rent', 'For Rent'),
        ('for_sale', 'For Sale'),
        ('for_lease', 'For Lease'),
    ]
    
    FURNISHING_STATUS_CHOICES = [
        ('fully_furnished', 'Fully Furnished'),
        ('semi_furnished', 'Semi Furnished'),
        ('unfurnished', 'Unfurnished'),
    ]
    
    PRICE_PERIOD_CHOICES = [
        ('per_month', 'Per Month'),
        ('per_year', 'Per Year'),
        ('one_time', 'One Time Payment'),
    ]
    
    CONTACT_METHOD_CHOICES = [
        ('phone', 'Via Phone Number'),
        ('email', 'Via Email'),
        ('external_link', 'External Link'),
    ]
    
    # Basic Information
    property_title = models.CharField(max_length=255)
    property_type = models.CharField(max_length=50, choices=PROPERTY_TYPE_CHOICES)
    listing_type = models.CharField(max_length=50, choices=LISTING_TYPE_CHOICES)
    full_address = models.TextField()
    state = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    
    # Property Details
    bedrooms = models.PositiveIntegerField(default=0)
    bathrooms = models.PositiveIntegerField(default=0)
    size_sqm = models.DecimalField(max_digits=10, decimal_places=2, help_text="Size in square meters")
    parking_spots = models.PositiveIntegerField(default=0)
    property_description = models.TextField()
    furnishing_status = models.CharField(max_length=50, choices=FURNISHING_STATUS_CHOICES)
    
    # Amenities (stored as comma-separated values or use JSONField)
    amenities = models.JSONField(default=list, blank=True, help_text="List of amenities")
    
    # Price & Media
    price = models.DecimalField(max_digits=12, decimal_places=2)
    price_period = models.CharField(max_length=20, choices=PRICE_PERIOD_CHOICES)
    
    # Contact Information
    contact_method = models.CharField(max_length=20, choices=CONTACT_METHOD_CHOICES)
    external_link = models.URLField(blank=True, null=True)
    
    # Admin approval fields
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    approved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='approved_properties'
    )
    approval_date = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)
    
    # Metadata
    posted_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='posted_properties'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    # Inquiry counter
    inquiry_count = models.PositiveIntegerField(default=0, help_text="Number of inquiries")
    view_count = models.PositiveIntegerField(default=0, help_text="Number of views")
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Property Listing'
        verbose_name_plural = 'Property Listings'
    
    def __str__(self):
        return f"{self.property_title} - {self.get_listing_type_display()}"
    
    def approve(self, admin_user):
        """Approve the property listing"""
        self.status = 'approved'
        self.approved_by = admin_user
        self.approval_date = timezone.now()
        self.save()
    
    def reject(self, admin_user, reason=None):
        """Reject the property listing"""
        self.status = 'rejected'
        self.approved_by = admin_user
        self.rejection_reason = reason
        self.approval_date = timezone.now()
        self.save()
    
    def increment_inquiry_count(self):
        """Increment the inquiry count"""
        self.inquiry_count += 1
        self.save(update_fields=['inquiry_count'])
    
    def increment_view_count(self):
        """Increment the view count"""
        self.view_count += 1
        self.save(update_fields=['view_count'])


class PropertyImage(models.Model):
    """Model to store multiple images for a property listing"""
    
    property = models.ForeignKey(
        Property, 
        on_delete=models.CASCADE, 
        related_name='images'
    )
    image_url = models.URLField(max_length=500)
    is_thumbnail = models.BooleanField(
        default=False,
        help_text="Mark as main thumbnail image"
    )
    caption = models.CharField(max_length=255, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    order = models.PositiveIntegerField(default=0, help_text="Display order")
    
    class Meta:
        ordering = ['order', '-is_thumbnail', 'uploaded_at']
        verbose_name = 'Property Image'
        verbose_name_plural = 'Property Images'
    
    def __str__(self):
        thumbnail_text = " (Thumbnail)" if self.is_thumbnail else ""
        return f"Image for {self.property.property_title}{thumbnail_text}"
    
    def save(self, *args, **kwargs):
        # Ensure only one thumbnail per property
        if self.is_thumbnail:
            PropertyImage.objects.filter(
                property=self.property, 
                is_thumbnail=True
            ).exclude(pk=self.pk).update(is_thumbnail=False)
        super().save(*args, **kwargs)


class PropertyInquiry(models.Model):
    """Model to store property inquiries"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('contacted', 'Contacted'),
        ('interested', 'Interested'),
        ('not_interested', 'Not Interested'),
        ('deal_closed', 'Deal Closed'),
    ]
    
    property = models.ForeignKey(
        Property, 
        on_delete=models.CASCADE, 
        related_name='inquiries'
    )
    inquirer = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='property_inquiries'
    )
    
    # Basic Information
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20)
    
    # Inquiry Details
    message = models.TextField(help_text="Inquiry message from the interested party")
    budget = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        blank=True, 
        null=True,
        help_text="Budget of the inquirer"
    )
    move_in_date = models.DateField(blank=True, null=True, help_text="Preferred move-in date")
    
    # Inquiry Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Metadata
    inquired_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-inquired_at']
        verbose_name = 'Property Inquiry'
        verbose_name_plural = 'Property Inquiries'
        unique_together = ['property', 'inquirer']
    
    def __str__(self):
        return f"{self.full_name} - {self.property.property_title} ({self.status})"


# Available Amenities (for reference)
AVAILABLE_AMENITIES = [
    'Swimming Pool',
    'Home Office',
    'Pet-Friendly',
    'Balcony',
    'Parking Space',
    'Garden',
    'Walk-in Closet',
    'Air Conditioning',
    'Laundry Room',
    'Security System',
    'Basement',
    'Gym',
    'Fireplace',
    'Smart Home Features',
    'Roof Deck',
    'Elevator',
]
