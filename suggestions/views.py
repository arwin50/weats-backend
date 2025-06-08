import os
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework import viewsets, permissions
from .models import Prompt, Location, Suggestion
from .serializers import PromptSerializer, LocationSerializer, SuggestionSerializer

GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
MAX_FINAL_RESULTS = 10   # Final number of recommendations

def get_or_create_prompt(data):
    # Set default values for required fields
    max_price = data.get('max_price', 0)  # Default to 0 if not provided
    food_preference = data.get('food_preference', 'any')
    dietary_preference = data.get('dietary_preference', 'any')
    lat = data.get('lat', 0.0)
    lng = data.get('lng', 0.0)

    prompt, created = Prompt.objects.get_or_create(
        price=max_price,
        food_preference=food_preference,
        dietary_preference=dietary_preference,
        lat=lat,
        lng=lng
    )
    return prompt

class PromptViewSet(viewsets.ModelViewSet):
    queryset = Prompt.objects.all()
    serializer_class = PromptSerializer

class LocationViewSet(viewsets.ModelViewSet):
    queryset = Location.objects.all()
    serializer_class = LocationSerializer

class SuggestionViewSet(viewsets.ModelViewSet):
    serializer_class = SuggestionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Suggestion.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_suggestions(request):
    lat = request.data.get("lat")
    lng = request.data.get("lng")
    preferences = request.data.get("preferences", {})
    locations = request.data.get("restaurants", {})

    if not lat or not lng:
        return Response({"error": "Missing latitude or longitude"}, status=400)

    try:
        lat = float(lat)
        lng = float(lng)
    except ValueError:
        return Response({"error": "Latitude and longitude must be numbers"}, status=400)

    try:
        prompt = get_or_create_prompt({
            "lat": lat,
            "lng": lng,
            "food_preference": preferences.get("food_preference", "any"),
            "dietary_preference": preferences.get("dietary_preference", "any"),
            "max_price": preferences.get("max_price", 0)
        })

        location_objs = []
        for loc in locations[:MAX_FINAL_RESULTS]:
            location, _ = Location.objects.get_or_create(
                name=loc.get("name"),
                address=loc.get("address"),
                lat=loc.get("lat"),
                lng=loc.get("lng"),
                defaults={
                    "rating": loc.get("rating", 0),
                    "user_ratings_total": loc.get("user_ratings_total", 0),
                    "price_level": loc.get("price_level", 1),
                    "types": loc.get("types", []),
                    "description": loc.get("description", ""),
                    "recommendation_reason": loc.get("recommendation_reason", ""),
                    "photo_url": loc.get("photo_url", None)
                }
            )
            location_objs.append(location)

        existing_suggestions = Suggestion.objects.filter(user=request.user, prompt=prompt)

        for existing in existing_suggestions:
            existing_location_ids = set(existing.locations.values_list("id", flat=True))
            new_location_ids = set([loc.id for loc in location_objs])
            if existing_location_ids == new_location_ids:
                return Response({
                    "error": "Suggestion already exists",
                    "code": "DUPLICATE_SUGGESTION"
                }, status=409)

        if len(location_objs) > 10:
            return Response({"error": "Cannot save more than 10 locations."}, status=400)

        suggestion = Suggestion.objects.create(prompt=prompt, user=request.user)
        suggestion.locations.set(location_objs)
        suggestion.save()

        return Response({
            "prompt_id": prompt.id,
            "suggestion_id": suggestion.id,
            "restaurants": locations,
            "count": len(locations)
        })

    except Exception as e:
        print(f"Error: {str(e)}")
        return Response({
            "error": "Failed to fetch restaurants",
            "details": str(e)
        }, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_suggestions(request):
    suggestions = Suggestion.objects.filter(user=request.user).order_by('-date_created').select_related("prompt")
    serializer = SuggestionSerializer(suggestions, many=True)
    return Response(serializer.data)