from django.contrib import admin

from .models import Document, Project

admin.site.register(Project)
admin.site.register(Document)
