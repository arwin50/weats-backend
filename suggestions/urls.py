from django.urls import path, include
from .views import PromptViewSet, LocationViewSet, SuggestionViewSet, save_suggestions, user_suggestions


urlpatterns = [
    path('prompts/', PromptViewSet.as_view, name="prompt-view"),
    path('locations/',LocationViewSet.as_view, name="location-view"),
    path('suggestions/',SuggestionViewSet.as_view, name="suggestion-view"),
    path('save_suggestions/', save_suggestions, name="save_suggestions"),
    path('user_suggestions/', user_suggestions, name="user_suggestions")
]
