import snowflake.connector 
from snowflake.connector.errors import (
    DatabaseError,
    ProgrammingError,
    OperationalError,
    Error  # Base Snowflake exception
) 

# Custom exception for IV query issues 
class IvolQueryError(Exception): 
    def __init__(self, tickerSymbol, symbols, startDate, endDate): 
        self.tickerSymbol = tickerSymbol 
        self.symbols = symbols 
        self.startDate = startDate 
        self.endDate = endDate 
        print(f"Failed to fetch IV data for symbols: {self.tickerSymbol} between {self.startDate} and {self.endDate}") 

# Function to query Snowflake for implied volatility 
def snowflakeIvolQueries(tickerSymbol, symbols, startDate, endDate, snowflakeConnection): 
    try:
        # Query to fetch implied volatility
        query = f""" 
        SELECT T_DATE, STOCK_ID, PERIOD, CALL_PUT, IV, STRIKE, OTM 
        FROM LANDING.RAW_IVOL.V_IV_SURFACE_HISTORICAL 
        WHERE STOCK_ID = '{symbols}' 
        AND T_DATE >= '{startDate}' 
        AND T_DATE <= '{endDate}' 
        AND PERIOD IN (7, 14, 21, 30, 60, 90, 180, 270, 360) 
        ORDER BY T_DATE DESC 
        """ 
        
        # Execute the query 
        snowflakeConnection.execute(query) 
        
        # Fetch results into a Pandas DataFrame
        df = snowflakeConnection.fetch_pandas_all() 
        
        # Check if the dataframe is empty
        if df.empty: 
            raise IvolQueryError(tickerSymbol, symbols, startDate, endDate) 
        
        return df 
    
    # Handle database related errors (e.g. authentication issues) 
    except DatabaseError as db_err: 
        print(f"Database error: {db_err}") 
        # raise 
    
    # Handle SQL related errors 
    except ProgrammingError as sql_err: 
        print(f"SQL error: {sql_err}") 
        # raise 
    
    # Handle network related errors 
    except OperationalError as net_err: 
        print(f"Network error: {net_err}") 
        # raise 
    
    # Catch any other Snowflake related errors 
    except Error as generic_sf_err: 
        print(f"Snowflake generic error: {generic_sf_err}") 
        # raise 
    
    # Catch any generic errors
    except Exception as generic_err: 
        print(f"Unexpected error: {generic_err}") 
        # raise 
