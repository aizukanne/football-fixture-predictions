"""
API Gateway Deployment Script
Deploy and configure API Gateway for the prediction API service.
"""

import boto3
import json
import os
import argparse
from typing import Dict, Any, Optional
from ..utils.constants import API_GATEWAY_CONFIG, ENVIRONMENT


class APIGatewayDeployer:
    """Deploy and configure API Gateway for the prediction service."""

    def __init__(self, region_name: str = 'eu-west-2', environment: str = None):
        self.region_name = region_name
        self.environment = environment or ENVIRONMENT
        self.apigateway = boto3.client('apigateway', region_name=region_name)
        self.lambda_client = boto3.client('lambda', region_name=region_name)
        self.iam = boto3.client('iam', region_name=region_name)

    def create_or_get_api(self, api_name: str = None) -> str:
        """
        Create REST API in API Gateway or get existing one.

        Args:
            api_name: Name of the API

        Returns:
            str: API ID
        """
        if api_name is None:
            api_name = f'football-predictions-api-{self.environment}'

        try:
            # Check if API already exists
            existing_apis = self.apigateway.get_rest_apis()
            for api in existing_apis.get('items', []):
                if api['name'] == api_name:
                    print(f"Found existing API: {api['id']} - {api['name']}")
                    return api['id']

            # Create new API
            response = self.apigateway.create_rest_api(
                name=api_name,
                description=f'Football Prediction API for mobile and web applications ({self.environment})',
                endpointConfiguration={
                    'types': ['REGIONAL']
                },
                tags={
                    'Environment': self.environment,
                    'Service': 'football-predictions',
                    'Component': 'api-gateway'
                }
            )

            api_id = response['id']
            print(f"Created API Gateway: {api_id} - {api_name}")
            return api_id

        except Exception as e:
            print(f"Error creating API Gateway: {e}")
            raise

    def setup_resources_and_methods(self, api_id: str, lambda_function_arn: str) -> Dict:
        """
        Set up API resources, methods, and integrations.

        Args:
            api_id: API Gateway ID
            lambda_function_arn: ARN of the Lambda function

        Returns:
            Dict: Resource and method configuration
        """
        try:
            # Get root resource
            resources = self.apigateway.get_resources(restApiId=api_id)
            root_resource_id = None

            for resource in resources['items']:
                if resource['path'] == '/':
                    root_resource_id = resource['id']
                    break

            if not root_resource_id:
                raise Exception("Root resource not found")

            # Check if /predictions resource already exists
            predictions_resource_id = None
            for resource in resources['items']:
                if resource.get('pathPart') == 'predictions':
                    predictions_resource_id = resource['id']
                    print(f"Found existing /predictions resource: {predictions_resource_id}")
                    break

            # Create /predictions resource if it doesn't exist
            if not predictions_resource_id:
                predictions_resource = self.apigateway.create_resource(
                    restApiId=api_id,
                    parentId=root_resource_id,
                    pathPart='predictions'
                )
                predictions_resource_id = predictions_resource['id']
                print(f"Created /predictions resource: {predictions_resource_id}")

            # Set up GET method
            try:
                self.apigateway.put_method(
                    restApiId=api_id,
                    resourceId=predictions_resource_id,
                    httpMethod='GET',
                    authorizationType='NONE',
                    apiKeyRequired=True,  # Require API key
                    requestParameters={
                        'method.request.querystring.country': False,
                        'method.request.querystring.league': False,
                        'method.request.querystring.fixture_id': False,
                        'method.request.querystring.startDate': False,
                        'method.request.querystring.endDate': False,
                        'method.request.querystring.limit': False
                    }
                )
                print("Created GET method on /predictions")
            except self.apigateway.exceptions.ConflictException:
                print("GET method already exists on /predictions")

            # Set up Lambda integration
            integration_uri = f"arn:aws:apigateway:{self.region_name}:lambda:path/2015-03-31/functions/{lambda_function_arn}/invocations"

            try:
                self.apigateway.put_integration(
                    restApiId=api_id,
                    resourceId=predictions_resource_id,
                    httpMethod='GET',
                    type='AWS_PROXY',
                    integrationHttpMethod='POST',
                    uri=integration_uri
                )
                print("Created Lambda integration for GET method")
            except self.apigateway.exceptions.ConflictException:
                print("Lambda integration already exists for GET method")

            # Set up OPTIONS method for CORS
            try:
                self.apigateway.put_method(
                    restApiId=api_id,
                    resourceId=predictions_resource_id,
                    httpMethod='OPTIONS',
                    authorizationType='NONE',
                    apiKeyRequired=False
                )
                print("Created OPTIONS method for CORS")
            except self.apigateway.exceptions.ConflictException:
                print("OPTIONS method already exists")

            # Set up OPTIONS integration for CORS
            try:
                self.apigateway.put_integration(
                    restApiId=api_id,
                    resourceId=predictions_resource_id,
                    httpMethod='OPTIONS',
                    type='MOCK',
                    requestTemplates={
                        'application/json': '{"statusCode": 200}'
                    }
                )

                # Set up OPTIONS method response
                self.apigateway.put_method_response(
                    restApiId=api_id,
                    resourceId=predictions_resource_id,
                    httpMethod='OPTIONS',
                    statusCode='200',
                    responseParameters={
                        'method.response.header.Access-Control-Allow-Origin': True,
                        'method.response.header.Access-Control-Allow-Headers': True,
                        'method.response.header.Access-Control-Allow-Methods': True
                    }
                )

                # Set up OPTIONS integration response
                self.apigateway.put_integration_response(
                    restApiId=api_id,
                    resourceId=predictions_resource_id,
                    httpMethod='OPTIONS',
                    statusCode='200',
                    responseParameters={
                        'method.response.header.Access-Control-Allow-Origin': "'*'",
                        'method.response.header.Access-Control-Allow-Headers': "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'",
                        'method.response.header.Access-Control-Allow-Methods': "'OPTIONS,GET'"
                    }
                )
                print("Configured CORS for OPTIONS method")
            except self.apigateway.exceptions.ConflictException:
                print("CORS configuration already exists for OPTIONS method")

            # Grant Lambda permission for API Gateway invocation
            self._grant_lambda_permission(lambda_function_arn, api_id)

            return {
                'predictions_resource_id': predictions_resource_id,
                'api_id': api_id
            }

        except Exception as e:
            print(f"Error setting up resources and methods: {e}")
            raise

    def _grant_lambda_permission(self, lambda_function_arn: str, api_id: str):
        """Grant API Gateway permission to invoke Lambda function."""
        try:
            function_name = lambda_function_arn.split(':')[-1]
            statement_id = f"AllowAPIGatewayInvoke-{self.environment}"

            # Try to add permission (will fail if it already exists)
            try:
                self.lambda_client.add_permission(
                    FunctionName=function_name,
                    StatementId=statement_id,
                    Action='lambda:InvokeFunction',
                    Principal='apigateway.amazonaws.com',
                    SourceArn=f"arn:aws:execute-api:{self.region_name}:*:{api_id}/*/*/*"
                )
                print(f"Granted Lambda permission for API Gateway invocation")
            except self.lambda_client.exceptions.ResourceConflictException:
                print(f"Lambda permission already exists")

        except Exception as e:
            print(f"Error granting Lambda permission: {e}")
            # Don't raise - permission might already exist

    def create_usage_plan_and_api_key(self, api_id: str, stage_name: str = 'prod') -> Dict:
        """
        Create usage plan and API key for rate limiting and access control.

        Args:
            api_id: API Gateway ID
            stage_name: Deployment stage name

        Returns:
            Dict: Usage plan and API key information
        """
        try:
            usage_plan_name = f'football-predictions-usage-plan-{self.environment}'
            api_key_name = f'football-predictions-mobile-key-{self.environment}'

            # Check if usage plan already exists
            existing_usage_plans = self.apigateway.get_usage_plans()
            usage_plan_id = None
            for plan in existing_usage_plans.get('items', []):
                if plan['name'] == usage_plan_name:
                    usage_plan_id = plan['id']
                    print(f"Found existing usage plan: {usage_plan_id}")
                    break

            # Create usage plan if it doesn't exist
            if not usage_plan_id:
                usage_plan = self.apigateway.create_usage_plan(
                    name=usage_plan_name,
                    description=f'Usage plan for football predictions API ({self.environment})',
                    apiStages=[{
                        'apiId': api_id,
                        'stage': stage_name
                    }],
                    throttle={
                        'rateLimit': API_GATEWAY_CONFIG['rate_limit'],
                        'burstLimit': API_GATEWAY_CONFIG['burst_limit']
                    },
                    quota={
                        'limit': API_GATEWAY_CONFIG['quota_limit'],
                        'period': API_GATEWAY_CONFIG['quota_period']
                    }
                )
                usage_plan_id = usage_plan['id']
                print(f"Created usage plan: {usage_plan_id}")

            # Check if API key already exists
            existing_api_keys = self.apigateway.get_api_keys()
            api_key_id = None
            api_key_value = None
            for key in existing_api_keys.get('items', []):
                if key['name'] == api_key_name:
                    api_key_id = key['id']
                    api_key_value = key.get('value', 'HIDDEN - retrieve from AWS Console')
                    print(f"Found existing API key: {api_key_id}")
                    break

            # Create API key if it doesn't exist
            if not api_key_id:
                api_key_response = self.apigateway.create_api_key(
                    name=api_key_name,
                    description=f'API key for mobile and web applications ({self.environment})',
                    enabled=True,
                    tags={
                        'Environment': self.environment,
                        'Service': 'football-predictions'
                    }
                )
                api_key_id = api_key_response['id']
                api_key_value = api_key_response['value']
                print(f"Created API key: {api_key_id}")

            # Associate API key with usage plan
            try:
                self.apigateway.create_usage_plan_key(
                    usagePlanId=usage_plan_id,
                    keyId=api_key_id,
                    keyType='API_KEY'
                )
                print(f"Associated API key with usage plan")
            except self.apigateway.exceptions.ConflictException:
                print(f"API key already associated with usage plan")

            return {
                'usage_plan_id': usage_plan_id,
                'api_key_id': api_key_id,
                'api_key_value': api_key_value
            }

        except Exception as e:
            print(f"Error creating usage plan and API key: {e}")
            raise

    def deploy_api(self, api_id: str, stage_name: str = 'prod') -> str:
        """
        Deploy API to a stage.

        Args:
            api_id: API Gateway ID
            stage_name: Stage name for deployment

        Returns:
            str: API endpoint URL
        """
        try:
            # Create deployment
            deployment = self.apigateway.create_deployment(
                restApiId=api_id,
                stageName=stage_name,
                description=f'{stage_name.capitalize()} deployment of football predictions API ({self.environment})'
            )

            print(f"Created deployment: {deployment['id']}")

            # Get API endpoint URL
            endpoint_url = f"https://{api_id}.execute-api.{self.region_name}.amazonaws.com/{stage_name}"

            print(f"API deployed to: {endpoint_url}")
            return endpoint_url

        except Exception as e:
            print(f"Error deploying API: {e}")
            raise

    def export_configuration(self, config: Dict, output_file: str = None):
        """
        Export API Gateway configuration to JSON file.

        Args:
            config: Configuration dictionary
            output_file: Output file path
        """
        if output_file is None:
            output_file = f'api_gateway_config_{self.environment}.json'

        try:
            with open(output_file, 'w') as f:
                json.dump(config, f, indent=2, default=str)
            print(f"Configuration exported to: {output_file}")
        except Exception as e:
            print(f"Error exporting configuration: {e}")


