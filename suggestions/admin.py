from django.contrib import admin
from .models import Suggestion, Prompt, Location

admin.site.register(Suggestion)
admin.site.register(Prompt)
admin.site.register(Location)
# Register your models here.
