from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import VisitedLocationViewSet

router = DefaultRouter()
router.register(r'', VisitedLocationViewSet, basename='visited-location')

urlpatterns = [
    path('', include(router.urls)),
] 