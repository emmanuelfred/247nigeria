"""
Email utility functions for sending property-related notifications
"""
from django.core.mail import send_mail
from django.conf import settings
from django.utils.html import strip_tags


def send_property_posted_email(user, property_obj):
    """
    Send confirmation email when a property is posted
    """
    subject = f'Property Posted Successfully: {property_obj.property_title}'
    
    html_message = f"""
    <html>
        <body>
            <h2>Hi {user.first_name},</h2>
            <p>Your property listing has been submitted successfully and is pending review.</p>
            
            <h3>Property Details:</h3>
            <ul>
                <li><strong>Property Title:</strong> {property_obj.property_title}</li>
                <li><strong>Property Type:</strong> {property_obj.get_property_type_display()}</li>
                <li><strong>Listing Type:</strong> {property_obj.get_listing_type_display()}</li>
                <li><strong>Location:</strong> {property_obj.city}, {property_obj.state}</li>
                <li><strong>Price:</strong> ₦{property_obj.price:,.2f}</li>
                <li><strong>Status:</strong> Pending Review</li>
            </ul>
            
            <p>Your property will be reviewed within 24 hours. You will receive an email once it's approved or if any changes are needed.</p>
            
            <p>Thank you for using our platform!</p>
            
            <p>Best regards,<br>The Property Portal Team</p>
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
        print(f"Error sending property posted email: {str(e)}")
        return False


def send_property_approved_email(user, property_obj):
    """
    Send email when a property is approved
    """
    subject = f'Property Approved: {property_obj.property_title}'
    
    html_message = f"""
    <html>
        <body>
            <h2>Great News, {user.first_name}!</h2>
            <p>Your property listing has been approved and is now live on our platform.</p>
            
            <h3>Property Details:</h3>
            <ul>
                <li><strong>Property Title:</strong> {property_obj.property_title}</li>
                <li><strong>Property Type:</strong> {property_obj.get_property_type_display()}</li>
                <li><strong>Listing Type:</strong> {property_obj.get_listing_type_display()}</li>
                <li><strong>Location:</strong> {property_obj.city}, {property_obj.state}</li>
                <li><strong>Price:</strong> ₦{property_obj.price:,.2f}</li>
                <li><strong>Status:</strong> Approved</li>
                <li><strong>Approved on:</strong> {property_obj.approval_date.strftime('%B %d, %Y at %I:%M %p') if property_obj.approval_date else 'N/A'}</li>
            </ul>
            
            <p>Your property is now visible to all interested parties. You will receive notifications when people inquire.</p>
            
            <p>Thank you for using our platform!</p>
            
            <p>Best regards,<br>The Property Portal Team</p>
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
        print(f"Error sending property approved email: {str(e)}")
        return False


