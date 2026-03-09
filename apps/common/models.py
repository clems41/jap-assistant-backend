from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base model that adds created_at and updated_at fields.

    All domain models should inherit from this class.

    Note: updated_at is NOT updated by QuerySet.update() — only by .save().
    Use update_fields=["field", "updated_at"] if you need to track it manually.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
