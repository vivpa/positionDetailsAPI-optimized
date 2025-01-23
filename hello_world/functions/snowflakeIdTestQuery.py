import snowflake.connector 
from snowflake.connector.errors import (
    DatabaseError,
    ProgrammingError,
    OperationalError,
    Error  # Base Snowflake exception
) 

class StockIdNotFoundError(Exception):
    def __init__(self, ticker):
        self.ticker = ticker
        super().__init__(f"Stock ID not found for ticker: {self.ticker}")

def snowflakeIdTestQuery(ticker, snowflakeConnection): 
    try: 
        # Query to fetch stock ID
        query = f"""
        SELECT STOCK_ID, NAME, T_DATE, SYMBOL
        FROM LANDING.RAW_IVOL.STOCKSYMBOL
        WHERE SYMBOL = '{ticker}'
        ORDER BY T_DATE DESC
        LIMIT 1
        """
        
        # Execute the query
        snowflakeConnection.execute(query)
        
        # Fetch results into a Pandas DataFrame
        df = snowflakeConnection.fetch_pandas_all()
        
        # Check if the DataFrame is empty
        if df.empty:
            raise StockIdNotFoundError(ticker)
        
        return df
    
    # Handle database related errors (e.g. authentication issues) 
    except DatabaseError as db_err: 
        print(f"Database error: {db_err}") 
        raise 
    
    # Handle SQL related errors 
    except ProgrammingError as sql_err: 
        print(f"SQL error: {sql_err}") 
        raise 

    # Handle network related errors 
    except OperationalError as net_err: 
        print(f"Network error: {net_err}") 
        raise 
    
    # Catch any other Snowflake related errors
    except Error as generic_sf_err: 
        print(f"Snowflake generic error: {generic_sf_err}") 
        raise 
    
    # Catch any generic errors 
    except Exception as generic_err: 
        print(f"Unexpected error: {generic_err}") 
        raise 
