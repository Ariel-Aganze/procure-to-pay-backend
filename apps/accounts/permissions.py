from rest_framework import permissions
from django.contrib.auth import get_user_model

User = get_user_model()


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions for any authenticated user
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions only to the owner of the object
        return obj.created_by == request.user


class IsStaffUser(permissions.BasePermission):
    """
    Permission class for staff users
    """

    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.is_staff_user()
        )


class IsApproverUser(permissions.BasePermission):
    """
    Permission class for approver users
    """

    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.can_approve_requests()
        )


class IsFinanceUser(permissions.BasePermission):
    """
    Permission class for finance users
    """

    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.can_access_finance()
        )


class IsPurchaseRequestOwner(permissions.BasePermission):
    """
    Permission to check if user owns the purchase request
    """

    def has_object_permission(self, request, view, obj):
        return obj.created_by == request.user


class CanApprovePurchaseRequest(permissions.BasePermission):
    """
    Permission to check if user can approve a specific purchase request
    More flexible version for debugging
    """

    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # Basic checks
        if not user.is_authenticated:
            return False
            
        if not user.can_approve_requests():
            return False
        
        # Request must be pending
        if obj.status != obj.Status.PENDING:
            return False
        
        # Admin can approve anything
        if user.role == user.Role.ADMIN:
            return True
        
        # Check if user is in pending approvers list
        pending_approvers = obj.get_pending_approvers()
        return user in pending_approvers


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Permission that allows read-only access to authenticated users,
    but write access only to admin users
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.role == User.Role.ADMIN
        )


class CanAccessPurchaseRequest(permissions.BasePermission):
    """
    Custom permission to control access to purchase requests
    """

    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # Owner can always access
        if obj.created_by == user:
            return True
        
        # Approvers can access requests they can approve
        if user.can_approve_requests():
            return True
        
        # Finance users can access approved requests
        if user.can_access_finance() and obj.status == obj.Status.APPROVED:
            return True
        
        # Admin can access all
        if user.role == User.Role.ADMIN:
            return True
        
        return False


class CanViewUserList(permissions.BasePermission):
    """
    Permission to view user lists - only approvers, finance, and admin
    """

    def has_permission(self, request, view):
        user = request.user
        return (
            user and 
            user.is_authenticated and 
            (user.can_approve_requests() or user.can_access_finance())
        )


class CanManageUsers(permissions.BasePermission):
    """
    Permission to manage users - only admin
    """

    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.role == User.Role.ADMIN
        )