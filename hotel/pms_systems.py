from abc import ABC, abstractmethod
import inspect
import json
import sys

from datetime import datetime
from typing import Optional

from hotel.external_api import (
    get_reservations_between_dates,
    get_reservation_details,
    get_guest_details,
    APIError,
)

from hotel.models import Stay, Guest, Hotel, Language
from hotel.utils import validate_phone_number, LANGUAGE_MAPPINGS, STATUS_MAPPINGS


class PMS(ABC):
    """
    Abstract class for Property Management Systems.
    """

    def __init__(self):
        pass

    @property
    def name(self):
        longname = self.__class__.__name__
        return longname[4:]

    @abstractmethod
    def clean_webhook_payload(self, payload: str) -> dict:
        """
        Clean the json payload and return a usable dict.
        """
        raise NotImplementedError

    @abstractmethod
    def handle_webhook(self, webhook_data: dict) -> bool:
        """
        This method is called when we receive a webhook from the PMS.
        Handle webhook handles the events and updates relevant models in the database.
        Requirements:
            - Now that the PMS has notified you about an update of a reservation, you need to
                get more details of this reservation. For this, you can use the mock API
                call get_reservation_details(reservation_id).
            - Handle the payload for the correct hotel.
            - Update or create a Stay.
            - Update or create Guest details.
        """
        raise NotImplementedError

    @abstractmethod
    def update_tomorrows_stays(self) -> bool:
        """
        This method is called every day at 00:00 to update the stays checking in tomorrow.
        Requirements:
            - Get all stays checking in tomorrow by calling the mock API
                get_reservations_between_dates(checkin_date, checkout_date).
            - Update or create the Stays.
            - Update or create Guest details. Deal with missing and incomplete data yourself
                as you see fit. Deal with the Language yourself. country != language.
        """
        raise NotImplementedError

    @abstractmethod
    def stay_has_breakfast(self, stay: Stay) -> Optional[bool]:
        """
        This method is called when we want to know if the stay includes breakfast.
        Notice that the breakfast data is not stored in any of the models?
        How would you deal with this?
        Requirements:
            - Your input is a Stay object.
            - Return True if the stay includes breakfast, otherwise False. Return None if
                you don't know.
        """
        raise NotImplementedError


class PMS_Mews(PMS):
    def clean_webhook_payload(self, payload: str) -> dict:
        try:
            return json.loads(payload)
        except:
            raise Exception("Invalid request body!")

    def handle_webhook(self, webhook_data: dict) -> bool:
        for event in webhook_data.get("Events"):
            # Extracting reservation_id from the payload and reservation_details from the mock API
            reservation_id = event.get("Value").get("ReservationId")
            reservation_details = json.loads(get_reservation_details(reservation_id))

            # Extracting guest_id from the payload and guest_details from the mock API
            guest_id = reservation_details.get("GuestId")
            guest_details = json.loads(get_guest_details(guest_id))

            # Extracting phone_number, country and status from the mock API
            phone_number = guest_details.get("Phone")
            country = guest_details.get("Country")
            status = reservation_details.get("Status")

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

                # Saving the guest in the DB after validation passed
                guest = Guest(
                    name = guest_details.get("Name"),
                    phone = phone_number,
                    language = LANGUAGE_MAPPINGS.get(country)
                )
                guest.save()
                
            try:
                # Try to grab and update the Stay if it exists in the DB
                stay_object = Stay.objects.get(pms_reservation_id=reservation_id)
                stay_object.guest = guest
                stay_object.status = STATUS_MAPPINGS.get(status)
                stay_object.checkin = datetime.strptime(
                    reservation_details.get("CheckInDate"), "%Y-%m-%d"
                    ),
                stay_object.checkout = datetime.strptime(
                    reservation_details.get("CheckOutDate"), "%Y-%m-%d"
                    )
            except Stay.DoesNotExist:
                # Saving the stay in the DB, since it doesn't already exist
                stay_object = Stay(
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
                stay_object.save()

        return True

    def update_tomorrows_stays(self) -> bool:
        # TODO: Implement the method
        return True

    def stay_has_breakfast(self, stay: Stay) -> Optional[bool]:
        # TODO: Implement the method
        return None


def get_pms(name):
    fullname = "PMS_" + name.capitalize()
    # find all class names in this module
    # from https://stackoverflow.com/questions/1796180/
    current_module = sys.modules[__name__]
    clsnames = [x[0] for x in inspect.getmembers(current_module, inspect.isclass)]

    # if we have a PMS class for the given name, return an instance of it
    return getattr(current_module, fullname)() if fullname in clsnames else False
