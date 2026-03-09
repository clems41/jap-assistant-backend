import factory
from django.contrib.auth import get_user_model
from factory.django import DjangoModelFactory

User = get_user_model()


class UserFactory(DjangoModelFactory):
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    first_name = factory.Faker("first_name", locale="fr_FR")
    last_name = factory.Faker("last_name", locale="fr_FR")
    is_active = True

    class Meta:
        model = User

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        password = kwargs.pop("password", "testpass123")
        user = model_class(*args, **kwargs)
        user.set_password(password)
        user.save()
        return user
