import snowflake.connector 
from snowflake.connector.errors import (
    DatabaseError,
    ProgrammingError,
    OperationalError,
    Error  # Base Snowflake exception
) 

# class StockIdNotFoundError(Exception):
#     def __init__(self, ticker):
#         self.ticker = ticker
#         super().__init__(f"Stock ID not found for ticker: {self.ticker}")

def snowflakeIdTestQuery(lstTickers, snowflakeConnection): 
    strTickers = '' 
    for eachTicker in lstTickers: 
        if strTickers != '': 
            strTickers = strTickers + ',' 
        
        strTickers = strTickers + "'" + eachTicker + "'" 

    # Query to fetch stock ID
    query = f"""
    SELECT STOCK_ID, NAME, T_DATE, SYMBOL
    FROM LANDING.RAW_IVOL.STOCKSYMBOL
    WHERE SYMBOL IN ({strTickers})
    ORDER BY T_DATE DESC
    """
    
    # Execute the query
    snowflakeConnection.execute(query)
    
    # Fetch results into a Pandas DataFrame
    df = snowflakeConnection.fetch_pandas_all() 

    dfCleaned = df.dropna(subset = ['STOCK_ID'], how = 'all') 
    dfCleaned = dfCleaned.drop_duplicates(subset = ['SYMBOL']) 

    lstTickersWithIds = list(dfCleaned['SYMBOL']) 

    strTickersWithNoIds = '' 
    for eachTicker in lstTickers: 
        if eachTicker not in lstTickersWithIds: 
            if strTickersWithNoIds != '': 
                strTickersWithNoIds = strTickersWithNoIds + ', ' 
            
            strTickersWithNoIds = strTickersWithNoIds + eachTicker 
    
    if strTickersWithNoIds == '': 
        errorMessage = 'Stock IDs found for all tickers' 
    elif len(lstTickersWithIds) == 0: 
        errorMessage = 'Stock IDs not found for any ticker' 
    else: 
        errorMessage = f'Stock IDs not found for ticker(s) {strTickersWithNoIds}' 

    return dfCleaned, errorMessage 
    
    # # Handle database related errors (e.g. authentication issues) 
    # except DatabaseError as db_err: 
    #     print(f"Database error: {db_err}") 
    #     raise 
    
    # # Handle SQL related errors 
    # except ProgrammingError as sql_err: 
    #     print(f"SQL error: {sql_err}") 
    #     raise 

    # # Handle network related errors 
    # except OperationalError as net_err: 
    #     print(f"Network error: {net_err}") 
    #     raise 
    
    # # Catch any other Snowflake related errors
    # except Error as generic_sf_err: 
    #     print(f"Snowflake generic error: {generic_sf_err}") 
    #     raise 
    
    # # Catch any generic errors 
    # except Exception as generic_err: 
    #     print(f"Unexpected error: {generic_err}") 
    #     raise 
