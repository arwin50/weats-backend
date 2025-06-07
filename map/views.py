import os
import requests
import time
import json
from rest_framework.decorators import api_view
from rest_framework.response import Response
from google import genai
from google.genai import types
from suggestions.models import Prompt, Location, Suggestion
from django.utils import timezone

vertex_location = os.getenv("VERTEX_LOCATION", "us-central1")  # Default to us-central1 if not set
project_id = os.getenv("VERTEX_PROJECT_ID")
use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "True")
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
MAX_SEARCH_RESULTS = 50  # Get more results for filtering
MAX_FINAL_RESULTS = 10   # Final number of recommendations
SEARCH_RADIUS = 2000  # Increased radius to compensate for single search
PLACES_API_URL = "https://places.googleapis.com/v1/places:searchText"
PLACES_PHOTO_URL = "https://places.googleapis.com/v1/{photo_name}/media"

# Initialize Vertex AI client
client = genai.Client(
    vertexai=True,
    project=project_id,
    location=vertex_location,
)

def get_photo_url(photo_name, max_width=400, max_height=400):
    """Get the URL for a place photo."""
    if not photo_name:
        return None
    
    url = PLACES_PHOTO_URL.format(photo_name=photo_name)
    params = {
        'key': GOOGLE_PLACES_API_KEY,
        'maxWidthPx': max_width,
        'maxHeightPx': max_height
    }
    return f"{url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"

def get_or_create_prompt(data):
    # Set default values for required fields
    price = data.get('max_price', 0)  # Default to 0 if not provided
    food_preference = data.get('food_preference', 'any')
    dietary_preference = data.get('dietary_preference', 'any')
    lat = data.get('lat', 0.0)
    lng = data.get('lng', 0.0)

    prompt, created = Prompt.objects.get_or_create(
        price=price,
        food_preference=food_preference,
        dietary_preference=dietary_preference,
        lat=lat,
        lng=lng
    )
    return prompt

