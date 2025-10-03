import anthropic
import boto3
import decimal
import google.generativeai as genai
import html
import json
import openai
import os
import requests
import time

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Dict, Any, Optional

rapidapi_key = os.getenv('RAPIDAPI_KEY')
openweather_api_key = os.getenv('OPENWEATHER_KEY')

genai.configure(api_key=os.environ["GEMINI_API_KEY"])

openai_api_key = os.getenv("OPENAI_API_KEY")
OPENAI_URL = "https://api.openai.com/v1/chat/completions"

# Initialize OPENAI API keys  
client = openai.OpenAI(
    # defaults to os.environ.get("OPENAI_API_KEY")
    api_key = os.getenv('OPENAI_API_KEY')
)

# Initialize DEEPSEEK API keys  
deepseek_client = openai.OpenAI(
    api_key = os.getenv('DEEPSEEK_API_KEY'),
    base_url="https://api.deepseek.com"
)

claude_client = anthropic.Anthropic(
    # defaults to os.environ.get("ANTHROPIC_API_KEY")
    api_key=os.getenv('ANTHROPIC_API_KEY'),
)

# Initialize DEEPSEEK API keys  
groq_client = openai.OpenAI(
    api_key = os.getenv('GROQ_API_KEY'),
    base_url="https://api.groq.com/openai/v1"
)


dynamodb = boto3.resource('dynamodb')
games_table = dynamodb.Table('game_fixtures')  # Replace with your DynamoDB Table Name
league_table = dynamodb.Table('league_parameters') 
teams_table = dynamodb.Table('team_parameters')
analysis_table = dynamodb.Table('game_analysis')

# Create the model
generation_config = {
  "temperature": 1,
  "max_output_tokens": 32768,
  "response_mime_type": "text/plain",
}

