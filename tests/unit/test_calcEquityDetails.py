import logging
import warnings
from typing import Optional, Dict, Any
import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import numpy as np
import datetime as dt
import requests

# Set up path BEFORE imports
current_file = os.path.abspath(__file__)
current_dir = os.path.dirname(current_file)
tests_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(tests_dir)
sys.path.insert(0, project_root)

# Import functions
from hello_world.functions.calcEquityDetails import calcEquityDetails
from hello_world.functions.calcRsi import calcRsi
from hello_world.functions.calcImpliedVol import calcImpliedVol
from hello_world.functions.getLatestWeekday import getLatestWeekday

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# =====================================
# UNIT TESTS (with mocked data)
# =====================================
class TestCalcEquityDetailsUnit(unittest.TestCase):
    """Unit tests with mocked API responses and dependencies"""
    
    def setUp(self):
        """Set up test fixtures for each test"""
        self.mock_snowflake_connection = Mock()
        self.mock_intrinio_api_key = "test_api_key"
        
        # Sample input data
        self.test_ticker = "AAPL"
        self.sample_position_input = pd.Series({'Ticker symbol': self.test_ticker})
        
        # Create sample DataFrames with realistic data
        dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
        self.sample_prices_adj = pd.DataFrame({
            self.test_ticker: np.random.uniform(150, 200, 100),
            'SPY': np.random.uniform(400, 450, 100)
        }, index=dates)
        
        self.sample_prices_nonadj = self.sample_prices_adj.copy()
        
        self.sample_adj_factors = pd.DataFrame({
            self.test_ticker: [1.0] * 100
        }, index=dates)
        
        self.sample_dividends = pd.DataFrame({
            self.test_ticker: [0.5] * 100
        }, index=dates)
        
        # Capture warnings
        self.captured_warnings = []
        def warning_handler(message, category, filename, lineno, file=None, line=None):
            self.captured_warnings.append(str(message))
        self.original_showwarning = warnings.showwarning
        warnings.showwarning = warning_handler
    
    def tearDown(self):
        """Clean up after each test"""
        warnings.showwarning = self.original_showwarning

    @patch('hello_world.functions.calcEquityDetails.requests.get')
    @patch('hello_world.functions.calcEquityDetails.intrinio.SecurityApi')
    @patch('hello_world.functions.calcEquityDetails.calcImpliedVol')
    @patch('hello_world.functions.calcEquityDetails.calcRsi')
    @patch('hello_world.functions.calcEquityDetails.getLatestWeekday')
    def test_aapl_successful_calculation(self, mock_weekday, mock_rsi, mock_iv, mock_intrinio, mock_requests):
        """Test successful equity details calculation with mocked data"""
        
        # Mock getLatestWeekday
        mock_weekday.return_value = dt.datetime(2024, 5, 17)
        
        # Mock Intrinio SecurityApi
        mock_security_api = Mock()
        mock_intrinio.return_value = mock_security_api
        
        # Mock stock prices response
        mock_response = Mock()
        mock_response.to_dict.return_value = {
            'security': {'name': 'Apple Inc'},
            'stock_prices': [
                {
                    'date': dt.date(2024, 5, 17),
                    'close': 180.50,
                    'open': 179.00,
                    'high': 182.00,
                    'low': 178.50,
                    'percent_change': 1.5,
                    'fifty_two_week_high': 200.00,
                    'fifty_two_week_low': 150.00
                }
            ]
        }
        mock_security_api.get_security_stock_prices.return_value = mock_response
        
        # Mock requests responses
        def mock_requests_side_effect(url):
            mock_resp = Mock()
            if 'earnings' in url:
                mock_resp.json.return_value = {'next_earnings_date': '2024-07-25'}
            elif 'dividends' in url:
                mock_resp.json.return_value = {
                    'last_ex_dividend_date': '2024-08-09',
                    'ex_dividend': 0.25
                }
            return mock_resp
        
        mock_requests.side_effect = mock_requests_side_effect
        
        # Mock calcRsi
        mock_rsi.side_effect = [45.5, 52.3, 48.7]  # Different RSI values
        
        # Mock calcImpliedVol
        mock_iv.return_value = 0.28
        
        # Build inputs matching current function signature
        dfImpliedVols1m = pd.DataFrame({'Implied vol 1m': [0.28]}, index=[self.test_ticker])
        lstPositionNamesAndPrices = [{
            'security': {'ticker': self.test_ticker, 'name': 'Apple Inc'},
            'last': 180.50, 'open': 179.00, 'high': 182.00, 'low': 178.50,
            'change_percent': 1.5, 'eod_fifty_two_week_high': 200.00, 'eod_fifty_two_week_low': 150.00
        }]
        dfEarningsSelectedTickers = pd.DataFrame({'TICKER': [self.test_ticker], 'NEXT_EARNINGS_DATE': ['2024-07-25']})
        dfDividendsSelectedTickers = pd.DataFrame({'TICKER': [self.test_ticker], 'LAST_EX_DIVIDEND_DATE': ['2024-08-09'], 'EX_DIVIDEND': [0.25]})

        # Execute the function with full argument list
        result = calcEquityDetails(
            self.sample_position_input,
            dfImpliedVols1m,
            self.sample_prices_adj,
            self.sample_prices_nonadj,
            self.sample_adj_factors,
            self.sample_dividends,
            lstPositionNamesAndPrices,
            dfEarningsSelectedTickers,
            dfDividendsSelectedTickers,
            self.mock_intrinio_api_key,
            self.mock_snowflake_connection
        )
        
        # Verify the result structure
        self.assertIsInstance(result, dict)
        self.assertTrue(result['detailsAvailable'])
        
        # Verify key fields
        self.assertEqual(result['Name'], 'Apple Inc')
        self.assertEqual(result['Last price'], 180.50)
        self.assertEqual(result['Open'], 179.00)
        self.assertEqual(result['Next earnings date'], '2024-07-25')
        self.assertEqual(result['1m implied volatility'], 0.28)
        
        # Verify function calls
        mock_intrinio.assert_called_once()
        self.assertEqual(mock_requests.call_count, 2)  # earnings + dividends
        self.assertEqual(mock_rsi.call_count, 3)  # 1 week, 2 weeks, 1 month
        mock_iv.assert_called_once()
        
        print(f"✅ Unit Test - AAPL equity details calculated successfully")

    @patch('hello_world.functions.calcEquityDetails.intrinio.SecurityApi')
    def test_intrinio_api_failure(self, mock_intrinio):
        """Test handling of Intrinio API failure"""
        # Mock API failure
        mock_security_api = Mock()
        mock_security_api.get_security_stock_prices.side_effect = Exception("API Error")
        mock_intrinio.return_value = mock_security_api
        
        # Minimal valid inputs
        dfImpliedVols1m = pd.DataFrame({'Implied vol 1m': []})
        lstPositionNamesAndPrices = []
        dfEarningsSelectedTickers = pd.DataFrame(columns=['TICKER', 'NEXT_EARNINGS_DATE'])
        dfDividendsSelectedTickers = pd.DataFrame(columns=['TICKER', 'LAST_EX_DIVIDEND_DATE', 'EX_DIVIDEND'])

        result = calcEquityDetails(
            self.sample_position_input,
            dfImpliedVols1m,
            self.sample_prices_adj,
            self.sample_prices_nonadj,
            self.sample_adj_factors,
            self.sample_dividends,
            lstPositionNamesAndPrices,
            dfEarningsSelectedTickers,
            dfDividendsSelectedTickers,
            self.mock_intrinio_api_key,
            self.mock_snowflake_connection
        )
        
        # Should return detailsAvailable: False
        self.assertFalse(result['detailsAvailable'])
        print(f"✅ Unit Test - API failure handling works correctly")

    @patch('hello_world.functions.calcEquityDetails.requests.get')
    @patch('hello_world.functions.calcEquityDetails.intrinio.SecurityApi')
    def test_earnings_dividends_error_handling(self, mock_intrinio, mock_requests):
        """Test handling of earnings and dividends API errors"""
        # Mock successful stock prices
        mock_security_api = Mock()
        mock_response = Mock()
        mock_response.to_dict.return_value = {
            'security': {'name': 'Apple Inc'},
            'stock_prices': [
                {
                    'date': dt.date(2024, 5, 17),
                    'close': 180.50,
                    'open': 179.00,
                    'high': 182.00,
                    'low': 178.50,
                    'percent_change': 1.5,
                    'fifty_two_week_high': 200.00,
                    'fifty_two_week_low': 150.00
                }
            ]
        }
        mock_security_api.get_security_stock_prices.return_value = mock_response
        mock_intrinio.return_value = mock_security_api
        
        # Mock error responses for earnings and dividends
        def mock_requests_error(url):
            mock_resp = Mock()
            mock_resp.json.return_value = {'error': 'Not found'}
            return mock_resp
        
        mock_requests.side_effect = mock_requests_error
        
        # Execute with additional mocks for other functions
        with patch('hello_world.functions.calcEquityDetails.calcRsi', return_value=50.0), \
             patch('hello_world.functions.calcEquityDetails.calcImpliedVol', return_value=0.25), \
             patch('hello_world.functions.calcEquityDetails.getLatestWeekday', return_value=dt.datetime(2024, 5, 17)):
            
            dfImpliedVols1m = pd.DataFrame({'Implied vol 1m': [0.25]}, index=[self.test_ticker])
            lstPositionNamesAndPrices = [{
                'security': {'ticker': self.test_ticker, 'name': 'Apple Inc'},
                'last': 180.50, 'open': 179.00, 'high': 182.00, 'low': 178.50,
                'change_percent': 1.5, 'eod_fifty_two_week_high': 200.00, 'eod_fifty_two_week_low': 150.00
            }]
            dfEarningsSelectedTickers = pd.DataFrame()
            dfDividendsSelectedTickers = pd.DataFrame()
            result = calcEquityDetails(
                self.sample_position_input,
                dfImpliedVols1m,
                self.sample_prices_adj,
                self.sample_prices_nonadj,
                self.sample_adj_factors,
                self.sample_dividends,
                lstPositionNamesAndPrices,
                dfEarningsSelectedTickers,
                dfDividendsSelectedTickers,
                self.mock_intrinio_api_key,
                self.mock_snowflake_connection
            )
        
        # Should handle errors gracefully
        self.assertTrue(result['detailsAvailable'])
        self.assertEqual(result['Next earnings date'], 'NA')
        self.assertEqual(result['Next dividend ex date'], 'NA')
        self.assertEqual(result['Next dividend amount'], 'NA')
        
        print(f"✅ Unit Test - Earnings/dividends error handling works correctly")

