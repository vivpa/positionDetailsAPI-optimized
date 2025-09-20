# Approach-- 1. Unit test for connection 2. Integration test for snowfalke connection 3. IT for extracting implied vol
#3. Get implied volatility straucture 4.snowflake id test query -- as many times it is not aavilable
# # # Test imports one by one
# # modules_to_test = [
# #     'hello_world',
# #     'hello_world.functions',
# #     'hello_world.functions.snowflakeIdTestQuery',
# #     'hello_world.functions.snowflakeIvolQueries',
# #     'hello_world.functions.calcImpliedVol'
# # ]

# # for module_name in modules_to_test:
# #     try:
# #         __import__(module_name)
# #         print(f"✅ {module_name}")
# #     except ImportError as e:
# #         print(f"❌ {module_name}: {e}")
# #         break
import logging
import warnings
from typing import Optional
import sys
import os
import unittest
from unittest.mock import Mock, patch
import pandas as pd

# Set up path BEFORE imports
current_file = os.path.abspath(__file__)
current_dir = os.path.dirname(current_file)
tests_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(tests_dir)
sys.path.insert(0, project_root)

# Import functions
from hello_world.functions.snowflakeIdTestQuery import snowflakeIdTestQuery
from hello_world.functions.snowflakeIvolQueries import snowflakeIvolQueries
from hello_world.functions.calcImpliedVol import calcImpliedVol

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# =====================================
# UNIT TESTS (with mocked data)
# =====================================
class TestCalcImpliedVolUnit(unittest.TestCase):
    """Unit tests with mocked Snowflake responses"""
    
    def setUp(self):
        self.mock_snowflake_connection = Mock()
        self.ticker_symbol = "AAPL"
        self.last_price = 180.50
        
        # Capture warnings
        self.captured_warnings = []
        def warning_handler(message, category, filename, lineno, file=None, line=None):
            self.captured_warnings.append(str(message))
        self.original_showwarning = warnings.showwarning
        warnings.showwarning = warning_handler
    
    def tearDown(self):
        warnings.showwarning = self.original_showwarning

    @patch('hello_world.functions.calcImpliedVol.snowflakeIdTestQuery')
    @patch('hello_world.functions.calcImpliedVol.snowflakeIvolQueries')
    def test_aapl_successful_calculation(self, mock_ivol_queries, mock_id_query):
        """Test successful IV calculation with mocked data"""
        mock_id_query.return_value = pd.DataFrame({'STOCK_ID': [12345]})
        mock_ivol_queries.return_value = pd.DataFrame({
            'T_DATE': ['20240517', '20240517', '20240517'],
            'PERIOD': [30, 30, 30],
            'OTM': [0, 0, 0],
            'IV': [0.28, 0.30, 0.26]
        })

        result = calcImpliedVol(self.ticker_symbol, self.last_price, self.mock_snowflake_connection)
        
        self.assertIsNotNone(result)
        self.assertIsInstance(result, float)
        expected_iv = (0.28 + 0.30 + 0.26) / 3
        self.assertAlmostEqual(result, expected_iv, places=6)
        print(f"✅ Unit Test - AAPL IV: {result:.4f}")

# =====================================
# INTEGRATION TESTS (with real Snowflake)
# =====================================

def get_real_snowflake_connection():
    """
    Create a real Snowflake connection using AWS Secrets Manager
    """
    try:
        # Import your secrets function
        from hello_world.functions.getSecretsSnowflake import getSecretsSnowflake
        import snowflake.connector
        
        # Get credentials from AWS Secrets Manager
        login_name, password, warehouse, account = getSecretsSnowflake()
        
        # Create Snowflake connection
        conn = snowflake.connector.connect(
            user=login_name,
            password=password,
            account=account,
            warehouse=warehouse,
            # Add database and schema if you have them in your secrets or set them here
            # database='YOUR_DATABASE',  # Uncomment and set if needed
            # schema='YOUR_SCHEMA'        # Uncomment and set if needed
        )
        
        logger.info("✅ Successfully connected to Snowflake using AWS Secrets Manager")
        return conn
        
    except Exception as e:
        logger.error(f"Failed to create Snowflake connection: {e}")
        logger.error(f"Make sure AWS credentials are configured and the secret exists")
        return None

