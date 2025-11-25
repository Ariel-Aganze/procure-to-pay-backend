from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.db import models

from .models import PurchaseRequest, Approval, RequestItem, DocumentProcessingLog
from .serializers import (
    PurchaseRequestListSerializer,
    PurchaseRequestDetailSerializer,
    PurchaseRequestCreateSerializer,
    PurchaseRequestUpdateSerializer,
    ApprovalActionSerializer,
    ReceiptUploadSerializer,
    RequestItemSerializer
)
from apps.accounts.permissions import (
    IsOwnerOrReadOnly,
    IsApproverUser,
    IsFinanceUser,
    CanApprovePurchaseRequest,
    CanAccessPurchaseRequest
)

User = get_user_model()


class PurchaseRequestListCreateView(generics.ListCreateAPIView):
    """
    List purchase requests or create a new one
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return PurchaseRequestCreateSerializer
        return PurchaseRequestListSerializer
    
    def get_queryset(self):
        user = self.request.user
        queryset = PurchaseRequest.objects.all()
        
        # Filter based on user role
        if user.is_staff_user():
            # Staff can only see their own requests
            queryset = queryset.filter(created_by=user)
        elif user.can_approve_requests():
            # Approvers can see all requests
            pass
        elif user.can_access_finance():
            # Finance can see approved requests
            queryset = queryset.filter(status=PurchaseRequest.Status.APPROVED)
        else:
            # Default: only own requests
            queryset = queryset.filter(created_by=user)
        
        # Apply filters
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        priority_filter = self.request.query_params.get('priority')
        if priority_filter:
            queryset = queryset.filter(priority=priority_filter)
        
        # Filter by amount range
        min_amount = self.request.query_params.get('min_amount')
        if min_amount:
            queryset = queryset.filter(amount__gte=min_amount)
        
        max_amount = self.request.query_params.get('max_amount')
        if max_amount:
            queryset = queryset.filter(amount__lte=max_amount)
        
        # Search in title and description
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                models.Q(title__icontains=search) | 
                models.Q(description__icontains=search)
            )
        
        return queryset.order_by('-created_at')
    
    @swagger_auto_schema(
        operation_description="List purchase requests with optional filtering",
        manual_parameters=[
            openapi.Parameter('status', openapi.IN_QUERY, description="Filter by status", type=openapi.TYPE_STRING),
            openapi.Parameter('priority', openapi.IN_QUERY, description="Filter by priority", type=openapi.TYPE_STRING),
            openapi.Parameter('min_amount', openapi.IN_QUERY, description="Minimum amount", type=openapi.TYPE_NUMBER),
            openapi.Parameter('max_amount', openapi.IN_QUERY, description="Maximum amount", type=openapi.TYPE_NUMBER),
            openapi.Parameter('search', openapi.IN_QUERY, description="Search in title/description", type=openapi.TYPE_STRING),
        ],
        responses={200: PurchaseRequestListSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @swagger_auto_schema(
        operation_description="Create a new purchase request",
        responses={
            201: PurchaseRequestDetailSerializer,
            400: "Bad Request"
        }
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            purchase_request = serializer.save()
            
            # Return detailed view of created request
            detail_serializer = PurchaseRequestDetailSerializer(
                purchase_request,
                context={'request': request}
            )
            return Response(detail_serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PurchaseRequestDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a purchase request
    """
    queryset = PurchaseRequest.objects.all()
    serializer_class = PurchaseRequestDetailSerializer
    permission_classes = [permissions.IsAuthenticated, CanAccessPurchaseRequest]
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return PurchaseRequestUpdateSerializer
        return PurchaseRequestDetailSerializer
    
    @swagger_auto_schema(
        operation_description="Get purchase request details",
        responses={200: PurchaseRequestDetailSerializer}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @swagger_auto_schema(
        operation_description="Update purchase request (owner only, pending status)",
        responses={200: PurchaseRequestDetailSerializer}
    )
    def patch(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Check if user can edit
        if instance.created_by != request.user:
            return Response(
                {'error': 'You can only edit your own requests'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if not instance.can_be_edited:
            return Response(
                {'error': 'This request cannot be edited anymore'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        response = super().patch(request, *args, **kwargs)
        
        # Return detailed view after update
        if response.status_code == 200:
            detail_serializer = PurchaseRequestDetailSerializer(
                instance,
                context={'request': request}
            )
            return Response(detail_serializer.data)
        
        return response
    
    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Check if user can delete
        if instance.created_by != request.user:
            return Response(
                {'error': 'You can only delete your own requests'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if not instance.can_be_edited:
            return Response(
                {'error': 'This request cannot be deleted anymore'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return super().delete(request, *args, **kwargs)


class ApprovalActionView(APIView):
    """
    Approve or reject a purchase request
    """
    permission_classes = [permissions.IsAuthenticated, IsApproverUser]
    
    @swagger_auto_schema(
        operation_description="Approve or reject a purchase request",
        request_body=ApprovalActionSerializer,
        responses={
            200: "Action completed successfully",
            400: "Bad Request",
            403: "Forbidden"
        }
    )
    def post(self, request, pk):
        purchase_request = get_object_or_404(PurchaseRequest, pk=pk)
        
        # Check permission for this specific request
        if not CanApprovePurchaseRequest().has_object_permission(request, self, purchase_request):
            return Response(
                {'error': 'You cannot approve/reject this request'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = ApprovalActionSerializer(
            data=request.data,
            context={'request': request, 'purchase_request': purchase_request}
        )
        
        if serializer.is_valid():
            approved = serializer.validated_data['approved']
            comments = serializer.validated_data.get('comments', '')
            
            with transaction.atomic():
                # Determine approval level
                user_approval_level = request.user.get_approval_level()
                if user_approval_level == 999:  # Admin can approve at any level
                    # Find the next required level
                    required_levels = purchase_request.get_required_approval_levels()
                    approved_levels = set(
                        purchase_request.approvals.filter(approved=True).values_list('approval_level', flat=True)
                    )
                    pending_levels = required_levels - approved_levels
                    user_approval_level = min(pending_levels) if pending_levels else 1
                
                # Create approval record
                approval, created = Approval.objects.get_or_create(
                    purchase_request=purchase_request,
                    approval_level=user_approval_level,
                    defaults={
                        'approver': request.user,
                        'approved': approved,
                        'comments': comments,
                        'approved_at': timezone.now()
                    }
                )
                
                if not created:
                    # Update existing approval
                    approval.approver = request.user
                    approval.approved = approved
                    approval.comments = comments
                    approval.approved_at = timezone.now()
                    approval.save()
                
                # Update purchase request status
                if not approved:
                    # Any rejection rejects the entire request
                    purchase_request.status = PurchaseRequest.Status.REJECTED
                    purchase_request.save()
                    
                    return Response({
                        'message': 'Request rejected successfully',
                        'status': 'rejected'
                    })
                else:
                    # Check if all required approvals are complete
                    if purchase_request.is_fully_approved:
                        purchase_request.status = PurchaseRequest.Status.APPROVED
                        purchase_request.save()
                        
                        # Trigger PO generation (we'll implement this in documents app)
                        # trigger_po_generation.delay(purchase_request.id)
                        
                        return Response({
                            'message': 'Request fully approved - PO generation initiated',
                            'status': 'approved'
                        })
                    else:
                        return Response({
                            'message': 'Approval recorded - waiting for additional approvals',
                            'status': 'pending_approval'
                        })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ReceiptUploadView(APIView):
    """
    Upload receipt for an approved purchase request
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Upload receipt for purchase request",
        request_body=ReceiptUploadSerializer,
        responses={
            200: "Receipt uploaded successfully",
            400: "Bad Request",
            403: "Forbidden"
        }
    )
    def post(self, request, pk):
        purchase_request = get_object_or_404(PurchaseRequest, pk=pk)
        
        # Check if user can upload receipt (owner or finance)
        if not (purchase_request.created_by == request.user or request.user.can_access_finance()):
            return Response(
                {'error': 'You cannot upload receipts for this request'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if request is approved
        if purchase_request.status != PurchaseRequest.Status.APPROVED:
            return Response(
                {'error': 'Receipts can only be uploaded for approved requests'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = ReceiptUploadSerializer(data=request.data)
        
        if serializer.is_valid():
            purchase_request.receipt = serializer.validated_data['receipt']
            purchase_request.save()
            
            # Trigger receipt validation (we'll implement this in documents app)
            # trigger_receipt_validation.delay(purchase_request.id)
            
            return Response({
                'message': 'Receipt uploaded successfully - validation initiated',
                'receipt_url': request.build_absolute_uri(purchase_request.receipt.url)
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MyRequestsView(generics.ListAPIView):
    """
    Get current user's purchase requests
    """
    serializer_class = PurchaseRequestListSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return self.request.user.purchase_requests.all().order_by('-created_at')
    
    @swagger_auto_schema(
        operation_description="Get current user's purchase requests",
        responses={200: PurchaseRequestListSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class PendingApprovalsView(generics.ListAPIView):
    """
    Get requests pending current user's approval
    """
    serializer_class = PurchaseRequestListSerializer
    permission_classes = [permissions.IsAuthenticated, IsApproverUser]
    
    def get_queryset(self):
        user = self.request.user
        pending_requests = []
        
        for request in PurchaseRequest.objects.filter(status=PurchaseRequest.Status.PENDING):
            if user in request.get_pending_approvers():
                pending_requests.append(request.id)
        
        return PurchaseRequest.objects.filter(id__in=pending_requests).order_by('-created_at')
    
    @swagger_auto_schema(
        operation_description="Get requests pending current user's approval",
        responses={200: PurchaseRequestListSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class FinanceRequestsView(generics.ListAPIView):
    """
    Get approved requests for finance team
    """
    serializer_class = PurchaseRequestListSerializer
    permission_classes = [permissions.IsAuthenticated, IsFinanceUser]
    
    def get_queryset(self):
        return PurchaseRequest.objects.filter(
            status=PurchaseRequest.Status.APPROVED
        ).order_by('-updated_at')
    
    @swagger_auto_schema(
        operation_description="Get approved requests for finance team",
        responses={200: PurchaseRequestListSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def purchase_dashboard_stats(request):
    """
    Get purchase-related dashboard statistics
    """
    user = request.user
    
    # Base stats
    stats = {
        'total_requests': PurchaseRequest.objects.count(),
        'pending_requests': PurchaseRequest.objects.filter(status=PurchaseRequest.Status.PENDING).count(),
        'approved_requests': PurchaseRequest.objects.filter(status=PurchaseRequest.Status.APPROVED).count(),
        'rejected_requests': PurchaseRequest.objects.filter(status=PurchaseRequest.Status.REJECTED).count(),
    }
    
    # User-specific stats
    if user.is_staff_user():
        my_requests = user.purchase_requests.all()
        stats['my_stats'] = {
            'total': my_requests.count(),
            'pending': my_requests.filter(status=PurchaseRequest.Status.PENDING).count(),
            'approved': my_requests.filter(status=PurchaseRequest.Status.APPROVED).count(),
            'rejected': my_requests.filter(status=PurchaseRequest.Status.REJECTED).count(),
            'total_value': sum(req.amount for req in my_requests.filter(status=PurchaseRequest.Status.APPROVED)),
        }
    
    elif user.can_approve_requests():
        # Get pending approvals for this user
        pending_for_user = []
        for req in PurchaseRequest.objects.filter(status=PurchaseRequest.Status.PENDING):
            if user in req.get_pending_approvers():
                pending_for_user.append(req)
        
        stats['approval_stats'] = {
            'pending_my_approval': len(pending_for_user),
            'total_pending_value': sum(req.amount for req in pending_for_user),
            'my_approvals_count': Approval.objects.filter(approver=user, approved=True).count(),
        }
    
    elif user.can_access_finance():
        approved_requests = PurchaseRequest.objects.filter(status=PurchaseRequest.Status.APPROVED)
        stats['finance_stats'] = {
            'approved_count': approved_requests.count(),
            'approved_value': sum(req.amount for req in approved_requests),
            'pending_po': approved_requests.filter(po_generated=False).count(),
            'pending_receipts': approved_requests.filter(receipt='').count(),
        }
    
    return Response(stats)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def request_workflow_info(request, pk):
    """
    Get detailed workflow information for a specific request
    """
    purchase_request = get_object_or_404(PurchaseRequest, pk=pk)
    
    # Check access permission
    if not CanAccessPurchaseRequest().has_object_permission(request, None, purchase_request):
        return Response(
            {'error': 'You cannot access this request'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    workflow_info = {
        'required_levels': list(purchase_request.get_required_approval_levels()),
        'current_approvals': [],
        'pending_approvers': [],
        'can_approve': False,
        'next_action': None
    }
    
    # Get current approvals
    for approval in purchase_request.approvals.all():
        workflow_info['current_approvals'].append({
            'level': approval.approval_level,
            'approver': approval.approver.full_name,
            'approved': approval.approved,
            'comments': approval.comments,
            'approved_at': approval.approved_at,
        })
    
    # Get pending approvers
    pending_approvers = purchase_request.get_pending_approvers()
    for approver in pending_approvers:
        workflow_info['pending_approvers'].append({
            'id': approver.id,
            'name': approver.full_name,
            'role': approver.get_role_display(),
        })
    
    # Check if current user can approve
    workflow_info['can_approve'] = request.user in pending_approvers
    
    # Determine next action
    if purchase_request.status == PurchaseRequest.Status.PENDING:
        if workflow_info['pending_approvers']:
            workflow_info['next_action'] = f"Waiting for approval from {workflow_info['pending_approvers'][0]['role']}"
        else:
            workflow_info['next_action'] = "All approvals complete"
    elif purchase_request.status == PurchaseRequest.Status.APPROVED:
        if not purchase_request.po_generated:
            workflow_info['next_action'] = "Generate Purchase Order"
        elif not purchase_request.receipt:
            workflow_info['next_action'] = "Upload Receipt"
        else:
            workflow_info['next_action'] = "Complete"
    else:
        workflow_info['next_action'] = "Rejected"
    
    return Response(workflow_info)