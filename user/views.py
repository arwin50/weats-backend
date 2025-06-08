from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from rest_framework import status
from .serializers import UserSerializer, RegisterSerializer, LoginSerializer
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
from dotenv import load_dotenv
import os
import random
import string
from django.core.mail import send_mail
from django.conf import settings
from django.core.cache import cache

load_dotenv()

User = get_user_model()


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def user_view(request):
    serializer = UserSerializer(request.user)
    return Response(serializer.data)

@api_view(["POST"])
def register_view(request):
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response({"message": "User registered successfully"}, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(["POST"])
def login_view(request):
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data 
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        # Serialize user data
        user_serializer = UserSerializer(user)

        return Response(
            {
                "access": access_token, 
                "refresh": str(refresh),
                "user": user_serializer.data
            }, 
            status=status.HTTP_200_OK
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(["POST"])
def logout_view(request):
    try:
        # Get refresh token from request data instead of cookies
        refresh_token = request.data.get("refresh")
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()  # Blacklist the refresh token

        # If user is authenticated, blacklist their tokens
        if hasattr(request, 'user') and request.user.is_authenticated:
            OutstandingToken.objects.filter(user=request.user).delete()

    except Exception as e:
        return Response({"error": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST)

    return Response({"message": "Successfully logged out"}, status=status.HTTP_200_OK)

@csrf_exempt
@api_view(["POST"])
def refresh_jwt(request):
    refresh_token = request.data.get("refresh")
    
    if not refresh_token:
        return Response(
            {"error": "Refresh token is required."},
            status=status.HTTP_400_BAD_REQUEST
        )
        
    try:
        refresh = RefreshToken(refresh_token)
        new_access_token = str(refresh.access_token)
        return Response({"access": new_access_token})
    except TokenError as e:
        return Response(
            {"error": "Invalid or expired refresh token."},
            status=status.HTTP_401_UNAUTHORIZED
        )

@api_view(["POST"])
def google_login_view(request):
    id_token_from_client = request.data.get('id_token')
    if not id_token_from_client:
        return Response({'error': 'ID token is required'}, status=status.HTTP_400_BAD_REQUEST)
 
    try:
        print("token", id_token_from_client)
        print("client",os.getenv('GOOGLE_CLIENT_ID'))
        id_info = google_id_token.verify_oauth2_token(
            id_token_from_client,
            google_requests.Request(),
            os.getenv('GOOGLE_CLIENT_ID') 
        )
        
        print('asdsadasd')
        email = id_info.get('email')
        first_name = id_info.get('given_name', '')
        last_name = id_info.get('family_name', '')
        username = email.split('@')[0]  # basic username

        if not email:
            print('here')
            return Response({'error': 'Google account did not return an email'}, status=status.HTTP_400_BAD_REQUEST)

        # Try to get existing user, or create if not exists
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'username': username,
                # Optionally: set is_active=True if you want immediate login
                'is_active': True,
            }
        )

        # You could update names if user was just created
        if created:
            user.first_name = first_name
            user.last_name = last_name
            user.save()

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        user_serializer = UserSerializer(user)
        
        print("access_token", access_token)

        return Response({
            "access": access_token,
            "refresh": str(refresh),
            "user": user_serializer.data
        }, status=status.HTTP_200_OK)

    except ValueError:
        return Response({'error': 'Invalid ID token'}, status=status.HTTP_400_BAD_REQUEST)
    

@api_view(["POST"])
def forgot_password(request):
    email = request.data.get('email')
    if not email:
        return Response(
            {"message": "Email is required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        # For security reasons, don't reveal if the email exists or not
        return Response(
            {"message": "If an account exists with this email, you will receive a verification code"},
            status=status.HTTP_200_OK
        )

    # Only proceed if user exists
    # Generate a 6-digit verification code
    verification_code = ''.join(random.choices(string.digits, k=6))
    
    # Store the code in cache with 10 minutes expiration
    cache_key = f'password_reset_{email}'
    cache.set(cache_key, verification_code, 600)  # 600 seconds = 10 minutes

    # Create a nice HTML email template
    html_message = f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2c3e50;">Password Reset Verification Code</h2>
                <p>Hello {user.username},</p>
                <p>We received a request to reset your password. Use the following verification code to proceed:</p>
                <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; text-align: center; margin: 20px 0;">
                    <h1 style="color: #2c3e50; margin: 0; font-size: 32px;">{verification_code}</h1>
                </div>
                <p>This code will expire in 10 minutes.</p>
                <p>If you didn't request this code, please ignore this email.</p>
                <hr style="border: 1px solid #eee; margin: 20px 0;">
                <p style="color: #666; font-size: 12px;">This is an automated message, please do not reply to this email.</p>
            </div>
        </body>
    </html>
    """

    # Send the verification code via email
    try:
        send_mail(
            'Password Reset Verification Code',
            f'Your verification code is: {verification_code}\n\nThis code will expire in 10 minutes.',
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
            html_message=html_message
        )
    except Exception as e:
        print(f"Email sending error: {str(e)}")  # For debugging
        return Response(
            {"message": "Failed to send verification code"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    return Response(
        {"message": "If an account exists with this email, you will receive a verification code"},
        status=status.HTTP_200_OK
    )

@api_view(["POST"])
def verify_code(request):
    email = request.data.get('email')
    code = request.data.get('code')

    if not email or not code:
        return Response(
            {"message": "Email and verification code are required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Get the stored code from cache
    cache_key = f'password_reset_{email}'
    stored_code = cache.get(cache_key)

    if not stored_code or stored_code != code:
        return Response(
            {"message": "Invalid or expired verification code"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Code is valid, generate a temporary token for password reset
    try:
        user = User.objects.get(email=email)
        reset_token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        cache.set(f'reset_token_{email}', reset_token, 600)  # 10 minutes expiration
        return Response(
            {"message": "Code verified successfully"},
            status=status.HTTP_200_OK
        )
    except User.DoesNotExist:
        return Response(
            {"message": "Invalid email"},
            status=status.HTTP_400_BAD_REQUEST
        )

@api_view(["POST"])
def reset_password(request):
    email = request.data.get('email')
    code = request.data.get('code')
    new_password = request.data.get('new_password')

    if not all([email, code, new_password]):
        return Response(
            {"message": "Email, verification code, and new password are required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Verify the code again
    cache_key = f'password_reset_{email}'
    stored_code = cache.get(cache_key)

    if not stored_code or stored_code != code:
        return Response(
            {"message": "Invalid or expired verification code"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        user = User.objects.get(email=email)
        user.set_password(new_password)
        user.save()

        # Clear the verification code and reset token from cache
        cache.delete(cache_key)
        cache.delete(f'reset_token_{email}')

        return Response(
            {"message": "Password has been reset successfully"},
            status=status.HTTP_200_OK
        )
    except User.DoesNotExist:
        return Response(
            {"message": "Invalid email"},
            status=status.HTTP_400_BAD_REQUEST
        )
