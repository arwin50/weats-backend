from rest_framework import serializers
from .models import Prompt, Location, Suggestion

class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = '__all__'


class PromptSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prompt
        fields = '__all__'


class SuggestionSerializer(serializers.ModelSerializer):
    prompt = PromptSerializer(read_only=True)
    prompt_id = serializers.PrimaryKeyRelatedField(queryset=Prompt.objects.all(), source='prompt', write_only=True)
    locations = LocationSerializer(many=True, read_only=True)
    location_ids = serializers.PrimaryKeyRelatedField(
        queryset=Location.objects.all(),
        many=True,
        write_only=True,
        source='locations'
    )

    class Meta:
        model = Suggestion
        fields = ['id', 'prompt', 'prompt_id', 'locations', 'location_ids', 'date_created', 'date_updated']

    def validate_location_ids(self, value):
        if len(value) > 10:
            raise serializers.ValidationError("You can only include up to 10 locations.")
        return value

    def create(self, validated_data):
        locations = validated_data.pop('locations', [])
        user = self.context['request'].user

        suggestion = Suggestion.objects.create(user=user, **validated_data)
        suggestion.locations.set(locations)
        return suggestion

    def update(self, instance, validated_data):
        if 'locations' in validated_data:
            locations = validated_data.pop('locations')
            instance.locations.set(locations)
        return super().update(instance, validated_data)
