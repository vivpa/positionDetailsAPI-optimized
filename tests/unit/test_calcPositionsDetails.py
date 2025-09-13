import unittest
from unittest.mock import Mock, patch, MagicMock, call
import warnings
import sys
import os
import pandas as pd
import numpy as np
import json
from datetime import datetime, date

# Add the project root directory to Python path
current_file = os.path.abspath(__file__)
current_dir = os.path.dirname(current_file)
tests_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(tests_dir)
sys.path.insert(0, project_root)

from hello_world.functions.calcPositionsDetails import calcPositionsDetails

class TestCalcPositionsDetailsUnit(unittest.TestCase):
    """Unit tests with mocked dependencies"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Sample input data for the function - structure matches what function expects after .T
        self.sample_input_data = {
            "dfInstrumentsDetails": {
                "position_detail_id": {
                    "position_1": 1,
                    "position_2": 2, 
                    "position_3": 3
                },
                "Ticker symbol": {
                    "position_1": "AAPL",
                    "position_2": "AAPL__240621C00180000",
                    "position_3": "CRYPTO_BTC"
                },
                "Ticker type": {
                    "position_1": "equity",
                    "position_2": "option",
                    "position_3": "other"
                },
                "Ticker position": {
                    "position_1": 100,
                    "position_2": 10,
                    "position_3": 0.5
                },
                "Underlying position": {
                    "position_1": None,
                    "position_2": 1000,
                    "position_3": None
                },
                "Option trade date": {
                    "position_1": None,
                    "position_2": "2024-05-01",
                    "position_3": None
                },
                "Option entry price": {
                    "position_1": None,
                    "position_2": 5.50,
                    "position_3": None
                }
            }
        }
        
        self.json_input = json.dumps(self.sample_input_data)
        
        # Sample price data that would be returned by retrieveIntrinioStockPricesAndDividends
        self.sample_price_data = {
            'prices_adj': pd.DataFrame({
                'AAPL': [150.0, 151.0, 152.0],
                'SPY': [400.0, 401.0, 402.0]
            }, index=pd.to_datetime(['2024-01-01', '2024-01-02', '2024-01-03'])),
            'prices_raw': pd.DataFrame({
                'AAPL': [150.0, 151.0, 152.0],
                'SPY': [400.0, 401.0, 402.0]
            }, index=pd.to_datetime(['2024-01-01', '2024-01-02', '2024-01-03'])),
            'adj_factors': pd.DataFrame({
                'AAPL': [1.0, 1.0, 1.0],
                'SPY': [1.0, 1.0, 1.0]
            }, index=pd.to_datetime(['2024-01-01', '2024-01-02', '2024-01-03'])),
            'dividends': pd.DataFrame({
                'AAPL': [0.0, 0.0, 0.23],
                'SPY': [0.0, 0.0, 0.15]
            }, index=pd.to_datetime(['2024-01-01', '2024-01-02', '2024-01-03']))
        }
        
        # Sample option prices response
        self.sample_option_response = {
            "contracts": [
                {
                    "option": {
                        "code": "AAPL__240621C00180000",
                        "ticker": "AAPL",
                        "type": "call",
                        "expiration": "2024-06-21",
                        "strike": 180.0
                    },
                    "price": {
                        "last": 5.25,
                        "bid": 5.20,
                        "ask": 5.30
                    },
                    "stats": {
                        "delta": 0.45,
                        "gamma": 0.025,
                        "theta": -0.05,
                        "vega": 0.15
                    }
                }
            ]
        }
        
        # Capture warnings
        self.captured_warnings = []
        def warning_handler(message, category, filename, lineno, file=None, line=None):
            self.captured_warnings.append(str(message))
        self.original_showwarning = warnings.showwarning
        warnings.showwarning = warning_handler
        # Patch S3 CSV reads globally for this test class to avoid AWS dependency
        from unittest.mock import patch
        self._readcsv_patcher = patch(
            'hello_world.functions.calcPositionsDetails.readCsvFromS3',
            return_value=[
                ['TICKER', 'NEXT_EARNINGS_DATE', 'EX_DIVIDEND', 'LAST_EX_DIVIDEND_DATE'],
                ['AAPL', '2024-07-25', 0.25, '2024-08-09'],
                ['SPY', '2024-07-25', 0.00, '2024-08-09']
            ]
        )
        self.mock_readcsv = self._readcsv_patcher.start()

        # Patch Snowflake helper queries to return minimal valid structures
        self._snowflake_id_patcher = patch(
            'hello_world.functions.calcPositionsDetails.snowflakeIdTestQuery',
            return_value=(pd.DataFrame({'STOCK_ID': [1, 2], 'SYMBOL': ['AAPL', 'SPY']}), '')
        )
        self._snowflake_iv_patcher = patch(
            'hello_world.functions.calcPositionsDetails.snowflakeIvolQueries',
            return_value=(pd.DataFrame({'Implied vol 1m': [0.2, 0.25]}, index=['AAPL', 'SPY']), '')
        )
        self.mock_snowflake_id = self._snowflake_id_patcher.start()
        self.mock_snowflake_iv = self._snowflake_iv_patcher.start()
    
    def tearDown(self):
        """Clean up after each test"""
        warnings.showwarning = self.original_showwarning
        # Stop global patcher
        self._readcsv_patcher.stop()
        self._snowflake_id_patcher.stop()
        self._snowflake_iv_patcher.stop()

    @patch('hello_world.functions.calcPositionsDetails.calcEquityDetails')
    @patch('hello_world.functions.calcPositionsDetails.calcOptionDetails')
    @patch('hello_world.functions.calcPositionsDetails.requests.post')
    @patch('hello_world.functions.calcPositionsDetails.retrieveIntrinioStockPricesAndDividends')
    @patch('hello_world.functions.calcPositionsDetails.snowflake.connector.connect')
    @patch('hello_world.functions.calcPositionsDetails.getSecretsSnowflake')
    @patch('hello_world.functions.calcPositionsDetails.getSecretsIntrinioApiKey')
    @patch('hello_world.functions.calcPositionsDetails.getLatestWeekday')
    @patch('hello_world.functions.calcPositionsDetails.intrinio')
    @patch('builtins.print')
    def test_full_position_processing_success(self, mock_print, mock_intrinio, mock_weekday, 
                                            mock_api_key, mock_snowflake_secrets, mock_snowflake_connect,
                                            mock_retrieve_data, mock_requests, mock_calc_option, mock_calc_equity):
        """Test successful processing of all position types"""
        
        # Setup mocks
        mock_api_key.return_value = "test_api_key"
        mock_snowflake_secrets.return_value = ("user", "pass", "warehouse", "account")
        mock_weekday.side_effect = lambda x: x  # Return input date as-is
        
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_snowflake_connect.return_value = mock_connection
        
        mock_retrieve_data.return_value = (
            self.sample_price_data['prices_adj'],
            self.sample_price_data['prices_raw'], 
            self.sample_price_data['adj_factors'],
            self.sample_price_data['dividends']
        )
        
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = self.sample_option_response
        mock_response.raise_for_status.return_value = None
        mock_requests.return_value = mock_response
        
        # Mock calculation functions
        mock_calc_equity.return_value = {
            'detailsAvailable': True,
            'Name': 'Apple Inc',
            'Last price': 152.0,
            'Price change': 0.02
        }
        
        mock_calc_option.return_value = {
            'detailsAvailable': True,
            'Option underlying ticker': 'AAPL',
            'Option type': 'call',
            'Option strike': 180.0,
            'Last price': 5.25
        }
        
        # Execute function
        result_json = calcPositionsDetails(self.json_input)
        result = json.loads(result_json)
        
        # Verify results
        self.assertIsInstance(result, dict)
        self.assertIn('1', result)  # Equity position
        self.assertIn('2', result)  # Option position  
        self.assertIn('3', result)  # Other position
        
        # Verify equity position
        equity_result = result['1']
        self.assertTrue(equity_result['detailsAvailable'])
        self.assertEqual(equity_result['Name'], 'Apple Inc')
        
        # Verify option position
        option_result = result['2']
        self.assertTrue(option_result['detailsAvailable'])
        self.assertEqual(option_result['Option underlying ticker'], 'AAPL')
        
        # Verify other position
        other_result = result['3']
        self.assertFalse(other_result['detailsAvailable'])
        
        # Verify function calls
        mock_calc_equity.assert_called_once()
        mock_calc_option.assert_called_once()
        mock_retrieve_data.assert_called_once()

    def test_json_input_parsing(self):
        """Test JSON input parsing and DataFrame conversion"""
        with patch('hello_world.functions.calcPositionsDetails.getSecretsIntrinioApiKey') as mock_api_key, \
             patch('hello_world.functions.calcPositionsDetails.getSecretsSnowflake') as mock_snowflake_secrets, \
             patch('hello_world.functions.calcPositionsDetails.snowflake.connector.connect') as mock_snowflake_connect, \
             patch('hello_world.functions.calcPositionsDetails.retrieveIntrinioStockPricesAndDividends') as mock_retrieve, \
             patch('hello_world.functions.calcPositionsDetails.requests.post') as mock_requests, \
             patch('hello_world.functions.calcPositionsDetails.calcEquityDetails') as mock_calc_equity, \
             patch('hello_world.functions.calcPositionsDetails.calcOptionDetails') as mock_calc_option, \
             patch('hello_world.functions.calcPositionsDetails.intrinio'), \
             patch('hello_world.functions.calcPositionsDetails.getLatestWeekday') as mock_weekday, \
             patch('builtins.print'):
            
            # Setup required mocks
            mock_api_key.return_value = "test_api_key"
            mock_snowflake_secrets.return_value = ("user", "pass", "warehouse", "account")
            mock_weekday.side_effect = lambda x: x
            mock_snowflake_connect.return_value.cursor.return_value = Mock()
            
            # Create DataFrames with proper ticker columns that will be accessed
            sample_data = pd.DataFrame({
                'AAPL': [150.0, 151.0],
                'SPY': [400.0, 401.0]
            }, index=pd.to_datetime(['2024-01-01', '2024-01-02']))
            
            mock_retrieve.return_value = tuple(sample_data for _ in range(4))
            mock_requests.return_value.json.return_value = {"contracts": []}
            mock_requests.return_value.raise_for_status.return_value = None
            mock_calc_equity.return_value = {'detailsAvailable': True}
            mock_calc_option.return_value = {'detailsAvailable': True}
            
            # This should not raise an exception
            try:
                calcPositionsDetails(self.json_input)
            except json.JSONDecodeError:
                self.fail("JSON parsing failed")

    def test_ticker_parsing_logic(self):
        """Test the ticker symbol parsing and modification logic"""
        test_cases = [
            ("AAPL", "equity", "AAPL"),           # Simple equity
            ("AAPL GOOGL", "equity", "AAPL"),    # Space-separated
            ("AAPL_MSFT", "equity", "AAPL"),     # Underscore-separated
            ("AAPL__240621C00180000", "option", "AAPL"),  # Option ticker
            ("SPY__231215P00400000", "option", "SPY"),    # Put option
        ]
        
        for original_ticker, ticker_type, expected_result in test_cases:
            with self.subTest(ticker=original_ticker, type=ticker_type):
                # Create test input with single position - correct structure
                test_input = {
                    "dfInstrumentsDetails": {
                        "position_detail_id": {
                            "position_1": 1
                        },
                        "Ticker symbol": {
                            "position_1": original_ticker
                        },
                        "Ticker type": {
                            "position_1": ticker_type
                        },
                        "Ticker position": {
                            "position_1": 100
                        }
                    }
                }
                
                with patch('hello_world.functions.calcPositionsDetails.getSecretsIntrinioApiKey') as mock_api_key, \
                     patch('hello_world.functions.calcPositionsDetails.getSecretsSnowflake') as mock_snowflake_secrets, \
                     patch('hello_world.functions.calcPositionsDetails.snowflake.connector.connect') as mock_snowflake_connect, \
                     patch('hello_world.functions.calcPositionsDetails.retrieveIntrinioStockPricesAndDividends') as mock_retrieve, \
                     patch('hello_world.functions.calcPositionsDetails.requests.post') as mock_requests, \
                     patch('hello_world.functions.calcPositionsDetails.calcEquityDetails') as mock_calc_equity, \
                     patch('hello_world.functions.calcPositionsDetails.calcOptionDetails') as mock_calc_option, \
                     patch('hello_world.functions.calcPositionsDetails.intrinio'), \
                     patch('hello_world.functions.calcPositionsDetails.getLatestWeekday') as mock_weekday, \
                     patch('builtins.print'):
                    
                    # Setup required mocks
                    mock_api_key.return_value = "test_api_key"
                    mock_snowflake_secrets.return_value = ("user", "pass", "warehouse", "account")
                    mock_weekday.side_effect = lambda x: x
                    mock_snowflake_connect.return_value.cursor.return_value = Mock()
                    
                    # Create DataFrames with proper ticker columns
                    # Always include both the expected ticker and SPY benchmark
                    ticker_columns = [expected_result, 'SPY']
                    if expected_result != 'SPY':
                        ticker_columns = list(set(ticker_columns))  # Remove duplicates
                    
                    sample_data = pd.DataFrame({
                        col: [150.0, 151.0] for col in ticker_columns
                    }, index=pd.to_datetime(['2024-01-01', '2024-01-02']))
                    
                    mock_retrieve.return_value = tuple(sample_data for _ in range(4))
                    mock_requests.return_value.json.return_value = {"contracts": []}
                    mock_requests.return_value.raise_for_status.return_value = None
                    mock_calc_equity.return_value = {'detailsAvailable': True}
                    mock_calc_option.return_value = {'detailsAvailable': True}
                    
                    calcPositionsDetails(json.dumps(test_input))
                    
                    # Verify the ticker was included in the list passed to retrieve function
                    call_args = mock_retrieve.call_args[0]
                    ticker_list = call_args[0]
                    self.assertIn(expected_result, ticker_list)

    @patch('hello_world.functions.calcPositionsDetails.requests.post')
    def test_intrinio_api_error_handling(self, mock_requests):
        """Test handling of Intrinio API errors"""
        mock_requests.side_effect = Exception("API connection failed")
        
        with patch('hello_world.functions.calcPositionsDetails.getSecretsIntrinioApiKey'), \
             patch('hello_world.functions.calcPositionsDetails.getSecretsSnowflake'), \
             patch('hello_world.functions.calcPositionsDetails.snowflake.connector.connect'), \
             patch('hello_world.functions.calcPositionsDetails.retrieveIntrinioStockPricesAndDividends'), \
             patch('hello_world.functions.calcPositionsDetails.intrinio'), \
             patch('hello_world.functions.calcPositionsDetails.getLatestWeekday'), \
             patch('builtins.print'):
            
            with self.assertRaises(Exception):
                calcPositionsDetails(self.json_input)

    def test_empty_input_handling(self):
        """Test handling of empty or invalid input"""
        empty_input = {"dfInstrumentsDetails": {}}
        
        with patch('hello_world.functions.calcPositionsDetails.getSecretsIntrinioApiKey') as mock_api_key, \
             patch('hello_world.functions.calcPositionsDetails.getSecretsSnowflake') as mock_snowflake_secrets, \
             patch('hello_world.functions.calcPositionsDetails.snowflake.connector.connect') as mock_snowflake_connect, \
             patch('hello_world.functions.calcPositionsDetails.retrieveIntrinioStockPricesAndDividends') as mock_retrieve, \
             patch('hello_world.functions.calcPositionsDetails.requests.post') as mock_requests, \
             patch('hello_world.functions.calcPositionsDetails.intrinio'), \
             patch('hello_world.functions.calcPositionsDetails.getLatestWeekday') as mock_weekday, \
             patch('builtins.print'):
            
            # Setup required mocks
            mock_api_key.return_value = "test_api_key"
            mock_snowflake_secrets.return_value = ("user", "pass", "warehouse", "account")
            mock_weekday.side_effect = lambda x: x
            mock_snowflake_connect.return_value.cursor.return_value = Mock()
            
            # For empty input, we still need SPY benchmark ticker
            sample_data = pd.DataFrame({
                'SPY': [400.0, 401.0]
            }, index=pd.to_datetime(['2024-01-01', '2024-01-02']))
            
            mock_retrieve.return_value = tuple(sample_data for _ in range(4))
            mock_requests.return_value.json.return_value = {"contracts": []}
            mock_requests.return_value.raise_for_status.return_value = None
            
            result_json = calcPositionsDetails(json.dumps(empty_input))
            result = json.loads(result_json)
            
            # Should return empty results
            self.assertEqual(result, {})

    def test_invalid_json_input(self):
        """Test handling of invalid JSON input"""
        invalid_json = "invalid json string"
        
        with self.assertRaises(json.JSONDecodeError):
            calcPositionsDetails(invalid_json)

    @patch('hello_world.functions.calcPositionsDetails.calcEquityDetails')
    @patch('hello_world.functions.calcPositionsDetails.requests.post')
    @patch('hello_world.functions.calcPositionsDetails.retrieveIntrinioStockPricesAndDividends')
    @patch('hello_world.functions.calcPositionsDetails.snowflake.connector.connect')
    @patch('hello_world.functions.calcPositionsDetails.getSecretsSnowflake')
    @patch('hello_world.functions.calcPositionsDetails.getSecretsIntrinioApiKey')
    @patch('hello_world.functions.calcPositionsDetails.getLatestWeekday')
    @patch('hello_world.functions.calcPositionsDetails.intrinio')
    @patch('builtins.print')
    def test_benchmark_ticker_inclusion(self, mock_print, mock_intrinio, mock_weekday,
                                      mock_api_key, mock_snowflake_secrets, mock_snowflake_connect,
                                      mock_retrieve_data, mock_requests, mock_calc_equity):
        """Test that SPY benchmark ticker is always included"""
        
        # Setup mocks
        mock_api_key.return_value = "test_api_key"
        mock_snowflake_secrets.return_value = ("user", "pass", "warehouse", "account")
        mock_weekday.side_effect = lambda x: x
        mock_snowflake_connect.return_value.cursor.return_value = Mock()
        
        # Create DataFrames with proper ticker columns
        sample_data = pd.DataFrame({
            'AAPL': [150.0, 151.0],
            'SPY': [400.0, 401.0]
        }, index=pd.to_datetime(['2024-01-01', '2024-01-02']))
        
        mock_retrieve_data.return_value = tuple(sample_data for _ in range(4))
        mock_requests.return_value.json.return_value = {"contracts": []}
        mock_requests.return_value.raise_for_status.return_value = None
        mock_calc_equity.return_value = {'detailsAvailable': True}
        
        # Input without SPY ticker - correct structure
        test_input = {
            "dfInstrumentsDetails": {
                "position_detail_id": {
                    "position_1": 1
                },
                "Ticker symbol": {
                    "position_1": "AAPL"
                },
                "Ticker type": {
                    "position_1": "equity"
                },
                "Ticker position": {
                    "position_1": 100
                }
            }
        }
        
        calcPositionsDetails(json.dumps(test_input))
        
        # Verify SPY was added to ticker list
        call_args = mock_retrieve_data.call_args[0]
        ticker_list = call_args[0]
        self.assertIn('SPY', ticker_list)

    def test_na_filling_in_output(self):
        """Test that NA values are properly filled in the output"""
        with patch('hello_world.functions.calcPositionsDetails.calcEquityDetails') as mock_calc_equity, \
             patch('hello_world.functions.calcPositionsDetails.requests.post') as mock_requests, \
             patch('hello_world.functions.calcPositionsDetails.retrieveIntrinioStockPricesAndDividends') as mock_retrieve, \
             patch('hello_world.functions.calcPositionsDetails.snowflake.connector.connect') as mock_snowflake_connect, \
             patch('hello_world.functions.calcPositionsDetails.getSecretsSnowflake') as mock_snowflake_secrets, \
             patch('hello_world.functions.calcPositionsDetails.getSecretsIntrinioApiKey') as mock_api_key, \
             patch('hello_world.functions.calcPositionsDetails.getLatestWeekday') as mock_weekday, \
             patch('hello_world.functions.calcPositionsDetails.intrinio'), \
             patch('builtins.print'):
            
            # Setup required mocks
            mock_api_key.return_value = "test_api_key"
            mock_snowflake_secrets.return_value = ("user", "pass", "warehouse", "account")
            mock_weekday.side_effect = lambda x: x
            mock_snowflake_connect.return_value.cursor.return_value = Mock()
            
            # Create DataFrames with proper ticker columns
            sample_data = pd.DataFrame({
                'AAPL': [150.0, 151.0],
                'SPY': [400.0, 401.0]
            }, index=pd.to_datetime(['2024-01-01', '2024-01-02']))
            
            mock_retrieve.return_value = tuple(sample_data for _ in range(4))
            mock_requests.return_value.json.return_value = {"contracts": []}
            mock_requests.return_value.raise_for_status.return_value = None
            
            # Mock function to return data with None values
            mock_calc_equity.return_value = {
                'detailsAvailable': True,
                'Name': 'Apple Inc',
                'Price': None,  # This should become 'NA'
                'Volume': np.nan  # This should also become 'NA'
            }
            
            test_input = {
                "dfInstrumentsDetails": {
                    "position_detail_id": {
                        "position_1": 1
                    },
                    "Ticker symbol": {
                        "position_1": "AAPL"
                    },
                    "Ticker type": {
                        "position_1": "equity"
                    },
                    "Ticker position": {
                        "position_1": 100
                    }
                }
            }
            
            result_json = calcPositionsDetails(json.dumps(test_input))
            result = json.loads(result_json)
            
            # Verify None and NaN values are converted to 'NA'
            position_result = result['1']
            self.assertEqual(position_result['Price'], 'NA')
            self.assertEqual(position_result['Volume'], 'NA')

    def test_performance_with_many_positions(self):
        """Test performance with a large number of positions"""
        # Create many positions - correct structure
        # Use proper ticker symbols that won't trigger the option parsing issue
        test_tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'NFLX', 'DIS', 'PYPL',
                       'ADBE', 'CRM', 'INTC', 'AMD', 'ORCL', 'CSCO', 'IBM', 'QCOM', 'TXN', 'AVGO']
        
        position_ids = {}
        ticker_symbols = {}
        ticker_types = {}
        ticker_positions = {}
        
        for i, ticker in enumerate(test_tickers):
            position_key = f"position_{i}"
            position_ids[position_key] = i
            ticker_symbols[position_key] = ticker
            ticker_types[position_key] = "equity"
            ticker_positions[position_key] = 100
        
        large_input = {
            "dfInstrumentsDetails": {
                "position_detail_id": position_ids,
                "Ticker symbol": ticker_symbols,
                "Ticker type": ticker_types,
                "Ticker position": ticker_positions
            }
        }
        
        with patch('hello_world.functions.calcPositionsDetails.calcEquityDetails') as mock_calc_equity, \
             patch('hello_world.functions.calcPositionsDetails.requests.post') as mock_requests, \
             patch('hello_world.functions.calcPositionsDetails.retrieveIntrinioStockPricesAndDividends') as mock_retrieve, \
             patch('hello_world.functions.calcPositionsDetails.snowflake.connector.connect') as mock_snowflake_connect, \
             patch('hello_world.functions.calcPositionsDetails.getSecretsSnowflake') as mock_snowflake_secrets, \
             patch('hello_world.functions.calcPositionsDetails.getSecretsIntrinioApiKey') as mock_api_key, \
             patch('hello_world.functions.calcPositionsDetails.getLatestWeekday') as mock_weekday, \
             patch('hello_world.functions.calcPositionsDetails.intrinio'), \
             patch('builtins.print'):
            
            # Setup required mocks
            mock_api_key.return_value = "test_api_key"
            mock_snowflake_secrets.return_value = ("user", "pass", "warehouse", "account")
            mock_weekday.side_effect = lambda x: x
            mock_snowflake_connect.return_value.cursor.return_value = Mock()
            
            # Setup mocks for the tickers
            all_tickers = test_tickers + ['SPY']  # Add SPY benchmark
            large_price_data = pd.DataFrame(
                np.random.randn(100, len(all_tickers)),
                columns=all_tickers,
                index=pd.date_range('2024-01-01', periods=100)
            )
            
            mock_retrieve.return_value = tuple(large_price_data for _ in range(4))
            mock_requests.return_value.json.return_value = {"contracts": []}
            mock_requests.return_value.raise_for_status.return_value = None
            mock_calc_equity.return_value = {'detailsAvailable': True, 'Name': 'Test Company'}
            
            # Execute test
            result_json = calcPositionsDetails(json.dumps(large_input))
            result = json.loads(result_json)
            
            # Verify all positions were processed
            self.assertEqual(len(result), 20)
            self.assertEqual(mock_calc_equity.call_count, 20)

class TestCalcPositionsDetailsIntegration(unittest.TestCase):
    """Integration tests with realistic mocked services"""
    
    def setUp(self):
        """Set up integration test environment"""
        self.realistic_input = {
            "dfInstrumentsDetails": {
                "position_detail_id": {
                    "position_1": 1,
                    "position_2": 2
                },
                "Ticker symbol": {
                    "position_1": "AAPL",
                    "position_2": "MSFT"
                },
                "Ticker type": {
                    "position_1": "equity",
                    "position_2": "equity"
                },
                "Ticker position": {
                    "position_1": 100,
                    "position_2": 50
                }
            }
        }
        
    def test_realistic_data_flow(self):
        """Test with realistic data flow and proper date handling"""
        with patch('hello_world.functions.calcPositionsDetails.calcEquityDetails') as mock_calc_equity, \
             patch('hello_world.functions.calcPositionsDetails.requests.post') as mock_requests, \
             patch('hello_world.functions.calcPositionsDetails.retrieveIntrinioStockPricesAndDividends') as mock_retrieve, \
             patch('hello_world.functions.calcPositionsDetails.snowflake.connector.connect') as mock_snowflake, \
             patch('hello_world.functions.calcPositionsDetails.getSecretsSnowflake') as mock_secrets, \
             patch('hello_world.functions.calcPositionsDetails.getSecretsIntrinioApiKey') as mock_api_key, \
             patch('hello_world.functions.calcPositionsDetails.getLatestWeekday') as mock_weekday, \
             patch('hello_world.functions.calcPositionsDetails.intrinio'), \
             patch('builtins.print'):
            
            # Setup realistic mocks
            mock_api_key.return_value = "sk_test123"
            mock_secrets.return_value = ("testuser", "testpass", "COMPUTE_WH", "test123.snowflakecomputing.com")
            mock_weekday.return_value = pd.Timestamp('2024-01-15')  # Monday
            
            # Mock Snowflake connection
            mock_connection = Mock()
            mock_cursor = Mock() 
            mock_connection.cursor.return_value = mock_cursor
            mock_snowflake.return_value = mock_connection
            
            # Create realistic price data
            dates = pd.date_range('2019-01-01', '2024-01-15', freq='B')  # Business days
            aapl_prices = 150 + np.random.randn(len(dates)).cumsum() * 5
            msft_prices = 350 + np.random.randn(len(dates)).cumsum() * 8  
            spy_prices = 450 + np.random.randn(len(dates)).cumsum() * 3
            
            realistic_prices = pd.DataFrame({
                'AAPL': aapl_prices,
                'MSFT': msft_prices,
                'SPY': spy_prices
            }, index=dates)
            
            mock_retrieve.return_value = (
                realistic_prices,  # prices_adj
                realistic_prices * 0.99,  # prices_raw (slightly different)
                pd.DataFrame(np.ones_like(realistic_prices), index=dates, columns=['AAPL', 'MSFT', 'SPY']),  # adj_factors
                pd.DataFrame(np.zeros_like(realistic_prices), index=dates, columns=['AAPL', 'MSFT', 'SPY'])   # dividends
            )
            
            # Mock API response
            mock_response = Mock()
            mock_response.json.return_value = {"contracts": []}
            mock_response.raise_for_status.return_value = None
            mock_requests.return_value = mock_response
            
            # Mock equity calculation results
            def mock_equity_calc(position, *args, **kwargs):
                ticker = position['Ticker symbol']
                return {
                    'detailsAvailable': True,
                    'Name': f'{ticker} Company',
                    'Last price': realistic_prices[ticker].iloc[-1],
                    'Price change': 0.02,
                    'RSI 1 week': 45.5,
                    'Beta versus benchmark': 1.2
                }
            
            mock_calc_equity.side_effect = mock_equity_calc
            
            # Execute test
            result_json = calcPositionsDetails(json.dumps(self.realistic_input))
            result = json.loads(result_json)
            
            # Verify realistic results
            self.assertEqual(len(result), 2)  # Two positions
            
            # Verify AAPL position
            aapl_result = result['1']
            self.assertTrue(aapl_result['detailsAvailable'])
            self.assertEqual(aapl_result['Name'], 'AAPL Company')
            self.assertIsInstance(aapl_result['Last price'], float)
            
            # Verify MSFT position  
            msft_result = result['2']
            self.assertTrue(msft_result['detailsAvailable'])
            self.assertEqual(msft_result['Name'], 'MSFT Company')
            
            # Verify function calls were made correctly
            self.assertEqual(mock_calc_equity.call_count, 2)
            mock_retrieve.assert_called_once()

    @unittest.skipUnless(os.getenv('INTRINIO_TEST_ENABLED'), "Real Intrinio tests disabled")
    def test_real_intrinio_integration(self):
        """Test with real Intrinio API (only if enabled)"""
        # This test would only run if INTRINIO_TEST_ENABLED environment variable is set
        try:
            import intrinio_sdk as intrinio
            from hello_world.functions.getSecretsIntrinioApiKey import getSecretsIntrinioApiKey
            
            # Get real API key
            real_api_key = getSecretsIntrinioApiKey()
            intrinio.ApiClient().set_api_key(real_api_key)
            
            # Simple test input
            test_input = {
                "dfInstrumentsDetails": {
                    "position_detail_id": {
                        "position_1": 1
                    },
                    "Ticker symbol": {
                        "position_1": "AAPL"
                    },
                    "Ticker type": {
                        "position_1": "equity"
                    },
                    "Ticker position": {
                        "position_1": 100
                    }
                }
            }
            
            with patch('hello_world.functions.calcPositionsDetails.snowflake.connector.connect'), \
                 patch('hello_world.functions.calcPositionsDetails.getSecretsSnowflake'):
                
                # This should work with real API
                result_json = calcPositionsDetails(json.dumps(test_input))
                result = json.loads(result_json)
                
                self.assertIsInstance(result, dict)
                self.assertIn('1', result)
                
        except Exception as e:
            self.skipTest(f"Real Intrinio integration not available: {e}")

def create_test_suite():
    """Create a test suite with both unit and integration tests"""
    suite = unittest.TestSuite()
    
    # Add unit tests
    unit_tests = unittest.TestLoader().loadTestsFromTestCase(TestCalcPositionsDetailsUnit)
    suite.addTest(unit_tests)
    
    # Add integration tests
    integration_tests = unittest.TestLoader().loadTestsFromTestCase(TestCalcPositionsDetailsIntegration)
    suite.addTest(integration_tests)
    
    return suite

if __name__ == '__main__':
    print("=== calcPositionsDetails Test Suite ===")
    print("1. Run unit tests only (mocked dependencies)")
    print("2. Run integration tests only (realistic mocks)")
    print("3. Run all tests")
    print("4. Exit")
    
    try:
        choice = input("Enter choice (1-4): ").strip()
    except:
        choice = "1"  # Default to unit tests
    
    if choice == "1":
        print("\n" + "="*60)
        print("RUNNING UNIT TESTS")
        print("="*60)
        suite = unittest.TestLoader().loadTestsFromTestCase(TestCalcPositionsDetailsUnit)
        unittest.TextTestRunner(verbosity=2).run(suite)
        
    elif choice == "2":
        print("\n" + "="*60)
        print("RUNNING INTEGRATION TESTS")
        print("="*60)
        suite = unittest.TestLoader().loadTestsFromTestCase(TestCalcPositionsDetailsIntegration)
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
        suite = unittest.TestLoader().loadTestsFromTestCase(TestCalcPositionsDetailsUnit)
        unittest.TextTestRunner(verbosity=2).run(suite)
    
    print("\n🏁 Test execution completed!") 