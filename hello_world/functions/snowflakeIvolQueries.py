import numpy as np 
import pandas as pd 
import snowflake.connector 
from snowflake.connector.errors import (
    DatabaseError,
    ProgrammingError,
    OperationalError,
    Error  # Base Snowflake exception
) 

# # Custom exception for IV query issues 
# class IvolQueryError(Exception): 
#     def __init__(self, tickerSymbol, symbols, startDate, endDate): 
#         self.tickerSymbol = tickerSymbol 
#         self.symbols = symbols 
#         self.startDate = startDate 
#         self.endDate = endDate 
#         print(f"Failed to fetch IV data for symbols: {self.tickerSymbol} between {self.startDate} and {self.endDate}") 
#         return f"Failed to fetch IV data for symbols: {self.tickerSymbol} between {self.startDate} and {self.endDate}" 

# Function to query Snowflake for implied volatility 
def snowflakeIvolQueries(dfSnowflakeIds, lstEquityTickers, startDate, endDate, snowflakeConnection): 
    strStockIds = '' 
    for eachIndex in dfSnowflakeIds.index: 
        if strStockIds != '': 
            strStockIds = strStockIds + ',' 
        
        strStockIds = strStockIds + "'" + str(dfSnowflakeIds.loc[eachIndex, 'STOCK_ID']) + "'" 

    # Query to fetch implied volatility
    query = f""" 
    SELECT T_DATE, STOCK_ID, PERIOD, CALL_PUT, IV, STRIKE, OTM 
    FROM LANDING.RAW_IVOL.V_IV_SURFACE_HISTORICAL 
    WHERE STOCK_ID IN ({strStockIds}) 
    AND T_DATE >= '{startDate}' 
    AND T_DATE <= '{endDate}' 
    AND PERIOD IN (30) 
    ORDER BY T_DATE DESC 
    """ 
    
    # Execute the query 
    snowflakeConnection.execute(query) 
    
    # Fetch results into a Pandas DataFrame
    dfImpliedVols = snowflakeConnection.fetch_pandas_all() 
    
    # # Check if the dataframe is empty
    # if df.empty: 
    #     raise IvolQueryError(tickerSymbol, symbols, startDate, endDate) 
    
    strTickersWithNoImpliedVols = '' 
    dfImpliedVolsOutput = pd.DataFrame(index = lstEquityTickers, columns = ['Stock ID', 'Implied vol 1m']) 
    for eachTicker in lstEquityTickers: 
        if eachTicker in list(dfSnowflakeIds['SYMBOL'].unique()): 
            eachStockId = dfSnowflakeIds[dfSnowflakeIds['SYMBOL'] == eachTicker]['STOCK_ID'].iloc[0] 
            dfImpliedVolForTicker = dfImpliedVols[dfImpliedVols['STOCK_ID'] == eachStockId].copy() 

            maxDateForTicker = dfImpliedVolForTicker['T_DATE'].max() 

            dfImpliedVolForTicker = dfImpliedVolForTicker[dfImpliedVolForTicker['T_DATE'] == maxDateForTicker] 

            impliedVolAtm1m = dfImpliedVolForTicker[dfImpliedVolForTicker['OTM'] == 0]['IV'].mean() 

            dfImpliedVolsOutput.loc[eachTicker, 'Stock ID'] = eachStockId 
            dfImpliedVolsOutput.loc[eachTicker, 'Implied vol 1m'] = impliedVolAtm1m 
        else: 
            dfImpliedVolsOutput.loc[eachTicker, 'Stock ID'] = np.nan 
            dfImpliedVolsOutput.loc[eachTicker, 'Implied vol 1m'] = np.nan 

            if strTickersWithNoImpliedVols != '': 
                strTickersWithNoImpliedVols = strTickersWithNoImpliedVols + ', ' 
            
            strTickersWithNoImpliedVols = strTickersWithNoImpliedVols + eachTicker 

    if strTickersWithNoImpliedVols == '': 
        errorMessage = 'Stock IDs found for all tickers' 
    else: 
        errorMessage = f'Stock IDs not found for ticker(s) {strTickersWithNoImpliedVols}' 

    return dfImpliedVolsOutput, errorMessage 
    
    # # Handle database related errors (e.g. authentication issues) 
    # except DatabaseError as db_err: 
    #     print(f"Database error: {db_err}") 
    #     return f"Failed to fetch IV data for symbols: {tickerSymbol}" 
    #     # raise 
    
    # # Handle SQL related errors 
    # except ProgrammingError as sql_err: 
    #     print(f"SQL error: {sql_err}") 
    #     return f"Failed to fetch IV data for symbols: {tickerSymbol}" 
    #     # raise 
    
    # # Handle network related errors 
    # except OperationalError as net_err: 
    #     print(f"Network error: {net_err}") 
    #     return f"Failed to fetch IV data for symbols: {tickerSymbol}" 
    #     # raise 
    
    # # Catch any other Snowflake related errors 
    # except Error as generic_sf_err: 
    #     print(f"Snowflake generic error: {generic_sf_err}") 
    #     return f"Failed to fetch IV data for symbols: {tickerSymbol}" 
    #     # raise 
    
    # # Catch any generic errors
    # except Exception as generic_err: 
    #     print(f"Unexpected error: {generic_err}") 
    #     return f"Failed to fetch IV data for symbols: {tickerSymbol}" 
    #     # raise 
