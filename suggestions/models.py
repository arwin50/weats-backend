from django.db import models
from django.core.exceptions import ValidationError

class Location(models.Model):
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

    def __str__(self):
        return self.name

class Prompt(models.Model):
    price = models.IntegerField()
    food_preference = models.CharField(max_length=255)
    dietary_preference = models.CharField(max_length=255)
    lat = models.FloatField()
    lng = models.FloatField()

    def __str__(self):
        return f"{self.food_preference} - {self.dietary_preference}"

class Suggestion(models.Model):
    prompt = models.ForeignKey(Prompt, on_delete=models.CASCADE, related_name='suggestions')
    locations = models.ManyToManyField(Location, related_name='suggestions')
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    def clean(self):
        if self.locations.count() > 10:
            raise ValidationError("A suggestion cannot have more than 10 locations.")

    def __str__(self):
        return f"Suggestion for {self.prompt} ({self.locations.count()} locations)"
