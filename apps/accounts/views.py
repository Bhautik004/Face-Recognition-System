from django.shortcuts import render
from django.shortcuts import redirect, render
from django.views.generic import TemplateView
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.edit import UpdateView
from django.urls import reverse_lazy
from .forms import StudentProfileForm
from django.contrib import messages
from django.shortcuts import redirect
# Create your views here.
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from .serializers import UserMeSerializer
from django import forms
from django.contrib.auth import get_user_model
User = get_user_model()

class LandingView(TemplateView):
    template_name = "landing.html"

class RoleLoginView(LoginView):
    template_name = "login.html"

    def get_success_url(self):
        # always send to role router
        return self.request.build_absolute_uri("/route-after-login/")

class StudentProfileUpdateView(LoginRequiredMixin, UpdateView):
    form_class = StudentProfileForm
    template_name = "accounts/profile_edit.html"
    success_url = reverse_lazy("student_home")  # change as needed

    def get_object(self, queryset=None):
        # only allow editing own profile
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "Profile updated successfully.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)

class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name']  # Add only editable fields
        # Exclude username and email here

@login_required
def role_redirect(request):
    user = request.user
    # If Django admin privileges, go to the built-in admin — no custom admin view
    if user.is_superuser or user.is_staff:
        return redirect("/admin/")
    # otherwise use your app roles
    if getattr(user, "role", "student") == "professor":
        return redirect("prof_home")
    return redirect("student_home")

# --- Simple stub pages (replace with your dashboards) ---
@login_required
def admin_home(request):
    return render(request, "admin_home.html")

@login_required
def professor_home(request):
    return render(request, "prof_home.html")

@login_required
def student_home(request):
    return render(request, "student_home.html")


@login_required
def profile_edit(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully!")
            return redirect('profile_edit')
    else:
        form = ProfileForm(instance=request.user)
    return render(request, 'accounts/profile_edit.html', {'form': form})