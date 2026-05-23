# app/weather.py
import httpx
from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

# Open-Meteo WMO weather codes
WEATHER_DESCRIPTIONS = {
    0: "Clear sky ☀️",
    1: "Mainly clear 🌤️", 2: "Partly cloudy ⛅", 3: "Overcast ☁️",
    45: "Foggy 🌫️", 48: "Icy fog 🌫️",
    51: "Light drizzle 🌦️", 53: "Drizzle 🌦️", 55: "Heavy drizzle 🌧️",
    61: "Light rain 🌧️", 63: "Rain 🌧️", 65: "Heavy rain 🌧️",
    71: "Light snow 🌨️", 73: "Snow 🌨️", 75: "Heavy snow ❄️",
    80: "Light showers 🌦️", 81: "Showers 🌧️", 82: "Heavy showers 🌧️",
    95: "Thunderstorm ⛈️", 96: "Thunderstorm with hail ⛈️", 99: "Thunderstorm with hail ⛈️"
}

BAD_WEATHER_CODES = {45, 48, 51, 53, 55, 61, 63, 65, 71, 73, 75, 80, 81, 82, 95, 96, 99}

OUTDOOR_KEYWORDS = [
    "jog", "jogging", "run", "running", "walk", "walking", "cycle", "cycling",
    "bike", "biking", "outdoor", "outside", "garden", "park", "cricket",
    "football", "exercise", "workout", "gym", "play", "picnic", "hike", "hiking",
    "swim", "swimming", "drive", "driving", "wash car", "car wash"
]

def is_outdoor_task(task_text: str) -> bool:
    """Check if task involves outdoor activity."""
    task_lower = task_text.lower()
    return any(keyword in task_lower for keyword in OUTDOOR_KEYWORDS)

def get_weather_for_time(reminder_time: datetime, lat: float = 21.1702, lon: float = 72.8311) -> dict:
    """
    Fetch weather for a specific datetime and location.
    Default coords: Surat, Gujarat (change to user's city or make dynamic)
    Returns dict with weather info or empty dict on failure.
    """
    try:
        # format date for API
        date_str = reminder_time.strftime("%Y-%m-%d")

        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&hourly=weathercode,temperature_2m,precipitation_probability"
            f"&timezone=Asia/Kolkata"
            f"&start_date={date_str}&end_date={date_str}"
        )

        response = httpx.get(url, timeout=5)
        data = response.json()

        # find the closest hour to reminder time
        target_hour = reminder_time.hour
        hours = data["hourly"]["time"]  # list of "2024-06-20T07:00"
        codes = data["hourly"]["weathercode"]
        temps = data["hourly"]["temperature_2m"]
        precip = data["hourly"]["precipitation_probability"]

        # find matching hour index
        idx = None
        for i, h in enumerate(hours):
            if f"T{target_hour:02d}:00" in h:
                idx = i
                break

        if idx is None:
            return {}

        code = codes[idx]
        temp = temps[idx]
        rain_chance = precip[idx]
        description = WEATHER_DESCRIPTIONS.get(code, "Unknown")
        is_bad = code in BAD_WEATHER_CODES

        return {
            "description": description,
            "temperature": temp,
            "rain_chance": rain_chance,
            "is_bad": is_bad,
            "code": code
        }

    except Exception as e:
        print(f"⚠️ Weather fetch error: {e}")
        return {}