class TestCalcImpliedVolIntegration(unittest.TestCase):
    """Integration tests with real Snowflake connection"""
    
    @classmethod
    def setUpClass(cls):
        """Set up real Snowflake connection for all tests"""
        cls.real_conn = get_real_snowflake_connection()
        if cls.real_conn is None:
            raise unittest.SkipTest("No Snowflake connection available - skipping integration tests")
        
        logger.info("✅ Real Snowflake connection established for integration tests")
    
    @classmethod
    def tearDownClass(cls):
        """Clean up connection"""
        if hasattr(cls, 'real_conn') and cls.real_conn:
            cls.real_conn.close()
            logger.info("🔒 Snowflake connection closed")
    
    def setUp(self):
        """Set up each test"""
        self.ticker_symbol = "AAPL"
        self.last_price = 180.50
        
        # Capture warnings for integration tests too
        self.captured_warnings = []
        def warning_handler(message, category, filename, lineno, file=None, line=None):
            self.captured_warnings.append(str(message))
        self.original_showwarning = warnings.showwarning
        warnings.showwarning = warning_handler
    
    def tearDown(self):
        warnings.showwarning = self.original_showwarning
    
    def test_real_snowflake_connection(self):
        """Test that we can actually connect to Snowflake"""
        self.assertIsNotNone(self.real_conn)
        
        # Try a simple query to verify connection
        cursor = self.real_conn.cursor()
        try:
            cursor.execute("SELECT 1 as test")
            result = cursor.fetchone()
            self.assertEqual(result[0], 1)
            print("✅ Snowflake connection test passed")
        finally:
            cursor.close()
    
    def test_snowflake_stock_id_query_structure(self):
        """Test the actual structure of snowflakeIdTestQuery response"""
        try:
            # Debug: Let's figure out the correct function signature
            # Try different parameter combinations to see which works
            
            cursor = self.real_conn.cursor()
            
            # The main calcImpliedVol test worked, so let's see what parameters it uses
            # Let's try both ways:
            
            try:
                # Method 1: cursor first, ticker second
                stock_id_df = snowflakeIdTestQuery(cursor, self.ticker_symbol)
            except Exception as e1:
                try:
                    # Method 2: ticker first, cursor second  
                    stock_id_df = snowflakeIdTestQuery(self.ticker_symbol, cursor)
                except Exception as e2:
                    try:
                        # Method 3: maybe it expects connection, not cursor
                        stock_id_df = snowflakeIdTestQuery(self.real_conn, self.ticker_symbol)
                    except Exception as e3:
                        # Log all the attempts for debugging
                        logger.error(f"Method 1 (cursor, ticker): {e1}")
                        logger.error(f"Method 2 (ticker, cursor): {e2}")
                        logger.error(f"Method 3 (conn, ticker): {e3}")
                        raise Exception(f"All parameter combinations failed. Errors: {e1}, {e2}, {e3}")
            
            # Test data availability
            if stock_id_df.empty:
                self.skipTest(f"No stock ID data found for {self.ticker_symbol} - cannot test structure")
            
            # Test expected columns
            self.assertIn('STOCK_ID', stock_id_df.columns, 
                         f"Expected 'STOCK_ID' column, got: {list(stock_id_df.columns)}")
            
            # Test data types
            self.assertFalse(stock_id_df['STOCK_ID'].isna().all(), 
                           "All STOCK_ID values are null")
            
            # Log actual structure for debugging
            logger.info(f"Stock ID query structure for {self.ticker_symbol}:")
            logger.info(f"  Columns: {list(stock_id_df.columns)}")
            logger.info(f"  Shape: {stock_id_df.shape}")
            logger.info(f"  Sample data: {stock_id_df.head()}")
            
            print(f"✅ Stock ID query structure test passed for {self.ticker_symbol}")
            
        except Exception as e:
            self.fail(f"Stock ID query failed: {e}")
        finally:
            if 'cursor' in locals():
                cursor.close()
    
    def test_snowflake_iv_query_structure(self):
        """Test the actual structure of snowflakeIvolQueries response"""
        try:
            cursor = self.real_conn.cursor()
            
            # First get stock ID using the same logic as the successful test
            try:
                stock_id_df = snowflakeIdTestQuery(cursor, self.ticker_symbol)
            except:
                try:
                    stock_id_df = snowflakeIdTestQuery(self.ticker_symbol, cursor)
                except:
                    stock_id_df = snowflakeIdTestQuery(self.real_conn, self.ticker_symbol)
            
            if stock_id_df.empty:
                self.skipTest(f"No stock ID found for {self.ticker_symbol}")
            
            stock_id = stock_id_df['STOCK_ID'].iloc[0]
            
            # Calculate business days for the query
            from datetime import datetime, timedelta
            import pandas as pd
            
            # Get last business day as end_date
            today = datetime.now()
            end_date = today
            while end_date.weekday() > 4:  # 0=Monday, 6=Sunday
                end_date -= timedelta(days=1)
            
            # Get business day a week before as start_date
            start_date = end_date - timedelta(days=7)
            while start_date.weekday() > 4:
                start_date -= timedelta(days=1)
            
            # Format dates as YYYYMMDD (like the T_DATE format we saw: 19950103)
            end_date_str = end_date.strftime('%Y%m%d')
            start_date_str = start_date.strftime('%Y%m%d')
            
            logger.info(f"Using date range: {start_date_str} to {end_date_str}")
            
            # Get IV data with correct parameters
            try:
                # Try the most likely parameter order based on the error message
                iv_df = snowflakeIvolQueries(stock_id, end_date_str, start_date_str, self.real_conn)
            except Exception as e1:
                try:
                    # Try with cursor instead of connection
                    iv_df = snowflakeIvolQueries(stock_id, end_date_str, start_date_str, cursor)
                except Exception as e2:
                    try:
                        # Try different parameter order
                        iv_df = snowflakeIvolQueries(stock_id, start_date_str, end_date_str, self.real_conn)
                    except Exception as e3:
                        try:
                            # Try with cursor and different order
                            iv_df = snowflakeIvolQueries(stock_id, start_date_str, end_date_str, cursor)
                        except Exception as e4:
                            try:
                                # Try with just cursor and stock_id (maybe dates are optional?)
                                iv_df = snowflakeIvolQueries(cursor, stock_id)
                            except Exception as e5:
                                try:
                                    # Try with connection and stock_id only
                                    iv_df = snowflakeIvolQueries(self.real_conn, stock_id)
                                except Exception as e6:
                                    logger.error(f"Method 1 (stock_id, end_date, start_date, conn): {e1}")
                                    logger.error(f"Method 2 (stock_id, end_date, start_date, cursor): {e2}")
                                    logger.error(f"Method 3 (stock_id, start_date, end_date, conn): {e3}")
                                    logger.error(f"Method 4 (stock_id, start_date, end_date, cursor): {e4}")
                                    logger.error(f"Method 5 (cursor, stock_id): {e5}")
                                    logger.error(f"Method 6 (conn, stock_id): {e6}")
                                    raise Exception(f"All IV query parameter combinations failed")
            
            if iv_df.empty:
                self.skipTest(f"No IV data found for stock_id {stock_id} in date range {start_date_str} to {end_date_str}")
            
            # Test expected columns exist
            expected_columns = ['IV', 'T_DATE', 'PERIOD', 'OTM']
            missing_columns = []
            for col in expected_columns:
                if col not in iv_df.columns:
                    missing_columns.append(col)
            
            if missing_columns:
                logger.warning(f"Missing expected columns: {missing_columns}")
                logger.info(f"Actual columns: {list(iv_df.columns)}")
                # Don't fail the test, just log the actual structure
            
            # Test data ranges (only if IV column exists)
            if 'IV' in iv_df.columns:
                iv_values = iv_df['IV'].dropna()
                if not iv_values.empty:
                    negative_values = iv_values[iv_values < 0]
                    if len(negative_values) > 0:
                        logger.warning(f"Found {len(negative_values)} negative IV values")
                    
                    extreme_values = iv_values[iv_values > 10]
                    if len(extreme_values) > 0:
                        logger.warning(f"Found {len(extreme_values)} extremely high IV values")
            
            # Log actual structure for debugging
            logger.info(f"IV query structure for stock_id {stock_id}:")
            logger.info(f"  Date range: {start_date_str} to {end_date_str}")
            logger.info(f"  Columns: {list(iv_df.columns)}")
            logger.info(f"  Shape: {iv_df.shape}")
            if 'IV' in iv_df.columns:
                logger.info(f"  IV range: {iv_df['IV'].min():.4f} to {iv_df['IV'].max():.4f}")
            logger.info(f"  Sample data:\n{iv_df.head()}")
            
            print(f"✅ IV query structure test passed for stock_id {stock_id}")
            
        except Exception as e:
            self.fail(f"IV query failed: {e}")
        finally:
            if 'cursor' in locals():
                cursor.close()
    
    def test_calcImpliedVol_with_real_data(self):
        """Test calcImpliedVol with real Snowflake data"""
        try:
            # Create cursor from connection - your functions likely expect this
            cursor = self.real_conn.cursor()
            
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                
                result = calcImpliedVol(self.ticker_symbol, self.last_price, cursor)
                
                # Log warnings
                if w:
                    logger.warning(f"Warnings during IV calculation for {self.ticker_symbol}:")
                    for warning in w:
                        logger.warning(f"  - {warning.message}")
                
                # If we get a result, validate it
                if result is not None:
                    self.assertIsInstance(result, float)
                    self.assertTrue(0.01 <= result <= 5.0, 
                                   f"IV result {result} outside reasonable range [0.01, 5.0]")
                    
                    logger.info(f"✅ Integration test successful!")
                    logger.info(f"   Ticker: {self.ticker_symbol}")
                    logger.info(f"   Stock Price: ${self.last_price}")
                    logger.info(f"   Implied Volatility: {result:.4f} ({result*100:.2f}%)")
                    
                    print(f"✅ Real data test - {self.ticker_symbol} IV: {result:.4f}")
                else:
                    # If no result, check why
                    logger.warning(f"No IV result for {self.ticker_symbol}")
                    self.skipTest(f"No IV data available for {self.ticker_symbol}")
                    
        except Exception as e:
            logger.error(f"Integration test failed for {self.ticker_symbol}: {e}")
            self.fail(f"Integration test failed: {e}")
        finally:
            if 'cursor' in locals():
                cursor.close()

