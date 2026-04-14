"""OpenWeatherMap API tool for current weather and short-term forecasts."""

from __future__ import annotations

import os
from collections import Counter, defaultdict
from datetime import UTC, datetime
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()


class WeatherTool:
    """Utility wrapper for querying OpenWeather current and forecast data."""

    BASE_URL = "https://api.openweathermap.org/data/2.5/"

    def __init__(self) -> None:
        """Initialize Weather API key and base URL settings."""
        self.api_key = os.getenv("OPENWEATHER_API_KEY", "").strip()
        if not self.api_key:
            print("Warning: OPENWEATHER_API_KEY is missing. Weather API requests will fail.")

    def get_current_weather(self, city: str) -> dict:
        """Get current weather conditions for a city.

        Args:
            city: City name (for example, "San Francisco").

        Returns:
            A normalized weather dictionary or an error dictionary.
        """
        try:
            if not self.api_key:
                return {"error": "API key not configured"}

            response = requests.get(
                f"{self.BASE_URL}weather",
                params={"q": city, "appid": self.api_key},
                timeout=15,
            )
            if response.status_code == 404:
                return {"error": "City not found"}
            response.raise_for_status()
            data = response.json()

            main_data = data.get("main", {})
            wind_data = data.get("wind", {})
            weather_data = data.get("weather", [{}])
            sys_data = data.get("sys", {})
            timezone_offset = int(data.get("timezone", 0))

            sunrise_ts = sys_data.get("sunrise")
            sunset_ts = sys_data.get("sunset")

            return {
                "city": data.get("name", city),
                "country": sys_data.get("country", ""),
                "temperature_c": self._k_to_c(main_data.get("temp")),
                "feels_like_c": self._k_to_c(main_data.get("feels_like")),
                "condition": weather_data[0].get("main", "Unknown"),
                "humidity_percent": int(main_data.get("humidity", 0)),
                "wind_kmh": self._ms_to_kmh(wind_data.get("speed")),
                "visibility_km": self._m_to_km(data.get("visibility")),
                "sunrise": self._format_time(sunrise_ts, timezone_offset),
                "sunset": self._format_time(sunset_ts, timezone_offset),
            }
        except requests.Timeout:
            print(f"Warning: Weather request timed out for '{city}'")
            return {"error": "Weather data unavailable"}
        except Exception as exc:
            print(f"Warning: Failed to fetch current weather for '{city}': {exc}")
            return {"error": "Weather data unavailable"}

    def get_forecast(self, city: str, days: int = 3) -> list[dict]:
        """Get daily forecast summaries from 3-hour forecast intervals.

        Args:
            city: City name to query.
            days: Number of day summaries to return.

        Returns:
            A list of date-grouped forecast summaries.
        """
        try:
            if not self.api_key:
                print("Warning: OPENWEATHER_API_KEY not configured.")
                return []

            response = requests.get(
                f"{self.BASE_URL}forecast",
                params={"q": city, "appid": self.api_key},
                timeout=15,
            )
            if response.status_code == 404:
                return []
            response.raise_for_status()
            data = response.json()

            grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for entry in data.get("list", []):
                dt_txt = entry.get("dt_txt", "")
                date_key = dt_txt.split(" ")[0]
                if date_key:
                    grouped[date_key].append(entry)

            summaries: list[dict] = []
            for date_key in sorted(grouped.keys()):
                entries = grouped[date_key]
                if not entries:
                    continue

                temps = [self._k_to_c(e.get("main", {}).get("temp")) for e in entries]
                humidities = [int(e.get("main", {}).get("humidity", 0)) for e in entries]
                conditions = [
                    (e.get("weather") or [{}])[0].get("main", "Unknown")
                    for e in entries
                ]

                valid_temps = [t for t in temps if isinstance(t, (int, float))]
                avg_temp = round(sum(valid_temps) / len(valid_temps), 2) if valid_temps else None
                avg_humidity = round(sum(humidities) / len(humidities), 1) if humidities else 0
                dominant_condition = Counter(conditions).most_common(1)[0][0] if conditions else "Unknown"

                summaries.append(
                    {
                        "date": date_key,
                        "avg_temp_c": avg_temp,
                        "condition": dominant_condition,
                        "humidity_percent": avg_humidity,
                    }
                )

                if len(summaries) >= max(1, days):
                    break

            return summaries
        except requests.Timeout:
            print(f"Warning: Weather forecast request timed out for '{city}'")
            return []
        except Exception as exc:
            print(f"Warning: Failed to fetch weather forecast for '{city}': {exc}")
            return []

    @staticmethod
    def _k_to_c(kelvin: Any) -> float | None:
        """Convert Kelvin to Celsius rounded to 2 decimals."""
        if kelvin is None:
            return None
        return round(float(kelvin) - 273.15, 2)

    @staticmethod
    def _ms_to_kmh(speed_mps: Any) -> float:
        """Convert meters/second to kilometers/hour rounded to 2 decimals."""
        return round(float(speed_mps or 0) * 3.6, 2)

    @staticmethod
    def _m_to_km(distance_m: Any) -> float:
        """Convert meters to kilometers rounded to 2 decimals."""
        return round(float(distance_m or 0) / 1000, 2)

    @staticmethod
    def _format_time(timestamp: Any, tz_offset_seconds: int) -> str:
        """Format a UTC timestamp shifted by timezone offset as HH:MM."""
        if timestamp is None:
            return ""
        shifted = int(timestamp) + tz_offset_seconds
        return datetime.fromtimestamp(shifted, tz=UTC).strftime("%H:%M")


weather_tool = WeatherTool()


if __name__ == "__main__":
    """Run a basic local self-test for weather endpoints."""
    sample_city = "New York"
    print("Current weather sample:")
    print(weather_tool.get_current_weather(sample_city))
    print("\nForecast sample:")
    print(weather_tool.get_forecast(sample_city, days=3))
