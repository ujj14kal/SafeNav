"""
SafeNav — SMS Service
Sends emergency SMS alerts to guardians via Twilio.
Falls back to returning the SMS content if Twilio is not configured.
"""
import os
from datetime import datetime
from urllib.parse import quote


# Twilio configuration (loaded from environment)
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER', '')


def is_sms_configured() -> bool:
    """Check if Twilio credentials are configured."""
    return bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER)


def format_emergency_sms(
    user_name: str,
    lat: float,
    lng: float,
    guardian_name: str = None,
    timestamp: datetime = None,
) -> str:
    """
    Format the emergency SMS message.
    Includes a clickable Google Maps link at the exact coordinates.
    """
    if timestamp is None:
        timestamp = datetime.now()

    time_str = timestamp.strftime("%I:%M %p on %B %d, %Y")
    maps_link = f"https://maps.google.com/?q={lat},{lng}"

    greeting = f"{guardian_name}," if guardian_name else ""

    message = (
        f"EMERGENCY ALERT: {user_name} may need assistance.\n"
        f"{greeting}\n"
        f"Current location: {maps_link}\n"
        f"Coordinates: {lat}, {lng}\n"
        f"Location captured at: {time_str}\n"
        f"\n"
        f"This is an automated alert from SafeNav. "
        f"Please try to contact {user_name} immediately or call local emergency services (100/112)."
    )

    return message


def send_emergency_sms(
    to_phone: str,
    user_name: str,
    lat: float,
    lng: float,
    guardian_name: str = None,
    timestamp: datetime = None,
) -> dict:
    """
    Send an emergency SMS to a guardian's phone number.

    Returns:
        {
            'success': bool,
            'method': 'twilio' | 'manual',
            'message_sid': str (if Twilio),
            'sms_content': str (always included),
            'error': str (if failed),
        }
    """
    sms_content = format_emergency_sms(
        user_name=user_name,
        lat=lat,
        lng=lng,
        guardian_name=guardian_name,
        timestamp=timestamp,
    )

    result = {
        'success': False,
        'sms_content': sms_content,
        'to_phone': to_phone,
        'timestamp': (timestamp or datetime.now()).isoformat(),
    }

    # Validate phone number format
    cleaned = _clean_phone_number(to_phone)
    if not cleaned:
        result['error'] = 'Invalid phone number format'
        result['method'] = 'failed'
        return result

    # Try Twilio if configured
    if is_sms_configured():
        try:
            result.update(_send_via_twilio(cleaned, sms_content))
            return result
        except Exception as e:
            result['error'] = f'Twilio error: {str(e)}'
            result['method'] = 'twilio_failed'
            # Fall through to manual mode

    # Fallback: return the SMS content for manual sending
    result['method'] = 'manual'
    result['error'] = None
    result['success'] = True  # Content is ready, user can send manually
    result['note'] = 'SMS service not configured. The message content is provided for manual sending. Configure TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER in .env to enable automatic SMS.'

    return result


def _send_via_twilio(to_phone: str, message: str) -> dict:
    """Send SMS via Twilio API."""
    from twilio.rest import Client

    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

    # Ensure phone numbers have country code
    if not to_phone.startswith('+'):
        to_phone = f'+91{to_phone}'  # Default to India (+91)

    sms = client.messages.create(
        body=message,
        from_=TWILIO_PHONE_NUMBER,
        to=to_phone,
    )

    return {
        'success': True,
        'method': 'twilio',
        'message_sid': sms.sid,
        'status': sms.status,
    }


def _clean_phone_number(phone: str) -> str:
    """
    Clean and validate a phone number.
    Returns cleaned number or empty string if invalid.
    """
    if not phone:
        return ''

    # Remove spaces, dashes, parentheses
    cleaned = phone.strip().replace(' ', '').replace('-', '').replace('(', '').replace(')', '')

    # Remove + prefix for validation, keep it for Twilio
    digits = cleaned.lstrip('+')

    # Must be all digits (after removing +)
    if not digits.isdigit():
        return ''

    # Must be at least 7 digits (shortest valid international number)
    if len(digits) < 7:
        return ''

    # Must be at most 15 digits (E.164 standard)
    if len(digits) > 15:
        return ''

    return cleaned


def validate_phone_number(phone: str) -> dict:
    """
    Validate a phone number and return details.
    """
    cleaned = _clean_phone_number(phone)
    if not cleaned:
        return {
            'valid': False,
            'error': 'Invalid phone number. Must be 7-15 digits.',
            'cleaned': None,
        }

    # Detect country
    digits = cleaned.lstrip('+')
    country = 'Unknown'
    if digits.startswith('91') and len(digits) == 12:
        country = 'India'
    elif digits.startswith('1') and len(digits) == 11:
        country = 'USA/Canada'
    elif len(digits) == 10:
        country = 'India (without country code)'

    return {
        'valid': True,
        'cleaned': cleaned,
        'country': country,
        'digits': len(digits),
    }
