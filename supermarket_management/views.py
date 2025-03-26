from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def home(request):
    return render(request, 'home.html', {'title': 'Supermarket Management System'})

def permission_denied(request, exception):
    return render(request, '403.html', status=403)