from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction
from accounts.models import User, IdentityVerification, Property, PropertyImage, PropertyInquiry

from s3_upload.utils import upload_file_to_s3
from django.conf import settings
from datetime import datetime, timezone
from django.utils.timesince import timesince
import json
from .property_email_utils import (
    send_property_posted_email,
    send_property_approved_email,
    send_property_rejected_email,
    send_inquiry_confirmation_to_inquirer,
    send_inquiry_notification_to_owner,
    send_inquiry_status_update_email
)

# Constants
BUCKET = settings.AWS_STORAGE_BUCKET_NAME
REGION = settings.AWS_S3_REGION_NAME


def humanize_time(dt):
    """Convert datetime to '2 days ago' format."""
    if not dt:
        return None
    now = datetime.now(timezone.utc)
    return timesince(dt, now) + " ago"


def clean_label(val):
    """Convert 'per_month' → 'Per month', 'for_rent' → 'For Rent'."""
    if not val:
        return val
    return val.replace("_", " ").title()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_property_post(request):
    """
    Create a new property listing with multiple images
    Requires email verification and identity verification
    """
    user = request.user
   
    # 1. CHECK EMAIL VERIFICATION
    if not user.email_verified:
        return Response(
            {'error': 'Please verify your email before posting a property.'},
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
            {'error': 'Please submit your identity verification before posting a property.'},
            status=status.HTTP_403_FORBIDDEN
        )
      

    try:
        data = request.data
        files = request.FILES
        
        # Validate required fields
        required_fields = [
            'property_title', 'property_type', 'listing_type',
            'full_address', 'state', 'city', 'bedrooms', 'bathrooms',
            'size_sqm', 'parking_spots', 'property_description',
            'furnishing_status', 'price', 'price_period', 'contact_method'
        ]
        
        for field in required_fields:
            if field not in data or not data[field]:
                return Response(
                    {'error': f'{field.replace("_", " ")} is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Parse amenities from request
        amenities = []
        if 'amenities' in data:
            if isinstance(data['amenities'], str):
                amenities = json.loads(data['amenities'])
            elif isinstance(data['amenities'], list):
                amenities = data['amenities']
        
        # Use transaction to ensure all or nothing
        with transaction.atomic():
            # Create the property
            property_obj = Property.objects.create(
                # Basic Information
                property_title=data['property_title'],
                property_type=data['property_type'],
                listing_type=data['listing_type'],
                full_address=data['full_address'],
                state=data['state'],
                city=data['city'],
                
                # Property Details
                bedrooms=int(data['bedrooms']),
                bathrooms=int(data['bathrooms']),
                size_sqm=float(data['size_sqm']),
                parking_spots=int(data['parking_spots']),
                property_description=data['property_description'],
                furnishing_status=data['furnishing_status'],
                amenities=amenities,
                
                # Price
                price=float(data['price']),
                price_period=data['price_period'],
                
                # Contact
                contact_method=data['contact_method'],
                external_link=data.get('external_link', ''),
                
                # Metadata
                posted_by=request.user,
                status='pending'
            )
            
            # Handle multiple image uploads
            uploaded_images = []
            thumbnail_index = int(data.get('thumbnail_index', 0))
            
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
                    folder='property-images',
                    content_type=image_file.content_type
                )
                
                # Create PropertyImage record
                property_image = PropertyImage.objects.create(
                    property=property_obj,
                    image_url=image_url,
                    is_thumbnail=(index == thumbnail_index),
                    order=index,
                    caption=data.get(f'caption_{index}', '')
                )
                
                uploaded_images.append({
                    'id': property_image.id,
                    'url': image_url,
                    'is_thumbnail': property_image.is_thumbnail
                })
            
            # Send confirmation email
            send_property_posted_email(user, property_obj)
            
            # Prepare response
            response_data = {
                'message': 'Property posted successfully! It will be reviewed within 24 hours.',
                'property': {
                    'id': property_obj.id,
                    'property_title': property_obj.property_title,
                    'property_type': property_obj.property_type,
                    'listing_type': property_obj.listing_type,
                    'full_address': property_obj.full_address,
                    'state': property_obj.state,
                    'city': property_obj.city,
                    'bedrooms': property_obj.bedrooms,
                    'bathrooms': property_obj.bathrooms,
                    'size_sqm': str(property_obj.size_sqm),
                    'parking_spots': property_obj.parking_spots,
                    'property_description': property_obj.property_description,
                    'furnishing_status': property_obj.furnishing_status,
                    'amenities': property_obj.amenities,
                    'price': str(property_obj.price),
                    'price_period': property_obj.price_period,
                    'contact_method': property_obj.contact_method,
                    'external_link': property_obj.external_link,
                    'status': property_obj.status,
                    'inquiry_count': property_obj.inquiry_count,
                    'view_count': property_obj.view_count,
                    'created_at': property_obj.created_at,
                    'posted_by': {
                        'id': property_obj.posted_by.id,
                        'user_id': property_obj.posted_by.id,
                        'email': property_obj.posted_by.email,
                        'first_name': property_obj.posted_by.first_name,
                        'last_name': property_obj.posted_by.last_name,
                        'profile_photo': property_obj.posted_by.profile_photo,
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
def get_property_detail(request, property_id):
    """
    Get property details with all images and poster info
    """
    try:
        property_obj = Property.objects.select_related('posted_by').get(id=property_id)
        
        # Increment view count
        property_obj.increment_view_count()
        
        # Get all images for this property
        images = property_obj.images.all()
        
        response_data = {
            'id': property_obj.id,
            'property_title': property_obj.property_title,
            'property_type': clean_label(property_obj.property_type),
            'listing_type': clean_label(property_obj.listing_type),
            'full_address': property_obj.full_address,
            'state': property_obj.state,
            'city': property_obj.city,
            'bedrooms': property_obj.bedrooms,
            'bathrooms': property_obj.bathrooms,
            'size_sqm': str(property_obj.size_sqm),
            'parking_spots': property_obj.parking_spots,
            'property_description': property_obj.property_description,
            'furnishing_status': clean_label(property_obj.furnishing_status),
            'amenities': property_obj.amenities,
            'price': str(property_obj.price),
            'price_period': clean_label(property_obj.price_period),
            'contact_method': property_obj.contact_method,
            'external_link': property_obj.external_link,
            'status': property_obj.status,
            'inquiry_count': property_obj.inquiry_count,
            'view_count': property_obj.view_count,
            'created_at': property_obj.created_at,
            'updated_at': property_obj.updated_at,
            'posted_by': {
                'id': property_obj.posted_by.id,
                'user_id': property_obj.posted_by.id,
                'email': property_obj.posted_by.email,
                'first_name': property_obj.posted_by.first_name,
                'last_name': property_obj.posted_by.last_name,
                'phone_number': property_obj.posted_by.phone_number,
                'location': property_obj.posted_by.location,
                'profile_photo': property_obj.posted_by.profile_photo,
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
        
    except Property.DoesNotExist:
        return Response(
            {'error': 'Property not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
def list_properties(request):
    """
    List all approved properties with poster info and thumbnail
    """
    properties = Property.objects.filter(
        status='pending',#approved
        is_active=True
    ).select_related('posted_by').prefetch_related('images').order_by('-created_at')
    
    properties_data = []
    for prop in properties:
        # Get thumbnail image
        thumbnail = prop.images.filter(is_thumbnail=True).first()
        
        properties_data.append({
            'id': prop.id,
            'property_title': prop.property_title,
            'property_type': clean_label(prop.property_type),
            'listing_type': clean_label(prop.listing_type),
            'city': prop.city,
            'state': prop.state,
            'bedrooms': prop.bedrooms,
            'bathrooms': prop.bathrooms,
            'size_sqm': str(prop.size_sqm),
            'price': str(prop.price),
            'price_period': clean_label(prop.price_period),
            'inquiry_count': prop.inquiry_count,
            'view_count': prop.view_count,
            'created_at': humanize_time(prop.created_at),
            'thumbnail': thumbnail.image_url if thumbnail else None,
            'posted_by': {
                'id': prop.posted_by.id,
                'user_id': prop.posted_by.id,
                'first_name': prop.posted_by.first_name,
                'last_name': prop.posted_by.last_name,
                'profile_photo': prop.posted_by.profile_photo,
            }
        })
    
    return Response(properties_data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_properties(request):
    """
    Get all properties posted by the current user
    """
    properties = Property.objects.filter(
        posted_by=request.user
    ).prefetch_related('images').order_by('-created_at')
    
    properties_data = []
    for prop in properties:
        thumbnail = prop.images.filter(is_thumbnail=True).first()
        
        properties_data.append({
            'id': prop.id,
            'property_title': prop.property_title,
            'property_type': clean_label(prop.property_type),
            'listing_type': clean_label(prop.listing_type),
            'city': prop.city,
            'state': prop.state,
            'status': prop.status,
            'inquiry_count': prop.inquiry_count,
            'view_count': prop.view_count,
            'created_at': prop.created_at,
            'updated_at': prop.updated_at,
            'approval_date': prop.approval_date,
            'rejection_reason': prop.rejection_reason,
            'thumbnail': thumbnail.image_url if thumbnail else None,
            'price': str(prop.price),
            'price_period': clean_label(prop.price_period),
        })
    
    return Response(properties_data, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_property(request, property_id):
    """
    Delete a property listing
    Only the user who posted the property can delete it
    """
    try:
        try:
            property_obj = Property.objects.get(id=property_id)
        except Property.DoesNotExist:
            return Response(
                {"error": "Property not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Ensure the user is the creator
        if property_obj.posted_by != request.user:
            return Response(
                {"error": "You are not allowed to delete this property."},
                status=status.HTTP_403_FORBIDDEN
            )

        property_obj.delete()

        return Response(
            {"message": "Property deleted successfully."},
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_property_inquiry(request, property_id):
    """
    Create an inquiry for a property
    Requires email verification and identity verification
    """
    user = request.user

    # 1. CHECK EMAIL VERIFICATION
    if not user.email_verified:
        return Response(
            {'error': 'Please verify your email before making an inquiry.'},
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
            {'error': 'Please submit your identity verification before making an inquiry.'},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        data = request.data

        # Check property exists and is approved
        try:
            property_obj = Property.objects.get(id=property_id, status='approved')
        except Property.DoesNotExist:
            return Response(
                {'error': 'Property not found or not available.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Extract fields
        full_name = data.get('full_name')
        email = data.get('email')
        phone_number = data.get('phone_number')
        message = data.get('message')
        budget = data.get('budget', None)
        move_in_date = data.get('move_in_date', None)

        # Check required fields
        if not all([full_name, email, phone_number, message]):
            return Response(
                {'error': 'All required fields must be filled.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Prevent duplicate inquiries
        if PropertyInquiry.objects.filter(property=property_obj, inquirer=request.user).exists():
            return Response(
                {'error': 'You have already made an inquiry for this property.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create inquiry
        inquiry = PropertyInquiry.objects.create(
            property=property_obj,
            inquirer=request.user,
            full_name=full_name,
            email=email,
            phone_number=phone_number,
            message=message,
            budget=budget if budget else None,
            move_in_date=move_in_date if move_in_date else None,
            status='pending'
        )

        # Increment inquiry count
        property_obj.increment_inquiry_count()

        # Send confirmation emails
        # To inquirer
        send_inquiry_confirmation_to_inquirer(request.user, property_obj, inquiry)
        # To property owner
        send_inquiry_notification_to_owner(property_obj.posted_by, property_obj, inquiry, request.user)

        return Response(
            {
                'message': 'Inquiry submitted successfully!',
                'inquiry': {
                    'id': inquiry.id,
                    'inquirer_id': request.user.id,
                    'full_name': inquiry.full_name,
                    'email': inquiry.email,
                    'message': inquiry.message,
                    'status': inquiry.status,
                    'created_at': inquiry.inquired_at,
                    'property': {
                        'id': property_obj.id,
                        'title': property_obj.property_title,
                        'inquiry_count': property_obj.inquiry_count,
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
def get_my_inquiries(request):
    """
    Get all inquiries made by the current user
    """
    inquiries = PropertyInquiry.objects.filter(
        inquirer=request.user
    ).select_related('property').prefetch_related('property__images')

    data = []
    for inq in inquiries:
        thumbnail = inq.property.images.filter(is_thumbnail=True).first()
        
        data.append({
            "inquiry_id": inq.id,
            "inquirer_id": request.user.id,
            "status": inq.status,
            "message": inq.message,
            "budget": str(inq.budget) if inq.budget else None,
            "move_in_date": inq.move_in_date,
            "inquired_at": humanize_time(inq.inquired_at),
            
            "property": {
                "id": inq.property.id,
                "title": inq.property.property_title,
                "property_type": clean_label(inq.property.property_type),
                "city": inq.property.city,
                "state": inq.property.state,
                "price": str(inq.property.price),
                "price_period": clean_label(inq.property.price_period),
                "inquiry_count": inq.property.inquiry_count,
                "thumbnail": thumbnail.image_url if thumbnail else None
            }
        })

    return Response({"inquiries": data}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_property_inquiries(request, property_id):
    """
    Get all inquiries for a specific property
    Only property owner can view
    """
    try:
        try:
            property_obj = Property.objects.get(id=property_id)
        except Property.DoesNotExist:
            return Response(
                {"error": "Property not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Ensure only property owner can view
        if property_obj.posted_by != request.user:
            return Response(
                {"error": "You are not allowed to view inquiries for this property."},
                status=status.HTTP_403_FORBIDDEN
            )

        inquiries = PropertyInquiry.objects.filter(
            property=property_obj
        ).select_related("inquirer")

        data = []
        for inq in inquiries:
            data.append({
                "inquiry_id": inq.id,
                "inquirer_id": inq.inquirer.id,
                "full_name": inq.full_name,
                "email": inq.email,
                "phone_number": inq.phone_number,
                "message": inq.message,
                "budget": str(inq.budget) if inq.budget else None,
                "move_in_date": inq.move_in_date,
                "status": inq.status,
                "inquired_at": inq.inquired_at,
                
                "inquirer": {
                    "id": inq.inquirer.id,
                    "user_id": inq.inquirer.id,
                    "email": inq.inquirer.email,
                    "phone_number": inq.inquirer.phone_number,
                    "profile_photo": inq.inquirer.profile_photo,
                }
            })

        return Response(
            {
                "property_title": property_obj.property_title,
                "inquiry_count": property_obj.inquiry_count,
                "inquiries": data
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ADMIN ENDPOINTS

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def approve_property(request, property_id):
    """
    Approve a property listing (Admin only)
    """
    if not request.user.is_staff:
        return Response(
            {"error": "Only administrators can approve properties."},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        property_obj = Property.objects.get(id=property_id)
        
        if property_obj.status == 'approved':
            return Response(
                {"error": "Property is already approved."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        property_obj.approve(request.user)
        
        # Send approval email to property owner
        send_property_approved_email(property_obj.posted_by, property_obj)
        
        return Response(
            {
                "message": "Property approved successfully.",
                "property": {
                    "id": property_obj.id,
                    "title": property_obj.property_title,
                    "status": property_obj.status,
                    "approved_by": request.user.email,
                    "approval_date": property_obj.approval_date
                }
            },
            status=status.HTTP_200_OK
        )
        
    except Property.DoesNotExist:
        return Response(
            {"error": "Property not found."},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reject_property(request, property_id):
    """
    Reject a property listing (Admin only)
    """
    if not request.user.is_staff:
        return Response(
            {"error": "Only administrators can reject properties."},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        property_obj = Property.objects.get(id=property_id)
        
        if property_obj.status == 'rejected':
            return Response(
                {"error": "Property is already rejected."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reason = request.data.get('reason', '')
        property_obj.reject(request.user, reason)
        
        # Send rejection email to property owner
        send_property_rejected_email(property_obj.posted_by, property_obj)
        
        return Response(
            {
                "message": "Property rejected successfully.",
                "property": {
                    "id": property_obj.id,
                    "title": property_obj.property_title,
                    "status": property_obj.status,
                    "rejected_by": request.user.email,
                    "rejection_reason": property_obj.rejection_reason
                }
            },
            status=status.HTTP_200_OK
        )
        
    except Property.DoesNotExist:
        return Response(
            {"error": "Property not found."},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_inquiry_status(request, inquiry_id):
    """
    Update inquiry status (contacted, interested, not_interested, deal_closed)
    Only property owner can update
    """
    try:
        inquiry = PropertyInquiry.objects.select_related('property', 'inquirer').get(id=inquiry_id)
        
        # Check if user is property owner
        if inquiry.property.posted_by != request.user:
            return Response(
                {"error": "You are not allowed to update this inquiry."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        old_status = inquiry.status
        new_status = request.data.get('status')
        
        if new_status not in ['pending', 'contacted', 'interested', 'not_interested', 'deal_closed']:
            return Response(
                {"error": "Invalid status."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        inquiry.status = new_status
        inquiry.save()
        
        # Send email notification to inquirer about status change
        if old_status != new_status:
            send_inquiry_status_update_email(
                inquiry.inquirer,
                inquiry.property,
                inquiry,
                old_status,
                new_status
            )
        
        return Response(
            {
                "message": "Inquiry status updated successfully.",
                "inquiry": {
                    "id": inquiry.id,
                    "old_status": old_status,
                    "new_status": new_status,
                    "updated_at": inquiry.updated_at
                }
            },
            status=status.HTTP_200_OK
        )
        
    except PropertyInquiry.DoesNotExist:
        return Response(
            {"error": "Inquiry not found."},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )