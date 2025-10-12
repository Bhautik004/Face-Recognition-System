from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.accounts.permissions import RoleAllowed
from rest_framework import viewsets, decorators, response, status
from .models import Department, Course, Professor, Room, CourseAssignment
from .serializers import (DepartmentSerializer, CourseSerializer, ProfessorSerializer,
                          RoomSerializer, CourseAssignmentSerializer)
from .permissions import IsAdmin, IsAdminOrReadOnly
import math


class ProfessorDashboard(APIView):
    permission_classes = [IsAuthenticated, RoleAllowed("professor","admin")]
    def get(self, request):
        # stub data for now
        return Response({"message":"Professor dashboard visible"})

class StudentDashboard(APIView):
    permission_classes = [IsAuthenticated, RoleAllowed("student","admin")]
    def get(self, request):
        return Response({"message":"Student dashboard visible"})


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsAdminOrReadOnly]

class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.select_related("department").all()
    serializer_class = CourseSerializer
    permission_classes = [IsAdminOrReadOnly]

class ProfessorViewSet(viewsets.ModelViewSet):
    queryset = Professor.objects.select_related("user","department").all()
    serializer_class = ProfessorSerializer
    permission_classes = [IsAdmin]  # only admin creates/edits professors

class RoomViewSet(viewsets.ModelViewSet):
    queryset = Room.objects.all()
    serializer_class = RoomSerializer
    permission_classes = [IsAdminOrReadOnly]

    @decorators.action(detail=True, methods=["get"], url_path="validate-geo")
    def validate_geo(self, request, pk=None):
        """Quick test endpoint: /api/rooms/{id}/validate-geo?lat=..&lng=.."""
        room = self.get_object()
        try:
            lat = float(request.query_params.get("lat"))
            lng = float(request.query_params.get("lng"))
        except (TypeError, ValueError):
            return response.Response({"detail":"lat & lng required"}, status=400)
        dist_m = haversine_m(float(room.latitude), float(room.longitude), lat, lng)
        return response.Response({
            "distance_m": round(dist_m, 2),
            "radius_m": room.radius_m,
            "inside": dist_m <= room.radius_m
        })

class CourseAssignmentViewSet(viewsets.ModelViewSet):
    queryset = CourseAssignment.objects.select_related("course","professor","professor__user").all()
    serializer_class = CourseAssignmentSerializer
    permission_classes = [IsAdmin]

# --- utils ---
def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))