def filter_restaurants_with_vertex(restaurants: list, preferences: dict) -> list:
    """Filter restaurants using Vertex AI Gemini model based on user preferences."""
    try:
        if len(restaurants) <= MAX_FINAL_RESULTS:
            for i, restaurant in enumerate(restaurants, 1):
                restaurant["description"] = f"A {restaurant.get('types', ['restaurant'])[0].replace('_', ' ').title()} in {restaurant.get('address', 'the area')}."
                restaurant["recommendation_reason"] = f"Selected based on your preferences for {preferences.get('food_preference', 'any cuisine')} and {preferences.get('dietary_preference', 'any dietary preference')}."
                restaurant["rank"] = i
            return restaurants

        # Extract preferences
        food_preference = preferences.get("food_preference", "Surprise me, Choosee!")
        dietary_pref = preferences.get("dietary_preference", "Not choosy atm!")
        
        def map_price_to_level(peso):
            if peso <= 0:
                return 0
            elif peso <= 150:
                return 1
            elif peso <= 300:
                return 2
            elif peso <= 600:
                return 3
            else:
                return 4

        # Map string levels from the restaurant data
        STRING_TO_LEVEL = {
            "PRICE_LEVEL_FREE": 0,
            "PRICE_LEVEL_INEXPENSIVE": 1,
            "PRICE_LEVEL_MODERATE": 2,
            "PRICE_LEVEL_EXPENSIVE": 3,
            "PRICE_LEVEL_VERY_EXPENSIVE": 4
        }

        # Convert preference price (in pesos) to price level
        raw_price = preferences.get("price", 1000)
        price = map_price_to_level(raw_price) if isinstance(raw_price, (int, float)) else 4

        # Construct prompt
        prompt = f"""
You are a restaurant recommendation engine. Your task is to analyze a list of restaurants and select the TOP 10 that best match the user's preferences.

## User Preferences
- Cuisine Type: {food_preference}
- Dietary Preference: {dietary_pref}
- Max Price Level: {price} (1=budget, 2=moderate, 3=expensive, 4=very expensive)

## Restaurant Candidates
{json.dumps(restaurants, indent=2)}

## Ranking Criteria (in priority order)
1. Price level must be within or below the user's budget.
2. Cuisine should match user preference (or be similar if no exact match).
3. Must support user's dietary preferences.
4. Higher-rated and more-reviewed restaurants are preferred.
5. General quality and reputation.

## Output Format
Return a **JSON array of exactly 10 restaurants**, ranked from best match (rank=1) to least match (rank=10).  
Each restaurant must preserve its original fields and include the following additional keys:
- "description": A short, engaging summary of the restaurant (1–2 sentences).
- "recommendation_reason": A specific explanation of why this restaurant was selected.
- "rank": An integer from 1 to 10 (1 = best match).

**Only output the final JSON array. Do not include any explanations, markdown, or additional text.**
"""

        print(preferences)

        # Send request to Vertex AI
        response = client.models.generate_content(
            model="gemini-2.5-pro-preview-05-06",
            contents=prompt
        )

        # Log the raw response for debugging
        print(f"Raw Vertex AI response: {response.text}")

        # Parse the response
        content = response.text.strip()
        
        # Handle potential markdown formatting
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        
        # Clean up any potential whitespace
        content = content.strip()
        
        # Log the cleaned content for debugging
        print(f"Cleaned content before JSON parsing: {content}")

        if not content:
            raise ValueError("Empty response from Vertex AI")

        try:
            filtered_restaurants = json.loads(content)
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {str(e)}")
            print(f"Content that failed to parse: {content}")
            raise

        # Validate the response structure
        if not isinstance(filtered_restaurants, list):
            raise ValueError(f"Expected list but got {type(filtered_restaurants)}")
        
        if len(filtered_restaurants) > MAX_FINAL_RESULTS:
            filtered_restaurants = filtered_restaurants[:MAX_FINAL_RESULTS]

        # Sort by rank and return
        filtered_restaurants.sort(key=lambda x: x.get("rank", 10))
        return filtered_restaurants

    except Exception as e:
        print(f"Error in Vertex AI filtering: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        
        # Fallback to basic filtering
        for i, restaurant in enumerate(restaurants[:MAX_FINAL_RESULTS], 1):
            restaurant["description"] = f"A {restaurant.get('types', ['restaurant'])[0].replace('_', ' ').title()} in {restaurant.get('address', 'the area')}."
            restaurant["recommendation_reason"] = f"Selected based on your preferences for {preferences.get('food_preference', 'any cuisine')} and {preferences.get('dietary_preference', 'any dietary preference')}."
            restaurant["rank"] = i
        return restaurants[:MAX_FINAL_RESULTS]

def search_restaurants(lat: float, lng: float, headers: dict, preferences: dict) -> list:
    """Search for restaurants in a specific area."""
    restaurants = []
    page_token = None
    search_attempt = 0
    current_radius = SEARCH_RADIUS

    PRICE_LEVEL_MAP = {
        "PRICE_LEVEL_FREE": 0,
        "PRICE_LEVEL_INEXPENSIVE": 1,
        "PRICE_LEVEL_MODERATE": 2,
        "PRICE_LEVEL_EXPENSIVE": 3,
        "PRICE_LEVEL_VERY_EXPENSIVE": 4
    }
    
    while len(restaurants) < MAX_SEARCH_RESULTS:
        if page_token:
            body = {"pageToken": page_token}
            time.sleep(2)  # Wait before using the token
        else:
            # Build text query based on search attempt
            if search_attempt == 0:
                # First attempt: Try specific cuisine and dietary preference
                cuisine = preferences.get("food_preference", "")
                dietary = preferences.get("dietary_preference", "")
                text_query = f"{cuisine} {dietary} restaurant PH" if cuisine or dietary else "restaurant PH"
            elif search_attempt == 1:
                # Second attempt: Try just cuisine type
                cuisine = preferences.get("food_preference", "")
                text_query = f"{cuisine} restaurant PH" if cuisine else "restaurant PH"
            else:
                # Final attempt: General restaurant search
                text_query = "restaurant PH"
            
            body = {
                "textQuery": text_query,
                "includedType": "restaurant",
                "locationBias": {
                    "circle": {
                        "center": {"latitude": lat, "longitude": lng},
                        "radius": current_radius
                    }
                },
            }
            print(f"Search attempt {search_attempt + 1} with query: {text_query}")

        try:
            response = requests.post(PLACES_API_URL, headers=headers, json=body)
            print(f"Response status: {response.status_code}")

            if response.status_code != 200:
                print(f"Error in search: {response.text}")
                break

            data = response.json()
            places = data.get("places", [])
            print(f"Found {len(places)} places in this page")

            for place in places:
                raw_price_level = place.get("priceLevel")
                price_level = PRICE_LEVEL_MAP.get(raw_price_level, None)

                restaurant = {
                    "name": place.get("displayName", {}).get("text"),
                    "address": place.get("formattedAddress"),
                    "lat": place.get("location", {}).get("latitude"),
                    "lng": place.get("location", {}).get("longitude"),
                    "rating": place.get("rating"),
                    "user_ratings_total": place.get("userRatingCount"),
                    "price_level": price_level,
                    "types": place.get("types", []),
                    "photos": place.get("photos", [])
                }
                restaurants.append(restaurant)

            page_token = data.get("nextPageToken")
            if not page_token:
                print("No more pages available")
                # If we have less than 10 results, try next search attempt
                if len(restaurants) < 10 and search_attempt < 2:
                    search_attempt += 1
                    page_token = None  # Reset page token for new search
                    continue
                break

            print(f"Total restaurants found: {len(restaurants)}")
            
        except Exception as e:
            print(f"Error searching: {str(e)}")
            break
            
    return restaurants

@api_view(['POST'])
def nearby_restaurants(request):
    print("Request data:", request.data)
    lat = request.data.get("lat")
    lng = request.data.get("lng")
    preferences = request.data.get("preferences", {}) 

    if not lat or not lng:
        return Response({"error": "Missing latitude or longitude"}, status=400)

    try:
        lat = float(lat)
        lng = float(lng)
    except ValueError:
        return Response({"error": "Latitude and longitude must be numbers"}, status=400)

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": (
            "places.displayName,places.formattedAddress,places.location,"
            "places.rating,places.userRatingCount,places.priceLevel,places.types,"
            "places.photos"
        )
    }

    try:
        # Search for restaurants in the center location
        all_restaurants = search_restaurants(lat, lng, headers, preferences)
        
        # Sort by rating
        all_restaurants.sort(key=lambda x: x.get('rating', 0) or 0, reverse=True)
        
        # Filter restaurants based on preferences
        if preferences:
            filtered_restaurants = filter_restaurants_with_vertex(all_restaurants, preferences)
        else:
            filtered_restaurants = all_restaurants[:MAX_FINAL_RESULTS]
    
        prompt = get_or_create_prompt({
            "lat": lat,
            "lng": lng,
            "food_preference": preferences.get("food_preference", "any"),
            "dietary_preference": preferences.get("dietary_preference", "any"),
            "price": preferences.get("price", 0)
        })

        location_dicts = []
        for rest in filtered_restaurants:
            photo_url = None
            if rest.get("photos") and len(rest["photos"]) > 0:
                photo_url = get_photo_url(rest["photos"][0].get("name"))

            location = Location(
                name=rest["name"],
                address=rest["address"],
                lat=rest["lat"],
                lng=rest["lng"],
                rating=rest.get("rating", 0),
                user_ratings_total=rest.get("user_ratings_total", 0),
                price_level=rest.get("price_level", 1),
                types=rest.get("types", []),
                description=rest.get("description", ""),
                recommendation_reason=rest.get("recommendation_reason", ""),
                photo_url=photo_url
            )

            location_dicts.append({
                "name": location.name,
                "address": location.address,
                "lat": location.lat,
                "lng": location.lng,
                "rating": location.rating,
                "user_ratings_total": location.user_ratings_total,
                "price_level": location.price_level,
                "types": location.types,
                "description": location.description,
                "recommendation_reason": location.recommendation_reason,
                "photo_url": photo_url,
            })

            print("MEOW: ", location.photo_url)

        suggestion_data = {
            "user": request.user.username if request.user.is_authenticated else None,
            "prompt": {
                "lat": prompt.lat,
                "lng": prompt.lng,
                "food_preference": prompt.food_preference,
                "dietary_preference": prompt.dietary_preference,
                "price": prompt.price
            },
            "locations": location_dicts
        }

        return Response({
            "prompt_id": prompt.id,
            "suggestion_id": suggestion_data,
            "restaurants": location_dicts,
            "count": len(location_dicts)
        })
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return Response({
            "error": "Failed to fetch restaurants",
            "details": str(e)
        }, status=500)
