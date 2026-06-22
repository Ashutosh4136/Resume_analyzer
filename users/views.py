from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction

from core.models import UserProfile
from .forms import CustomRegisterForm, CustomLoginForm


# -----------------------------------------------------------------------
# Register
# -----------------------------------------------------------------------
def register_view(request):
    if request.user.is_authenticated:
        return redirect('core:upload')

    if request.method == 'POST':
        form = CustomRegisterForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save()
                # Create the linked UserProfile immediately
                UserProfile.objects.create(user=user)
            login(request, user)
            messages.success(
                request,
                f'🎉 Welcome, {user.username}! Your account has been created.'
            )
            return redirect('core:upload')
        else:
            messages.error(request, 'Please fix the errors below.')
    else:
        form = CustomRegisterForm()

    return render(request, 'users/register.html', {'form': form})


# -----------------------------------------------------------------------
# Login
# -----------------------------------------------------------------------
def login_view(request):
    if request.user.is_authenticated:
        return redirect('core:upload')

    if request.method == 'POST':
        form = CustomLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            # Honour ?next= redirect (e.g. after @login_required bounce)
            next_url = request.GET.get('next', 'core:upload')
            messages.success(request, f'Welcome back, {user.username}!')
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid username or password. Please try again.')
    else:
        form = CustomLoginForm(request)

    return render(request, 'users/login.html', {'form': form})


# -----------------------------------------------------------------------
# Logout
# -----------------------------------------------------------------------
def logout_view(request):
    username = request.user.username
    logout(request)
    messages.info(request, f'You have been logged out, {username}. See you soon!')
    return redirect('users:login')


# -----------------------------------------------------------------------
# Profile  (bonus — shows stats from UserProfile)
# -----------------------------------------------------------------------
@login_required
def profile_view(request):
    profile = request.user.profile   # UserProfile via OneToOne

    if request.method == 'POST':
        target_role = request.POST.get('target_role', '').strip()
        profile.target_role = target_role
        profile.save(update_fields=['target_role'])
        messages.success(request, 'Profile updated successfully.')
        return redirect('users:profile')

    recent_sessions = request.user.sessions.all()[:5]
    context = {
        'profile': profile,
        'recent_sessions': recent_sessions,
    }
    return render(request, 'users/profile.html', context)