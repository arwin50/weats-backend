from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PromptViewSet, LocationViewSet, SuggestionViewSet

router = DefaultRouter()
router.register(r'prompts', PromptViewSet)
router.register(r'locations', LocationViewSet)
router.register(r'suggestions', SuggestionViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
