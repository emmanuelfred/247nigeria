from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework import status
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth import authenticate
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import transaction, IntegrityError   # ✅ ADD THIS
from accounts.models import User,PasswordResetOTP,PasswordResetToken
from .serializers import SignupSerializer, IdentityVerificationSerializer,ResetPasswordSerializer,UpdateEmailSerializer,UpdatePasswordSerializer
from .utils import send_verification_email, send_otp_email
from .error_response import error_response
from accounts.models import User, IdentityVerification
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from datetime import timedelta
import random
from django.core.files.base import ContentFile

from s3_upload.utils import upload_file_to_s3,delete_file_from_s3  # import utility
# ✅ Add these imports for S3 uploads
from s3_upload.utils import upload_file_to_s3, delete_file_from_s3
from django.conf import settings

# ✅ Add these constants
BUCKET = settings.AWS_STORAGE_BUCKET_NAME
REGION = settings.AWS_S3_REGION_NAME

from django.core.files.base import ContentFile
@api_view(['POST'])
def verify_identity(request, user_id):
    try:
        user = User.objects.filter(id=user_id).first()
        if not user:
            return Response({"error": "User not found"}, status=404)

        uploaded = request.FILES.get("id_document")
        if not uploaded:
            return Response({"error": "id_document file is required"}, status=400)

        # Create a fresh copy of the file to avoid closed file errors
        file_bytes = uploaded.read()
        upload_copy = ContentFile(file_bytes)
        upload_copy.name = uploaded.name

        # Upload to S3
        file_url, file_key = upload_file_to_s3(
            upload_copy,
            folder="ids",
            content_type=uploaded.content_type
        )

        # Clear Django internal files to prevent closed file errors
        request._files = {}

        # Prepare serializer data
        data = request.data.copy()
        data["id_document"] = file_url

        serializer = IdentityVerificationSerializer(data=data)

        if not serializer.is_valid():
            return Response({"error": "Invalid data", "details": serializer.errors}, status=400)

        # ✅ Use update_or_create directly
        verification, created = IdentityVerification.objects.update_or_create(
            user=user,
            defaults=serializer.validated_data
        )

        message = "Identity submitted successfully" if created else "Identity updated successfully"
        return Response({"success": True, "message": message}, status=201)

    except Exception as e:
        return Response({"error": "Failed to verify identity", "details": str(e)}, status=500)
@api_view(['POST'])
def signup(request):
    """
    Create a new user.
    - Returns a clear error if the email already exists.
    - Returns JSON always (no HTML).
    - If email sending fails, account is created and a helpful message is returned.
    """
    try:
        data = request.data

        # quick email presence check
        email = data.get("email")
        if not email:
            return error_response("Email is required", code=status.HTTP_400_BAD_REQUEST)

        # if email already exists — return a friendly error
        if User.objects.filter(email__iexact=email).exists():
            # Use iexact so 'Test@Email.com' and 'test@email.com' conflict
            return error_response(
                message="An account with that email already exists. Try logging in or use a different email.",
                code=status.HTTP_400_BAD_REQUEST
            )

        # validate serializer
        serializer = SignupSerializer(data=data)
        if not serializer.is_valid():
            # Provide friendly messages; keep serializer.errors in details for debugging
            friendly = {}
            for field, msgs in serializer.errors.items():
                # Customize common fields
                if field == "email":
                    friendly[field] = "Enter a valid, unique email address."
                elif field == "password":
                    friendly[field] = "Password is invalid (must meet requirements)."
                elif field in ("first_name", "surname"):
                    friendly[field] = f"{field.replace('_',' ').capitalize()} is required."
                else:
                    friendly[field] = msgs
            return error_response(
                message="Please correct the highlighted fields.",
                code=status.HTTP_400_BAD_REQUEST,
                details={"fields": friendly, "raw": serializer.errors}
            )

        # Save user inside a transaction and guard against race condition (unique constraint)
        try:
            with transaction.atomic():
                user = serializer.save()
        except IntegrityError as e:
            # This catches rare race where two requests try to create same email concurrently
            return error_response(
                message="An account with that email already exists.",
                code=status.HTTP_400_BAD_REQUEST,
                details=str(e)
            )

        # attempt to send verification email, but don't fail the whole request if it errors
        try:
            send_verification_email(user)
        except Exception as e:
            # Log the exception server-side (omitted here) and return a helpful message client-side
            return Response(
                {
                    "success": True,
                    "message": "Account created successfully, but we couldn't send a verification email right now. Please try resending verification from your profile or contact support.",
                    "user_id": user.id,
                },
                status=status.HTTP_201_CREATED
            )

        # success
        return Response(
            {
                "success": True,
                "message": "Signup successful. A verification email has been sent to your address.",
                "user_id": user.id,
            },
            status=status.HTTP_201_CREATED
        )

    except Exception as exc:
        # Last-resort error handler — never return HTML
        return error_response(
            message="An unexpected error occurred during signup. Please try again later.",
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(exc)
        )
