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

from hotel.models import Stay, Guest
from hotel.utils import fetch_or_create_guest, update_or_create_stay


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
        # Guests and Stays lists are used for bulk_create
        guests = []
        stays = []
        phones = []

        for event in webhook_data.get("Events"):
            # Extracting reservation_id from the payload and reservation_details from the mock API
            reservation_id = event.get("Value").get("ReservationId")
            reservation_details = json.loads(get_reservation_details(reservation_id))

            # Extracting guest_id from the payload and guest_details from the mock API
            guest_id = reservation_details.get("GuestId")
            guest_details = json.loads(get_guest_details(guest_id))

            guest = fetch_or_create_guest(guest_details, phones)
            guests.append(guest)
                
            stay = update_or_create_stay(reservation_details, guest)
            stays.append(stay)

        # Bulk_create to minimize the calls made to the DB
        try:
            Guest.objects.bulk_create(guests)
            Stay.objects.bulk_create(stays)
        except:
            raise Exception("Error occurred while persisting to DB!")

        return True

    def update_tomorrows_stays(self) -> bool:
        # Guests and Stays lists are used for bulk_create
        guests = []
        stays = []
        phones = []

        # Running with checkin and checkout as today because the function will be run at 00:00
        stays_to_update = json.loads(get_reservations_between_dates(datetime.date.today(), datetime.date.today()))
        for stay_object in stays_to_update:
            if stay_object.get("CheckInDate") == datetime.date.today():
                status = Stay.Status.INSTAY.value
            if stay_object.get("CheckOutDate") == datetime.date.today():
                status = Stay.Status.AFTER.value
            stay_object[status] = status

            #Try to fetch guest if it exists in the DB
            try:
                guest_object = Stay.objects.get(pms_reservation_id=stay_object.get("ReservationId")).guest
            except Stay.DoesNotExist:
                guest_object = json.loads(get_guest_details(stay_object.get("GuestId")))

            guest = fetch_or_create_guest(guest_object, phones)
            guests.append(guest)

            stay = update_or_create_stay(stay_object, guest)
            stays.append(stay)
        
        # Bulk_create to minimize the calls made to the DB
        try:
            Guest.objects.bulk_create(guests)
            Stay.objects.bulk_create(stays)
        except:
            raise Exception("Error occurred while persisting to DB!")

        return True

    def stay_has_breakfast(self, stay: Stay) -> Optional[bool]:
        return json.loads(get_reservation_details(stay.pms_reservation_id)).get("BreakfastIncluded")


def get_pms(name):
    fullname = "PMS_" + name.capitalize()
    # find all class names in this module
    # from https://stackoverflow.com/questions/1796180/
    current_module = sys.modules[__name__]
    clsnames = [x[0] for x in inspect.getmembers(current_module, inspect.isclass)]

    # if we have a PMS class for the given name, return an instance of it
    return getattr(current_module, fullname)() if fullname in clsnames else False