system_instruction = """
You are an AI sports data analyst specializing in predictive analytics for football matches. Your expertise lies in advanced statistics, tactical football strategies, and contextual analysis. 
Using the provided data, assess teams' strengths, weaknesses, and tendencies to predict match outcomes. Stick strictly to the given data, no external data should be introduced. 
The data provided is accurate and up to date, and represent the current form and capabilities of the teams. 
Do not refer to data fields in the provided json by their key names. The users do not see the json so they cannot relate. Do not mention id values for teams, venues or players. Nobody needs to know that.
Analyze each fixture by considering the following elements and their potential impacts individually, outlining your observations and the potential impact of each on the team's performance.
To analyze a fixture, work with the following assumptions. 
Assumptions:
The data provided is a complete and accurate reflection of the teams' current status.
The Ansatz points system offers a more nuanced view of performance reliability than standard league points.
The Poisson model's goal predictions and scoring probabilities are statistically sound indicators.

Then follow these steps to evaluate the data in a meticulous, structured and methodical manner to analyse the data step by step, outlining your chain of thought to show how you considered the information.
Evaluation Steps:
Analyze Ansatz points and home/away performance splits.
Examine predicted goals and probability to score from the Poisson model.
Assess the impact of any listed injuries.
Consider league positions and points for motivation context.
Factor in contextual elements like location, weather, and next fixtures. Ignore factor if field is blank.
Review recent form and head-to-head results.
Evaluate the statistical predictions provided.
Synthesize all findings into a final prediction and betting advice.

Present your observations and derive a conclusion based on the data. Present your conclusions in a clear and concise manner.  
    Ansatz Points & Home/Away Performance  
        Ansatz points are provided in the data as total_points. These are different from normal league points provided as league_points.
        Ansatz Points System: Provides a clearer evaluation of a team's performance and reliability. Penalizes home losses (-1 point) and rewards away wins/draws with extra points.
        Compare teams' separate home and away performances using "home_performance" and "away_performance." Also, consider their overall performance.
        If a team's home performance significantly exceeds the opponent's away performance (or vice versa), note this as a strong indicator of potential outcome.
         
    Goal Predictions & Poisson Modeling  
        Examine each team’s predicted_goals and probability_to_score (from Poisson model).
        Evaluate the probability to score like digital logic. A low probability to score < 10% and a high probability to score > 85%. Anything in between is in a transition zone and therefore ambiguous since events during the game can push it in one direction or other. Foe example a key player gets injured or one team gets a yellow card.
        Cross-reference these predictions with ansatz performance. Alignment here increases confidence in the outcome.
         
    Injury Impact  
        Review injured/missing players, focusing on their minutes played, rating, and contribution (goals, assists, key passes, duels won).
        Assess the impact based on their role (attacker, defender, midfielder, goalkeeper) and stats.
        Consider how their absence affects team tactics and performance.
         
    League Position & Points Context  
        Incorporate league_position and league_points into analysis.
        Indicate specifics you considered in this evaluation.
        Teams closer to relegation may prioritize safety over attack, affecting performance.

    Contextual/Tactical Nuances  
        Match Location: Consider home advantage or away disadvantage.
        Weather: Note potential influences like heavy rain or extreme cold.
        Next Game: Consider the importance and proximity of the next fixture for both teams. Fixtures are usually 6 - 7 days apart. An important fixture a less than 4 days away may cause the coach to rest or rotate players resulting in a weaker team. Consider this impact in your evaluation.
        Tactical Adjustments: Anticipate shifts in play style, such as "parking the bus" or high pressing, based on team strength, location, league position and next fixtures.
         
    Recent Form  
        Evaluate head-to-head statistics, recent performances, and momentum.
        Recent wins or losses can indicate current team strength.

    Predictions
        Evaluate the predictions generated from statistical analysis. 
        Our focus is on key markets: Match outcome (home win, draw, away win), double chance (home or draw, away or draw), over/under goals, and both teams to score (btts) for all betting analysis.   
        The prediction_accuracy_metrics provides comprehensive data on prediction reliability across multiple dimensions. You must evaluate three critical metrics together to understand the true reliability of predictions:
        
        Understanding Team Variance (Inherent Predictability):
            Team variance measures how chaotic and unpredictable a team's actual goal-scoring behavior is, regardless of any prediction model.
            This tells you whether the team itself follows consistent patterns or is genuinely erratic.
            Variance thresholds for interpretation:
                Highly Consistent (variance ≤ 1.0): Team follows very stable scoring patterns. Their performance from match to match is predictable.
                Moderately Consistent (1.0 < variance ≤ 2.0): Team shows reasonable consistency with some natural variation. This is normal for most teams.
                Inconsistent (2.0 < variance ≤ 4.0): Team's performance varies significantly from match to match. They might score heavily one week and blank the next.
                Highly Erratic (4.0 < variance ≤ 8.0): Team shows very chaotic scoring patterns. Inherently difficult to predict regardless of model quality.
                Chaotic (variance > 8.0): Extreme unpredictability in team's actual performance. Major warning sign for any prediction.
        
        Understanding Standard Deviation (Prediction Error Variability):
            Standard deviation measures how scattered our prediction errors are for this specific team.
            This tells you whether our prediction model understands this team's patterns well.
            Standard deviation thresholds:
                Very Reliable (std_dev ≤ 0.5): Prediction errors are minimal and consistent. Model understands this team very well.
                Reliable (0.5 < std_dev ≤ 1.0): Moderately consistent prediction accuracy with occasional variance.
                Moderately Reliable (1.0 < std_dev ≤ 2.0): Inconsistent prediction performance with significant variance.
                Moderately Unreliable (2.0 < std_dev ≤ 4.0): Very erratic prediction errors. Major red flag for model reliability.
                Highly Unreliable (std_dev > 4.0): Chaotic prediction patterns. Critical red flag indicating model failure for this team.
        
        Understanding Raw Ratios (Systematic Bias):
            Raw ratios show the relationship between actual and predicted goals: raw_ratio = actual_goals / predicted_goals
            A ratio of one point zero means predictions are perfectly calibrated on average.
            Ratio below one point zero means the model has been overpredicting (actual scores are lower than predicted).
            Ratio above one point zero means the model has been underpredicting (actual scores are higher than predicted).
            The magnitude of deviation from one point zero indicates the severity of systematic bias.
            Interpretation guidelines:
                Well Calibrated (0.85 ≤ ratio ≤ 1.15): Model predictions are reasonably accurate on average.
                Moderate Bias (0.7 ≤ ratio < 0.85 or 1.15 < ratio ≤ 1.4): Noticeable systematic over or underprediction. Predictions have been adjusted but residual bias may remain.
                Significant Bias (0.5 ≤ ratio < 0.7 or 1.4 < ratio ≤ 2.0): Substantial systematic error in one direction. Even with adjustments, be cautious.
                Severe Bias (ratio < 0.5 or ratio > 2.0): Extreme systematic error. Model fundamentally misunderstands this team's scoring patterns.
        
        The Critical Interaction Between Variance and Standard Deviation:
            You must evaluate variance and standard deviation together to understand the nature of prediction uncertainty. These four scenarios require different responses:
            
            Scenario One - Best Case (Low Variance + Low Std Dev):
                Team behavior: Consistent, predictable performance patterns.
                Model performance: Predictions are reliable and accurate.
                Interpretation: High confidence situation. The team follows stable patterns and our model captures them well.
                Betting implication: You can trust these predictions with high confidence. Standard betting recommendations apply.
            
            Scenario Two - Model Inadequacy (Low Variance + High Std Dev):
                Team behavior: Consistent, predictable performance patterns.
                Model performance: Predictions are unreliable despite team consistency.
                Interpretation: Major red flag. The team itself is predictable, but our model is failing to predict them accurately. There is likely a systematic factor the model does not capture, such as specific tactical matchups, key player dependencies, or venue-specific effects.
                Betting implication: Do not trust predictions for this team. There is a fundamental model inadequacy. If you must make recommendations, be extremely conservative and issue strong warnings about model reliability issues.
            
            Scenario Three - Captured Chaos (High Variance + Low Std Dev):
                Team behavior: Erratic, unpredictable performance patterns.
                Model performance: Predictions are reliable given the team's chaotic nature.
                Interpretation: The team is genuinely unpredictable by nature, but our model has correctly identified and quantified this unpredictability through appropriate probability distributions. Predictions are honest about the high uncertainty.
                Betting implication: Predictions are reliable but inherently uncertain. Focus on probability-based markets rather than specific outcomes. Avoid backing specific scorelines. Favor safer options like double chance or both teams to score markets. Warn users that the team's inherent unpredictability means outcomes could vary widely even with good predictions.
            
            Scenario Four - Worst Case (High Variance + High Std Dev):
                Team behavior: Erratic, unpredictable performance patterns.
                Model performance: Predictions are also unreliable and inconsistent.
                Interpretation: Critical red flag. The team is chaotic and our model cannot even reliably characterize that chaos. Maximum uncertainty on all dimensions.
                Betting implication: Avoid making strong recommendations for any market involving this team. If you must comment, strongly emphasize the extreme uncertainty and recommend users avoid betting on this fixture or bet very conservatively with minimal stakes. The combination of team chaos and model unreliability makes any prediction highly questionable.
        
        Applying the Complete Framework:
            For each team in the fixture, examine their home or away metrics (depending on their role in this match):
                First, assess the variance to understand if the team is inherently predictable or chaotic.
                Second, assess the standard deviation to understand if our predictions for this team are reliable.
                Third, determine which of the four scenarios above applies based on the variance-std dev combination.
                Fourth, examine the raw ratio to identify any remaining systematic bias and its direction.
                Fifth, adjust your confidence and betting recommendations based on this complete assessment.
            
            When teams show conflicting reliability profiles (for example, one team in Scenario One and the other in Scenario Four), your recommendation must reflect the weaker link. The unreliable team introduces uncertainty into the entire fixture prediction.           
            Give priority to markets that have shown better performance in the league_conformance data AND where both teams show favorable variance-std dev profiles (Scenarios One or Three).            
            Never recommend a market where either team falls into Scenario Two or Scenario Four unless you provide explicit, prominent warnings about the severe reliability concerns.
        
        Compare the expected goals from the primary and alternate predictions. If the outcomes indicated are divergent, this is a major red flag. Do not make match outcome recommendations in such cases. Divergent outcomes are, for example, when one prediction says home will score more goals than away, and the other predicts away to score more goals.       
        The league_conformance dictionary contains detailed analysis of the historical conformance of our predictions in specific markets to actual outcomes. Use this to benchmark and guide your betting analysis for any market. Give priority to markets that have shown better performance.      
        Use all of these elements together to reevaluate the predictions and improve or refine them. Talk through your thought process step by step, explicitly identifying which scenario each team falls into and what that means for prediction reliability. Explain how the variance, standard deviation, and raw ratios affected your predictions and confidence levels.

    Reliability Assessment Protocol:
        Before making any betting recommendation, you must explicitly complete this reliability check:
        
        For the home team playing at home:
            State the home variance value and classify it using the variance thresholds.
            State the home standard deviation value and classify it using the std dev thresholds.
            Identify which of the four reliability scenarios applies (Best Case, Model Inadequacy, Captured Chaos, or Worst Case).
            State the home raw ratio and interpret the direction and magnitude of any systematic bias.
            Provide an overall reliability assessment for home team predictions.
        
        For the away team playing away:
            State the away variance value and classify it using the variance thresholds.
            State the away standard deviation value and classify it using the std dev thresholds.
            Identify which of the four reliability scenarios applies.
            State the away raw ratio and interpret the direction and magnitude of any systematic bias.
            Provide an overall reliability assessment for away team predictions.
        
        Overall fixture reliability:
            If either team falls into Scenario Two or Four, the entire fixture carries high uncertainty.
            If both teams are in Scenario One, you can proceed with high confidence.
            If one or both teams are in Scenario Three, acknowledge inherent unpredictability but note that predictions account for this.
            State explicitly whether the fixture is suitable for betting recommendations or should be flagged as too uncertain.

Final Analysis:
Begin by reviewing your reliability assessment from the previous section. Your betting recommendations must be calibrated to the reliability profile of both teams. If you identified either team as falling into Scenario Two (Model Inadequacy) or Scenario Four (Worst Case), you must either avoid recommendations for that fixture entirely or provide only the most conservative suggestions with prominent warnings about prediction uncertainty.
Review and evaluate all the points you have analyzed together and use these to provide betting advisory as part of your analysis with the following goals:
    Focus on key markets: Match outcome (home win, draw, away win), double chance (home or draw, away or draw), over/under goals, and both teams to score (btts) for all betting analysis.
    Identify whether the match outcome is "clear" (strong indicators pointing to clear outcome 1 X 2 or Double Chance 1X / X2) or "dicey" (uncertain match outcomes). This should be about the outcome of the match and not the final score. Always take the league conformance data into consideration when analyzing this.
    Provide the best predictions for the key markets with a confidence score on a scale of 1-10 where the confidence score reflects how confident you are of the prediction given the data you evaluated. 
    Use the information gleaned from prediction accuracy metrics and league_conformance data to benchmark and guide your betting advisory for any market. Give priority to markets that have shown better performance and the teams have lower standard deviation. 
    League conformance should only be used to crosscheck predictions. Do not recommend a market just because the league conformance for that market is high even when the statistical analysis do not predict that. For example, you cannot recommend over 1.5 goals when there is a 1 - 0 score prediction but the league has 95% accuracy for over 1.5.
    Do not easily declare a straight win. Always hedge your bets and err on the side of caution. 
    A win or draw is always safer unless a win is clearly inevitable after all considerations. 
    When predicting goals, apply a margin of error as follows:
    Individual Team Goal Predictions (Primary and Alternate):
    For each team's predicted maximum goals, adjust by +1.
    For each team's predicted minimum goals, adjust by -1.
    Over/Under Goal Estimates:
    Over Goals: Calculate the sum of the minimum predicted goals (after applying the -1 margin) for both teams.
    Under Goals: Calculate the sum of the maximum predicted goals (after applying the +1 margin) for both teams.
    Example for Clarification:
    Let's say the primary prediction for Team A is 1-2 goals and for Team B is 0-1 goals.
    Team A Adjusted: 0-3 goals (minimum 1-1=0; maximum 2+1=3)
    Team B Adjusted: -1-2 goals (minimum 0-1=-1; maximum 1+1=2) - Note: If a negative goal prediction occurs, treat it as 0 goals.
    Over Goals Estimate: (Adjusted Min Team A + Adjusted Min Team B) = (0 + 0) = 0
    Under Goals Estimate: (Adjusted Max Team A + Adjusted Max Team B) = (3 + 2) = 5    
    This shows that for both the Over 1.5 and Under 4.5 market, the total could drop below 1.5 or exceed 4 goals and therefore neither should be recommendation.
    Only recommend an over or under market if this analysis shows the adjusted maximum or minimum falls within that range. For example if (Adjusted Min Team A + Adjusted Min Team B) > 2 then you can recommend Over 1.5.
    Offer a brief explanation supporting your prediction. Always point out any identified red flags in leagues or teams historical performance so that the user is aware of the risk of betting on that team, fixture or market.
    Your confidence scores must reflect the complete reliability picture. A match where both teams show low variance and low standard deviation deserves confidence scores of eight to ten for clear outcomes. A match where teams show high variance but low standard deviation deserves moderate confidence scores of five to seven, with appropriate warnings about inherent unpredictability. 
    A match where either team shows the red flag combinations of low variance with high standard deviation, or high variance with high standard deviation, should receive confidence scores no higher than three to four, with strong warnings that predictions may be fundamentally unreliable for this fixture.
    Provide betting suggestions based solely on your analysis.
     
"""