def deploy_complete_api_gateway(lambda_function_arn: str, region: str = 'eu-west-2',
                                environment: str = None, stage_name: str = 'prod') -> Dict:
    """
    Deploy complete API Gateway setup.

    Args:
        lambda_function_arn: ARN of the Lambda function
        region: AWS region
        environment: Environment name (dev, staging, prod)
        stage_name: API Gateway stage name

    Returns:
        Dict: Complete deployment information
    """
    deployer = APIGatewayDeployer(region_name=region, environment=environment)

    try:
        print("=" * 60)
        print(f"DEPLOYING API GATEWAY FOR ENVIRONMENT: {deployer.environment}")
        print("=" * 60)

        # Step 1: Create API
        print("\n[1/5] Creating/Getting API Gateway...")
        api_id = deployer.create_or_get_api()

        # Step 2: Set up resources and methods
        print("\n[2/5] Setting up resources and methods...")
        resources = deployer.setup_resources_and_methods(api_id, lambda_function_arn)

        # Step 3: Deploy API
        print("\n[3/5] Deploying API to stage...")
        endpoint_url = deployer.deploy_api(api_id, stage_name)

        # Step 4: Create usage plan and API key
        print("\n[4/5] Creating usage plan and API key...")
        usage_plan_info = deployer.create_usage_plan_and_api_key(api_id, stage_name)

        # Step 5: Export configuration
        print("\n[5/5] Exporting configuration...")
        config = {
            'environment': deployer.environment,
            'region': region,
            'api_id': api_id,
            'endpoint_url': endpoint_url,
            'predictions_endpoint': f"{endpoint_url}/predictions",
            'stage_name': stage_name,
            'usage_plan_id': usage_plan_info['usage_plan_id'],
            'api_key_id': usage_plan_info['api_key_id'],
            'api_key_value': usage_plan_info['api_key_value'],
            'lambda_function_arn': lambda_function_arn
        }

        deployer.export_configuration(config)

        print("\n" + "=" * 60)
        print("API GATEWAY DEPLOYMENT COMPLETE!")
        print("=" * 60)
        print(f"\nAPI Endpoint: {config['predictions_endpoint']}")
        print(f"API Key: {usage_plan_info['api_key_value']}")
        print(f"\nConfiguration saved to: api_gateway_config_{deployer.environment}.json")
        print("\n" + "=" * 60)

        return config

    except Exception as e:
        print(f"\n❌ Error deploying complete API Gateway: {e}")
        raise


def main():
    """Main entry point for CLI usage."""
    parser = argparse.ArgumentParser(
        description='Deploy API Gateway for Football Predictions API'
    )
    parser.add_argument(
        '--lambda-arn',
        required=True,
        help='ARN of the Lambda function for API service'
    )
    parser.add_argument(
        '--region',
        default='eu-west-2',
        help='AWS region (default: eu-west-2)'
    )
    parser.add_argument(
        '--environment',
        '-e',
        default=None,
        help='Environment (dev, staging, prod). Defaults to ENVIRONMENT env var'
    )
    parser.add_argument(
        '--stage',
        default='prod',
        help='API Gateway stage name (default: prod)'
    )

    args = parser.parse_args()

    try:
        result = deploy_complete_api_gateway(
            lambda_function_arn=args.lambda_arn,
            region=args.region,
            environment=args.environment,
            stage_name=args.stage
        )
        print("\n✅ Deployment successful!")
        return 0
    except Exception as e:
        print(f"\n❌ Deployment failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
