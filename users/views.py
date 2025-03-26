from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .decorators import role_required
from django.contrib.auth.models import User
from .models import UserProfile
from .forms import UserEditForm  # We’ll create this next

@login_required
@role_required('admin')
def user_list(request):
    users = User.objects.all()
    return render(request, 'users/user_list.html', {'users': users})

@login_required
@role_required('admin')
def user_edit(request, user_id):
    user = get_object_or_404(User, id=user_id)
    profile = user.userprofile
    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            # Update role separately since it’s in UserProfile
            profile.role = form.cleaned_data['role']
            profile.save()
            messages.success(request, f"User {user.username} updated successfully!")
            return redirect('user_list')
    else:
        form = UserEditForm(instance=user, initial={'role': profile.role})
    return render(request, 'users/user_edit.html', {'form': form, 'user': user})