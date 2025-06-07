from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import VisitedLocation
from .serializers import VisitedLocationSerializer

class VisitedLocationViewSet(viewsets.ModelViewSet):
    serializer_class = VisitedLocationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return VisitedLocation.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'visited_locations': serializer.data,
            'count': queryset.count()
        })

    @action(detail=False, methods=['post'])
    def check_visited(self, request):
        """
        Check if a location is visited by the current user.
        """
        location_data = request.data.get('location')
        if not location_data:
            return Response(
                {'error': 'location data is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            visited_location = VisitedLocation.objects.get(
                user=request.user,
                name=location_data.get('name'),
                address=location_data.get('address')
            )
            serializer = self.get_serializer(visited_location)
            return Response({
                'is_visited': True,
                'data': serializer.data
            })
        except VisitedLocation.DoesNotExist:
            return Response({
                'is_visited': False
            })

    @action(detail=False, methods=['post'])
    def toggle_visited(self, request):
        """
        Toggle a location's visited status.
        If the location is not visited, it will be added to visited list.
        If the location is already visited, it will be removed from visited list.
        """
        location_data = request.data.get('location')
        notes = request.data.get('notes', '')

        if not location_data:
            return Response(
                {'error': 'location data is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Try to find existing visited location
            visited_location = VisitedLocation.objects.get(
                user=request.user,
                name=location_data.get('name'),
                address=location_data.get('address')
            )
            # If found, delete it (mark as unvisited)
            visited_location.delete()
            return Response({
                'message': 'Location removed from visited list',
                'is_visited': False
            }, status=status.HTTP_200_OK)

        except VisitedLocation.DoesNotExist:
            # If not found, create new visited location
            visited_location = VisitedLocation.objects.create(
                user=request.user,
                name=location_data.get('name'),
                address=location_data.get('address'),
                lat=location_data.get('lat'),
                lng=location_data.get('lng'),
                rating=location_data.get('rating'),
                user_ratings_total=location_data.get('user_ratings_total'),
                price_level=location_data.get('price_level'),
                types=location_data.get('types'),
                description=location_data.get('description'),
                recommendation_reason=location_data.get('recommendation_reason'),
                photo_url=location_data.get('photo_url'),
                notes=notes
            )
            serializer = self.get_serializer(visited_location)
            return Response({
                'message': 'Location added to visited list',
                'is_visited': True,
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)