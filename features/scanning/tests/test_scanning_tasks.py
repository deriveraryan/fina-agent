"""Unit tests for Fina scanning orchestration task pipelines.

Runs completely offline using unittest mocks.
"""

import unittest
from unittest.mock import patch, MagicMock, AsyncMock
from features.scanning.tasks import scan_city_maps_listings, run_maps_scan_all_cities


class TestScanningTasks(unittest.IsolatedAsyncioTestCase):
    """Offline unit test suite for task orchestration and scheduler hooks."""

    @patch("features.scanning.tasks.execute_graphql_operation")
    @patch.dict("os.environ", {"GOOGLE_MAPS_API_KEY": "mock-key", "GEMINI_API_KEY": ""})
    async def test_scan_city_maps_listings_execution(self, mock_execute: AsyncMock) -> None:
        """Tests that the scan_city_maps_listings pipeline discovery and database persistence flow works."""
        mock_execute.return_value = {
            "data": {
                "listings": []
            }
        }

        # Mock check_duplicate to return None (no duplicate exists)
        with patch("features.scanning.tasks.check_duplicate", new_callable=AsyncMock) as mock_dup:
            mock_dup.return_value = None
            
            results = await scan_city_maps_listings("SYDNEY")
            
            self.assertIsNotNone(results)
            self.assertGreater(results["found"], 0)
            self.assertGreater(results["created"], 0)
            
            # Verify database calls were made
            mock_execute.assert_any_call(
                operation_name="CreateListing",
                variables=unittest.mock.ANY
            )
            mock_execute.assert_any_call(
                operation_name="LogAgentScan",
                variables=unittest.mock.ANY
            )

    @patch("features.scanning.tasks.scan_city_maps_listings", new_callable=AsyncMock)
    async def test_run_maps_scan_all_cities(self, mock_scan_city: AsyncMock) -> None:
        """Tests that run_maps_scan_all_cities iterates over all target cities correctly."""
        mock_scan_city.return_value = {"found": 1, "created": 1, "updated": 0}
        
        await run_maps_scan_all_cities()
        
        # Verify it iterated and ran for all cities
        self.assertGreater(mock_scan_city.call_count, 1)


if __name__ == "__main__":
    unittest.main()