@api_view(['GET'])
def verify_email(request, uid, token):
    try:
        try:
            uid = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=uid)
            
        except Exception:
            return error_response("Invalid verification link", 400)

        if default_token_generator.check_token(user, token):
            user.email_verified = True
            user.save()
            return Response({"success": True, "message": "Email verified successfully"})

        return error_response("Invalid or expired verification token", 400)

    except Exception as e:
        return error_response("Email verification failed", 500, str(e))

@api_view(['POST'])
def resend_verification(request):
    email = request.data.get("email")
    if not email:
        return error_response("Email is required", 400)

    try:
        user = User.objects.get(email__iexact=email)
    except User.DoesNotExist:
        return error_response("No account found with this email", 404)

    if user.email_verified:
        return error_response("Email is already verified", 400)

    try:
        send_verification_email(user)
        return Response(
            {"success": True, "message": "A new verification email has been sent."},
            status=200
        )
    except Exception as e:
        return error_response("Unable to resend verification email", 500, str(e))




@api_view(['POST'])
def login_view(request):
    email = request.data.get("email")
    password = request.data.get("password")

    if not email or not password:
        return Response({"message": "Email and password are required"}, status=400)

    # Authenticate using email + password
    user = authenticate(request, email=email, password=password)

    if not user:
        return Response({"message": "Invalid credentials"}, status=400)

    # Generate JWT tokens
    refresh = RefreshToken.for_user(user)

    # Get identity verification info (if exists)
    identity = IdentityVerification.objects.filter(user=user).first()

    identity_data = None
    if identity:
        identity_data = {
            "id_document": identity.id_document,  # ✅ Removed .url - it's already a URL string
            "date_of_birth": identity.date_of_birth,
            "gender": identity.gender,
            "address": identity.address,
            "verified": identity.verified,
            "submitted_at": identity.submitted_at
        }

    # Build user response (excluding password)
    user_data = {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "surname": user.surname,
        "last_name": user.last_name,
        "phone_number": user.phone_number,
        "location": user.location,
        "cover_photo": user.cover_photo or None,  # ✅ Removed .url
        "profile_photo": user.profile_photo or None,
        "email_verified": user.email_verified,
        "identity": identity_data,
    }

    return Response({
        "user": user_data,
        "token": str(refresh.access_token),
        "refresh": str(refresh)
    }, status=200)


@api_view(["PUT"])
#@permission_classes([IsAuthenticated])
def update_profile(request):
    user = request.user  # logged-in user

    # Check if user exists (should always exist if authenticated, but safer)
    if not user or not isinstance(user, User):
        return Response(
            {"message": "User not found or not authenticated"},
            status=status.HTTP_404_NOT_FOUND
        )

    data = request.data

    # Update fields if provided
    user.first_name = data.get("first_name", user.first_name)
    user.surname = data.get("surname", user.surname)
    user.last_name = data.get("last_name", user.last_name)
    user.phone_number = data.get("phone_number", user.phone_number)
    user.location = data.get("location", user.location)

    user.save()

    # Include identity verification info if it exists
    identity_data = None
    if hasattr(user, "identityverification") and user.identityverification:
        identity = user.identityverification
        identity_data = {
            "id_document": identity.id_document,  # ✅ Removed .url
            "date_of_birth": identity.date_of_birth,
            "gender": identity.gender,
            "address": identity.address,
            "verified": identity.verified,
            "submitted_at": identity.submitted_at,
        }

    user_data = {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "surname": user.surname,
        "last_name": user.last_name,
        "phone_number": user.phone_number,
        "location": user.location,
        "cover_photo": user.cover_photo or None,  # ✅ Removed .url
        "profile_photo": user.profile_photo or None,
        "email_verified": user.email_verified,
        "identity": identity_data,
    }

    return Response(
        {"user": user_data, "message": "Profile updated successfully"},
        status=status.HTTP_200_OK
    )

# 1️⃣ Request OTP
@api_view(['POST'])
def request_password_reset(request):
    email = request.data.get("email")
    if not email:
        return Response({"message": "Email is required"}, status=400)

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({"message": "No account found with this email"}, status=404)

    otp = f"{random.randint(1000, 9999)}"
    PasswordResetOTP.objects.create(
        user=user,
        code=otp,
        expires_at=timezone.now() + timedelta(minutes=15)
    )

    # send email
    try:
        send_otp_email(user, otp)
       
    except Exception as e:
        return Response({"message": "Failed to send email", "error": str(e)}, status=500)

    return Response({"message": "OTP sent to your email",'email':email}, status=200)


