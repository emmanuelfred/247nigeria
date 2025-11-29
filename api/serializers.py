from rest_framework import serializers
from accounts.models import User, IdentityVerification
from django.contrib.auth.hashers import make_password
from django.contrib.auth import authenticate

class IdentityVerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = IdentityVerification
        fields = ['id_document', 'date_of_birth', 'gender', 'address']
        
        
class SignupSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'surname', 'email', 'password']

    def create(self, validated_data):
        validated_data["password"] = make_password(validated_data["password"])
        user = User.objects.create(**validated_data)
        return user
class IdentityVerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = IdentityVerification
        fields = ['id_document', 'date_of_birth', 'gender', 'address']



class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get("email")
        password = data.get("password")

        user = authenticate(username=email, password=password)

        if not user:
            raise serializers.ValidationError("Invalid email or password.")

        if not user.is_active:
            raise serializers.ValidationError("Account disabled. Please contact support.")

        data["user"] = user
        return data

class ResetPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(
        min_length=8,                 # enforce minimum length
        max_length=128,               # optional max length
        write_only=True,              # won't be returned in responses
        style={'input_type': 'password'}
    )


class UpdatePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)


class UpdateEmailSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)