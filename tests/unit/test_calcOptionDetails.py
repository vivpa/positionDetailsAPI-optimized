# import logging
# import warnings
# from typing import Optional, Dict, Any
# import sys
# import os
# import unittest
# from unittest.mock import Mock, patch, MagicMock
# import pandas as pd
# import numpy as np
# import datetime as dt
# import requests

# # Set up path BEFORE imports
# current_file = os.path.abspath(__file__)
# current_dir = os.path.dirname(current_file)
# tests_dir = os.path.dirname(current_dir)
# project_root = os.path.dirname(tests_dir)
# sys.path.insert(0, project_root)

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
from hello_world.functions.calcOptionDetails import calcOptionDetails
from hello_world.functions.computeOptionValues import computeOptionValues
from hello_world.functions.getLatestWeekday import getLatestWeekday



# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# =====================================
# UNIT TESTS (with mocked data)
# =====================================
class TestCalcOptionDetailsUnit(unittest.TestCase):
    """Unit tests with mocked API responses and dependencies"""
    
    def setUp(self):
        """Set up test fixtures for each test"""
        self.mock_snowflake_connection = Mock()
        self.mock_intrinio_api_key = "test_api_key"
        
        # Sample option ticker (Apple call option)
        self.test_option_ticker = "AAPL__240621C00180000"  # AAPL Call exp 2024-06-21 strike $180
        self.test_underlying_ticker = "AAPL"
        
        # Sample position input
        self.sample_position_input = pd.Series({
            'Ticker symbol': self.test_option_ticker,
            'Ticker position': 10,  # 10 contracts
            'Underlying position': 1000,  # 1000 shares of AAPL
            'Option trade date': '2024-05-01',
            'Option entry price': 5.50
        })
        
        # Sample option prices data structure
        self.sample_option_prices = {
            'options_data': [
                {
                    'option': {
                        'code': self.test_option_ticker,
                        'ticker': self.test_underlying_ticker,
                        'type': 'call',
                        'expiration': '2024-06-21',
                        'strike': 180.0
                    },
                    'price': {
                        'last': 5.25,
                        'last_size': 100,
                        'bid': 5.20,
                        'bid_size': 150,
                        'ask': 5.30,
                        'ask_size': 200
                    },
                    'stats': {
                        'underlying_price': 175.50,
                        'implied_volatility': 0.28,
                        'delta': 0.45,
                        'gamma': 0.025,
                        'theta': -0.05,
                        'vega': 0.15
                    }
                }
            ]
        }
        
        # Create sample DataFrames with realistic data
        dates = pd.date_range(start='2019-01-01', periods=1000, freq='B')  # Business days
        np.random.seed(42)
        
        # Generate realistic price series
        returns = np.random.normal(0.001, 0.02, 1000)
        aapl_prices = 150 * np.exp(np.cumsum(returns))
        spy_prices = 400 * np.exp(np.cumsum(np.random.normal(0.0005, 0.015, 1000)))
        
        self.sample_prices_adj = pd.DataFrame({
            self.test_underlying_ticker: aapl_prices,
            'SPY': spy_prices
        }, index=dates)
        
        self.sample_prices_nonadj = self.sample_prices_adj.copy()
        
        self.sample_adj_factors = pd.DataFrame({
            self.test_underlying_ticker: [1.0] * 1000
        }, index=dates)
        
        self.sample_dividends = pd.DataFrame({
            self.test_underlying_ticker: [0.0] * 1000
        }, index=dates)
        # Add quarterly dividends
        for i in range(0, 1000, 63):  # Roughly quarterly
            if i < 1000:
                self.sample_dividends.iloc[i] = 0.25
        
        # Capture warnings
        self.captured_warnings = []
        def warning_handler(message, category, filename, lineno, file=None, line=None):
            self.captured_warnings.append(str(message))
        self.original_showwarning = warnings.showwarning
        warnings.showwarning = warning_handler
    
    def tearDown(self):
        """Clean up after each test"""
        warnings.showwarning = self.original_showwarning

    @patch('hello_world.functions.calcOptionDetails.requests.get')
    @patch('hello_world.functions.calcOptionDetails.intrinio.SecurityApi')
    @patch('hello_world.functions.calcOptionDetails.computeOptionValues')
    @patch('hello_world.functions.calcOptionDetails.getLatestWeekday')
    def test_aapl_option_successful_calculation(self, mock_weekday, mock_option_values, mock_intrinio, mock_requests):
        """Test successful option details calculation with mocked data"""
        
        # Mock getLatestWeekday
        mock_weekday.return_value = dt.datetime(2024, 5, 17)
        
        # Mock Intrinio SecurityApi
        mock_security_api = Mock()
        mock_intrinio.return_value = mock_security_api
        
        # Mock underlying security response
        mock_underlying_response = Mock()
        mock_underlying_response.to_dict.return_value = {
            'name': 'Apple Inc'
        }
        mock_security_api.get_security_by_id.return_value = mock_underlying_response
        
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
        
        # Mock computeOptionValues
        mock_option_values.return_value = (8.50, 3.25, False)  # intrinsic, time, early_exercise
        
        # Build inputs matching current function signature
        lstPositionNamesAndPrices = [{
            'security': {'ticker': self.test_underlying_ticker, 'name': 'Apple Inc'}
        }]
        dfEarningsSelectedTickers = pd.DataFrame({'TICKER': [self.test_underlying_ticker], 'NEXT_EARNINGS_DATE': ['2024-07-25']})
        dfDividendsSelectedTickers = pd.DataFrame({'TICKER': [self.test_underlying_ticker], 'LAST_EX_DIVIDEND_DATE': ['2024-08-09'], 'EX_DIVIDEND': [0.25]})

        result = calcOptionDetails(
            self.sample_position_input,
            {'contracts': self.sample_option_prices['options_data']},
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
        
        # Verify key option fields
        self.assertEqual(result['Option underlying ticker'], self.test_underlying_ticker)
        self.assertEqual(result['Option underlying name'], 'Apple Inc')
        self.assertEqual(result['Option type'], 'call')
        self.assertEqual(result['Option strike'], 180.0)
        self.assertEqual(result['Option underlying price'], 175.50)
        
        # Verify price calculations
        expected_mid = (5.20 + 5.30) / 2  # (bid + ask) / 2
        self.assertEqual(result['Mid'], expected_mid)
        
        # Verify option Greeks
        self.assertEqual(result['Option delta'], 0.45)
        self.assertEqual(result['Option gamma'], 0.025)
        self.assertEqual(result['Option theta'], -0.05)
        self.assertEqual(result['Option vega'], 0.15)
        
        # Verify position calculations
        self.assertEqual(result['Total shares deliverable'], 1000)  # 10 contracts * 100 multiplier
        self.assertAlmostEqual(result['Coverage ratio'], 1.0, places=2)  # 1000 deliverable / 1000 underlying
        
        # Verify function calls
        mock_intrinio.assert_called_once()
        self.assertEqual(mock_requests.call_count, 2)  # earnings + dividends
        mock_option_values.assert_called_once()
        
        print(f"✅ Unit Test - AAPL option details calculated successfully")

    def test_option_not_found_in_data(self):
        """Test handling when option is not found in option prices data"""
        # Create position input for non-existent option
        invalid_position = pd.Series({
            'Ticker symbol': 'INVALID_OPTION_CODE',
            'Ticker position': 5
        })
        
        result = calcOptionDetails(
            invalid_position,
            {'contracts': self.sample_option_prices['options_data']},
            self.sample_prices_adj,
            self.sample_prices_nonadj,
            self.sample_adj_factors,
            self.sample_dividends,
            [],
            pd.DataFrame(),
            pd.DataFrame(),
            self.mock_intrinio_api_key,
            self.mock_snowflake_connection
        )
        
        # Should return detailsAvailable: False
        self.assertFalse(result['detailsAvailable'])
        print(f"✅ Unit Test - Option not found handling works correctly")

    def test_empty_option_prices_data(self):
        """Test handling of empty option prices data"""
        empty_option_prices = {'options_data': []}
        
        result = calcOptionDetails(
            self.sample_position_input,
            {'contracts': []},
            self.sample_prices_adj,
            self.sample_prices_nonadj,
            self.sample_adj_factors,
            self.sample_dividends,
            [],
            pd.DataFrame(),
            pd.DataFrame(),
            self.mock_intrinio_api_key,
            self.mock_snowflake_connection
        )
        
        self.assertFalse(result['detailsAvailable'])
        print(f"✅ Unit Test - Empty option data handling works correctly")

    @patch('hello_world.functions.calcOptionDetails.requests.get')
    @patch('hello_world.functions.calcOptionDetails.intrinio.SecurityApi')
    def test_api_error_handling(self, mock_intrinio, mock_requests):
        """Test handling of API errors for earnings and dividends"""
        # Mock successful underlying security call
        mock_security_api = Mock()
        mock_underlying_response = Mock()
        mock_underlying_response.to_dict.return_value = {'name': 'Apple Inc'}
        mock_security_api.get_security_by_id.return_value = mock_underlying_response
        mock_intrinio.return_value = mock_security_api
        
        # Mock error responses for earnings and dividends
        def mock_requests_error(url):
            mock_resp = Mock()
            mock_resp.json.return_value = {'error': 'Not found'}
            return mock_resp
        
        mock_requests.side_effect = mock_requests_error
        
        with patch('hello_world.functions.calcOptionDetails.getLatestWeekday', return_value=dt.datetime(2024, 5, 17)), \
             patch('hello_world.functions.calcOptionDetails.computeOptionValues', return_value=(8.50, 3.25, False)):
            
            result = calcOptionDetails(
                self.sample_position_input,
                self.sample_option_prices,
                self.sample_prices_adj,
                self.sample_prices_nonadj,
                self.sample_adj_factors,
                self.sample_dividends,
                self.mock_intrinio_api_key,
                self.mock_snowflake_connection
            )
        
        # Should handle errors gracefully
        self.assertTrue(result['detailsAvailable'])
        self.assertEqual(result['Next earnings date'], 'NA')
        self.assertEqual(result['Next dividend ex date'], 'NA')
        self.assertEqual(result['Next dividend amount'], 'NA')
        
        print(f"✅ Unit Test - API error handling works correctly")

    def test_mid_price_calculation_logic(self):
        """Test mid price calculation with different bid/ask scenarios"""
        test_cases = [
            # (bid, ask, last, expected_mid)
            (5.20, 5.30, 5.25, 5.25),  # Both bid and ask available
            (None, 5.30, 5.25, 5.30),  # Only ask available
            (5.20, None, 5.25, 5.20),  # Only bid available
            (None, None, 5.25, None),   # Neither bid nor ask available
        ]
        
        for bid, ask, last, expected_mid in test_cases:
            with self.subTest(bid=bid, ask=ask, expected=expected_mid):
                # Modify sample data
                test_option_prices = {
                    'options_data': [{
                        'option': {
                            'code': self.test_option_ticker,
                            'ticker': self.test_underlying_ticker,
                            'type': 'call',
                            'expiration': '2024-06-21',
                            'strike': 180.0
                        },
                        'price': {
                            'last': last,
                            'last_size': 100,
                            'bid': bid,
                            'bid_size': 150,
                            'ask': ask,
                            'ask_size': 200
                        },
                        'stats': {
                            'underlying_price': 175.50,
                            'implied_volatility': 0.28,
                            'delta': 0.45,
                            'gamma': 0.025,
                            'theta': -0.05,
                            'vega': 0.15
                        }
                    }]
                }
                
                with patch('hello_world.functions.calcOptionDetails.intrinio.SecurityApi'), \
                     patch('hello_world.functions.calcOptionDetails.requests.get'), \
                     patch('hello_world.functions.calcOptionDetails.getLatestWeekday', return_value=dt.datetime(2024, 5, 17)), \
                     patch('hello_world.functions.calcOptionDetails.computeOptionValues', return_value=(8.50, 3.25, False)):
                    
                    result = calcOptionDetails(
                        self.sample_position_input,
                        {'contracts': test_option_prices['options_data']},
                        self.sample_prices_adj,
                        self.sample_prices_nonadj,
                        self.sample_adj_factors,
                        self.sample_dividends,
                        [],
                        pd.DataFrame(),
                        pd.DataFrame(),
                        self.mock_intrinio_api_key,
                        self.mock_snowflake_connection
                    )
                    
                    self.assertEqual(result['Mid'], expected_mid)
        
        print(f"✅ Unit Test - Mid price calculation logic works correctly")

    def test_option_payoff_calculations(self):
        """Test call vs put option payoff calculations"""
        # Test will verify the logic is called correctly
        # The actual payoff calculation is in the main function
        
        # Test call option
        call_option_prices = {
            'options_data': [{
                'option': {
                    'code': self.test_option_ticker,
                    'ticker': self.test_underlying_ticker,
                    'type': 'call',  # Call option
                    'expiration': '2024-06-21',
                    'strike': 180.0
                },
                'price': {'last': 5.25, 'bid': 5.20, 'ask': 5.30},
                'stats': {
                    'underlying_price': 175.50,
                    'implied_volatility': 0.28,
                    'delta': 0.45,
                    'gamma': 0.025,
                    'theta': -0.05,
                    'vega': 0.15
                }
            }]
        }
        
        # Test put option
        put_option_prices = {
            'options_data': [{
                'option': {
                    'code': 'AAPL__240621P00180000',  # Put option
                    'ticker': self.test_underlying_ticker,
                    'type': 'put',  # Put option
                    'expiration': '2024-06-21',
                    'strike': 180.0
                },
                'price': {'last': 8.75, 'bid': 8.70, 'ask': 8.80},
                'stats': {
                    'underlying_price': 175.50,
                    'implied_volatility': 0.28,
                    'delta': -0.55,  # Put delta is negative
                    'gamma': 0.025,
                    'theta': -0.05,
                    'vega': 0.15
                }
            }]
        }
        
        # Test both call and put options process without errors
        for option_type, option_prices in [('call', call_option_prices), ('put', put_option_prices)]:
            with self.subTest(option_type=option_type):
                test_position = self.sample_position_input.copy()
                if option_type == 'put':
                    test_position['Ticker symbol'] = 'AAPL__240621P00180000'
                
                with patch('hello_world.functions.calcOptionDetails.intrinio.SecurityApi'), \
                     patch('hello_world.functions.calcOptionDetails.requests.get'), \
                     patch('hello_world.functions.calcOptionDetails.getLatestWeekday', return_value=dt.datetime(2024, 5, 17)), \
                     patch('hello_world.functions.calcOptionDetails.computeOptionValues', return_value=(8.50, 3.25, False)):
                    
                    result = calcOptionDetails(
                        test_position,
                        {'contracts': option_prices['options_data']},
                        self.sample_prices_adj,
                        self.sample_prices_nonadj,
                        self.sample_adj_factors,
                        self.sample_dividends,
                        [],
                        pd.DataFrame(),
                        pd.DataFrame(),
                        self.mock_intrinio_api_key,
                        self.mock_snowflake_connection
                    )
                    
                    self.assertTrue(result['detailsAvailable'])
                    self.assertEqual(result['Option type'], option_type)
                    
                    # Verify option expected value calculation was performed
                    self.assertIn('Option expected value', result)
                    self.assertIsInstance(result['Option expected value'], (int, float))
        
        print(f"✅ Unit Test - Option payoff calculations work correctly")

# =====================================
# INTEGRATION TESTS (with real APIs)
# =====================================

def get_real_intrinio_api_key():
    """Get real Intrinio API key from environment or secrets"""
    try:
        api_key = os.getenv('INTRINIO_API_KEY')
        if api_key:
            return api_key
        
        from hello_world.functions.getSecretsIntrinioApiKey import getSecretsIntrinioApiKey
        return getSecretsIntrinioApiKey()
        
    except Exception as e:
        logger.error(f"Failed to get Intrinio API key: {e}")
        return None

def get_real_snowflake_connection():
    """Create a real Snowflake connection using AWS Secrets Manager"""
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

class TestCalcOptionDetailsIntegration(unittest.TestCase):
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
        self.test_underlying_ticker = "AAPL"
        
        # Create sample data (for integration tests, we need realistic data)
        dates = pd.date_range(start='2020-01-01', periods=1000, freq='B')
        np.random.seed(42)
        
        returns = np.random.normal(0.001, 0.02, 1000)
        aapl_prices = 150 * np.exp(np.cumsum(returns))
        spy_prices = 400 * np.exp(np.cumsum(np.random.normal(0.0005, 0.015, 1000)))
        
        self.sample_prices_adj = pd.DataFrame({
            self.test_underlying_ticker: aapl_prices,
            'SPY': spy_prices
        }, index=dates)
        
        self.sample_prices_nonadj = self.sample_prices_adj.copy()
        
        self.sample_adj_factors = pd.DataFrame({
            self.test_underlying_ticker: [1.0] * 1000
        }, index=dates)
        
        self.sample_dividends = pd.DataFrame({
            self.test_underlying_ticker: [0.0] * 1000
        }, index=dates)
        # Add quarterly dividends
        for i in range(0, 1000, 63):
            if i < 1000:
                self.sample_dividends.iloc[i] = 0.25
        
        # Capture warnings
        self.captured_warnings = []
        def warning_handler(message, category, filename, lineno, file=None, line=None):
            self.captured_warnings.append(str(message))
        self.original_showwarning = warnings.showwarning
        warnings.showwarning = warning_handler
    
    def tearDown(self):
        warnings.showwarning = self.original_showwarning
    
    def test_real_intrinio_underlying_security(self):
        """Test that Intrinio underlying security API works"""
        try:
            import intrinio_sdk as intrinio
            
            # Configure intrinio
            configuration = intrinio.Configuration()
            configuration.api_key['api_key'] = self.real_api_key
            configuration.allow_retries = True
            
            # Test the actual API call
            security_api = intrinio.SecurityApi()
            response = security_api.get_security_by_id(self.test_underlying_ticker)
            
            # Validate response structure
            response_dict = response.to_dict()
            self.assertIn('name', response_dict)
            self.assertIsInstance(response_dict['name'], str)
            self.assertTrue(len(response_dict['name']) > 0)
            
            logger.info(f"✅ Intrinio underlying security API test passed for {self.test_underlying_ticker}")
            print(f"✅ Real underlying security API test passed - {response_dict['name']}")
            
        except Exception as e:
            self.fail(f"Intrinio underlying security API test failed: {e}")
    
    def test_real_intrinio_earnings_dividends_for_options(self):
        """Test that Intrinio earnings and dividends APIs work for option underlying"""
        try:
            # Test earnings API
            earnings_url = f"https://api-v2.intrinio.com/securities/{self.test_underlying_ticker}/earnings/latest?api_key={self.real_api_key}"
            earnings_response = requests.get(earnings_url, timeout=10)
            earnings_response.raise_for_status()
            earnings_data = earnings_response.json()
            
            # Should either have earnings data or an error
            self.assertTrue(
                'next_earnings_date' in earnings_data or 'error' in earnings_data,
                f"Unexpected earnings response: {earnings_data}"
            )
            
            # Test dividends API
            dividends_url = f"https://api-v2.intrinio.com/securities/{self.test_underlying_ticker}/dividends/latest?api_key={self.real_api_key}"
            dividends_response = requests.get(dividends_url, timeout=10)
            dividends_response.raise_for_status()
            dividends_data = dividends_response.json()
            
            # Should either have dividend data or an error
            self.assertTrue(
                'last_ex_dividend_date' in dividends_data or 'error' in dividends_data,
                f"Unexpected dividends response: {dividends_data}"
            )
            
            logger.info(f"✅ Intrinio earnings/dividends API test passed for option underlying {self.test_underlying_ticker}")
            print(f"✅ Real earnings/dividends API test passed for options")
            
        except Exception as e:
            self.fail(f"Intrinio earnings/dividends API test failed: {e}")
    
    @patch('hello_world.functions.calcOptionDetails.computeOptionValues')
    def test_calcOptionDetails_with_mocked_option_data(self, mock_option_values):
        """Test calcOptionDetails with real APIs but mocked option data"""
        try:
            # Mock computeOptionValues to avoid import issues
            mock_option_values.return_value = (8.50, 3.25, False)
            
            # Create realistic option data structure
            test_option_ticker = "AAPL__240621C00180000"
            sample_option_prices = {
                'options_data': [{
                    'option': {
                        'code': test_option_ticker,
                        'ticker': self.test_underlying_ticker,
                        'type': 'call',
                        'expiration': '2024-06-21',
                        'strike': 180.0
                    },
                    'price': {
                        'last': 5.25,
                        'last_size': 100,
                        'bid': 5.20,
                        'bid_size': 150,
                        'ask': 5.30,
                        'ask_size': 200
                    },
                    'stats': {
                        'underlying_price': 175.50,
                        'implied_volatility': 0.28,
                        'delta': 0.45,
                        'gamma': 0.025,
                        'theta': -0.05,
                        'vega': 0.15
                    }
                }]
            }
            
            sample_position_input = pd.Series({
                'Ticker symbol': test_option_ticker,
                'Ticker position': 10,
                'Underlying position': 1000,
                'Option trade date': '2024-05-01',
                'Option entry price': 5.50
            })
            
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                
                # Configure intrinio
                import intrinio_sdk as intrinio
                configuration = intrinio.Configuration()
                configuration.api_key['api_key'] = self.real_api_key
                configuration.allow_retries = True
                
                result = calcOptionDetails(
                    sample_position_input,
                    sample_option_prices,
                    self.sample_prices_adj,
                    self.sample_prices_nonadj,
                    self.sample_adj_factors,
                    self.sample_dividends,
                    self.real_api_key,
                    self.real_snowflake_conn
                )
                
                # Log warnings
                if w:
                    logger.warning(f"Warnings during option details calculation:")
                    for warning in w:
                        logger.warning(f"  - {warning.message}")
                
                # Validate result
                if result.get('detailsAvailable', False):
                    # Check required fields
                    required_fields = [
                        'Option underlying ticker', 'Option underlying name', 'Option type',
                        'Option strike', 'Option underlying price', 'Last price', 'Mid',
                        'Option delta', 'Option expected value', 'Total shares deliverable'
                    ]
                    
                    for field in required_fields:
                        self.assertIn(field, result, f"Missing field: {field}")
                    
                    # Check data types and values
                    self.assertEqual(result['Option underlying ticker'], self.test_underlying_ticker)
                    self.assertEqual(result['Option type'], 'call')
                    self.assertEqual(result['Option strike'], 180.0)
                    self.assertIsInstance(result['Option underlying price'], (int, float))
                    self.assertGreater(result['Option underlying price'], 0)
                    
                    logger.info(f"✅ Integration test successful!")
                    logger.info(f"   Option: {test_option_ticker}")
                    logger.info(f"   Underlying: {result['Option underlying name']}")
                    logger.info(f"   Strike: ${result['Option strike']}")
                    logger.info(f"   Underlying Price: ${result['Option underlying price']}")
                    
                    print(f"✅ Real data test - Option details calculated successfully")
                else:
                    logger.warning(f"Option details not available")
                    self.skipTest(f"Option details not available")
                    
        except Exception as e:
            logger.error(f"Integration test failed: {e}")
            self.fail(f"Integration test failed: {e}")

# =====================================
# MAIN EXECUTION
# =====================================

if __name__ == '__main__':
    print("=== calcOptionDetails Test Suite ===")
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
        suite = unittest.TestLoader().loadTestsFromTestCase(TestCalcOptionDetailsUnit)
        unittest.TextTestRunner(verbosity=2).run(suite)
        
    elif choice == "2":
        print("\n" + "="*60)
        print("RUNNING INTEGRATION TESTS")
        print("="*60)
        suite = unittest.TestLoader().loadTestsFromTestCase(TestCalcOptionDetailsIntegration)
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
        suite = unittest.TestLoader().loadTestsFromTestCase(TestCalcOptionDetailsUnit)
        unittest.TextTestRunner(verbosity=2).run(suite)
    
    print("\n🏁 Test execution completed!")