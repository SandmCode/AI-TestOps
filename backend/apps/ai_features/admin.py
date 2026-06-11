from django.contrib import admin

from .models import AIProviderConfig, AISkill, AISkillsSettings, TestReport

admin.site.register(TestReport)
admin.site.register(AIProviderConfig)
admin.site.register(AISkill)
admin.site.register(AISkillsSettings)
