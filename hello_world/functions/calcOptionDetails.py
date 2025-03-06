import datetime as dt 
import intrinio_sdk as intrinio 
import pandas as pd 
import requests 

from functions.computeOptionValues import computeOptionValues 
from functions.getLatestWeekday import getLatestWeekday 
from functions.retrieveIntrinioStockPrices import retrieveIntrinioStockPrices 

def calcOptionDetails(serPositionsDetailsInput, intrinioApiKey, snowflakeConnection): 
    source = '' 
    stockPriceSource = '' 
    model = '' 
    showExtendedPrice = '' 

    if serPositionsDetailsInput['Ticker symbol'].find(' ') != -1: 
        tickerRevised = serPositionsDetailsInput['Ticker symbol'].replace(' ', '') 
    else: 
        tickerRevised = serPositionsDetailsInput['Ticker symbol'] 

    responseOptionDetails = intrinio.OptionsApi().get_options_prices_realtime(tickerRevised, source = source, stock_price_source = stockPriceSource, model = model, show_extended_price = showExtendedPrice) 
    dictResponseOptionDetails = responseOptionDetails.to_dict() 
    
    dictDetailsOutput = {} 
    dictDetailsOutput['Option underlying ticker'] = dictResponseOptionDetails['option']['ticker'] 
    
    startDate = (dt.datetime.now() - dt.timedelta(days = 5)).strftime('%Y-%m-%d') 
    endDate = dt.datetime.now().strftime('%Y-%m-%d') 
    frequency = 'daily' 
    pageSize = 100 
    nextPage = '' 
    responseEquityPrices = intrinio.SecurityApi().get_security_stock_prices(dictDetailsOutput['Option underlying ticker'], start_date = startDate, end_date = endDate, frequency = frequency, page_size = pageSize, next_page = nextPage) 
    dictResponseEquityPrices = responseEquityPrices.to_dict() 
    
    dictDetailsOutput['Option underlying name'] = dictResponseEquityPrices['security']['name']     # To be done further 
    dictDetailsOutput['Option underlying price'] = dictResponseOptionDetails['stats']['underlying_price'] 
    dictDetailsOutput['Option type'] = dictResponseOptionDetails['option']['type'] 
    dictDetailsOutput['Option expiry'] = pd.to_datetime(dictResponseOptionDetails['option']['expiration']).strftime('%Y-%m-%d') 
    dictDetailsOutput['Option strike'] = dictResponseOptionDetails['option']['strike'] 
    
    # Methodology to be fixed for deliverableMultiplier - Vivek seeking details from ivol 
    dictDetailsOutput['Deliverable multiplier'] = 100.0 
    
    dictDetailsOutput['Last price'] = dictResponseOptionDetails['price']['last'] 
    dictDetailsOutput['Last size'] = dictResponseOptionDetails['price']['last_size'] 
    dictDetailsOutput['Ask'] = dictResponseOptionDetails['price']['ask'] 
    dictDetailsOutput['Ask size'] = dictResponseOptionDetails['price']['ask_size'] 
    dictDetailsOutput['Bid'] = dictResponseOptionDetails['price']['bid'] 
    dictDetailsOutput['Bid size'] = dictResponseOptionDetails['price']['bid_size'] 
    dictDetailsOutput['Mid'] = (dictDetailsOutput['Ask'] + dictDetailsOutput['Bid']) / 2 
    dictDetailsOutput['Option implied volatility'] = dictResponseOptionDetails['stats']['implied_volatility'] 
    dictDetailsOutput['Option moneyness'] = dictDetailsOutput['Option underlying price'] / dictDetailsOutput['Option strike'] 
    dictDetailsOutput['Option days till expiration'] = (dictResponseOptionDetails['option']['expiration'] - dt.datetime.now().date()).days 
    dictDetailsOutput['Option delta'] = dictResponseOptionDetails['stats']['delta'] 
    dictDetailsOutput['Option gamma'] = dictResponseOptionDetails['stats']['gamma'] 
    dictDetailsOutput['Option theta'] = dictResponseOptionDetails['stats']['theta'] 
    dictDetailsOutput['Option vega'] = dictResponseOptionDetails['stats']['vega'] 
    if dictDetailsOutput['Option delta'] == None: 
        dictDetailsOutput['Option OTM probability'] = 'NA' 
    else: 
        dictDetailsOutput['Option OTM probability'] = 1 - dictDetailsOutput['Option delta'] 
    
    responseEarnings = requests.get(f"https://api-v2.intrinio.com/securities/{dictDetailsOutput['Option underlying ticker']}/earnings/latest?api_key={intrinioApiKey}") 
    dictResponseEarnings = responseEarnings.json() 
    if 'error' in dictResponseEarnings.keys(): 
        dictDetailsOutput['Next earnings date'] = 'NA' 
    else: 
        dictDetailsOutput['Next earnings date'] = dictResponseEarnings['next_earnings_date'] 
    
    responseDividends = requests.get(f"https://api-v2.intrinio.com/securities/{dictDetailsOutput['Option underlying ticker']}/dividends/latest?api_key={intrinioApiKey}") 
    dictResponseDividends = responseDividends.json() 
    if 'error' in dictResponseDividends.keys(): 
        dictDetailsOutput['Next dividend ex date'] = 'NA' 
        dictDetailsOutput['Next dividend amount'] = 'NA' 
    else: 
        latestExDividendDate = dictResponseDividends['last_ex_dividend_date'] 
        if pd.to_datetime(latestExDividendDate, format = '%Y-%m-%d') > dt.datetime.now() - dt.timedelta(days = 1): 
            dictDetailsOutput['Next dividend ex date'] = dictResponseDividends['next_earnings_date'] 
            dictDetailsOutput['Next dividend amount'] = dictResponseDividends['ex_dividend'] 
        else: 
            dictDetailsOutput['Next dividend ex date'] = 'NA' 
            dictDetailsOutput['Next dividend amount'] = 'NA' 
    
    # Option rho to be done later, Rajeev working on the model for option exercise probability 
    # optionRho = TBC 
    # optionExerciseProbability = TBC 
    
    # Calculation of option exercise value 
    optionWeekdaysTillExpiration = int(dictDetailsOutput['Option days till expiration'] * 5 / 7) 
    
    numOfYearsForDataExtraction = 5 
    endDate = dt.datetime.now() 
    endDate = getLatestWeekday(endDate) 
    startDate = endDate - dt.timedelta(days = numOfYearsForDataExtraction * 365) 
    startDate = getLatestWeekday(startDate) 
    
    # Data for SPY extracted to calculate the beta 
    # Needs to be made dynamic to deal with fixed income underlyings as well 
    benchmarkTicker = 'SPY' 
    
    dfPricesFinal = retrieveIntrinioStockPrices([dictDetailsOutput['Option underlying ticker'], benchmarkTicker], startDate, endDate, 'adjclose', snowflakeConnection) 
    dfPricesFinal.index = pd.to_datetime(dfPricesFinal.index) 
    dfReturnsData = (dfPricesFinal / dfPricesFinal.shift(optionWeekdaysTillExpiration) - 1).dropna() 
    
    dfPricesFinalNonAdj, dfAdjFactors = retrieveIntrinioStockPrices([dictDetailsOutput['Option underlying name'], benchmarkTicker], startDate, endDate, 'close', snowflakeConnection) 
    dfPricesFinalNonAdj.index = pd.to_datetime(dfPricesFinalNonAdj.index) 
    
    # Rebasing the non-adjusted prices to start from the startDate 
    dfPricesFinalNonAdj = dfPricesFinalNonAdj[dfPricesFinalNonAdj.index >= startDate].copy() 
    
    # Calculating the cumulative adjustment factors 
    dfCumuAdjFactors = dfAdjFactors.sort_index(ascending = False) 
    dfCumuAdjFactors = dfCumuAdjFactors.cumprod() 
    dfCumuAdjFactors = dfCumuAdjFactors.sort_index(ascending = True) 
    dfCumuAdjFactors = dfCumuAdjFactors.shift(-1).ffill() 
    
    dfDividendsNonAdj = retrieveIntrinioStockPrices([dictDetailsOutput['Option underlying ticker']], startDate, endDate, 'dividend', snowflakeConnection) 
    
    # Calculating the split adjusted dividends 
    dfDividendsSplitAdj = (dfDividendsNonAdj * dfCumuAdjFactors).dropna(how = 'all') 
    
    # Calculation of the option's expected value 
    lstPercentiles = [0.01 * i for i in range(101)] 
    dfReturnsDistribution = pd.DataFrame(index = lstPercentiles, columns = ['Underlying return', 'Underlying price', 'Option payoff']) 
    for eachPercentile in lstPercentiles: 
        dfReturnsDistribution.loc[eachPercentile, 'Underlying return'] = dfReturnsData[dictDetailsOutput['Option underlying ticker']].quantile(eachPercentile) 
        dfReturnsDistribution.loc[eachPercentile, 'Underlying price'] = dictDetailsOutput['Option underlying price'] * (1 + dfReturnsDistribution.loc[eachPercentile, 'Underlying return']) 
        
        if dictDetailsOutput['Option type'].lower() == 'call': 
            dfReturnsDistribution.loc[eachPercentile, 'Option payoff'] = max(0, dfReturnsDistribution.loc[eachPercentile, 'Underlying price'] - dictDetailsOutput['Option strike']) 
        elif dictDetailsOutput['Option type'].lower() == 'put': 
            dfReturnsDistribution.loc[eachPercentile, 'Option payoff'] = max(0, dictDetailsOutput['Option strike'] - dfReturnsDistribution.loc[eachPercentile, 'Underlying price']) 
    
    dictDetailsOutput['Option expected value'] = dfReturnsDistribution.loc[eachPercentile, 'Option payoff'].mean() 
    
    # Calculating the relevant quantities if the options position is available 
    if serPositionsDetailsInput.loc['Ticker position'] != 'NA': 
        dictDetailsOutput['Total shares deliverable'] = serPositionsDetailsInput['Ticker position'] * dictDetailsOutput['Deliverable multiplier'] 
        dictDetailsOutput['Total option notional'] = dictDetailsOutput['Total shares deliverable'] * dictDetailsOutput['Option underlying price'] 
        dictDetailsOutput['Total delta'] = 'NA' if dictDetailsOutput['Option delta'] == None else dictDetailsOutput['Option delta'] * dictDetailsOutput['Total shares deliverable'] 
        dictDetailsOutput['Total gamma'] = 'NA' if dictDetailsOutput['Option gamma'] == None else dictDetailsOutput['Option gamma'] * dictDetailsOutput['Total shares deliverable'] 
        dictDetailsOutput['Total theta'] = 'NA' if dictDetailsOutput['Option theta'] == None else dictDetailsOutput['Option theta'] * dictDetailsOutput['Total shares deliverable'] 
        dictDetailsOutput['Total vega'] = 'NA' if dictDetailsOutput['Option vega'] == None else dictDetailsOutput['Option vega'] * dictDetailsOutput['Total shares deliverable'] 
        
        if serPositionsDetailsInput['Underlying position'] != 'NA': 
            dictDetailsOutput['Coverage ratio'] = dictDetailsOutput['Total shares deliverable'] / serPositionsDetailsInput['Underlying position'] 
            dictDetailsOutput['Covered call delta'] = 1 - dictDetailsOutput['Coverage ratio'] * dictDetailsOutput['Option delta'] 
            
            # Calculation of beta versus benchmark 
            dfReturns = (dfPricesFinal / dfPricesFinal.shift(1) - 1).dropna() 
            dfCovMatrix = dfReturns.cov() 
            
            betaVsBenchmark = dfCovMatrix.loc[dictDetailsOutput['Option underlying ticker'], benchmarkTicker] / dfReturns.std()[benchmarkTicker] ** 2 
            
            dictDetailsOutput['Covered call beta'] = dictDetailsOutput['Covered call delta'] * betaVsBenchmark 
            dictDetailsOutput['Total covered call delta'] = dictDetailsOutput['Covered call delta'] * dictDetailsOutput['Total shares deliverable'] 
            dictDetailsOutput['Total covered call beta'] = dictDetailsOutput['Covered call beta'] * dictDetailsOutput['Total shares deliverable'] 
    
    if serPositionsDetailsInput['Option trade date'] != 'NA': 
        tradeDate = pd.to_datetime(serPositionsDetailsInput['Option trade date'], format = '%Y-%m-%d').date() 
        underlyingPriceTradeDate = dfPricesFinal[dfPricesFinal.index <= pd.to_datetime(tradeDate)][dictDetailsOutput['Option underlying ticker']].iloc[-1] 
        if 'Option entry price' in serPositionsDetailsInput.index: 
            dictDetailsOutput['Annualized premium at inception'] = (serPositionsDetailsInput['Option entry price'] / underlyingPriceTradeDate) * (365 / (pd.to_datetime(dictResponseOptionDetails['option']['expiration']).date() - tradeDate).days) 
    
    date1yAgo = endDate - dt.timedelta(days = 365) 
    dividendsLast1y = dfDividendsSplitAdj[dfDividendsSplitAdj.index >= date1yAgo][dictDetailsOutput['Option underlying ticker']].sum() 
    
    # Calculating intrinsic value, time value and whether or not the option is likely to be early exercised 
    # Expected dividend over the next year would be the same as the dividend over the last 1y multiplied by the number of years to maturity 
    daysToMaturity = (pd.to_datetime(dictDetailsOutput['Option expiry'], format = '%Y-%m-%d') - endDate).days 
    expectedDividend = dividendsLast1y * daysToMaturity / 365.0 
    intrinsicValue, timeValue, earlyExercise = computeOptionValues(dictDetailsOutput['Option type'], dictDetailsOutput['Option underlying price'], dictDetailsOutput['Option strike'], dictDetailsOutput['Mid'], expectedDividend) 
    
    dictDetailsOutput['Intrinsic value'] = intrinsicValue 
    dictDetailsOutput['Time value'] = timeValue 
    dictDetailsOutput['Early exercise'] = earlyExercise 
    
    return dictDetailsOutput 