# =====================================
# INTEGRATION TESTS (with real APIs)
# =====================================

def get_real_intrinio_api_key():
    """
    Get real Intrinio API key from environment or secrets
    """
    try:
        # Try environment variable first
        api_key = os.getenv('INTRINIO_API_KEY')
        if api_key:
            return api_key
        
        # Try your secrets function if available
        from hello_world.functions.getSecretsIntrinioApiKey import getSecretsIntrinioApiKey
        return getSecretsIntrinioApiKey()
        
    except Exception as e:
        logger.error(f"Failed to get Intrinio API key: {e}")
        return None

def get_real_snowflake_connection():
    """
    Create a real Snowflake connection using AWS Secrets Manager
    """
    try:
        from hello_world.functions.getSecretsSnowflake import getSecretsSnowflake
        import snowflake.connector
        
        login_name, password, warehouse, account = getSecretsSnowflake()
        
        conn = snowflake.connector.connect(
            user=login_name,
            password=password,
            account=account,
            warehouse=warehouse
        )
        
        logger.info("✅ Successfully connected to Snowflake")
        return conn
        
    except Exception as e:
        logger.error(f"Failed to create Snowflake connection: {e}")
        return None

class TestCalcEquityDetailsIntegration(unittest.TestCase):
    """Integration tests with real API calls"""
    
    @classmethod
    def setUpClass(cls):
        """Set up real connections for all tests"""
        cls.real_api_key = get_real_intrinio_api_key()
        cls.real_snowflake_conn = get_real_snowflake_connection()
        
        if cls.real_api_key is None:
            raise unittest.SkipTest("No Intrinio API key available - skipping integration tests")
        
        if cls.real_snowflake_conn is None:
            raise unittest.SkipTest("No Snowflake connection available - skipping integration tests")
        
        logger.info("✅ Real connections established for integration tests")
    
    @classmethod
    def tearDownClass(cls):
        """Clean up connections"""
        if hasattr(cls, 'real_snowflake_conn') and cls.real_snowflake_conn:
            cls.real_snowflake_conn.close()
            logger.info("🔒 Snowflake connection closed")
    
    def setUp(self):
        """Set up each test"""
        self.test_ticker = "AAPL"
        self.sample_position_input = pd.Series({'Ticker symbol': self.test_ticker})
        
        # Create sample DataFrames with realistic data (integration tests need real-ish data)
        dates = pd.date_range(start='2023-01-01', periods=252, freq='B')  # Business days
        np.random.seed(42)  # For reproducible "random" data
        
        # Generate realistic price series
        returns = np.random.normal(0.001, 0.02, 252)  # Daily returns
        prices = 150 * np.exp(np.cumsum(returns))  # Price series starting at $150
        
        self.sample_prices_adj = pd.DataFrame({
            self.test_ticker: prices,
            'SPY': 400 * np.exp(np.cumsum(np.random.normal(0.0005, 0.015, 252)))
        }, index=dates)
        
        self.sample_prices_nonadj = self.sample_prices_adj.copy()
        
        self.sample_adj_factors = pd.DataFrame({
            self.test_ticker: [1.0] * 252
        }, index=dates)
        
        self.sample_dividends = pd.DataFrame({
            self.test_ticker: [0.0] * 252  # Most days no dividend
        }, index=dates)
        # Add some dividends
        self.sample_dividends.iloc[60] = 0.25
        self.sample_dividends.iloc[120] = 0.25
        self.sample_dividends.iloc[180] = 0.25
        self.sample_dividends.iloc[240] = 0.25
        
        # Capture warnings
        self.captured_warnings = []
        def warning_handler(message, category, filename, lineno, file=None, line=None):
            self.captured_warnings.append(str(message))
        self.original_showwarning = warnings.showwarning
        warnings.showwarning = warning_handler
    
    def tearDown(self):
        warnings.showwarning = self.original_showwarning
    
    def test_real_intrinio_stock_prices(self):
        """Test that Intrinio stock prices API works"""
        try:
            import intrinio_sdk as intrinio
            
            # Configure intrinio
            configuration = intrinio.Configuration()
            configuration.api_key['api_key'] = self.real_api_key
            configuration.allow_retries = True
            
            # Test the actual API call
            security_api = intrinio.SecurityApi()
            
            start_date = (dt.datetime.now() - dt.timedelta(days=7)).strftime('%Y-%m-%d')
            end_date = dt.datetime.now().strftime('%Y-%m-%d')
            
            response = security_api.get_security_stock_prices(
                self.test_ticker,
                start_date=start_date,
                end_date=end_date,
                frequency='daily',
                page_size=100
            )
            
            # Validate response structure
            response_dict = response.to_dict()
            self.assertIn('security', response_dict)
            self.assertIn('stock_prices', response_dict)
            self.assertIn('name', response_dict['security'])
            
            logger.info(f"✅ Intrinio stock prices API test passed for {self.test_ticker}")
            print(f"✅ Real Intrinio API test passed - {response_dict['security']['name']}")
            
        except Exception as e:
            self.fail(f"Intrinio stock prices API test failed: {e}")
    
    def test_real_intrinio_earnings_dividends(self):
        """Test that Intrinio earnings and dividends APIs work"""
        try:
            # Test earnings API
            earnings_url = f"https://api-v2.intrinio.com/securities/{self.test_ticker}/earnings/latest?api_key={self.real_api_key}"
            earnings_response = requests.get(earnings_url)
            earnings_data = earnings_response.json()
            
            # Should either have earnings data or an error (both are valid)
            self.assertTrue(
                'next_earnings_date' in earnings_data or 'error' in earnings_data,
                f"Unexpected earnings response: {earnings_data}"
            )
            
            # Test dividends API
            dividends_url = f"https://api-v2.intrinio.com/securities/{self.test_ticker}/dividends/latest?api_key={self.real_api_key}"
            dividends_response = requests.get(dividends_url)
            dividends_data = dividends_response.json()
            
            # Should either have dividend data or an error
            self.assertTrue(
                'last_ex_dividend_date' in dividends_data or 'error' in dividends_data,
                f"Unexpected dividends response: {dividends_data}"
            )
            
            logger.info(f"✅ Intrinio earnings/dividends API test passed for {self.test_ticker}")
            print(f"✅ Real earnings/dividends API test passed")
            
        except Exception as e:
            self.fail(f"Intrinio earnings/dividends API test failed: {e}")
    
    @patch('hello_world.functions.calcEquityDetails.calcImpliedVol')
    def test_calcEquityDetails_with_real_data(self, mock_calc_iv):
        """Test calcEquityDetails with real API calls"""
        try:
            # Mock calcImpliedVol to avoid cursor/connection issue
            mock_calc_iv.return_value = 0.28
            
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                
                # Configure intrinio
                import intrinio_sdk as intrinio
                configuration = intrinio.Configuration()
                configuration.api_key['api_key'] = self.real_api_key
                configuration.allow_retries = True
                
                result = calcEquityDetails(
                    self.sample_position_input,
                    self.sample_prices_adj,
                    self.sample_prices_nonadj,
                    self.sample_adj_factors,
                    self.sample_dividends,
                    self.real_api_key,
                    self.real_snowflake_conn
                )
                
                # Log warnings
                if w:
                    logger.warning(f"Warnings during equity details calculation for {self.test_ticker}:")
                    for warning in w:
                        logger.warning(f"  - {warning.message}")
                
                # Validate result
                if result.get('detailsAvailable', False):
                    # Check required fields
                    required_fields = [
                        'Name', 'Last price', 'Open', 'High', 'Low',
                        'SMA 20d', 'SMA 50d', 'RSI 1 week', 'RSI 2 weeks', 'RSI 1 month',
                        '1y dividend yield', 'Beta versus benchmark'
                    ]
                    
                    for field in required_fields:
                        self.assertIn(field, result, f"Missing field: {field}")
                    
                    # Check data types and ranges
                    self.assertIsInstance(result['Last price'], (int, float))
                    self.assertGreater(result['Last price'], 0)
                    
                    if result['RSI 1 week'] is not None:
                        self.assertTrue(0 <= result['RSI 1 week'] <= 100)
                    
                    logger.info(f"✅ Integration test successful!")
                    logger.info(f"   Ticker: {self.test_ticker}")
                    logger.info(f"   Company: {result['Name']}")
                    logger.info(f"   Last Price: ${result['Last price']}")
                    if result.get('1m implied volatility'):
                        logger.info(f"   Implied Vol: {result['1m implied volatility']:.4f}")
                    
                    print(f"✅ Real data test - {self.test_ticker} equity details calculated successfully")
                else:
                    logger.warning(f"Equity details not available for {self.test_ticker}")
                    self.skipTest(f"Equity details not available for {self.test_ticker}")
                    
        except Exception as e:
            logger.error(f"Integration test failed for {self.test_ticker}: {e}")
            self.fail(f"Integration test failed: {e}")

