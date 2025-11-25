from django.urls import path
from . import views

urlpatterns = [
    # Document processing
    path('status/<uuid:pk>/', views.DocumentProcessingStatusView.as_view(), name='document-processing-status'),
    path('upload-proforma/<uuid:pk>/', views.ProformaUploadView.as_view(), name='upload-proforma'),
    path('trigger/<uuid:pk>/', views.TriggerDocumentProcessingView.as_view(), name='trigger-processing'),
    
    # Processing jobs
    path('jobs/', views.AIProcessingJobListView.as_view(), name='processing-jobs'),
    path('jobs/<uuid:pk>/', views.AIProcessingJobDetailView.as_view(), name='processing-job-detail'),
    
    # Extracted data and validation results
    path('extracted-data/', views.ExtractedDataListView.as_view(), name='extracted-data'),
    path('validation-results/', views.ValidationResultListView.as_view(), name='validation-results'),
    
    # Service status and stats
    path('ollama-status/', views.ollama_status, name='ollama-status'),
    path('processing-stats/', views.document_processing_stats, name='processing-stats'),
]