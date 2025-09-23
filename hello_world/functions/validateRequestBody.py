import pandas as pd
import datetime
import re

def validateRequestBody(parsedBody):
    # Check if all the required keys are present
    lstRequiredKeys = ['dfInstrumentsDetails'] 
    
    for eachKey in lstRequiredKeys: 
        if eachKey not in parsedBody: 
            error_response = {
                "error": {
                    "type": "ValidationError",
                    "message": f"Missing required key: {eachKey}",
                    "details": {
                        "field": eachKey,
                        "service": "position details api",
                        "component": "request_validation"
                    }
                }
            }
            return False, error_response            

    # Validate dfInstrumentsDetails is a list
    if not isinstance(parsedBody['dfInstrumentsDetails'], list):
        error_response = {
            "error": {
                "type": "ValidationError",
                "message": "dfInstrumentsDetails must be a list",
                "details": {
                    "field": "dfInstrumentsDetails",
                    "service": "position details api",
                    "component": "request_validation"
                }
            }
        }
        return False, error_response

    # Validate dfInstrumentsDetails is not empty
    if len(parsedBody['dfInstrumentsDetails']) == 0:
        error_response = {
            "error": {
                "type": "ValidationError",
                "message": "dfInstrumentsDetails cannot be empty",
                "details": {
                    "field": "dfInstrumentsDetails",
                    "service": "position details api",
                    "component": "request_validation"
                }
            }
        }
        return False, error_response

    lstRequiredFields = ['Ticker symbol', 'Ticker type', 'Ticker position', 'Underlying position', 'Option entry price', 'Option trade date', 'position_detail_id'] 
    
    # Check if all required fields are present in the DataFrame columns
    df = pd.DataFrame(parsedBody['dfInstrumentsDetails'])
    for eachField in lstRequiredFields: 
        if eachField not in list(df.columns): 
            error_response = {
                "error": {
                    "type": "ValidationError",
                    "message": f"Missing required field: {eachField}",
                    "details": {
                        "field": eachField,
                        "service": "position details api",
                        "component": "request_validation"
                    }
                }
            }
            return False, error_response

    # # Validate data types for each row
    # for index, row in df.iterrows():
    #     # Validate Ticker type
    #     COVERED 
    #     if not isinstance(row['Ticker type'], str):
    #         error_response = {
    #             "error": {
    #                 "type": "ValidationError",
    #                 "message": f"Ticker type must be a string. Got {type(row['Ticker type']).__name__} at position {index + 1}",
    #                 "details": {
    #                     "field": "Ticker type",
    #                     "position": index + 1,
    #                     "value": row['Ticker type'],
    #                     "service": "position details api",
    #                     "component": "request_validation"
    #                 }
    #             }
    #         }
    #         return False, error_response

    #     if row['Ticker type'] not in ['Equity', 'Option', 'Other']:
    #         error_response = {
    #             "error": {
    #                 "type": "ValidationError",
    #                 "message": f"Ticker type must be one of ['Equity', 'Option', 'Other']. Got '{row['Ticker type']}' at position {index + 1}",
    #                 "details": {
    #                     "field": "Ticker type",
    #                     "position": index + 1,
    #                     "value": row['Ticker type'],
    #                     "service": "position details api",
    #                     "component": "request_validation"
    #                 }
    #             }
    #         }
    #         return False, error_response

    #     # Validate Ticker symbol
    #     if not isinstance(row['Ticker symbol'], str):
    #         error_response = {
    #             "error": {
    #                 "type": "ValidationError",
    #                 "message": f"Ticker symbol must be a string. Got {type(row['Ticker symbol']).__name__} at position {index + 1}",
    #                 "details": {
    #                     "field": "Ticker symbol",
    #                     "position": index + 1,
    #                     "value": row['Ticker symbol'],
    #                     "service": "position details api",
    #                     "component": "request_validation"
    #                 }
    #             }
    #         }
    #         return False, error_response

    #     if not row['Ticker symbol'].strip():
    #         error_response = {
    #             "error": {
    #                 "type": "ValidationError",
    #                 "message": f"Ticker symbol cannot be empty at position {index + 1}",
    #                 "details": {
    #                     "field": "Ticker symbol",
    #                     "position": index + 1,
    #                     "value": row['Ticker symbol'],
    #                     "service": "position details api",
    #                     "component": "request_validation"
    #                 }
    #             }
    #         }
    #         return False, error_response

    #     # Validate Ticker position
    #     if not isinstance(row['Ticker position'], (int, float)):
    #         error_response = {
    #             "error": {
    #                 "type": "ValidationError",
    #                 "message": f"Ticker position must be a number. Got {type(row['Ticker position']).__name__} at position {index + 1}",
    #                 "details": {
    #                     "field": "Ticker position",
    #                     "position": index + 1,
    #                     "value": row['Ticker position'],
    #                     "service": "position details api",
    #                     "component": "request_validation"
    #                 }
    #             }
    #         }
    #         return False, error_response

    #     if row['Ticker position'] < 0:
    #         error_response = {
    #             "error": {
    #                 "type": "ValidationError",
    #                 "message": f"Ticker position must be positive. Got {row['Ticker position']} at position {index + 1}",
    #                 "details": {
    #                     "field": "Ticker position",
    #                     "position": index + 1,
    #                     "value": row['Ticker position'],
    #                     "service": "position details api",
    #                     "component": "request_validation"
    #                 }
    #             }
    #         }
    #         return False, error_response

    #     # Validate Option trade date
    #     if row['Option trade date'] != 'NA':
    #         if not isinstance(row['Option trade date'], str):
    #             error_response = {
    #                 "error": {
    #                     "type": "ValidationError",
    #                     "message": f"Option trade date must be a string or 'NA'. Got {type(row['Option trade date']).__name__} at position {index + 1}",
    #                     "details": {
    #                         "field": "Option trade date",
    #                         "position": index + 1,
    #                         "value": row['Option trade date'],
    #                         "service": "position details api",
    #                         "component": "request_validation"
    #                     }
    #                 }
    #             }
    #             return False, error_response

    #         # Validate date format YYYY-MM-DD
    #         date_pattern = r'^\d{4}-\d{2}-\d{2}$'
    #         if not re.match(date_pattern, row['Option trade date']):
    #             error_response = {
    #                 "error": {
    #                     "type": "ValidationError",
    #                     "message": f"Option trade date must be in YYYY-MM-DD format or 'NA'. Got '{row['Option trade date']}' at position {index + 1}",
    #                     "details": {
    #                         "field": "Option trade date",
    #                         "position": index + 1,
    #                         "value": row['Option trade date'],
    #                         "service": "position details api",
    #                         "component": "request_validation"
    #                     }
    #                 }
    #             }
    #             return False, error_response

    #         # Validate it's a valid date
    #         try:
    #             datetime.datetime.strptime(row['Option trade date'], '%Y-%m-%d')
    #         except ValueError:
    #             error_response = {
    #                 "error": {
    #                     "type": "ValidationError",
    #                     "message": f"Option trade date is not a valid date. Got '{row['Option trade date']}' at position {index + 1}",
    #                     "details": {
    #                         "field": "Option trade date",
    #                         "position": index + 1,
    #                         "value": row['Option trade date'],
    #                         "service": "position details api",
    #                         "component": "request_validation"
    #                     }
    #                 }
    #             }
    #             return False, error_response

    #     # Validate Option entry price
    #     if row['Option entry price'] != 'NA':
    #         if not isinstance(row['Option entry price'], (int, float)):
    #             error_response = {
    #                 "error": {
    #                     "type": "ValidationError",
    #                     "message": f"Option entry price must be a number or 'NA'. Got {type(row['Option entry price']).__name__} at position {index + 1}",
    #                     "details": {
    #                         "field": "Option entry price",
    #                         "position": index + 1,
    #                         "value": row['Option entry price'],
    #                         "service": "position details api",
    #                         "component": "request_validation"
    #                     }
    #                 }
    #             }
    #             return False, error_response

    #         if row['Option entry price'] < 0:
    #             error_response = {
    #                 "error": {
    #                     "type": "ValidationError",
    #                     "message": f"Option entry price cannot be negative. Got {row['Option entry price']} at position {index + 1}",
    #                     "details": {
    #                         "field": "Option entry price",
    #                         "position": index + 1,
    #                         "value": row['Option entry price'],
    #                         "service": "position details api",
    #                         "component": "request_validation"
    #                     }
    #                 }
    #             }
    #             return False, error_response

    #     # Validate position_detail_id
    #     if not isinstance(row['position_detail_id'], str):
    #         error_response = {
    #             "error": {
    #                 "type": "ValidationError",
    #                 "message": f"position_detail_id must be a string. Got {type(row['position_detail_id']).__name__} at position {index + 1}",
    #                 "details": {
    #                     "field": "position_detail_id",
    #                     "position": index + 1,
    #                     "value": row['position_detail_id'],
    #                     "service": "position details api",
    #                     "component": "request_validation"
    #                 }
    #             }
    #         }
    #         return False, error_response

    #     if not row['position_detail_id'].strip():
    #         error_response = {
    #             "error": {
    #                 "type": "ValidationError",
    #                 "message": f"position_detail_id cannot be empty at position {index + 1}",
    #                 "details": {
    #                     "field": "position_detail_id",
    #                     "position": index + 1,
    #                     "value": row['position_detail_id'],
    #                     "service": "position details api",
    #                     "component": "request_validation"
    #                 }
    #             }
    #         }
    #         return False, error_response

    #     # Validate Underlying position
    #     if row['Underlying position'] != 'NA':
    #         if not isinstance(row['Underlying position'], (int, float)):
    #             error_response = {
    #                 "error": {
    #                     "type": "ValidationError",
    #                     "message": f"Underlying position must be a number or 'NA'. Got {type(row['Underlying position']).__name__} at position {index + 1}",
    #                     "details": {
    #                         "field": "Underlying position",
    #                         "position": index + 1,
    #                         "value": row['Underlying position'],
    #                         "service": "position details api",
    #                         "component": "request_validation"
    #                     }
    #                 }
    #             }
    #             return False, error_response

    #         if row['Underlying position'] < 0:
    #             error_response = {
    #                 "error": {
    #                     "type": "ValidationError",
    #                     "message": f"Underlying position must be positive when not 'NA'. Got {row['Underlying position']} at position {index + 1}",
    #                     "details": {
    #                         "field": "Underlying position",
    #                         "position": index + 1,
    #                         "value": row['Underlying position'],
    #                         "service": "position details api",
    #                         "component": "request_validation"
    #                     }
    #                 }
    #             }
    #             return False, error_response

    # # Check for duplicate position_detail_ids
    # position_ids = df['position_detail_id'].tolist()
    # if len(position_ids) != len(set(position_ids)):
    #     error_response = {
    #         "error": {
    #             "type": "ValidationError",
    #             "message": "Duplicate position_detail_id values found. Each position must have a unique position_detail_id",
    #             "details": {
    #                 "field": "position_detail_id",
    #                 "service": "position details api",
    #                 "component": "request_validation"
    #             }
    #         }
    #     }
    #     return False, error_response

    return True, "Valid request body" 