# 2️⃣ Verify OTP (generates reset token)
@api_view(['POST'])
def verify_otp(request):
    email = request.data.get("email")
    otp = request.data.get("otp")

    if not email or not otp:
        return Response({"message": "Email and OTP are required"}, status=400)

    try:
        user = User.objects.get(email=email)

        # Clean expired OTPs
        PasswordResetOTP.objects.filter(user=user, expires_at__lt=timezone.now()).delete()

        # Validate OTP
        otp_obj = PasswordResetOTP.objects.filter(user=user, code=otp).last()

        if not otp_obj:
            return Response({"message": "Invalid OTP"}, status=400)

        # OTP is valid → generate reset token
        reset_token = PasswordResetToken.objects.create(
            user=user,
            token=f"{random.randint(10000000, 99999999)}",
            expires_at=timezone.now() + timedelta(minutes=15)
        )

        # Delete ALL OTPs for this user after success
        PasswordResetOTP.objects.filter(user=user).delete()

        return Response({
            "message": "OTP verified successfully",
            "reset_token": reset_token.token
        }, status=200)

    except User.DoesNotExist:
        return Response({"message": "No account found with this email"}, status=404)

# 3️⃣ Reset Password using reset_token
@api_view(['POST'])
def reset_password(request):
    serializer = ResetPasswordSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({"message": "Invalid data", "errors": serializer.errors}, status=400)

    reset_token = request.data.get("reset_token")
    if not reset_token:
        return Response({"message": "Reset token is required"}, status=400)

    # Clean expired tokens first
    PasswordResetToken.objects.filter(expires_at__lt=timezone.now()).delete()

    try:
        token_obj = PasswordResetToken.objects.get(token=reset_token)

        # Check expiration
        if token_obj.expires_at < timezone.now():
            token_obj.delete()
            return Response({"message": "Reset token expired"}, status=400)

        user = token_obj.user
        user.set_password(serializer.validated_data["password"])
        user.save()

        # Delete all reset tokens for this user to prevent reuse
        PasswordResetToken.objects.filter(user=user).delete()

        return Response({"message": "Password reset successfully"}, status=200)

    except PasswordResetToken.DoesNotExist:
        return Response({"message": "Invalid reset token"}, status=400)

@api_view(["POST"])
#@permission_classes([IsAuthenticated])
def update_password(request, user_id):
    """
    Update user password:
    - Requires current_password and new_password
    - Uses authenticated user for security
    """
    serializer = UpdatePasswordSerializer(data=request.data)

    if not serializer.is_valid():
        return error_response(
            message="Invalid data",
            code=status.HTTP_400_BAD_REQUEST,
            details=serializer.errors
        )

    current_password = serializer.validated_data["current_password"]
    new_password = serializer.validated_data["new_password"]

    # Only allow logged-in user to change THEIR OWN password
    if request.user.id != int(user_id):
        return error_response(
            message="You are not allowed to change another user's password",
            code=status.HTTP_403_FORBIDDEN
        )

    user = request.user

    # Check old password
    if not user.check_password(current_password):
        return error_response(
            message="Current password is incorrect",
            code=status.HTTP_400_BAD_REQUEST
        )

    # Set new password
    user.set_password(new_password)
    user.save()

    return Response(
        {"success": True, "message": "Password updated successfully"},
        status=status.HTTP_200_OK
    )



