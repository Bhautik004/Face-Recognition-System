import requests

def get_location():
    try:
        response = requests.get('https://ipinfo.io/json')
        data = response.json()
        loc = data['loc'].split(',')
        latitude = float(loc[0])
        longitude = float(loc[1])
        print(f"Latitude: {latitude}")
        print(f"Longitude: {longitude}")
        print(f"City: {data.get('city', 'Unknown')}")
        print(f"Region: {data.get('region', 'Unknown')}")
        print(f"Country: {data.get('country', 'Unknown')}")
    except Exception as e:
        print("Error getting location:", e)

get_location()
42.037594120230274, -87.95679187644679