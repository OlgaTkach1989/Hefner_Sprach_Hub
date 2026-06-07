from django.contrib import admin

from apps.employees.models import Lehrer


@admin.register(Lehrer)
class LehrerAdmin(admin.ModelAdmin):
    list_display = ("id", "Nachname", "Vorname", "Schule_Email", "KurzName", "user")
    search_fields = ("Nachname", "Vorname", "Schule_Email", "KurzName", "user__email")