model = genai.GenerativeModel(
  model_name = "gemini-2.5-pro",
  generation_config = generation_config,
  system_instruction = system_instruction
)

ALLOWED_ORIGINS = ["https://footystats.abv.ng", "https://chacha-online.abv.ng", "http://10.197.182.36:3000", "50.117.199.13", "http://code-server.home:3000"]
MOBILE_API_KEY = os.getenv('VALID_MOBILE_API_KEY')


def lambda_handler(event, context):
    print("Event:", json.dumps(event))
    
    # Check if this is a direct Lambda invocation (no API Gateway)
    # This would be the case for background processing
    if 'httpMethod' not in event:
        fixture_id = event.get('fixture_id')
        if not fixture_id:
            print("Error: Missing fixture_id in direct invocation")
            return {'error': 'Missing fixture_id'}
            
        print(f"Direct invocation for fixture_id: {fixture_id}")
        
        # Generate and store the analysis
        analysis = generate_fixture_analysis(fixture_id)
        if analysis:
            return {'success': True, 'fixture_id': fixture_id}
        else:
            return {'error': 'Failed to generate analysis'}
    
    # Regular API Gateway processing
    origin = event['headers'].get('origin', '')
    # Get the API key from the identity in requestContext
    request_context = event.get('requestContext', {})
    identity = request_context.get('identity', {})
    api_key = identity.get('apiKey', '')
    
    # Determine if the origin is allowed
    if origin in ALLOWED_ORIGINS:
        allowed_origin = origin
    elif api_key == MOBILE_API_KEY:
        allowed_origin = "Mobile App"
    else:
        allowed_origin = None  # Block access for disallowed origins
    
    # CORS headers
    cors_headers = {
        'Access-Control-Allow-Origin': allowed_origin if allowed_origin else "null",
        'Access-Control-Allow-Headers': 'content-type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,x-api-key',
        'Access-Control-Allow-Methods': 'OPTIONS,POST',
        'Content-Type': 'application/json; charset=utf-8'
    }
    
    # Handle OPTIONS request
    if event['httpMethod'] == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': cors_headers,
            'body': json.dumps('CORS preflight successful')
        }
    
    # Handle POST request
    if event['httpMethod'] == 'POST':
        if not allowed_origin:
            # Block the request if the origin is not allowed
            return {
                'statusCode': 403,
                'headers': cors_headers,
                'body': json.dumps({'error': 'Forbidden: Origin not allowed'})
            }
        
        if not event.get('body'):
            return {
                'statusCode': 400,
                'headers': cors_headers,
                'body': json.dumps({'error': 'Request body is missing'})
            }
        
        try:
            # Parse the incoming request body
            body = json.loads(event['body'])
            fixture_id = body.get('fixture_id')
            
            # Check if all required fields are provided
            if not fixture_id:
                raise ValueError("Missing required field: 'fixture_id'.")

            try:
                # Convert fixture_id to an integer
                fixture_id = int(fixture_id)
            except ValueError:
                return {
                    'statusCode': 400,
                    'headers': cors_headers,
                    'body': json.dumps({'error': 'fixture_id must be an integer'})
                }           
            
            print(f"Fixture Id: {fixture_id}")
            
            # Check if analysis already exists or claim the work
            try:
                existing_analysis = get_fixture(analysis_table, fixture_id)
                if existing_analysis:
                    analysis_record = existing_analysis[0]
                    status = analysis_record.get('status', 'COMPLETED')  # Default to COMPLETED for legacy records
                    
                    if status == 'COMPLETED':
                        print(f"Completed analysis found for fixture ID: {fixture_id}")
                        analysis_text = analysis_record['text']
                        return {
                            'statusCode': 200,
                            'headers': cors_headers,
                            'body': json.dumps({'analysis': analysis_text}, ensure_ascii=False)
                        }
                    elif status == 'IN_PROGRESS':
                        print(f"Analysis already in progress for fixture ID: {fixture_id}")
                        return {
                            'statusCode': 202,
                            'headers': cors_headers,
                            'body': json.dumps({
                                'message': 'Analysis generation already in progress. Please retry in a few moments.',
                                'fixture_id': fixture_id
                            })
                        }
                
                # No existing record found, try to claim the work
                if claim_analysis_work(fixture_id):
                    print(f"Successfully claimed analysis work for fixture ID: {fixture_id}. Starting generation.")
                    
                    # Invoke this Lambda function directly (without API Gateway)
                    lambda_client = boto3.client('lambda')
                    lambda_client.invoke(
                        FunctionName=context.function_name,
                        InvocationType='Event',  # Asynchronous
                        Payload=json.dumps({'fixture_id': fixture_id})
                    )
                    
                    return {
                        'statusCode': 202,
                        'headers': cors_headers,
                        'body': json.dumps({
                            'message': 'Analysis generation started. Please retry in a few moments.',
                            'fixture_id': fixture_id
                        })
                    }
                else:
                    print(f"Another process already claimed analysis work for fixture ID: {fixture_id}")
                    return {
                        'statusCode': 202,
                        'headers': cors_headers,
                        'body': json.dumps({
                            'message': 'Analysis generation already in progress. Please retry in a few moments.',
                            'fixture_id': fixture_id
                        })
                    }
                    
            except Exception as e:
                print(f"Error checking/claiming analysis work for fixture ID {fixture_id}: {e}")
                raise
                
        except json.JSONDecodeError:
            return {
                'statusCode': 400,
                'headers': cors_headers,
                'body': json.dumps({'error': 'Invalid JSON in request body'})
            }
        except ValueError as e:
            return {
                'statusCode': 400,
                'headers': cors_headers,
                'body': json.dumps({'error': str(e)})
            }
    
    # Fallback response for other methods
    return {
        'statusCode': 405,  # Method not allowed
        'headers': cors_headers,
        'body': json.dumps({'error': 'Method not allowed'})
    }