@api_view(["POST"])
#@permission_classes([IsAuthenticated])
def update_email(request, user_id):
    print(user_id)
    serializer = UpdateEmailSerializer(data=request.data)

    if not serializer.is_valid():
        return error_response(
            message="Invalid email",
            code=status.HTTP_400_BAD_REQUEST,
            details=serializer.errors
        )

    new_email = serializer.validated_data["email"]

    # Only allow user to edit their own account
    if request.user.id != int(user_id):
        return error_response(
            message="You are not allowed to update another user's email",
            code=status.HTTP_403_FORBIDDEN
        )

    # Check for duplicate email
    if User.objects.filter(email__iexact=new_email).exclude(id=request.user.id).exists():
        return error_response(
            message="Email already in use by another account",
            code=status.HTTP_400_BAD_REQUEST
        )

    user = request.user
    user.email = new_email
    user.email_verified = False  # force re-verification
    user.save()

    # OPTIONAL: send verification again
    try:
        send_verification_email(user)
    except:
        pass  # don't block user if email fails

    return Response(
        {"success": True, "message": "Email updated successfully"},
        status=status.HTTP_200_OK
    )
    
    

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_cover_photo(request, user_id):
    """
    Upload cover photo to S3
    - Validates file type and size
    - Deletes old cover photo from S3 (if not default)
    - Uploads new cover photo
    - Updates database
    """
    try:
        # Security check: only allow users to update their own cover photo
        if request.user.id != int(user_id):
            return Response(
                {"error": "You can only update your own cover photo"}, 
                status=403
            )

        user = request.user

        if 'cover_photo' not in request.FILES:
            return Response(
                {"error": "cover_photo file is required"}, 
                status=400
            )

        cover_file = request.FILES['cover_photo']

        # ✅ Validate file type
        allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp']
        if cover_file.content_type not in allowed_types:
            return Response(
                {"error": "Please select an image file (JPEG, PNG, GIF, or WebP)"}, 
                status=400
            )

        # ✅ Validate file size (max 5MB)
        max_size = 5 * 1024 * 1024  # 5MB in bytes
        if cover_file.size > max_size:
            return Response(
                {"error": "Image size should be less than 5MB"}, 
                status=400
            )

        # Delete old cover photo from S3 (only if it's not the default)
        if user.cover_photo:
            default_cover = 'https://247nigeria.s3.eu-north-1.amazonaws.com/cover-photo.jpg'
            
            # Only delete if it's not the default cover photo
            if user.cover_photo != default_cover:
                try:
                    # Extract the S3 key from the URL
                    # URL format: https://247nigeria.s3.eu-north-1.amazonaws.com/cover_photos/uuid.jpg
                    old_key = user.cover_photo.split(f'{BUCKET}.s3.{REGION}.amazonaws.com/')[-1]
                    delete_file_from_s3(old_key)
                except Exception as e:
                    print(f"Failed to delete old cover photo: {e}")
                    # Continue anyway - don't block upload if deletion fails

        # Upload new cover photo
        file_bytes = cover_file.read()
        upload_copy = ContentFile(file_bytes)
        upload_copy.name = cover_file.name

        cover_url, cover_key = upload_file_to_s3(
            upload_copy,
            folder="cover_photos",
            content_type=cover_file.content_type
        )

        # Update database
        user.cover_photo = cover_url
        user.save()

        # Clear files
        request._files = {}

        return Response({
            "success": True,
            "message": "Cover photo uploaded successfully",
            "cover_photo": cover_url
        }, status=200)

    except Exception as e:
        return Response(
            {"error": "Failed to upload cover photo", "details": str(e)}, 
            status=500
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_profile_photo(request, user_id):
    """
    Upload profile photo to S3
    - Validates file type and size
    - Deletes old profile photo from S3 (if exists)
    - Uploads new profile photo
    - Updates database
    """
    try:
        # Security check: only allow users to update their own profile photo
        if request.user.id != int(user_id):
            return Response(
                {"error": "You can only update your own profile photo"}, 
                status=403
            )

        user = request.user

        if 'profile_photo' not in request.FILES:
            return Response(
                {"error": "profile_photo file is required"}, 
                status=400
            )

        profile_file = request.FILES['profile_photo']

        # ✅ Validate file type
        allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp']
        if profile_file.content_type not in allowed_types:
            return Response(
                {"error": "Please select an image file (JPEG, PNG, GIF, or WebP)"}, 
                status=400
            )

        # ✅ Validate file size (max 5MB)
        max_size = 5 * 1024 * 1024  # 5MB in bytes
        if profile_file.size > max_size:
            return Response(
                {"error": "Image size should be less than 5MB"}, 
                status=400
            )

        # Delete old profile photo from S3 (if exists)
        if user.profile_photo:
            try:
                # Extract the S3 key from the URL
                # URL format: https://247nigeria.s3.eu-north-1.amazonaws.com/profile_photos/uuid.jpg
                old_key = user.profile_photo.split(f'{BUCKET}.s3.{REGION}.amazonaws.com/')[-1]
                delete_file_from_s3(old_key)
            except Exception as e:
                print(f"Failed to delete old profile photo: {e}")
                # Continue anyway - don't block upload if deletion fails

        # Upload new profile photo
        file_bytes = profile_file.read()
        upload_copy = ContentFile(file_bytes)
        upload_copy.name = profile_file.name

        profile_url, profile_key = upload_file_to_s3(
            upload_copy,
            folder="profile_photos",
            content_type=profile_file.content_type
        )

        # Update database
        user.profile_photo = profile_url
        user.save()

        # Clear files
        request._files = {}

        return Response({
            "success": True,
            "message": "Profile photo uploaded successfully",
            "profile_photo": profile_url
        }, status=200)

    except Exception as e:
        return Response(
            {"error": "Failed to upload profile photo", "details": str(e)}, 
            status=500
        )