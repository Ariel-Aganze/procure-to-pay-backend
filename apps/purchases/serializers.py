from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import PurchaseRequest, Approval, RequestItem, DocumentProcessingLog

User = get_user_model()


class RequestItemSerializer(serializers.ModelSerializer):
    """
    Serializer for request items
    """
    total_price = serializers.ReadOnlyField()
    
    class Meta:
        model = RequestItem
        fields = [
            'id', 'description', 'quantity', 'unit_price', 'total_price',
            'brand', 'model', 'specifications'
        ]


class ApprovalSerializer(serializers.ModelSerializer):
    """
    Serializer for approval records
    """
    approver_name = serializers.CharField(source='approver.full_name', read_only=True)
    approver_role = serializers.CharField(source='approver.get_role_display', read_only=True)
    
    class Meta:
        model = Approval
        fields = [
            'id', 'approver', 'approver_name', 'approver_role',
            'approval_level', 'approved', 'comments', 'approved_at'
        ]
        read_only_fields = ['id', 'approved_at', 'approver_name', 'approver_role']


class DocumentProcessingLogSerializer(serializers.ModelSerializer):
    """
    Serializer for document processing logs
    """
    process_type_display = serializers.CharField(source='get_process_type_display', read_only=True)
    
    class Meta:
        model = DocumentProcessingLog
        fields = [
            'id', 'process_type', 'process_type_display', 'status',
            'input_file', 'output_data', 'error_message',
            'processing_time', 'created_at'
        ]


class PurchaseRequestListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for purchase request lists
    """
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    approval_count = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    
    class Meta:
        model = PurchaseRequest
        fields = [
            'id', 'title', 'description', 'amount', 'status', 'status_display',
            'priority', 'priority_display', 'created_by', 'created_by_name',
            'vendor_name', 'expected_delivery_date', 'created_at', 'updated_at',
            'approval_count', 'can_edit'
        ]
    
    def get_approval_count(self, obj):
        return obj.approvals.filter(approved=True).count()
    
    def get_can_edit(self, obj):
        request = self.context.get('request')
        if not request or not request.user:
            return False
        
        # Only creator can edit, and only if status is pending
        return obj.created_by == request.user and obj.can_be_edited


class PurchaseRequestDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for purchase request
    """
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    items = RequestItemSerializer(many=True, read_only=True)
    approvals = ApprovalSerializer(many=True, read_only=True)
    processing_logs = DocumentProcessingLogSerializer(many=True, read_only=True)
    
    # Workflow information
    can_edit = serializers.SerializerMethodField()
    can_approve = serializers.SerializerMethodField()
    required_approval_levels = serializers.SerializerMethodField()
    pending_approvers = serializers.SerializerMethodField()
    
    class Meta:
        model = PurchaseRequest
        fields = [
            'id', 'title', 'description', 'amount', 'status', 'status_display',
            'priority', 'priority_display', 'created_by', 'created_by_name',
            'vendor_name', 'vendor_email', 'expected_delivery_date',
            'proforma', 'purchase_order', 'receipt',
            'proforma_processed', 'po_generated', 'receipt_validated',
            'created_at', 'updated_at', 'items', 'approvals', 'processing_logs',
            'can_edit', 'can_approve', 'required_approval_levels', 'pending_approvers'
        ]
    
    def get_can_edit(self, obj):
        request = self.context.get('request')
        if not request or not request.user:
            return False
        return obj.created_by == request.user and obj.can_be_edited
    
    def get_can_approve(self, obj):
        request = self.context.get('request')
        if not request or not request.user:
            return False
        
        user = request.user
        
        # Check if user can approve and request is pending
        if not user.can_approve_requests() or obj.status != PurchaseRequest.Status.PENDING:
            return False
        
        # Check if user is in pending approvers list
        pending_approvers = obj.get_pending_approvers()
        return user in pending_approvers
    
    def get_required_approval_levels(self, obj):
        return list(obj.get_required_approval_levels())
    
    def get_pending_approvers(self, obj):
        from apps.accounts.serializers import UserListSerializer
        pending_approvers = obj.get_pending_approvers()
        return UserListSerializer(pending_approvers, many=True).data


class PurchaseRequestCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating purchase requests
    """
    items = RequestItemSerializer(many=True, required=False)
    
    class Meta:
        model = PurchaseRequest
        fields = [
            'title', 'description', 'amount', 'priority',
            'vendor_name', 'vendor_email', 'expected_delivery_date',
            'proforma', 'items'
        ]
    
    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        request = self.context['request']
        validated_data['created_by'] = request.user
        
        purchase_request = PurchaseRequest.objects.create(**validated_data)
        
        # Create items
        for item_data in items_data:
            RequestItem.objects.create(purchase_request=purchase_request, **item_data)
        
        return purchase_request


class PurchaseRequestUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating purchase requests
    """
    items = RequestItemSerializer(many=True, required=False)
    
    class Meta:
        model = PurchaseRequest
        fields = [
            'title', 'description', 'amount', 'priority',
            'vendor_name', 'vendor_email', 'expected_delivery_date',
            'proforma', 'items'
        ]
    
    def validate(self, attrs):
        if not self.instance.can_be_edited:
            raise serializers.ValidationError(
                "This request cannot be edited anymore."
            )
        return attrs
    
    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        
        # Update the main instance
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update items if provided
        if items_data is not None:
            # Delete existing items and create new ones
            instance.items.all().delete()
            for item_data in items_data:
                RequestItem.objects.create(purchase_request=instance, **item_data)
        
        return instance


class ApprovalActionSerializer(serializers.Serializer):
    """
    Serializer for approval/rejection actions
    """
    approved = serializers.BooleanField()
    comments = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, attrs):
        request = self.context['request']
        purchase_request = self.context['purchase_request']
        user = request.user
        
        # Check if user can approve
        if not user.can_approve_requests():
            raise serializers.ValidationError("You don't have permission to approve requests")
        
        # Check if request is pending
        if purchase_request.status != PurchaseRequest.Status.PENDING:
            raise serializers.ValidationError("This request cannot be approved/rejected")
        
        # Check if user is in pending approvers
        if user not in purchase_request.get_pending_approvers():
            raise serializers.ValidationError("You cannot approve this request at this time")
        
        return attrs


class ReceiptUploadSerializer(serializers.Serializer):
    """
    Serializer for receipt upload
    """
    receipt = serializers.FileField()
    
    def validate_receipt(self, value):
        # Validate file type
        allowed_types = ['application/pdf', 'image/jpeg', 'image/png', 'image/jpg']
        if value.content_type not in allowed_types:
            raise serializers.ValidationError(
                "Only PDF and image files are allowed for receipts"
            )
        
        # Validate file size (10MB limit)
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("Receipt file too large ( > 10MB )")
        
        return value