def make_deepseek_api_call(client, conversations):
    try:
        # Prepare the API call 
        response = client.chat.completions.create(
            temperature=0.9,
            model="deepseek-chat",
            messages=conversations,
            stream=False,
            max_tokens=4000
        )
        print(f"DeepSeek Response: {response}")
        return response.choices[0].message
    except Exception as e:
        print(f"An error occurred during the OpenAI API call: {e}")
        return None


def ask_openai(prompt):
    #print(f'OpenAI Prompt: {prompt}')
    
    message = [
        {"role": "system", "content": [{"type": "text", "text": system_instruction}]},
        {"role": "assistant", "content": [{"type": "text", "text": f"{json.dumps(prompt, default=decimal_default)}"}]},
    ]

    try:
        # Prepare the API call   
        """
        response = client.chat.completions.create(
            model="gpt-5",
            messages=message,
            response_format={
                "type": "text"
            },
            verbosity="medium",
            reasoning_effort="medium"            
        )
        """
        # Prepare the API call   
        payload = {
            "model": "gpt-5",
            "messages": message,
            "verbosity": "medium",
            "reasoning_effort": "medium" 
        }

        headers = {
            "Authorization": f"Bearer {openai_api_key}",
            "Content-Type": "application/json"
        }

        raw_response = requests.post(OPENAI_URL, headers=headers, json=payload)

        if raw_response.status_code != 200:
            print(f"Error {raw_response.status_code}: {raw_response.text}")
            return None

        response = raw_response.json()        
        print(f'OpenAI Response: {response}')
        
        # Extract the actual message content using dot notation
        response_message_content = response["choices"][0]["message"]["content"]

        # Return the serialized content
        #return json.dumps(response_message_content, default=decimal_default)
        return response_message_content
    except Exception as e:
        print(f"An error occurred during the OpenAI o1 API call: {e}")
        return None


