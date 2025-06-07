from rest_framework import serializers
from .models import VisitedLocation

class VisitedLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = VisitedLocation
        fields = [
            'id', 'name', 'address', 'lat', 'lng', 
            'rating', 'user_ratings_total', 'price_level',
            'types', 'description', 'recommendation_reason',
            'photo_url', 'date_visited', 'notes'
        ]
        read_only_fields = ['date_visited'] 