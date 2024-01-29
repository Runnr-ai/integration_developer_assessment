import phonenumbers

from hotel.models import Guest, Language, Stay


# Map the country provided by the mock API to the relevant Language choice in models.py
LANGUAGE_MAPPINGS = {
    "NL": Language.DUTCH,
    "DE": Language.GERMAN,
    "GG": Language.BRITISH_ENGLISH,
    "GB": Language.BRITISH_ENGLISH,
    "CA": Language.BRITISH_ENGLISH,
    "BR": Language.PORTUGUESE_PORTUGAL,
    "CN": Language.BRITISH_ENGLISH,
    "AU": Language.BRITISH_ENGLISH
}

# Map the status provided by the mock API with the relevant status choice in the Stay Model
STATUS_MAPPINGS = {
    "in_house": (Stay.Status.INSTAY.value, Stay.Status.INSTAY.label),
    "checked_out": (Stay.Status.AFTER.value, Stay.Status.AFTER.label),
    "cancelled": (Stay.Status.CANCEL.value, Stay.Status.CANCEL.label),
    "no_show": (Stay.Status.UNKNOWN.value, Stay.Status.UNKNOWN.label),
    "not_confirmed": (Stay.Status.UNKNOWN.value, Stay.Status.UNKNOWN.label),
    "booked": (Stay.Status.BEFORE.value, Stay.Status.BEFORE.label),
}


def is_valid_phone_number(phone_number: str) -> bool:
    """
    Validates a phone number

    Args:
        phone_number: The phone number that needs validation

    Returns:
        True if the phone number is valid, else False
    """
    try:
        number = phonenumbers.parse(phone_number)
        return phonenumbers.is_valid_number(number)
    except phonenumbers.NumberParseException:
        raise Exception(f"Invalid phone number: {phone_number}")

def is_unique_phone_number(phone_number: str) -> bool:
    """
    Checking if the phone number provided is a unique phone number in our DB

    Args:
        phone_number: The phone number that needs validation
    
    Returns:
        True if the phone number is unique (not found in the DB), else False
    """
    return not Guest.objects.filter(phone=phone_number).exists()

def validate_phone_number(phone_number: str) -> bool:
    """
    Checking if the phone number provided is a valid phone number and if it is unique in our DB

    Args:
        phone_number: The phone number that needs validation

    Returns:
        True if the phone number is valid and unique, else False 
    """
    return True if is_valid_phone_number(phone_number) and is_unique_phone_number(phone_number) else False