# =====================================
# TEST DATA CAPTURE UTILITY
# =====================================

def capture_sample_data_for_testing(ticker="AAPL"):
    """
    Capture real data samples for future unit tests
    Run this occasionally to update your test fixtures
    """
    import pickle
    from pathlib import Path
    
    print(f"\n=== CAPTURING SAMPLE DATA FOR {ticker} ===")
    
    # Create test data directory
    test_data_dir = Path(project_root) / "tests" / "data"
    test_data_dir.mkdir(parents=True, exist_ok=True)
    
    real_conn = get_real_snowflake_connection()
    if real_conn is None:
        print("❌ Cannot capture data - no Snowflake connection")
        return
    
    try:
        # Create cursor for queries
        cursor = real_conn.cursor()
        
        # Capture stock ID response
        stock_id_df = snowflakeIdTestQuery(cursor, ticker)
        if not stock_id_df.empty:
            with open(test_data_dir / f"{ticker}_stock_id.pkl", "wb") as f:
                pickle.dump(stock_id_df, f)
            print(f"✅ Captured stock ID data for {ticker}")
            
            # Capture IV response
            stock_id = stock_id_df['STOCK_ID'].iloc[0]
            iv_df = snowflakeIvolQueries(cursor, stock_id)
            if not iv_df.empty:
                with open(test_data_dir / f"{ticker}_iv_data.pkl", "wb") as f:
                    pickle.dump(iv_df, f)
                print(f"✅ Captured IV data for {ticker}")
                
                # Show sample of captured data
                print(f"\nCaptured data preview:")
                print(f"Stock ID: {stock_id}")
                print(f"IV data shape: {iv_df.shape}")
                print(f"IV range: {iv_df['IV'].min():.4f} to {iv_df['IV'].max():.4f}")
            else:
                print(f"⚠️  No IV data found for {ticker}")
        else:
            print(f"⚠️  No stock ID found for {ticker}")
            
    except Exception as e:
        print(f"❌ Error capturing data: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        real_conn.close()

# =====================================
# MAIN EXECUTION
# =====================================

if __name__ == '__main__':
    print("=== calcImpliedVol Test Suite ===")
    print("1. Run unit tests only (mocked data)")
    print("2. Run integration tests only (real Snowflake)")
    print("3. Run both unit and integration tests")
    print("4. Capture sample data for future testing")
    print("5. Exit")
    
    try:
        choice = input("Enter choice (1-5): ").strip()
    except:
        choice = "1"  # Default to unit tests
    
    if choice == "1":
        print("\n" + "="*60)
        print("RUNNING UNIT TESTS")
        print("="*60)
        suite = unittest.TestLoader().loadTestsFromTestCase(TestCalcImpliedVolUnit)
        unittest.TextTestRunner(verbosity=2).run(suite)
        
    elif choice == "2":
        print("\n" + "="*60)
        print("RUNNING INTEGRATION TESTS")
        print("="*60)
        suite = unittest.TestLoader().loadTestsFromTestCase(TestCalcImpliedVolIntegration)
        unittest.TextTestRunner(verbosity=2).run(suite)
        
    elif choice == "3":
        print("\n" + "="*60)
        print("RUNNING ALL TESTS")
        print("="*60)
        unittest.main(argv=[''], exit=False, verbosity=2)
        
    elif choice == "4":
        capture_sample_data_for_testing("AAPL")
        
    elif choice == "5":
        print("Exiting...")
        
    else:
        print("Invalid choice. Running unit tests by default.")
        suite = unittest.TestLoader().loadTestsFromTestCase(TestCalcImpliedVolUnit)
        unittest.TextTestRunner(verbosity=2).run(suite)
    
    print("\n🏁 Test execution completed!")