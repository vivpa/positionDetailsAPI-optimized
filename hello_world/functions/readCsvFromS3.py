import boto3 
import csv 
from io import StringIO 

def readCsvFromS3(bucket, folder, filename): 
    # Create an S3 client 
    s3Client = boto3.client('s3') 
    
    # Construct the S3 object key by combining folder and filename.
    key = f"{folder}/{filename}" if folder else filename
    
    # Retrieve the object from S3
    response = s3Client.get_object(Bucket = bucket, Key = key) 
    
    # Read and decode the CSV file content (assumes UTF-8 encoding)
    csvContent = response['Body'].read().decode('utf-8') 
    
    # Wrap the CSV content string in a StringIO object so it can be read by csv.reader
    csvFile = StringIO(csvContent) 
    
    # Option 1: Use csv.reader if your CSV does not include a header row.
    reader = csv.reader(csvFile) 
    lstRows = [eachRow for eachRow in reader] 
    
    return lstRows 

