from django.db import models
from django.conf import settings

# Create your models here.

class VisitedLocation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='visited_locations')
    name = models.CharField(max_length=255)
    address = models.TextField()
    lat = models.FloatField()
    lng = models.FloatField()
    rating = models.FloatField(null=True, blank=True)
    user_ratings_total = models.IntegerField(null=True, blank=True)
    price_level = models.IntegerField(null=True, blank=True)
    types = models.JSONField(null=True, blank=True)  # stores array of strings
    description = models.TextField(null=True, blank=True)
    recommendation_reason = models.TextField(null=True, blank=True)
    photo_url = models.URLField(null=True, blank=True)
    date_visited = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('user', 'name', 'address')  # Prevent duplicate visits
        ordering = ['-date_visited']  # Most recent visits first

    def __str__(self):
        return f"{self.user.username} visited {self.name} on {self.date_visited}"
