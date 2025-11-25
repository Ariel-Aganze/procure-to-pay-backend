from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Admin configuration for custom User model
    """
    
    # Fields to display in the user list
    list_display = ('username', 'email', 'role', 'department', 'employee_id', 'is_active', 'date_joined')
    list_filter = ('role', 'is_active', 'is_staff', 'department', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'employee_id')
    ordering = ('-date_joined',)
    
    # Fieldsets for the user detail/edit page
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Role & Department', {
            'fields': ('role', 'department', 'employee_id', 'phone_number'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    # Fields for creating a new user
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Role & Department', {
            'fields': ('role', 'department', 'employee_id', 'phone_number'),
        }),
    )
    
    # Read-only fields
    readonly_fields = ('created_at', 'updated_at', 'date_joined', 'last_login')
    
    # Actions
    actions = ['make_staff', 'make_approver_level_1', 'make_approver_level_2', 'make_finance']
    
    def make_staff(self, request, queryset):
        queryset.update(role=User.Role.STAFF)
        self.message_user(request, f"{queryset.count()} users marked as Staff.")
    make_staff.short_description = "Mark selected users as Staff"
    
    def make_approver_level_1(self, request, queryset):
        queryset.update(role=User.Role.APPROVER_LEVEL_1)
        self.message_user(request, f"{queryset.count()} users marked as Approver Level 1.")
    make_approver_level_1.short_description = "Mark selected users as Approver Level 1"
    
    def make_approver_level_2(self, request, queryset):
        queryset.update(role=User.Role.APPROVER_LEVEL_2)
        self.message_user(request, f"{queryset.count()} users marked as Approver Level 2.")
    make_approver_level_2.short_description = "Mark selected users as Approver Level 2"
    
    def make_finance(self, request, queryset):
        queryset.update(role=User.Role.FINANCE)
        self.message_user(request, f"{queryset.count()} users marked as Finance.")
    make_finance.short_description = "Mark selected users as Finance"