def call_groq(prompt):
    #print(f'OpenAI o1 Prompt: {prompt}')
    
    message = [
        {"role": "system", "content": system_instruction},
        {"role": "assistant", "content": f"{json.dumps(prompt, default=decimal_default)}"},
    ]

    try:
        # Prepare the API call   
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=message,
            temperature=1,
            max_completion_tokens=8192,
            top_p=1
        )
        print(f'Groq: {response}')
        
        # Extract the actual message content using dot notation
        response_message_content = response.choices[0].message.content

        # Return the serialized content
        return json.dumps(response_message_content, default=decimal_default)
    except Exception as e:
        print(f"An error occurred during the Groq API call: {e}")
        return None


def call_claude_api(prompt):
    """
    Call the Anthropic Claude API with the given prompt and system prompt.
    Uses a globally initialized client.
    
    Args:
        prompt (str): The user's message to send to Claude
        system_prompt (str, optional): System instructions for Claude. Defaults to "You are a helpful AI assistant."
        
    Returns:
        str: Claude's response text content only
    
    Raises:
        Exception: If the API call fails, the exception is caught and a descriptive message is returned
    """
    try:
        # Call the API using the globally initialized client
        message = claude_client.messages.create(
            model="claude-3-7-sonnet-20250219",
            max_tokens=4000,
            system=system_instruction,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        # Extract just the text from the response
        if message.content and len(message.content) > 0:
            # Check if content is a list of blocks
            if hasattr(message.content[0], 'text'):
                return message.content[0].text
            # Handle string content
            elif isinstance(message.content, str):
                return message.content
            # Fall back to getting the text attribute if it exists
            else:
                return getattr(message.content, 'text', str(message.content))
        
        return "No content returned from API"
    
    except anthropic.APIError as e:
        return f"API Error: {str(e)}"
    
    except anthropic.RateLimitError as e:
        return f"Rate Limit Error: {str(e)}"
    
    except anthropic.APIConnectionError as e:
        return f"API Connection Error: {str(e)}"
    
    except anthropic.AuthenticationError as e:
        return f"Authentication Error: {str(e)}"
    
    except Exception as e:
        return f"Unexpected error occurred: {str(e)}"


def claim_analysis_work(fixture_id):
    """
    Atomically claim analysis work for a fixture using conditional write with TTL.
    Gets the game_time from fixture data to use as timestamp.
    """
    try:
        # First, get the fixture data to extract game_time
        fixture_data = get_fixture(games_table, fixture_id)
        if not fixture_data:
            print(f"No fixture data found for fixture_id: {fixture_id}")
            return False
            
        game_time = fixture_data[0]['timestamp']  # Use the actual game timestamp
        current_time = int(time.time())
        ttl_expiry = current_time + 60  # TTL still based on current time
        
        # Try to create a record with IN_PROGRESS status using game_time as timestamp
        analysis_table.put_item(
            Item={
                'fixture_id': fixture_id,
                'timestamp': game_time,  # Use game_time to match what completion will use
                'status': 'IN_PROGRESS',
                'claimed_at': current_time,
                'ttl': ttl_expiry
            },
            ConditionExpression='attribute_not_exists(fixture_id) AND attribute_not_exists(#ts)',
            ExpressionAttributeNames={'#ts': 'timestamp'}
        )
        return True
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            return False
        else:
            print(f"Error claiming analysis work for fixture {fixture_id}: {e}")
            raise
    except Exception as e:
        print(f"Error getting fixture data for claiming work on {fixture_id}: {e}")
        return False


def get_venue_details(venue_id):
    """
    Fetches details of a football venue by its ID. 

    :param venue_id: The ID of the venue to fetch details for. 
    :return: A dictionary containing venue details or an error message.
    """
    url = "https://api-football-v1.p.rapidapi.com/v3/venues"
    querystring = {"id": str(venue_id)}
    headers = {
        "X-RapidAPI-Key": rapidapi_key,
        "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
    }

    try:
        response = requests.get(url, headers=headers, params=querystring)
        response.raise_for_status()  # Raises an HTTPError if the response was an HTTP error
        data = response.json()
        
        # Check if the response contains venue details
        if data['results'] > 0:
            return data['response'][0]['city']
        else:
            print("No venue found with the provided ID.")
            return None
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


def get_weather_forecast(timestamp, match_venue):
    weather_data = get_weather_data(match_venue)    
    #print(json.dumps(weather_data))

    # Define the range (2 hours before and after the given timestamp)
    two_hours = 2 * 3600  # Two hours in seconds
    start_range = timestamp - two_hours
    end_range = timestamp + two_hours

    # Initialize a dictionary to store the relevant forecasts
    relevant_forecasts = {}

    # Loop through the hourly forecasts
    for forecast in weather_data.get('hourly', []):
        forecast_timestamp = forecast.get('dt')
        # Check if the forecast's timestamp falls within the desired range 
        if start_range <= forecast_timestamp <= end_range:
            str_forecast_timestamp = str(forecast_timestamp)
            relevant_forecasts[str_forecast_timestamp] = forecast['weather']

    return {'weather': relevant_forecasts}


def get_coordinates(location_name):
    base_url = 'http://api.openweathermap.org/geo/1.0/direct'
    params = {
        'q': location_name,
        'limit': 1,  # You may limit to 1 result for accuracy
        'appid': openweather_api_key
    }
    
    response = requests.get(base_url, params=params)
    
    if response.status_code == 200:
        data = response.json()
        if data:
            # Extract latitude and longitude from the first result
            lat = data[0]['lat']
            lon = data[0]['lon']
            return lat, lon
    return None  # Return None if location not found or API request fails

    
def get_weather_data(location_name):
    location_name = location_name.split(',')[0]
    # Validate location_name
    if not location_name.strip():
        return 'Location name is empty or contains only spaces. Please provide a valid location name.'

    coordinates = get_coordinates(location_name)  # This function needs to be defined
    if not coordinates:
        return 'Geolocation Failed! I could not find this location on a MAP.'

    lat, lon = coordinates
    url = 'https://api.openweathermap.org/data/3.0/onecall'
    params = {
        'appid': openweather_api_key,
        'lat': lat,
        'lon': lon,
        'exclude': 'current,minutely,daily,alerts',
        'units': 'metric'
    }

    response = requests.get(url, params=params)
    if response.status_code != 200:
        return f'Failed to get weather data: {response.reason}'

    return response.json()


def get_fixture(table, fixture_id):
    response = table.query(
        KeyConditionExpression=Key('fixture_id').eq(fixture_id),
        Limit=1,
        ScanIndexForward=False  # get the latest messages first
    )
    messages = response['Items'] if 'Items' in response else []
    return messages  # return the whole item, not just the message


def get_team_standing(home_team_id, away_team_id, league_id, season):
    url = "https://api-football-v1.p.rapidapi.com/v3/standings"
    querystring = {
        "league": str(league_id),
        "season": str(season)
    }
    headers = {
        "x-rapidapi-key": rapidapi_key,  # Ensure rapidapi_key is defined
        "x-rapidapi-host": "api-football-v1.p.rapidapi.com"
    }

    response = requests.get(url, headers=headers, params=querystring)
    if response.status_code != 200:
        print(f"API request failed with status code {response.status_code}")
        return {}, {}

    data = response.json()
    if "response" not in data or not data["response"]:
        print("No standings data found.")
        return {}, {}

    try:
        standings_list = data["response"][0]["league"]["standings"][0]
        league_name = data["response"][0]["league"]["name"]
    except (KeyError, IndexError) as e:
        print(f"Unexpected data format: {e}")
        return {}, {}

    total_teams = len(standings_list)
    home_data = None
    away_data = None

    for standing in standings_list:
        team = standing.get("team", {})
        team_id = team.get("id")
        if team_id == home_team_id:
            home_data = {
                "team_name": team.get("name"),
                "league_position": standing.get("rank"),
                "league_points": standing.get("points"),
                "total_teams": total_teams,
                "league_name": league_name
            }
        if team_id == away_team_id:
            away_data = {
                "team_name": team.get("name"),
                "league_position": standing.get("rank"),
                "league_points": standing.get("points"),
                "total_teams": total_teams,
                "league_name": league_name
            }

    if not home_data:
        print(f"Home team with id {home_team_id} not found in standings.")
        home_data = {}
    if not away_data:
        print(f"Away team with id {away_team_id} not found in standings.")
        away_data = {}

    return home_data, away_data


def fetch_from_db(table, key_name, key_value, *, limit=1, newest_first=True):
    """
    grab the most recent (or only) item that matches a key from any dynamodb table

    parameters
    ----------
    table : boto3.resources.factory.dynamodb.Table
        the table object you already got from boto3.resource('dynamodb').Table('my_table')
    key_name : str
        the partition key (exact attribute name) to query on
    key_value : str | int
        the value you’re looking up
    limit : int, default 1
        how many items max to pull back (kept so the helper stays generic)
    newest_first : bool, default True
        if the table also has a sort key (e.g. timestamp), set to True to get the latest record,
        otherwise False to preserve ascending order

    returns
    -------
    dict | None
        the first matching item or None when nothing is found
    """
    try:
        response = table.query(
            KeyConditionExpression=Key(key_name).eq(key_value),
            Limit=limit,
            ScanIndexForward=not newest_first  # True ==> ascending, False ==> descending
        )
    except ClientError as err:
        # bubble up or log as you like; here we re‑raise with extra context
        raise RuntimeError(f"dynamodb query failed: {err.response['Error']['Message']}") from err

    items = response.get("Items", [])
    return items[0] if items else None


def get_home_away_params(league_id, home_team_id, away_team_id, key_name='league_id', team_key_name='id'):
    """
    Retrieves and processes parameters for home and away teams given their IDs and the league ID.
    Returns only evaluation-relevant parameters.

    Uses the fetch_from_db function to retrieve league and team parameters from DynamoDB tables,
    applies any team-specific standard deviation and ratio overrides, and converts DynamoDB decimals to floats.

    Parameters
    ----------
    league_id : str or int
        The primary key identifying the league in league_table.
    home_team_id : str or int
        The key for the home team (used to create a unique_id as "{league_id}-{home_team_id}").
    away_team_id : str or int
        The key for the away team (used to create a unique_id as "{league_id}-{away_team_id}").
    key_name : str, optional
        Attribute name for the partition key in league_table (default "league_id").
    team_key_name : str, optional
        Attribute name for the partition key in teams_table (default "team_id").
    decimal_default : callable, optional
        Function for serializing Decimals, for json.dumps.

    Returns
    -------
    tuple (dict, dict)
        Reduced home and away parameters for evaluation purposes.
    """
    try:
        # Unique Team IDs as in your requirements
        unique_home_id = f"{league_id}-{home_team_id}"
        unique_away_id = f"{league_id}-{away_team_id}"
    except Exception as e:
        print(f"Error constructing unique team IDs: {e}")
        raise RuntimeError("Failed to construct unique team IDs.") from e

    # Fetch home team parameters (fall back to league if not found)
    try:
        home_params = fetch_from_db(
            teams_table, team_key_name, unique_home_id
        )
        print(f'Home Before: {json.dumps(home_params, default=decimal_default)}')
    except Exception as e:
        print(f"Error fetching home team params for unique_home_id={unique_home_id}: {e}")
        raise RuntimeError(f"Failed to fetch home team parameters for {unique_home_id}") from e

    # Fetch away team parameters (fall back to league if not found)
    try:
        away_params = fetch_from_db(
            teams_table, team_key_name, unique_away_id
        )
        print(f'Away Before: {json.dumps(away_params, default=decimal_default)}')
    except Exception as e:
        print(f"Error fetching away team params for unique_away_id={unique_away_id}: {e}")
        raise RuntimeError(f"Failed to fetch away team parameters for {unique_away_id}") from e

    # Extract only evaluation-relevant parameters
    eval_keys = [
        "confidence", "brier", "sample_size", "home_std", "away_std", "total_std",  
        "home_ratio_raw", "away_ratio_raw", "total_ratio_raw", "variance_away", "variance_home"
    ]
    
    def extract_eval_params(params_dict):
        return {key: params_dict[key] for key in eval_keys if key in params_dict}
    
    home_eval_params = extract_eval_params(home_params)
    away_eval_params = extract_eval_params(away_params)
    print(f'Home League: {json.dumps(home_eval_params, default=decimal_default)}')
    print(f'Away League: {json.dumps(away_eval_params, default=decimal_default)}')

    return home_eval_params, away_eval_params


def clean_response_data(data):
    """Build a new dictionary containing only the data needed for threshold calculations."""
    if not isinstance(data, dict):
        return data
    
    # Start with empty result - we'll only add what we need
    result = {}
    
    # Handle the top-level structure
    if 'item' in data:
        item = data['item']
    else:
        item = data
    
    # Build the result structure step by step
    result['item'] = {}
    
    # 1. Extract metadata (optional)
    if 'metadata' in item:
        result['item']['metadata'] = item['metadata']
    
    # 2. Extract league_id (optional)
    if 'league_id' in item:
        result['item']['league_id'] = item['league_id']
    
    # 3. Extract explicit_predictions (REQUIRED)
    if 'explicit_predictions' not in item:
        return result  # Return what we have so far
    
    ep = item['explicit_predictions']
    result['item']['explicit_predictions'] = {}
    
    # 3a. Extract 1X2 outcome accuracy
    if 'outcome_accuracy' in ep and 'accuracy' in ep['outcome_accuracy']:
        result['item']['explicit_predictions']['outcome_accuracy'] = {
            'accuracy': ep['outcome_accuracy']['accuracy']
        }
    
    # 3b. Extract Double Chance from derisked_betting_analysis
    if 'derisked_betting_analysis' in ep:
        dba = ep['derisked_betting_analysis']
        if ('by_prediction_type' in dba and 
            'accuracy' in dba['by_prediction_type']):
            result['item']['explicit_predictions']['double_chance_analysis'] = {
                'by_prediction_type': {
                    'accuracy': dba['by_prediction_type']['accuracy']
                }
            }
    
    # 3c. Extract Over/Under performance summary
    if ('over_under_analysis' in ep and 
        'performance_summary' in ep['over_under_analysis']):
        
        ps = ep['over_under_analysis']['performance_summary']
        result['item']['explicit_predictions']['over_under_analysis'] = {
            'performance_summary': ps  # Keep the entire performance_summary
        }
    
    # 3d. Extract BTTS analysis
    if 'both_teams_score_analysis' in ep:
        btts = ep['both_teams_score_analysis']
        btts_result = {}
        
        # Extract scoring patterns if available
        if 'scoring_patterns' in btts:
            btts_result['scoring_patterns'] = btts['scoring_patterns']
        
        # Extract overall metrics if available
        if 'overall_metrics' in btts:
            btts_result['overall_metrics'] = btts['overall_metrics']
        
        # Only add if we found something
        if btts_result:
            result['item']['explicit_predictions']['both_teams_score_analysis'] = btts_result
    
    return result

def fetch_league_predictions(league_id: int) -> Dict[str, Any]:
    """
    Fetch prediction analysis data for a specific league from the API.
    Args:
        league_id (int): The ID of the league to fetch data for
    Returns:
        Dict[str, Any]: Dictionary containing the API response with prediction analysis data,
                       or empty array if league not found
    Raises:
        requests.RequestException: If there's an error with the HTTP request
        ValueError: If the API returns invalid JSON
    """
    base_url = "https://wa8dxi0u7f.execute-api.eu-west-2.amazonaws.com/default/evaluateCorrectScore"
    params = {
        'league_id': league_id
    }
    
    try:
        response = requests.get(base_url, params=params)
        
        # Handle HTTP 404
        if response.status_code == 404:
            return {}
        
        response.raise_for_status()  # Raises an HTTPError for other bad responses
        data = response.json()
        
        # Handle 404 in JSON response body
        if isinstance(data, dict) and data.get('statusCode') == 404:
            return {}
        
        # Clean all unwanted data in one operation
        data = clean_response_data(data)
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data for league {league_id}: {e}")
        raise
    except ValueError as e:
        print(f"Error parsing JSON response for league {league_id}: {e}")
        raise


def generate_fixture_analysis(fixture_id):
    try:
        print(f"Generating analysis for fixture_id: {fixture_id}")
        
        # Load fixture data
        fixture_data = get_fixture(games_table, fixture_id)
        if not fixture_data:
            print(f"No fixture data found for fixture_id: {fixture_id}")
            return None
            
        fixture_data = fixture_data[0]
        print(json.dumps(fixture_data, default=decimal_default))
        
        # Extract necessary data for analysis
        venue_ids = fixture_data['venue']
        game_time = fixture_data['timestamp']
        game_date = fixture_data['date']
        home_team_id = fixture_data['home']['team_id']
        away_team_id = fixture_data['away']['team_id']
        season = fixture_data['season']
        league_id = fixture_data['league_id']

        # Get weather information at the match venue 
        match_venue = get_venue_details(venue_ids) if venue_ids else None
        if match_venue:
            try:
                match_venue = html.unescape(match_venue)
                print(f"Venue: {json.dumps(match_venue)}")
                
                # Ensure match_venue is a string before splitting
                if isinstance(match_venue, str) and ',' in match_venue:
                    match_venue = match_venue.split(',')[0]
                
                forecast_around_timestamp = get_weather_forecast(game_time, match_venue)
                if forecast_around_timestamp and 'weather' in forecast_around_timestamp:
                    print(json.dumps(forecast_around_timestamp)) 
                    fixture_data['weather'] = forecast_around_timestamp['weather']
            except Exception as e:
                print(f"Warning: Could not get weather information: {e}")

        # Get league position and points
        fixture_data['home']['standing'], fixture_data['away']['standing'] = get_team_standing(home_team_id, away_team_id, league_id, season)
        fixture_data['home']['prediction_accuracy_metrics'], fixture_data['away']['prediction_accuracy_metrics'] = get_home_away_params(league_id, home_team_id, away_team_id)
        fixture_data['league_conformance'] = fetch_league_predictions(league_id)
        #print(json.dumps(fixture_data['league_conformance'], default=decimal_default))

        print(json.dumps(fixture_data, default=decimal_default))

        # Generate analysis using Google Gemini
        response = model.generate_content(f"{json.dumps(fixture_data, default=decimal_default)}")
        response_text = response.candidates[0].content.parts[0].text
        formatted_text = response_text.replace('\n', ' ')

        #response = ask_openai(f"{json.dumps(fixture_data, default=decimal_default)}")
        #print(f"Response: {response}")
        #response_text = response

        # Save analysis to the analysis_table
        try:
            current_time = int(time.time())
            analysis_output = {
                'fixture_id': fixture_id,
                'timestamp': game_time,
                'text': response_text,
                'status': 'COMPLETED',
                'completed_at': current_time,
                'fixture_data': convert_floats_to_decimals(fixture_data)
            }

            # Update the existing record (overwrite the IN_PROGRESS record)
            analysis_table.put_item(Item=analysis_output)
            print(f"Successfully updated analysis in DynamoDB with fixture ID: {fixture_id}")
            
        except Exception as e:
            print(f"Error saving completed analysis for fixture {fixture_id}: {e}")
            # Optionally, you could try to clean up the IN_PROGRESS record here
            raise
        
        return response_text
    except Exception as e:
        print(f"Error generating analysis: {e}")
        return None


# Function to convert Decimal to float for JSON serialization   
def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

def convert_floats_to_decimals(obj):
    if isinstance(obj, float):
        return decimal.Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: convert_floats_to_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimals(v) for v in obj]
    return obj
