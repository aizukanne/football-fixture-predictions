import json
import requests
import datetime
import boto3
import os
import time
from datetime import timedelta, datetime
from leagues import allLeagues, someLeagues

#allLeagues = someLeagues

rapidapi_key = os.getenv('RAPIDAPI_KEY')

def lambda_handler(event, context):
    all_leagues_flat = [league for sublist in allLeagues.values() for league in sublist]
    
    to_start = 12  #Time to start of the first game
    current_day = datetime.today().weekday()

    # Initialize to_end 
    to_end = None

    # Set to_end based on the current day 
    if current_day == 0:  # Monday
        to_end = 2
    elif current_day == 3:  # Thursday
        to_end = 3
    else:
        to_end = 2
    
    start_date = (datetime.now() + timedelta(hours=to_start)).strftime('%Y-%m-%d')
    #start_date = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
    print(f"Now: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    end_date = (datetime.now() + timedelta(days=to_end, hours=to_start)).strftime('%Y-%m-%d')
    #end_date = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
    print(f'Start Date: {start_date}')
    print(f'End Date: {end_date}')


    headers = {
    	"X-RapidAPI-Key": rapidapi_key,
    	"X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
    }

    for league in all_leagues_flat:
        league_id = league['id']
        print(f'League: {json.dumps(league)}')
        season = get_league_start_date(league_id)[:4]
        url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
        
        querystring = {
            "league": str(league_id),
            "season": str(season),
            "from": start_date,
            "to": end_date
        }
        
        response = requests.get(url, headers=headers, params=querystring)
        if response.status_code == 200:
            games = response.json()['response']
            games_count = response.json()['results']
            fixtures = []

            for i in range(games_count):
                fixtures.append({
                    'fixture_id': games[i]['fixture']['id'],
                    'date' : games[i]['fixture']['date'],
                    'timestamp' : games[i]['fixture']['timestamp'],
                    'home_team': games[i]['teams']['home']['name'],
                    'home_id': games[i]['teams']['home']['id'],
                    'away_team': games[i]['teams']['away']['name'],
                    'away_id': games[i]['teams']['away']['id'],
                    'league_id': games[i]['league']['id'],
                    'season': games[i]['league']['season']
                })
            
            # Forward this data to another lambda function only if fixtures is non-empty    
            if len(fixtures) > 0:
                #print("Fixtures:", json.dumps(fixtures))
                #forward_to_another_lambda(fixtures)
                send_to_sqs(fixtures)
        pass 


def get_league_start_date(league_id):
    """
    Fetch the start date of the current season for a given league.

    Parameters:
    - league_id: The league ID.

    Returns:
    - The start date of the league season (format: YYYY-MM-DD) or None if not found.
    """
    url = "https://api-football-v1.p.rapidapi.com/v3/leagues"
    querystring = {"id": league_id, "current": "true"}

    headers = {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": "api-football-v1.p.rapidapi.com"
    }

    response = requests.get(url, headers=headers, params=querystring)

    if response.status_code == 429:
        # Handle rate limiting specifically
        rate_limit_remaining = response.headers.get('x-ratelimit-requests-remaining', 'Not available')
        print(f"Rate limit exceeded (429). X-RateLimit-Remaining: {rate_limit_remaining}")
        return None
    elif response.status_code != 200:
        print(f"Error: API request failed with status code {response.status_code}")
        return None

    data = response.json()

    if "response" not in data or not data["response"]:
        print("Error: Unexpected API response format or no data found")
        return None

    try:
        # Extract the start date of the current season
        seasons = data["response"][0].get("seasons", [])
        for season in seasons:
            if season.get("current"):
                return season.get("start")
    except (IndexError, KeyError, TypeError):
        print("Error: Failed to extract league start date")

    return None


def forward_to_another_lambda(fixtures):
    lambda_client = boto3.client('lambda')
    payload = {
        'payload': fixtures
    }
    response = lambda_client.invoke(
        FunctionName='getFixtureData',
        InvocationType='Event',
        Payload=json.dumps(payload),
    )
    
def send_to_sqs(fixtures):
    sqs = boto3.client('sqs')
    queue_url = 'https://sqs.eu-west-2.amazonaws.com/985019772236/leagueLists'
    payload = {
        'payload': fixtures
    }
    
    sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(payload)
    )

