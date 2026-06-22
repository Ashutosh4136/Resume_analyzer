from django.contrib import admin

# Register your models here.
from django.contrib import admin
from core.models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display  = ['user', 'target_role', 'total_analyses']
    search_fields = ['user__username', 'target_role']
    readonly_fields = ['total_analyses']