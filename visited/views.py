from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import VisitedLocation
from .serializers import VisitedLocationSerializer
from django.db.models import Count
from datetime import datetime, timedelta

class VisitedLocationViewSet(viewsets.ModelViewSet):
    serializer_class = VisitedLocationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return VisitedLocation.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'])
    def recent_visits(self, request):
        """
        Get recently visited locations with visit counts and statistics.
        """
        # Get time range from query params (default to last 30 days)
        days = int(request.query_params.get('days', 30))
        start_date = datetime.now() - timedelta(days=days)

        # Get visited locations in the time range
        recent_visits = VisitedLocation.objects.filter(
            user=request.user,
            date_visited__gte=start_date
        ).order_by('-date_visited')

        # Get visit statistics
        total_visits = recent_visits.count()
        visits_by_day = recent_visits.extra(
            select={'day': 'date(date_visited)'}
        ).values('day').annotate(count=Count('id')).order_by('day')

        # Get most visited locations
        most_visited = recent_visits.values('name', 'address').annotate(
            visit_count=Count('id')
        ).order_by('-visit_count')[:5]

        # Serialize the data
        serializer = self.get_serializer(recent_visits, many=True)

        return Response({
            'recent_visits': serializer.data,
            'statistics': {
                'total_visits': total_visits,
                'visits_by_day': list(visits_by_day),
                'most_visited': list(most_visited),
                'time_range': f'Last {days} days'
            }
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