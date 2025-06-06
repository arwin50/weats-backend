import os
import requests
import time
import json
from rest_framework.decorators import api_view
from rest_framework.response import Response
from google import genai
from google.genai.types import HttpOptions

vertex_location = os.getenv("VERTEX_LOCATION")
project_id = os.getenv("VERTEX_PROJECT_ID")
use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI")
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
MAX_SEARCH_RESULTS = 50  # Get more results for filtering
MAX_FINAL_RESULTS = 10   # Final number of recommendations
SEARCH_RADIUS = 1000  # meters
OFFSET_DISTANCE = 2000  # meters to offset for adjacent searches
PLACES_API_URL = "https://places.googleapis.com/v1/places:searchText"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

def filter_restaurants_with_deepseek(restaurants: list, preferences: dict) -> list:
    """Filter restaurants using DeepSeek LLM based on user preferences."""
    try:
        if len(restaurants) <= MAX_FINAL_RESULTS:
            for i, restaurant in enumerate(restaurants, 1):
                restaurant["description"] = f"A {restaurant.get('types', ['restaurant'])[0].replace('_', ' ').title()} in {restaurant.get('address', 'the area')}."
                restaurant["recommendation_reason"] = f"Selected based on your preferences for {preferences.get('cuisine_type', 'any cuisine')} and {preferences.get('dietary_preference', 'any dietary preference')}."
                restaurant["rank"] = i
            return restaurants

        # Extract preferences
        cuisine_type = preferences.get("cuisine_type", "Surprise me, Choosee!")
        dietary_pref = preferences.get("dietary_preference", "Not choosy atm!")
        max_price = preferences.get("max_price", 4)

        # Construct prompt
        prompt = f"""
You are a restaurant recommendation engine. Your task is to analyze a list of restaurants and select the TOP 10 that best match the user's preferences.

## User Preferences
- Cuisine Type: {cuisine_type}
- Dietary Preference: {dietary_pref}
- Max Price Level: {max_price} (1=budget, 2=moderate, 3=expensive, 4=very expensive)

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

        # Prepare request to DeepSeek
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
        }
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "You are a helpful and intelligent restaurant recommendation assistant."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7
        }

        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload)
        if response.status_code != 200:
            print(f"DeepSeek API error: {response.text}")
            raise Exception("DeepSeek API call failed")

        content = response.json()["choices"][0]["message"]["content"]

        # Clean up and parse JSON
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]

        filtered_restaurants = json.loads(content)

        # Sort by rank and return
        filtered_restaurants.sort(key=lambda x: x.get("rank", 10))
        return filtered_restaurants[:MAX_FINAL_RESULTS]

    except Exception as e:
        print(f"Error in DeepSeek filtering: {str(e)}")
        for i, restaurant in enumerate(restaurants[:MAX_FINAL_RESULTS], 1):
            restaurant["description"] = "Description not available"
            restaurant["recommendation_reason"] = "Recommendation reason not available"
            restaurant["rank"] = i
        return restaurants[:MAX_FINAL_RESULTS]

def get_search_locations(lat: float, lng: float) -> list:
    """Generate 5 search locations: center, north, south, east, west."""
    # Approximate conversion of meters to degrees (roughly)
    # 1 degree ≈ 111,000 meters at the equator
    lat_offset = OFFSET_DISTANCE / 111000
    lng_offset = OFFSET_DISTANCE / (111000 * abs(lat))
    
    return [
        {"name": "center", "lat": lat, "lng": lng},
        {"name": "north", "lat": lat + lat_offset, "lng": lng},
        {"name": "south", "lat": lat - lat_offset, "lng": lng},
        {"name": "east", "lat": lat, "lng": lng + lng_offset},
        {"name": "west", "lat": lat, "lng": lng - lng_offset}
    ]

def search_area(lat: float, lng: float, headers: dict, preferences: dict) -> list:
    """Search for restaurants in a specific area."""
    restaurants = []
    page_token = None
    expanded_search = False
    current_radius = SEARCH_RADIUS
    search_attempt = 0  # Track search attempts
    
    while len(restaurants) < MAX_SEARCH_RESULTS:
        if page_token:
            body = {"pageToken": page_token}
            time.sleep(2)  # Wait before using the token
        else:
            # If we have less than 10 results and haven't expanded search yet, double the radius
            if len(restaurants) < 10 and not expanded_search:
                current_radius = SEARCH_RADIUS * 2
                expanded_search = True
                print(f"Expanding search radius to {current_radius}m due to low results")
            
            # Build text query based on search attempt
            if search_attempt == 0:
                # First attempt: Try specific cuisine and dietary preference
                cuisine = preferences.get("cuisine_type", "")
                dietary = preferences.get("dietary_preference", "")
                text_query = f"{cuisine} {dietary} restaurant PH" if cuisine or dietary else "restaurant PH"
            elif search_attempt == 1:
                # Second attempt: Try just cuisine type
                cuisine = preferences.get("cuisine_type", "")
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
                print(f"Error in area {lat}, {lng}: {response.text}")
                break

            data = response.json()
            places = data.get("places", [])
            print(f"Found {len(places)} places in this page")

            for place in places:
                restaurant = {
                    "name": place.get("displayName", {}).get("text"),
                    "address": place.get("formattedAddress"),
                    "lat": place.get("location", {}).get("latitude"),
                    "lng": place.get("location", {}).get("longitude"),
                    "rating": place.get("rating"),
                    "user_ratings_total": place.get("userRatingCount"),
                    "price_level": place.get("priceLevel"),
                    "types": place.get("types", [])
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

            print(f"Total restaurants in this area: {len(restaurants)}")
            
        except Exception as e:
            print(f"Error searching area: {str(e)}")
            break
            
    return restaurants

@api_view(['POST'])
def nearby_restaurants(request):
    print(request.data)
    lat = request.data.get("lat")
    lng = request.data.get("lng")
    preferences = request.data.get("preferences", {})  # Get user preferences

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
            "places.rating,places.userRatingCount,places.priceLevel,places.types"
        )
    }

    try:
        # Get all search locations
        search_locations = get_search_locations(lat, lng)
        all_restaurants = []
        seen_places = set()  # To track unique places

        # Search each area
        for location in search_locations:
            print(f"\nSearching {location['name']} area...")
            area_restaurants = search_area(location['lat'], location['lng'], headers,preferences)
            
            # Add only unique restaurants
            for restaurant in area_restaurants:
                # Use name and address as unique identifier
                place_id = f"{restaurant['name']}_{restaurant['address']}"
                if place_id not in seen_places:
                    seen_places.add(place_id)
                    all_restaurants.append(restaurant)
            
            print(f"Total unique restaurants so far: {len(all_restaurants)}")
            
            if len(all_restaurants) >= MAX_SEARCH_RESULTS:
                break

        # Sort by rating (highest first)
        all_restaurants.sort(key=lambda x: x.get('rating', 0) or 0, reverse=True)
        
        # Filter restaurants based on user preferences using Gemini
        if preferences:
            filtered_restaurants = filter_restaurants_with_deepseek(all_restaurants, preferences)
        else:
            filtered_restaurants = all_restaurants[:MAX_FINAL_RESULTS]
        
        return Response({
            "restaurants": filtered_restaurants,
            "count": len(filtered_restaurants)
        })
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return Response({
            "error": "Failed to fetch restaurants",
            "details": str(e)
        }, status=500)
