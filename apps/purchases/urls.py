from django.urls import path
from . import views

urlpatterns = [
    # Purchase Requests CRUD
    path('requests/', views.PurchaseRequestListCreateView.as_view(), name='purchase-request-list-create'),
    path('requests/<uuid:pk>/', views.PurchaseRequestDetailView.as_view(), name='purchase-request-detail'),
    
    # Approval workflow
    path('requests/<uuid:pk>/approve/', views.ApprovalActionView.as_view(), name='purchase-request-approve'),
    path('requests/<uuid:pk>/receipt/', views.ReceiptUploadView.as_view(), name='purchase-request-receipt'),
    path('requests/<uuid:pk>/workflow/', views.request_workflow_info, name='purchase-request-workflow'),
    
    # User-specific views
    path('my-requests/', views.MyRequestsView.as_view(), name='my-requests'),
    path('pending-approvals/', views.PendingApprovalsView.as_view(), name='pending-approvals'),
    path('finance-requests/', views.FinanceRequestsView.as_view(), name='finance-requests'),
    
    # Dashboard
    path('dashboard-stats/', views.purchase_dashboard_stats, name='purchase-dashboard-stats'),
]