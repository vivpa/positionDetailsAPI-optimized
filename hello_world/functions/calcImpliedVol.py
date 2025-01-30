import datetime as dt 

from functions.snowflakeIdTestQuery import snowflakeIdTestQuery 
from functions.snowflakeIvolQueries import snowflakeIvolQueries 

def calcImpliedVol(tickerSymbol, lastPrice, snowflakeConnection): 
    # Extracting stock ID for the relevant ticker 
    dfResults = snowflakeIdTestQuery(tickerSymbol.strip(), snowflakeConnection) 
    stockId = dfResults['STOCK_ID'].iloc[0] 
    
    # Extracting implied vol for the relevant ticker 
    startDate = (dt.datetime.now() - dt.timedelta(days = 30)).strftime("%Y%m%d") 
    endDate = dt.datetime.now().strftime("%Y%m%d") 
    dfImpVol = snowflakeIvolQueries(str(stockId), startDate, endDate, snowflakeConnection) 
    dfImpVol = dfImpVol.drop_duplicates() 
    
    maxDate = dfImpVol['T_DATE'].max() 
    dfImpVol1m = dfImpVol[(dfImpVol['T_DATE'] == maxDate) & (dfImpVol['PERIOD'] == 30)] 
    
    impliedVolAtm1m = dfImpVol1m[dfImpVol1m['OTM'] == 0]['IV'].mean() 
    
    return impliedVolAtm1m 
