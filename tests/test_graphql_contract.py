"""Contract tests for GraphQL queries shared between Fina backend and Fina Agent."""

import os
import unittest
import re

class TestGraphQLContract(unittest.TestCase):
    def test_required_operations_exist(self):
        """Verifies that necessary GraphQL operations are defined in the Fina repository."""
        # Find path to fina repository dataconnect directory
        fina_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../fina/dataconnect"))
        
        # Files to check
        files_to_check = [
            os.path.join(fina_path, "connector/queries.gql"),
            os.path.join(fina_path, "connector/mutations.gql"),
            os.path.join(fina_path, "admin-connector/queries.gql"),
            os.path.join(fina_path, "admin-connector/mutations.gql"),
        ]
        
        all_gql_content = ""
        for file_path in files_to_check:
            if os.path.exists(file_path):
                with open(file_path, "r") as f:
                    all_gql_content += f.read() + "\n"
        
        if not all_gql_content:
            self.skipTest("Fina repository dataconnect files not found, skipping contract test.")

        # Extract operation names using regex
        operations = re.findall(r"(?:query|mutation)\s+([A-Za-z0-9_]+)", all_gql_content)
        
        # Verify required operations
        required_ops = {
            "ListCategories",
            "CreateListing",
            "UpdateListingData",
            "UpdateListingStatus",
            "CreateReview",
            "SemanticSearchListings",
            "SearchListings",
        }
        
        for op in required_ops:
            self.assertIn(op, operations, f"Required GraphQL operation '{op}' not found in Fina repository!")

if __name__ == "__main__":
    unittest.main()