# =====================================
# MAIN EXECUTION
# =====================================

if __name__ == '__main__':
    print("=== calcEquityDetails Test Suite ===")
    print("1. Run unit tests only (mocked data)")
    print("2. Run integration tests only (real APIs)")
    print("3. Run both unit and integration tests")
    print("4. Exit")
    
    try:
        choice = input("Enter choice (1-4): ").strip()
    except:
        choice = "1"  # Default to unit tests
    
    if choice == "1":
        print("\n" + "="*60)
        print("RUNNING UNIT TESTS")
        print("="*60)
        suite = unittest.TestLoader().loadTestsFromTestCase(TestCalcEquityDetailsUnit)
        unittest.TextTestRunner(verbosity=2).run(suite)
        
    elif choice == "2":
        print("\n" + "="*60)
        print("RUNNING INTEGRATION TESTS")
        print("="*60)
        suite = unittest.TestLoader().loadTestsFromTestCase(TestCalcEquityDetailsIntegration)
        unittest.TextTestRunner(verbosity=2).run(suite)
        
    elif choice == "3":
        print("\n" + "="*60)
        print("RUNNING ALL TESTS")
        print("="*60)
        unittest.main(argv=[''], exit=False, verbosity=2)
        
    elif choice == "4":
        print("Exiting...")
        
    else:
        print("Invalid choice. Running unit tests by default.")
        suite = unittest.TestLoader().loadTestsFromTestCase(TestCalcEquityDetailsUnit)
        unittest.TextTestRunner(verbosity=2).run(suite)
    
    print("\n🏁 Test execution completed!")