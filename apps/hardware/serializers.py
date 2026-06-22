from rest_framework import serializers


class HardwareEventPayloadSerializer(serializers.Serializer):
    face_id_code = serializers.CharField(max_length=64)
    event_type = serializers.CharField(max_length=20)
    timestamp = serializers.CharField()
    device_ip = serializers.IPAddressField(required=False)


class HardwareHistoryPayloadSerializer(serializers.Serializer):
    logs = HardwareEventPayloadSerializer(many=True)


class FaceIDSyncUserSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    face_id_code = serializers.CharField()
    full_name = serializers.CharField()
    phone = serializers.CharField()
    role = serializers.CharField()
    face_image_url = serializers.CharField(allow_null=True)


class FaceIDUsersListDataSerializer(serializers.Serializer):
    users = FaceIDSyncUserSerializer(many=True)
    count = serializers.IntegerField()


class FaceIDUsersListResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    data = FaceIDUsersListDataSerializer()


class FaceIDLastSyncDataSerializer(serializers.Serializer):
    last_synced_at = serializers.CharField(allow_null=True)


class FaceIDLastSyncResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    data = FaceIDLastSyncDataSerializer()


class FaceIDHistorySyncDataSerializer(serializers.Serializer):
    processed = serializers.IntegerField()
    created = serializers.IntegerField()


class FaceIDHistorySyncResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    data = FaceIDHistorySyncDataSerializer()


class FaceIDEventResponseDataSerializer(serializers.Serializer):
    created = serializers.BooleanField()
    user_id = serializers.IntegerField(allow_null=True)
    event_type = serializers.CharField()
    event_label = serializers.CharField()
    occurred_at = serializers.CharField()


class FaceIDEventResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    data = FaceIDEventResponseDataSerializer()
