from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom User model with role-based access control
    """
    
    class Role(models.TextChoices):
        STAFF = 'staff', 'Staff'
        APPROVER_LEVEL_1 = 'approver_level_1', 'Approver Level 1'
        APPROVER_LEVEL_2 = 'approver_level_2', 'Approver Level 2'
        FINANCE = 'finance', 'Finance'
        ADMIN = 'admin', 'Admin'
    
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STAFF,
        help_text="User role determines access permissions"
    )
    
    phone_number = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        help_text="Contact phone number"
    )
    
    department = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Department or division"
    )
    
    employee_id = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        unique=True,
        help_text="Employee identification number"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
    
    def can_approve_requests(self):
        """Check if user can approve purchase requests"""
        return self.role in [
            self.Role.APPROVER_LEVEL_1,
            self.Role.APPROVER_LEVEL_2,
            self.Role.ADMIN
        ]
    
    def can_access_finance(self):
        """Check if user can access finance features"""
        return self.role in [self.Role.FINANCE, self.Role.ADMIN]
    
    def is_staff_user(self):
        """Check if user is staff level"""
        return self.role == self.Role.STAFF
    
    def get_approval_level(self):
        """Get the approval level for this user"""
        if self.role == self.Role.APPROVER_LEVEL_1:
            return 1
        elif self.role == self.Role.APPROVER_LEVEL_2:
            return 2
        elif self.role == self.Role.ADMIN:
            return 999  # Admin can approve at any level
        return 0