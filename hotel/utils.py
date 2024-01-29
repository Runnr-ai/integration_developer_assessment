import datetime
import phonenumbers

from hotel.models import Guest, Hotel, Language, Stay


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
    Validates a phone number.

    Args:
        phone_number: The phone number that needs validation.

    Returns:
        True if the phone number is valid, else False.
    """
    try:
        number = phonenumbers.parse(phone_number)
        return phonenumbers.is_valid_number(number)
    except phonenumbers.NumberParseException:
        raise Exception(f"Invalid phone number: {phone_number}")

def is_unique_phone_number(phone_number: str) -> bool:
    """
    Checking if the phone number provided is a unique phone number in our DB.

    Args:
        phone_number: The phone number that needs validation.
    
    Returns:
        True if the phone number is unique (not found in the DB), else False.
    """
    return not Guest.objects.filter(phone=phone_number).exists()

def validate_phone_number(phone_number: str) -> bool:
    """
    Checking if the phone number provided is a valid phone number and if it is unique in our DB.

    Args:
        phone_number: The phone number that needs validation.

    Returns:
        True if the phone number is valid and unique, else False.
    """
    return True if is_valid_phone_number(phone_number) and is_unique_phone_number(phone_number) else False

def fetch_or_create_guest(guest_details: dict, phones: list) -> Guest:
    """
    Performing a get or create of the Guest.
    When creating also runs validation of the name, phone number and country.

        Args:
            guest_details: Dictionary that consists of the guest data provided by the external API.
            phones: List that is used to check if the phonenumber is given multiple times in the request,
            for different Guests.
        
        Returns:
            A Guest object that is either fetched from or persisted to the DB.
    """
    phone_number = guest_details.get("Phone")
    country = guest_details.get("Country")

    try:
        # Performing a check for the guest in the DB
        guest = Guest.objects.get(phone=phone_number)
    except Guest.DoesNotExist:
        # Performing name validation
        if not guest_details.get("Name"):
            raise Exception("Please enter a valid name!")

        # Performing a phone number validation (using phonenumbers library)
        if not validate_phone_number(phone_number):
            raise Exception("Please enter a valid phone number!")
        
        # Performing country validation
        if not country:
            raise Exception("Please enter a valid country!")
        
        # This was added because when using the mock API we can have multiple guests
        # with the same phone number in the request. Normally this will not be the case.
        if phone_number in phones:
            raise Exception("Same phone number used for multiple guests!")

        # Saving the guest in the DB after validation passed
        phones.append(phone_number)
        guest = Guest(
            name = guest_details.get("Name"),
            phone = phone_number,
            language = LANGUAGE_MAPPINGS.get(country)
        )

    return guest

def update_or_create_stay(reservation_details: dict, guest: Guest):
    """
    Performing an update or create of the Stay.

        Args:
            reservation_details: Dictionary that consists of the stay data provided by the external API.
        
        Returns:
            A Stay object that is either fetched and updated from or persisted to the DB.
    """
    status = reservation_details.get("Status")
    reservation_id = reservation_details.get("ReservationId")
    guest_id = reservation_details.get("GuestId")
    try:
        # Try to grab and update the Stay if it exists in the DB
        stay = Stay.objects.get(pms_reservation_id=reservation_id)
        stay.guest = guest
        stay.status = STATUS_MAPPINGS.get(status)
        stay.checkin = datetime.strptime(
            reservation_details.get("CheckInDate"), "%Y-%m-%d"
            ),
        stay.checkout = datetime.strptime(
            reservation_details.get("CheckOutDate"), "%Y-%m-%d"
            )
    except Stay.DoesNotExist:
        # Saving the stay in the DB, since it doesn't already exist
        stay = Stay(
            hotel = Hotel.objects.filter(
                pms_hotel_id=reservation_details.get("HotelId")
                ).first(),
            guest = guest,
            pms_reservation_id = reservation_id,
            pms_guest_id = guest_id,
            status = STATUS_MAPPINGS.get(status),
            checkin = reservation_details.get("CheckInDate"),
            checkout = reservation_details.get("CheckOutDate")
        )

    return stay
