"""
Email utility functions for sending job-related notifications
"""
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags


def send_job_posted_email(user, job):
    """
    Send confirmation email when a job is posted
    """
    subject = f'Job Posted Successfully: {job.job_title}'
    
    html_message = f"""
    <html>
        <body>
            <h2>Hi {user.first_name},</h2>
            <p>Your job posting has been submitted successfully and is pending review.</p>
            
            <h3>Job Details:</h3>
            <ul>
                <li><strong>Job Title:</strong> {job.job_title}</li>
                <li><strong>Company:</strong> {job.company_name}</li>
                <li><strong>Location:</strong> {job.city}, {job.state}</li>
                <li><strong>Status:</strong> Pending Review</li>
            </ul>
            
            <p>Your job will be reviewed within 24 hours. You will receive an email once it's approved or if any changes are needed.</p>
            
            <p>Thank you for using our platform!</p>
            
            <p>Best regards,<br>The Job Portal Team</p>
        </body>
    </html>
    """
    
    plain_message = strip_tags(html_message)
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending job posted email: {str(e)}")
        return False


def send_job_approved_email(user, job):
    """
    Send email when a job is approved
    """
    subject = f'Job Approved: {job.job_title}'
    
    html_message = f"""
    <html>
        <body>
            <h2>Great News, {user.first_name}!</h2>
            <p>Your job posting has been approved and is now live on our platform.</p>
            
            <h3>Job Details:</h3>
            <ul>
                <li><strong>Job Title:</strong> {job.job_title}</li>
                <li><strong>Company:</strong> {job.company_name}</li>
                <li><strong>Location:</strong> {job.city}, {job.state}</li>
                <li><strong>Status:</strong> Approved</li>
                <li><strong>Approved on:</strong> {job.approval_date.strftime('%B %d, %Y at %I:%M %p') if job.approval_date else 'N/A'}</li>
            </ul>
            
            <p>Your job is now visible to all job seekers. You will receive notifications when candidates apply.</p>
            
            <p>Thank you for using our platform!</p>
            
            <p>Best regards,<br>The Job Portal Team</p>
        </body>
    </html>
    """
    
    plain_message = strip_tags(html_message)
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending job approved email: {str(e)}")
        return False


def send_job_rejected_email(user, job):
    """
    Send email when a job is rejected
    """
    subject = f'Job Posting Update: {job.job_title}'
    
    html_message = f"""
    <html>
        <body>
            <h2>Hi {user.first_name},</h2>
            <p>We regret to inform you that your job posting has not been approved at this time.</p>
            
            <h3>Job Details:</h3>
            <ul>
                <li><strong>Job Title:</strong> {job.job_title}</li>
                <li><strong>Company:</strong> {job.company_name}</li>
                <li><strong>Status:</strong> Rejected</li>
            </ul>
            
            {f'<p><strong>Reason:</strong> {job.rejection_reason}</p>' if job.rejection_reason else ''}
            
            <p>You can edit and resubmit your job posting after addressing the issues mentioned above.</p>
            
            <p>If you have any questions, please contact our support team.</p>
            
            <p>Best regards,<br>The Job Portal Team</p>
        </body>
    </html>
    """
    
    plain_message = strip_tags(html_message)
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending job rejected email: {str(e)}")
        return False


def send_application_confirmation_to_applicant(applicant, job, application):
    """
    Send confirmation email to applicant when they apply for a job
    """
    subject = f'Application Submitted: {job.job_title} at {job.company_name}'
    
    html_message = f"""
    <html>
        <body>
            <h2>Hi {applicant.first_name},</h2>
            <p>Your application has been submitted successfully!</p>
            
            <h3>Application Details:</h3>
            <ul>
                <li><strong>Job Title:</strong> {job.job_title}</li>
                <li><strong>Company:</strong> {job.company_name}</li>
                <li><strong>Location:</strong> {job.city}, {job.state}</li>
                <li><strong>Applied on:</strong> {application.applied_at.strftime('%B %d, %Y at %I:%M %p')}</li>
                <li><strong>Expected Salary:</strong> ₦{application.expected_salary}</li>
            </ul>
            
            <p>Your application is now under review. The employer will contact you directly if they're interested.</p>
            
            <p>You can track your application status in your dashboard.</p>
            
            <p>Good luck!</p>
            
            <p>Best regards,<br>The Job Portal Team</p>
        </body>
    </html>
    """
    
    plain_message = strip_tags(html_message)
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[applicant.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending application confirmation to applicant: {str(e)}")
        return False


def send_application_notification_to_employer(employer, job, application, applicant):
    """
    Send notification email to employer when someone applies for their job
    """
    subject = f'New Application: {job.job_title}'
    
    html_message = f"""
    <html>
        <body>
            <h2>Hi {employer.first_name},</h2>
            <p>You have received a new application for your job posting!</p>
            
            <h3>Job Details:</h3>
            <ul>
                <li><strong>Job Title:</strong> {job.job_title}</li>
                <li><strong>Company:</strong> {job.company_name}</li>
                <li><strong>Total Applicants:</strong> {job.applicant_count}</li>
            </ul>
            
            <h3>Applicant Details:</h3>
            <ul>
                <li><strong>Name:</strong> {application.full_name}</li>
                <li><strong>Email:</strong> {application.email}</li>
                <li><strong>Phone:</strong> {application.phone_number}</li>
                <li><strong>Expected Salary:</strong> ₦{application.expected_salary}</li>
                {f'<li><strong>Portfolio:</strong> <a href="{application.portfolio_website}">{application.portfolio_website}</a></li>' if application.portfolio_website else ''}
            </ul>
            
            <p><strong>Cover Letter:</strong></p>
            <p>{application.cover_letter[:200]}...</p>
            
            <p>You can view the full application and CV in your dashboard.</p>
            
            <p>Best regards,<br>The Job Portal Team</p>
        </body>
    </html>
    """
    
    plain_message = strip_tags(html_message)
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[employer.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending application notification to employer: {str(e)}")
        return False