from django.contrib import admin

from .models import ApiInterface, ApiTestCase, AsyncTask, Requirement, TestCase, TestPoint

admin.site.register(Requirement)
admin.site.register(TestPoint)
admin.site.register(TestCase)
admin.site.register(ApiInterface)
admin.site.register(ApiTestCase)
admin.site.register(AsyncTask)
