import unittest
import sys
import os

# Add the project root directory to Python path
current_file = os.path.abspath(__file__)
current_dir = os.path.dirname(current_file)
tests_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(tests_dir)
sys.path.insert(0, project_root)

from hello_world.functions.computeOptionValues import computeOptionValues

class TestComputeOptionValues(unittest.TestCase):
    """Unit tests for computeOptionValues function"""
    
    def test_call_option_out_of_money(self):
        """Test call option that is out of the money"""
        # Call with strike > underlying price
        intrinsic, time_val, early_ex = computeOptionValues(
            optionType="call",
            underlyingPrice=100.0,
            strikePrice=110.0,
            optionMidPrice=2.50,
            expectedDividend=0.25
        )
        
        self.assertEqual(intrinsic, 0.0)  # max(0, 100-110) = 0
        self.assertEqual(time_val, 2.50)  # 2.50 - 0 = 2.50
        self.assertEqual(early_ex, 'N')   # OTM, no early exercise

    def test_call_option_in_the_money(self):
        """Test call option that is in the money"""
        # Call with underlying > strike
        intrinsic, time_val, early_ex = computeOptionValues(
            optionType="call",
            underlyingPrice=115.0,
            strikePrice=110.0,
            optionMidPrice=7.50,
            expectedDividend=0.25
        )
        
        self.assertEqual(intrinsic, 5.0)  # max(0, 115-110) = 5
        self.assertEqual(time_val, 2.50)  # 7.50 - 5 = 2.50
        self.assertEqual(early_ex, 'N')   # ITM but time_val > dividend

    def test_call_option_early_exercise_condition(self):
        """Test call option that meets early exercise condition"""
        # ITM call with time value < expected dividend
        intrinsic, time_val, early_ex = computeOptionValues(
            optionType="call",
            underlyingPrice=115.0,
            strikePrice=110.0,
            optionMidPrice=5.10,  # Low time value
            expectedDividend=0.25
        )
        
        self.assertEqual(intrinsic, 5.0)   # max(0, 115-110) = 5
        self.assertAlmostEqual(time_val, 0.10, places=7)   # 5.10 - 5 = 0.10 (floating point precision)
        self.assertEqual(early_ex, 'Y')    # time_val (0.10) < dividend (0.25)

    def test_put_option_out_of_money(self):
        """Test put option that is out of the money"""
        # Put with underlying > strike
        intrinsic, time_val, early_ex = computeOptionValues(
            optionType="put",
            underlyingPrice=115.0,
            strikePrice=110.0,
            optionMidPrice=1.50,
            expectedDividend=0.25
        )
        
        self.assertEqual(intrinsic, 0.0)  # max(0, 110-115) = 0
        self.assertEqual(time_val, 1.50)  # 1.50 - 0 = 1.50
        self.assertEqual(early_ex, 'N')   # Not a call

    def test_put_option_in_the_money(self):
        """Test put option that is in the money"""
        # Put with strike > underlying
        intrinsic, time_val, early_ex = computeOptionValues(
            optionType="put",
            underlyingPrice=105.0,
            strikePrice=110.0,
            optionMidPrice=7.25,
            expectedDividend=0.25
        )
        
        self.assertEqual(intrinsic, 5.0)  # max(0, 110-105) = 5
        self.assertEqual(time_val, 2.25)  # 7.25 - 5 = 2.25
        self.assertEqual(early_ex, 'N')   # Not a call

    def test_negative_time_value(self):
        """Test scenario where time value becomes negative (stale/illiquid data)"""
        # Option price < intrinsic value
        intrinsic, time_val, early_ex = computeOptionValues(
            optionType="call",
            underlyingPrice=115.0,
            strikePrice=110.0,
            optionMidPrice=4.50,  # Less than intrinsic value of 5
            expectedDividend=0.25
        )
        
        self.assertEqual(intrinsic, 5.0)   # max(0, 115-110) = 5
        self.assertEqual(time_val, -0.50)  # 4.50 - 5 = -0.50 (negative!)
        self.assertEqual(early_ex, 'Y')    # time_val (-0.50) < dividend (0.25)

    def test_case_insensitive_option_types(self):
        """Test that option types work with different cases"""
        # Test uppercase
        intrinsic1, _, _ = computeOptionValues("CALL", 110, 100, 12, 0.25)
        intrinsic2, _, _ = computeOptionValues("PUT", 90, 100, 12, 0.25)
        
        # Test mixed case
        intrinsic3, _, _ = computeOptionValues("Call", 110, 100, 12, 0.25)
        intrinsic4, _, _ = computeOptionValues("Put", 90, 100, 12, 0.25)
        
        # Test lowercase
        intrinsic5, _, _ = computeOptionValues("call", 110, 100, 12, 0.25)
        intrinsic6, _, _ = computeOptionValues("put", 90, 100, 12, 0.25)
        
        # All should give same results
        self.assertEqual(intrinsic1, intrinsic3)
        self.assertEqual(intrinsic1, intrinsic5)
        self.assertEqual(intrinsic2, intrinsic4)
        self.assertEqual(intrinsic2, intrinsic6)
        
        # Verify values
        self.assertEqual(intrinsic1, 10.0)  # call: max(0, 110-100)
        self.assertEqual(intrinsic2, 10.0)  # put: max(0, 100-90)

    def test_case_sensitivity_bug_in_early_exercise(self):
        """Test the case sensitivity bug in early exercise logic"""
        # This test exposes the bug: early exercise check uses exact match
        # while intrinsic value calculation uses case-insensitive match
        
        # Test with uppercase "CALL" - should trigger early exercise but won't due to bug
        intrinsic, time_val, early_ex = computeOptionValues(
            optionType="CALL",  # Uppercase
            underlyingPrice=115.0,
            strikePrice=110.0,
            optionMidPrice=5.10,
            expectedDividend=0.25
        )
        
        self.assertEqual(intrinsic, 5.0)   # Intrinsic calculation works (case-insensitive)
        self.assertAlmostEqual(time_val, 0.10, places=7)   # Time value calculation works (floating point precision)
        # BUG: This should be 'Y' but will be 'N' due to case sensitivity bug
        self.assertEqual(early_ex, 'N')    # Bug: exact match "CALL" != "call"

    def test_at_the_money_options(self):
        """Test options that are exactly at the money"""
        # Call ATM
        intrinsic1, time_val1, early_ex1 = computeOptionValues(
            "call", 100.0, 100.0, 3.50, 0.25
        )
        
        # Put ATM  
        intrinsic2, time_val2, early_ex2 = computeOptionValues(
            "put", 100.0, 100.0, 3.50, 0.25
        )
        
        # Both should have zero intrinsic value
        self.assertEqual(intrinsic1, 0.0)
        self.assertEqual(intrinsic2, 0.0)
        
        # Both should have same time value
        self.assertEqual(time_val1, 3.50)
        self.assertEqual(time_val2, 3.50)
        
        # Neither should early exercise
        self.assertEqual(early_ex1, 'N')
        self.assertEqual(early_ex2, 'N')

    def test_zero_dividend(self):
        """Test with zero expected dividend"""
        intrinsic, time_val, early_ex = computeOptionValues(
            optionType="call",
            underlyingPrice=115.0,
            strikePrice=110.0,
            optionMidPrice=5.10,
            expectedDividend=0.0  # No dividend
        )
        
        self.assertEqual(intrinsic, 5.0)
        self.assertAlmostEqual(time_val, 0.10, places=7)  # Fix floating point precision
        self.assertEqual(early_ex, 'N')  # time_val (0.10) > dividend (0.0)

    def test_high_dividend(self):
        """Test with high expected dividend"""
        intrinsic, time_val, early_ex = computeOptionValues(
            optionType="call",
            underlyingPrice=115.0,
            strikePrice=110.0,
            optionMidPrice=7.50,
            expectedDividend=5.0  # Very high dividend
        )
        
        self.assertEqual(intrinsic, 5.0)
        self.assertEqual(time_val, 2.50)
        self.assertEqual(early_ex, 'Y')  # time_val (2.50) < dividend (5.0)

    def test_edge_case_zero_prices(self):
        """Test edge cases with zero prices"""
        # Zero underlying price
        intrinsic1, time_val1, early_ex1 = computeOptionValues(
            "call", 0.0, 100.0, 0.50, 0.25
        )
        self.assertEqual(intrinsic1, 0.0)  # max(0, 0-100) = 0
        
        # Zero strike price (call)
        intrinsic2, time_val2, early_ex2 = computeOptionValues(
            "call", 100.0, 0.0, 100.50, 0.25
        )
        self.assertEqual(intrinsic2, 100.0)  # max(0, 100-0) = 100
        
        # Zero option price
        intrinsic3, time_val3, early_ex3 = computeOptionValues(
            "call", 100.0, 110.0, 0.0, 0.25
        )
        self.assertEqual(intrinsic3, 0.0)   # OTM call
        self.assertEqual(time_val3, 0.0)    # 0 - 0 = 0

    def test_invalid_option_type(self):
        """Test with invalid option type - should cause UnboundLocalError"""
        # The current code doesn't validate option type, so intrinsicValue is never defined
        # This will cause an UnboundLocalError - this is a bug in the original code
        with self.assertRaises(UnboundLocalError):
            computeOptionValues(
                optionType="invalid",
                underlyingPrice=100.0,
                strikePrice=110.0,
                optionMidPrice=2.50,
                expectedDividend=0.25
            )

if __name__ == '__main__':
    print("=== computeOptionValues Unit Tests ===")
    print("Testing option valuation calculations...")
    print()
    
    # Run the tests
    unittest.main(verbosity=2) 