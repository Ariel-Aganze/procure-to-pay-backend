from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import get_user_model
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .serializers import (
    UserRegistrationSerializer,
    UserLoginSerializer,
    UserProfileSerializer,
    UserListSerializer,
    ChangePasswordSerializer
)
from .permissions import CanViewUserList, CanManageUsers

User = get_user_model()


class UserRegistrationView(generics.CreateAPIView):
    """
    Register a new user
    """
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]
    
    @swagger_auto_schema(
        operation_description="Register a new user",
        responses={
            201: openapi.Response("User created successfully", UserProfileSerializer),
            400: "Bad Request"
        }
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            
            # Generate tokens
            refresh = RefreshToken.for_user(user)
            
            # Return user data with tokens
            user_serializer = UserProfileSerializer(user)
            return Response({
                'message': 'User registered successfully',
                'user': user_serializer.data,
                'tokens': {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh)
                }
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserLoginView(APIView):
    """
    Login user and return JWT tokens
    """
    permission_classes = [permissions.AllowAny]
    
    @swagger_auto_schema(
        operation_description="Login user",
        request_body=UserLoginSerializer,
        responses={
            200: openapi.Response("Login successful", UserProfileSerializer),
            401: "Invalid credentials"
        }
    )
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            
            # Generate tokens
            refresh = RefreshToken.for_user(user)
            
            # Return user data with tokens
            user_serializer = UserProfileSerializer(user)
            return Response({
                'message': 'Login successful',
                'user': user_serializer.data,
                'tokens': {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh)
                }
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_401_UNAUTHORIZED)


class UserLogoutView(APIView):
    """
    Logout user by blacklisting refresh token
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Logout user",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'refresh': openapi.Schema(type=openapi.TYPE_STRING, description='Refresh token')
            },
            required=['refresh']
        ),
        responses={
            200: "Logout successful",
            400: "Bad Request"
        }
    )
    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            
            return Response({
                'message': 'Logout successful'
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'error': 'Invalid token'
            }, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    Get and update user profile
    """
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return self.request.user
    
    @swagger_auto_schema(
        operation_description="Get user profile",
        responses={200: UserProfileSerializer}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @swagger_auto_schema(
        operation_description="Update user profile",
        responses={200: UserProfileSerializer}
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)


class ChangePasswordView(APIView):
    """
    Change user password
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Change user password",
        request_body=ChangePasswordSerializer,
        responses={
            200: "Password changed successfully",
            400: "Bad Request"
        }
    )
    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            user = request.user
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            
            return Response({
                'message': 'Password changed successfully'
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserListView(generics.ListAPIView):
    """
    List all users (for approvers, finance, and admin)
    """
    queryset = User.objects.filter(is_active=True).order_by('username')
    serializer_class = UserListSerializer
    permission_classes = [CanViewUserList]
    
    @swagger_auto_schema(
        operation_description="List all active users",
        responses={200: UserListSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by role if specified
        role = self.request.query_params.get('role')
        if role:
            queryset = queryset.filter(role=role)
        
        # Filter by department if specified
        department = self.request.query_params.get('department')
        if department:
            queryset = queryset.filter(department__icontains=department)
        
        return queryset


class UserDetailView(generics.RetrieveUpdateAPIView):
    """
    Get and update user details (admin only for updates)
    """
    queryset = User.objects.all()
    serializer_class = UserProfileSerializer
    
    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [CanViewUserList()]
        else:
            return [CanManageUsers()]
    
    @swagger_auto_schema(
        operation_description="Get user details",
        responses={200: UserProfileSerializer}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @swagger_auto_schema(
        operation_description="Update user (admin only)",
        responses={200: UserProfileSerializer}
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_dashboard_stats(request):
    """
    Get dashboard statistics for the current user
    """
    user = request.user
    
    stats = {
        'user_role': user.get_role_display(),
        'can_approve': user.can_approve_requests(),
        'can_access_finance': user.can_access_finance(),
    }
    
    # Add role-specific stats
    if user.is_staff_user():
        from apps.purchases.models import PurchaseRequest
        stats['my_requests'] = {
            'total': user.purchase_requests.count(),
            'pending': user.purchase_requests.filter(status=PurchaseRequest.Status.PENDING).count(),
            'approved': user.purchase_requests.filter(status=PurchaseRequest.Status.APPROVED).count(),
            'rejected': user.purchase_requests.filter(status=PurchaseRequest.Status.REJECTED).count(),
        }
    
    elif user.can_approve_requests():
        from apps.purchases.models import PurchaseRequest
        # Get requests pending this user's approval level
        pending_requests = []
        for request in PurchaseRequest.objects.filter(status=PurchaseRequest.Status.PENDING):
            if user in request.get_pending_approvers():
                pending_requests.append(request)
        
        stats['approval_stats'] = {
            'pending_my_approval': len(pending_requests),
            'total_approved_by_me': user.approved_requests.filter(
                approval__approved=True
            ).count()
        }
    
    elif user.can_access_finance():
        from apps.purchases.models import PurchaseRequest
        approved_requests = PurchaseRequest.objects.filter(status=PurchaseRequest.Status.APPROVED)
        stats['finance_stats'] = {
            'approved_requests': approved_requests.count(),
            'total_value': sum(req.amount for req in approved_requests),
            'pending_po_generation': approved_requests.filter(po_generated=False).count(),
        }
    
    return Response(stats)