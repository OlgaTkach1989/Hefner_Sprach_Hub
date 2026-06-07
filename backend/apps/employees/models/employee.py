from django.conf import settings
from django.db import models


class Lehrer(models.Model):
    Nachname = models.CharField(max_length=255, verbose_name="Nachname")
    Vorname = models.CharField(max_length=255, verbose_name="Vorname")
    Schule_Email = models.EmailField(unique=True)
    Private_Email = models.EmailField(blank=True, default="")
    KurzName = models.CharField(max_length=20, unique=True)
    Telefonnummer = models.CharField(max_length=25, blank=True, null=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lehrer_user")

    def __str__(self):
        return f"{self.Nachname} {self.Vorname} user.id:{self.user_id}"

    class Meta:
        verbose_name = "Lehrer"
        verbose_name_plural = "Lehrer"
        ordering = ["user_id"]
        db_table = "Lehrer"
