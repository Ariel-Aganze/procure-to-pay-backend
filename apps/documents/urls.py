from django.urls import path, re_path
from . import views

urlpatterns = [
    # Comet AI Status
    path('comet-status/', views.CometStatusView.as_view(), name='comet-status'),
    
    # Document Upload - Handle both numeric and 'null' request IDs
    re_path(r'^upload-proforma/(?P<request_id>\w+)/$', views.UploadProformaView.as_view(), name='upload-proforma'),
    
    # Document Processing - Handle both numeric and 'null' request IDs  
    re_path(r'^comet-process/(?P<request_id>\w+)/$', views.ProcessDocumentView.as_view(), name='comet-process'),
    re_path(r'^comet-status/(?P<request_id>\w+)/(?P<job_id>[\w\-]+)/$', views.ProcessingStatusView.as_view(), name='comet-processing-status'),
    
    # Receipt upload
    re_path(r'^upload-receipt/(?P<request_id>\w+)/$', views.UploadReceiptView.as_view(), name='upload-receipt'),
    
    # Stats
    path('processing-stats/', views.ProcessingStatsView.as_view(), name='processing-stats'),
    
    # Legacy compatibility - Handle both numeric and 'null' request IDs
    re_path(r'^trigger/(?P<request_id>\w+)/$', views.ProcessDocumentView.as_view(), name='trigger-processing'),
    re_path(r'^status/(?P<request_id>\w+)/(?P<job_id>[\w\-]+)/$', views.ProcessingStatusView.as_view(), name='processing-status'),
]