def send_property_rejected_email(user, property_obj):
    """
    Send email when a property is rejected
    """
    subject = f'Property Listing Update: {property_obj.property_title}'
    
    html_message = f"""
    <html>
        <body>
            <h2>Hi {user.first_name},</h2>
            <p>We regret to inform you that your property listing has not been approved at this time.</p>
            
            <h3>Property Details:</h3>
            <ul>
                <li><strong>Property Title:</strong> {property_obj.property_title}</li>
                <li><strong>Property Type:</strong> {property_obj.get_property_type_display()}</li>
                <li><strong>Listing Type:</strong> {property_obj.get_listing_type_display()}</li>
                <li><strong>Status:</strong> Rejected</li>
            </ul>
            
            {f'<p><strong>Reason:</strong> {property_obj.rejection_reason}</p>' if property_obj.rejection_reason else ''}
            
            <p>You can edit and resubmit your property listing after addressing the issues mentioned above.</p>
            
            <p>If you have any questions, please contact our support team.</p>
            
            <p>Best regards,<br>The Property Portal Team</p>
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
        print(f"Error sending property rejected email: {str(e)}")
        return False


def send_inquiry_confirmation_to_inquirer(inquirer, property_obj, inquiry):
    """
    Send confirmation email to inquirer when they submit an inquiry
    """
    subject = f'Inquiry Submitted: {property_obj.property_title}'
    
    html_message = f"""
    <html>
        <body>
            <h2>Hi {inquirer.first_name},</h2>
            <p>Your inquiry has been submitted successfully!</p>
            
            <h3>Property Details:</h3>
            <ul>
                <li><strong>Property Title:</strong> {property_obj.property_title}</li>
                <li><strong>Property Type:</strong> {property_obj.get_property_type_display()}</li>
                <li><strong>Listing Type:</strong> {property_obj.get_listing_type_display()}</li>
                <li><strong>Location:</strong> {property_obj.city}, {property_obj.state}</li>
                <li><strong>Price:</strong> ₦{property_obj.price:,.2f} {property_obj.get_price_period_display()}</li>
                <li><strong>Inquired on:</strong> {inquiry.inquired_at.strftime('%B %d, %Y at %I:%M %p')}</li>
            </ul>
            
            <h3>Your Inquiry:</h3>
            <p><strong>Message:</strong> {inquiry.message[:200]}...</p>
            {f'<p><strong>Your Budget:</strong> ₦{inquiry.budget:,.2f}</p>' if inquiry.budget else ''}
            {f'<p><strong>Preferred Move-in Date:</strong> {inquiry.move_in_date.strftime("%B %d, %Y")}</p>' if inquiry.move_in_date else ''}
            
            <p>Your inquiry is now under review. The property owner will contact you directly if they're interested.</p>
            
            <p>You can track your inquiry status in your dashboard.</p>
            
            <p>Good luck!</p>
            
            <p>Best regards,<br>The Property Portal Team</p>
        </body>
    </html>
    """
    
    plain_message = strip_tags(html_message)
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[inquirer.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending inquiry confirmation to inquirer: {str(e)}")
        return False


def send_inquiry_notification_to_owner(owner, property_obj, inquiry, inquirer):
    """
    Send notification email to property owner when someone inquires about their property
    """
    subject = f'New Inquiry: {property_obj.property_title}'
    
    html_message = f"""
    <html>
        <body>
            <h2>Hi {owner.first_name},</h2>
            <p>You have received a new inquiry for your property listing!</p>
            
            <h3>Property Details:</h3>
            <ul>
                <li><strong>Property Title:</strong> {property_obj.property_title}</li>
                <li><strong>Property Type:</strong> {property_obj.get_property_type_display()}</li>
                <li><strong>Listing Type:</strong> {property_obj.get_listing_type_display()}</li>
                <li><strong>Total Inquiries:</strong> {property_obj.inquiry_count}</li>
                <li><strong>Total Views:</strong> {property_obj.view_count}</li>
            </ul>
            
            <h3>Inquirer Details:</h3>
            <ul>
                <li><strong>Name:</strong> {inquiry.full_name}</li>
                <li><strong>Email:</strong> {inquiry.email}</li>
                <li><strong>Phone:</strong> {inquiry.phone_number}</li>
                {f'<li><strong>Budget:</strong> ₦{inquiry.budget:,.2f}</li>' if inquiry.budget else ''}
                {f'<li><strong>Preferred Move-in Date:</strong> {inquiry.move_in_date.strftime("%B %d, %Y")}</li>' if inquiry.move_in_date else ''}
            </ul>
            
            <p><strong>Inquiry Message:</strong></p>
            <p>{inquiry.message}</p>
            
            <p>You can view the full inquiry and contact the inquirer through your dashboard.</p>
            
            <p>Best regards,<br>The Property Portal Team</p>
        </body>
    </html>
    """
    
    plain_message = strip_tags(html_message)
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[owner.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending inquiry notification to owner: {str(e)}")
        return False


def send_inquiry_status_update_email(inquirer, property_obj, inquiry, old_status, new_status):
    """
    Send email when inquiry status is updated by property owner
    """
    status_messages = {
        'contacted': 'The property owner has contacted you!',
        'interested': 'Great news! The property owner is interested in your inquiry.',
        'not_interested': 'Unfortunately, the property owner is not interested at this time.',
        'deal_closed': 'Congratulations! The deal has been closed.',
    }
    
    subject = f'Inquiry Status Update: {property_obj.property_title}'
    
    html_message = f"""
    <html>
        <body>
            <h2>Hi {inquirer.first_name},</h2>
            <p>{status_messages.get(new_status, 'Your inquiry status has been updated.')}</p>
            
            <h3>Property Details:</h3>
            <ul>
                <li><strong>Property Title:</strong> {property_obj.property_title}</li>
                <li><strong>Property Type:</strong> {property_obj.get_property_type_display()}</li>
                <li><strong>Location:</strong> {property_obj.city}, {property_obj.state}</li>
                <li><strong>Price:</strong> ₦{property_obj.price:,.2f}</li>
            </ul>
            
            <h3>Inquiry Status:</h3>
            <ul>
                <li><strong>Previous Status:</strong> {old_status.title()}</li>
                <li><strong>New Status:</strong> {new_status.title()}</li>
            </ul>
            
            {'''
            <p>The property owner may reach out to you soon. Please check your email and phone regularly.</p>
            ''' if new_status in ['contacted', 'interested'] else ''}
            
            {'''
            <p>Don't worry! There are many other great properties available. Keep searching!</p>
            ''' if new_status == 'not_interested' else ''}
            
            {'''
            <p>Congratulations on your new property! We hope you enjoy your new place.</p>
            ''' if new_status == 'deal_closed' else ''}
            
            <p>You can view your inquiry details in your dashboard.</p>
            
            <p>Best regards,<br>The Property Portal Team</p>
        </body>
    </html>
    """
    
    plain_message = strip_tags(html_message)
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[inquirer.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending inquiry status update email: {str(e)}")
        return False