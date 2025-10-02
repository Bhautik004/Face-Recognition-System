# apps/biometrics/admin_views.py
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.shortcuts import redirect
from apps.biometrics.services.training import train_users

@staff_member_required
def train_all_view(request):
    summary = train_users(None)  # all users
    messages.success(
        request,
        f"Training complete: users={summary['users']}, embeddings={summary['embeddings']}, skipped(no-face)={summary['skipped']}"
    )
    return redirect("admin:index")

# helper to inject our URL into admin
def biometrics_admin_urls(site):
    return [
        path("biometrics/train-all/", site.admin_view(train_all_view), name="biometrics_train_all"),
    ]
