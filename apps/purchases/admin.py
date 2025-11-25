from django.contrib import admin
from django.utils.html import format_html
from .models import PurchaseRequest, Approval, RequestItem, DocumentProcessingLog


class RequestItemInline(admin.TabularInline):
    model = RequestItem
    extra = 0
    readonly_fields = ('total_price',)


class ApprovalInline(admin.TabularInline):
    model = Approval
    extra = 0
    readonly_fields = ('approved_at',)


@admin.register(PurchaseRequest)
class PurchaseRequestAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'created_by', 'amount', 'status', 'priority',
        'approval_count', 'created_at'
    ]
    list_filter = ['status', 'priority', 'created_at', 'updated_at']
    search_fields = ['title', 'description', 'vendor_name', 'created_by__username']
    readonly_fields = [
        'id', 'created_at', 'updated_at', 'proforma_processed',
        'po_generated', 'receipt_validated'
    ]
    inlines = [RequestItemInline, ApprovalInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'title', 'description', 'amount', 'priority')
        }),
        ('Status & Workflow', {
            'fields': ('status', 'created_by')
        }),
        ('Vendor Information', {
            'fields': ('vendor_name', 'vendor_email', 'expected_delivery_date'),
            'classes': ('collapse',)
        }),
        ('Documents', {
            'fields': ('proforma', 'purchase_order', 'receipt'),
            'classes': ('collapse',)
        }),
        ('Processing Status', {
            'fields': ('proforma_processed', 'po_generated', 'receipt_validated'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def approval_count(self, obj):
        count = obj.approvals.filter(approved=True).count()
        required = len(obj.get_required_approval_levels())
        return f"{count}/{required}"
    approval_count.short_description = "Approvals"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('created_by')


@admin.register(Approval)
class ApprovalAdmin(admin.ModelAdmin):
    list_display = [
        'purchase_request', 'approver', 'approval_level',
        'approved', 'approved_at'
    ]
    list_filter = ['approved', 'approval_level', 'approved_at']
    search_fields = [
        'purchase_request__title', 'approver__username',
        'approver__first_name', 'approver__last_name'
    ]
    readonly_fields = ['approved_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'purchase_request', 'approver'
        )


@admin.register(RequestItem)
class RequestItemAdmin(admin.ModelAdmin):
    list_display = [
        'purchase_request', 'description', 'quantity',
        'unit_price', 'total_price'
    ]
    search_fields = ['description', 'purchase_request__title']
    readonly_fields = ['total_price']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('purchase_request')


@admin.register(DocumentProcessingLog)
class DocumentProcessingLogAdmin(admin.ModelAdmin):
    list_display = [
        'purchase_request', 'process_type', 'status',
        'processing_time', 'created_at'
    ]
    list_filter = ['process_type', 'status', 'created_at']
    search_fields = ['purchase_request__title']
    readonly_fields = ['created_at', 'processing_time', 'output_data']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('purchase_request', 'process_type', 'status')
        }),
        ('Processing Details', {
            'fields': ('input_file', 'processing_time', 'created_at')
        }),
        ('Results', {
            'fields': ('output_data', 'error_message'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('purchase_request')