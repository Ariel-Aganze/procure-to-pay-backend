from django.contrib import admin
from django.utils.html import format_html
from .models import DocumentTemplate, AIProcessingJob, ExtractedDocumentData, DocumentValidationResult


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'template_type', 'is_active', 'created_by', 'created_at']
    list_filter = ['template_type', 'is_active', 'created_at']
    search_fields = ['name', 'template_type']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(AIProcessingJob)
class AIProcessingJobAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'job_type', 'status', 'purchase_request',
        'created_by', 'processing_time', 'created_at'
    ]
    list_filter = ['job_type', 'status', 'created_at']
    search_fields = ['id', 'purchase_request__title', 'created_by__username']
    readonly_fields = [
        'id', 'started_at', 'completed_at', 'processing_time',
        'output_data', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'job_type', 'status', 'purchase_request', 'created_by')
        }),
        ('Input', {
            'fields': ('input_file', 'input_data'),
            'classes': ('collapse',)
        }),
        ('Output', {
            'fields': ('output_data', 'output_file'),
            'classes': ('collapse',)
        }),
        ('Processing Details', {
            'fields': ('started_at', 'completed_at', 'processing_time', 'retry_count', 'max_retries')
        }),
        ('Error Information', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'purchase_request', 'created_by'
        )


@admin.register(ExtractedDocumentData)
class ExtractedDocumentDataAdmin(admin.ModelAdmin):
    list_display = [
        'document_type', 'vendor_name', 'total_amount', 'currency',
        'confidence_score', 'extraction_quality', 'created_at'
    ]
    list_filter = ['document_type', 'extraction_quality', 'currency', 'created_at']
    search_fields = ['vendor_name', 'document_number', 'vendor_email']
    readonly_fields = ['created_at', 'processing_job']
    
    fieldsets = (
        ('Document Information', {
            'fields': ('processing_job', 'document_type', 'document_number', 'document_date')
        }),
        ('Vendor Information', {
            'fields': ('vendor_name', 'vendor_address', 'vendor_email', 'vendor_phone')
        }),
        ('Financial Information', {
            'fields': ('subtotal', 'tax_amount', 'total_amount', 'currency')
        }),
        ('Items and Terms', {
            'fields': ('line_items', 'terms_and_conditions', 'payment_terms', 'delivery_terms'),
            'classes': ('collapse',)
        }),
        ('Quality Metrics', {
            'fields': ('confidence_score', 'extraction_quality'),
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(DocumentValidationResult)
class DocumentValidationResultAdmin(admin.ModelAdmin):
    list_display = [
        'processing_job', 'validation_status', 'overall_score',
        'vendor_match', 'amount_match', 'items_match', 'created_at'
    ]
    list_filter = ['validation_status', 'vendor_match', 'amount_match', 'items_match', 'created_at']
    search_fields = ['processing_job__id', 'reference_po__title']
    readonly_fields = ['created_at', 'processing_job', 'reference_po']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('processing_job', 'reference_po', 'validation_status', 'overall_score')
        }),
        ('Match Results', {
            'fields': ('vendor_match', 'amount_match', 'items_match', 'date_valid')
        }),
        ('Detailed Results', {
            'fields': ('discrepancies', 'warnings', 'recommendations'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'processing_job', 'reference_po'
        )