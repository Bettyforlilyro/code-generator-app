from enum import Enum


class ChatMessageType(Enum):
    USER = "user"
    AI = "ai"

    @classmethod
    def get_all_message_types(cls):
        return [item.value for item in cls]

    @classmethod
    def is_valid_message_type(cls, message_type: str) -> bool:
        return message_type in cls.get_all_message_types()

    @classmethod
    def get_message_type_by_value(cls, message_type: str) -> "ChatMessageType":
        return next((item for item in cls if item.value == message_type), None)

    def __str__(self):
        return self.value

