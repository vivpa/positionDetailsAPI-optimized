import boto3 
from botocore.exceptions import ClientError 
import json 

def getSecretsIntrinioApiKey(): 
    secretName = "INTRINIO_API_KEY" 
    regionName = "us-west-2" 
    
    # Create a Secrets Manager client 
    session = boto3.session.Session() 
    client = session.client( 
        service_name = 'secretsmanager', 
        region_name = regionName 
    ) 

    try: 
        get_secret_value_response = client.get_secret_value( 
            SecretId = secretName 
        ) 
    
    except ClientError as e: 
        # For a list of exceptions thrown, see 
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html 
        raise e 

    # Decrypts secret using the associated KMS key.
    strSecret = get_secret_value_response['SecretString'] 
    dictSecret = json.loads(strSecret) 
    
    return dictSecret['INTRINIO_API_KEY'] 
