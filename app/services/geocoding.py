"""
SafeRoute — Geocoding Service
Converts lat/lng to real place names using Nominatim (OpenStreetMap).
Free, no API key required. Caches results.
"""
import requests
import time

# Cache for geocoding results
_geocode_cache = {}


def reverse_geocode(lat: float, lng: float) -> str:
    """
    Convert lat/lng coordinates to a human-readable place name.
    Uses OpenStreetMap Nominatim (free, no API key).
    
    Returns: e.g. "Manipal University Jaipur, Jaipur, Rajasthan"
    or empty string if lookup fails.
    """
    cache_key = f"{lat:.5f},{lng:.5f}"
    if cache_key in _geocode_cache:
        return _geocode_cache[cache_key]

    try:
        resp = requests.get(
            'https://nominatim.openstreetmap.org/reverse',
            params={
                'lat': lat,
                'lon': lng,
                'format': 'json',
                'addressdetails': 1,
                'zoom': 18,  # high detail
            },
            headers={'User-Agent': 'SafeRoute/1.0 (women safety app)'},
            timeout=5,
        )
        data = resp.json()

        if 'error' in data:
            return ''

        # Build a readable name from the response
        name = data.get('name', '')
        address = data.get('address', {})

        # Priority: specific place name > road > neighbourhood > suburb
        if name:
            # Good — this is a named place like "Manipal University Jaipur"
            parts = [name]
            if address.get('city') or address.get('town'):
                parts.append(address.get('city') or address.get('town'))
            elif address.get('state'):
                parts.append(address.get('state'))
            result = ', '.join(parts)
        elif address.get('road'):
            parts = [address['road']]
            if address.get('neighbourhood'):
                parts.append(address['neighbourhood'])
            elif address.get('suburb'):
                parts.append(address['suburb'])
            if address.get('city') or address.get('town'):
                parts.append(address.get('city') or address.get('town'))
            result = ', '.join(parts)
        elif address.get('neighbourhood'):
            result = address['neighbourhood']
        elif address.get('suburb'):
            result = address['suburb']
        else:
            # Last resort: use display_name but trim it
            display = data.get('display_name', '')
            # Take first 3 parts of display_name
            parts = display.split(', ')[:3]
            result = ', '.join(parts)

        _geocode_cache[cache_key] = result
        return result

    except Exception as e:
        print(f'[Geocode] Error for ({lat}, {lng}): {e}')
        return ''


def reverse_geocode_google(lat: float, lng: float, api_key: str) -> str:
    """
    Reverse geocode using Google Maps API (higher accuracy for India).
    Falls back to Nominatim if Google fails.
    """
    if not api_key:
        return reverse_geocode(lat, lng)

    cache_key = f"g_{lat:.5f},{lng:.5f}"
    if cache_key in _geocode_cache:
        return _geocode_cache[cache_key]

    try:
        resp = requests.get(
            'https://maps.googleapis.com/maps/api/geocode/json',
            params={
                'latlng': f'{lat},{lng}',
                'key': api_key,
            },
            timeout=5,
        )
        data = resp.json()

        if data.get('status') == 'OK' and data.get('results'):
            result = data['results'][0]['formatted_address']
            # Trim to reasonable length
            parts = result.split(', ')
            if len(parts) > 4:
                result = ', '.join(parts[:4])
            _geocode_cache[cache_key] = result
            return result

    except Exception as e:
        print(f'[Geocode] Google failed: {e}')

    # Fallback to Nominatim
    return reverse_geocode(lat, lng)
