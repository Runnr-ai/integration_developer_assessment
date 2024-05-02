from abc import ABC, abstractmethod
import inspect
import sys
from typing import Optional
import logging
import json
from datetime import datetime, timedelta

from hotel.external_api import (
    get_reservations_for_given_checkin_date,
    get_reservation_details,
    get_guest_details,
    APIError,
)

from hotel.models import Stay, Guest, Hotel


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
        Clean the json payload and return a usable object.
        Make sure the payload contains all the needed information to handle it properly
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
        This method is called every day at 00:00 to update the stays with a checkin date tomorrow.
        Requirements:
            - Get all stays checking in tomorrow by calling the mock API endpoint get_reservations_for_given_checkin_date.
            - Update or create the Stays.
            - Update or create Guest details. Deal with missing and incomplete data yourself
                as you see fit. Deal with the Language yourself. country != language.
        """
        raise NotImplementedError

    @abstractmethod
    def stay_has_breakfast(self, stay: Stay) -> Optional[bool]:
        """
        This method is called when we want to know if the stay includes breakfast.
        Notice that the breakfast data is not stored in any of the models, we always want real time data.
        - Return True if the stay includes breakfast, otherwise False. Return None if you don't know.
        """
        raise NotImplementedError


class PMS_Mews(PMS):

    def clean_webhook_payload(self, payload: str) -> dict:
        try:
            cleaned_payload = {}
            cleaned_payload['HotelId'] = str(payload.get('HotelId', ''))
            cleaned_payload['IntegrationId'] = str(payload.get('IntegrationId', ''))
            events = payload.get('Events', [])
            cleaned_payload['Events'] = []
            for event in events:
                event_name = event.get('Name', '')
                reservation_id = event.get('Value', {}).get('ReservationId', '')
                if event_name and reservation_id:
                    cleaned_payload['Events'].append({'Name': event_name, 'ReservationId': reservation_id})
            return cleaned_payload
        except Exception as e:
            logging.error(f"Error cleaning webhook payload: {e}")
            return {}

    def handle_webhook(self, webhook_data: dict) -> bool:
        try:
            cleaned_payload = self.clean_webhook_payload(webhook_data)
            if cleaned_payload:
                hotel_id = cleaned_payload.get('HotelId')
                self.update_database(hotel_id)
                return True
            else:
                logging.warning("Invalid webhook payload")
                return False
        except Exception as e:
            logging.error(f"Error handling webhook: {e}")
            return False

    def update_tomorrows_stays(self) -> bool:
        try:
            tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
            reservations = self.get_reservations_for_date(tomorrow)
            for reservation in reservations:
                self.update_stay(reservation)
            return True
        except Exception as e:
            logging.error(f"Error updating tomorrow's stays: {e}")
            return False

    def stay_has_breakfast(self, stay: Stay) -> Optional[bool]:
        try:
            reservation_details = self.get_reservation_details(stay.pms_reservation_id)

            # Check if breakfast is included in the reservation
            return reservation_details.get('has_breakfast', None)
        except Exception as e:
            logging.error(f"Error checking if stay has breakfast: {e}")
            return None

    def update_database(self, payload: dict) -> None:
        try:
            # Extract relevant data from the payload
            hotel_id = payload.get('HotelId')
            integration_id = payload.get('IntegrationId')
            events = payload.get('Events', [])

            # Update database with each event
            for event in events:
                reservation_id = event.get('ReservationId')
                # Create or update Stay objects
                Stay.objects.update_or_create(
                    hotel_id=hotel_id,
                    pms_reservation_id=reservation_id,
                    defaults={'hotel_id': hotel_id, 'pms_reservation_id': reservation_id}
                )
        except Exception as e:
            logging.error(f"Error updating database with payload: {e}")

    def get_reservations_for_date(self, date: str) -> list:
        try:
            stays = Stay.objects.filter(checkin=date)

            # Return a list of reservation
            reservation_data = []
            for stay in stays:
                reservation_data.append({
                    'reservation_id': stay.pms_reservation_id,
                })
            return reservation_data
        except Exception as e:
            logging.error(f"Error fetching reservations for date {date}: {e}")
            return []

    def update_stay(self, reservation: dict) -> None:
        try:
            reservation_id = reservation.get('ReservationId')
            stay = Stay.objects.get(pms_reservation_id=reservation_id)
            stay.status = reservation.get('status', stay.status)
            stay.checkin = reservation.get('checkin', stay.checkin)
            stay.checkout = reservation.get('checkout', stay.checkout)
            stay.save()
        except Exception as e:
            logging.error(f"Error updating stay with reservation ID {reservation_id}: {e}")

    def get_reservation_details(self, reservation_id: str) -> dict:
        try:
            stay = Stay.objects.get(pms_reservation_id=reservation_id)
            reservation_details = {
                'reservation_id': stay.pms_reservation_id,
                'guest_name': stay.guest.name if stay.guest else "Unknown",
                'status': stay.status,
                'checkin': stay.checkin,
                'checkout': stay.checkout,
            }
            return reservation_details
        except Exception as e:
            logging.error(f"Error fetching reservation details for ID {reservation_id}: {e}")
            return {}

    def get_pms(name):
        fullname = "PMS_" + name.capitalize()
        # find all class names in this module
        # from https://stackoverflow.com/questions/1796180/
        current_module = sys.modules[__name__]
        clsnames = [x[0] for x in inspect.getmembers(current_module, inspect.isclass)]

        # if we have a PMS class for the given name, return an instance of it
        return getattr(current_module, fullname)() if fullname in clsnames else False
