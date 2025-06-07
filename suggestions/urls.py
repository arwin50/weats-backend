from django.urls import path, include
from .views import PromptViewSet, LocationViewSet, SuggestionViewSet


urlpatterns = [
    path('prompts/', PromptViewSet.as_view, name="prompt-view"),
    path('locations/',LocationViewSet.as_view, name="location-view"),
    path('suggestions/',SuggestionViewSet.as_view, name="suggestion-view")
]
