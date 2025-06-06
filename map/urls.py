from .views import nearby_restaurants
from django.urls import path

urlpatterns = [
    path('search_places/', nearby_restaurants,name="nearby restaurants"),
]