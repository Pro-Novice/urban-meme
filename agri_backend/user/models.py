import re
from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser, PermissionsMixin
from django.core.validators import validate_email as django_validate_email
from Services.logger import logger
from ..enums.enums import UserType



def validate_email(value):
    """email format validation"""
    try:
        django_validate_email(value)
    except ValidationError:
        raise ValidationError("Invalid email address")

def validate_pincode(value):
    if not re.match(r"^[1-9][0-9]{5}$", str(value)):
        raise ValidationError("Pincode must be 6 digits (no leading zero)")

def validate_aadhaar(value):
    if not re.match(r"^[1-9][0-9]{11}$", value):
        raise ValidationError("Aadhaar must be 12 digits (no leading zero)")

def validate_mobile(value):
    if not re.match(r"^(\+91[\-\s]?)?[6-9]\d{9}$", value):
        raise ValidationError("Invalid phone number")

def validate_username(value):
    if not re.match(r"^[\w.@+-]+$", value):
        raise ValidationError("Username may contain only letters, digits and @/./+/-/_")

def validate_name(value):
    if not re.match(r"^[a-zA-Z \-'.]{2,100}$", value):
        raise ValidationError("Name must be 2-100 characters with valid characters")

def validate_password(value):
    if len(value) < 8:
        raise ValidationError("Password must be at least 8 characters long")
    if not re.search(r"[A-Z]", value):
        raise ValidationError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", value):
        raise ValidationError("Password must contain at least one lowercase letter")
    if not re.search(r"[0-9]", value):
        raise ValidationError("Password must contain at least one digit")

def validate_address(value):
    if not isinstance(value, dict):
        raise ValidationError("Address must be a dictionary")
    required_fields = ['address', 'city', 'state', 'postal_code', 'country']
    missing = [field for field in required_fields if field not in value]
    if missing:
        raise ValidationError(f"Missing address fields: {', '.join(missing)}")
    validate_pincode(value['postal_code'])

class AddressField(models.JSONField):
    def validate(self, value, model_instance):
        super().validate(value, model_instance)
        validate_address(value)



class AgriUserManager(BaseUserManager):
    def create_user(self, username, email, name, phone_no, address, aadhaar_no, password=None, user_type=UserType.USER.value, **extra_fields):
        validate_username(username)
        validate_email(email)
        validate_name(name)
        validate_mobile(phone_no)
        validate_aadhaar(aadhaar_no)
        validate_address(address)
        if not password:
            raise ValueError("Password is required")
        validate_password(password)
        if user_type not in [ut.value for ut in UserType]:
          raise ValidationError(f"Invalid user_type: {user_type}")
        
        if user_type == UserType.ADMIN.value:
            extra_fields.setdefault('is_admin', True)
            extra_fields.setdefault('is_superuser', False) 

        user = self.model(
            username=username,
            email=self.normalize_email(email),
            name=name,
            phone_no=phone_no,
            address=address,
            aadhaar_no=aadhaar_no,
            user_type=user_type,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        logger.info(f"User registered: {email}")
        return user

    def create_superuser(self, username, email, password, **extra_fields):
        if not username or not email or not password:
            raise ValueError("Username, email, and password are required")
        validate_username(username)
        validate_email(email)
        validate_password(password)

        extra_fields.setdefault('user_type', UserType.ADMIN.value)
        extra_fields.setdefault('is_admin', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('name', 'Admin User')
        extra_fields.setdefault('phone_no', '+910000000000')
        extra_fields.setdefault('address', {
            'address': 'Admin HQ',
            'city': 'Admin City',
            'state': 'Admin State',
            'postal_code': '000000',
            'country': 'India'
        })
        extra_fields.setdefault('aadhaar_no', '000000000000')

        user = self.model(
            username=username,
            email=self.normalize_email(email),
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        logger.info(f"Superuser created: {email}")
        return user


class AgriUser(AbstractBaseUser, PermissionsMixin):
    username = models.CharField(
        max_length=150,
        unique=True,
        validators=[validate_username],
        error_messages={'unique': "Username already exists."}
    )
    email = models.EmailField(
        unique=True,
        validators=[validate_email],
        error_messages={'unique': "Email already exists."}
    )
    name = models.CharField(
        max_length=100,
        validators=[validate_name]
    )
    phone_no = models.CharField(
        max_length=13,
        validators=[validate_mobile]
    )
    address = AddressField()
    password = models.CharField(max_length=128)
    aadhaar_no = models.CharField(
        max_length=12,
        unique=True,
        validators=[validate_aadhaar],
        error_messages={'unique': "Aadhaar already exists."}
    )
    user_type = models.CharField(
        max_length=20,
        choices=[(tag.value, tag.name) for tag in UserType],
        default=UserType.USER.value
    )
    date_joined = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    objects = AgriUserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    def __str__(self):
        return f"{self.name} ({self.username})"

    @property
    def is_staff(self):
        return self.is_admin

    def clean(self):
        super().clean()
        if self.user_type == UserType.ADMIN.value:
            if not self.is_admin:
                raise ValidationError("Admin users must have is_admin=True")
        elif self.is_admin:  # Regular user shouldn't be admin
            raise ValidationError("Non-admin users cannot have is_admin=True")

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'name': self.name,
            'phone_no': self.phone_no,
            'address': self.address,
            'aadhaar_no': self.aadhaar_no,
            'user_type': self.user_type,
            'date_joined': self.date_joined.isoformat(),
            'is_active': self.is_active,
            'is_admin': self.is_admin,
            'is_superuser': self.is_superuser
        }
