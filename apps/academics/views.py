from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.accounts.permissions import RoleAllowed

class ProfessorDashboard(APIView):
    permission_classes = [IsAuthenticated, RoleAllowed("professor","admin")]
    def get(self, request):
        # stub data for now
        return Response({"message":"Professor dashboard visible"})

class StudentDashboard(APIView):
    permission_classes = [IsAuthenticated, RoleAllowed("student","admin")]
    def get(self, request):
        return Response({"message":"Student dashboard visible"})
