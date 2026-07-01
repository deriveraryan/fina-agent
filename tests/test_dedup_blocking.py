"""Unit tests for the deduplication blocking engine.

TDD-first: These tests define the expected behavior of dedup_blocking.py
before implementation.
"""

import unittest


class TestNormalizeAddress(unittest.TestCase):
    """Tests for normalize_address() — expands abbreviations, normalizes case/whitespace."""

    def test_expands_parade_abbreviation(self):
        from features.scanning.dedup_blocking import normalize_address
        result = normalize_address("123 Anzac Pde, Kensington NSW 2033")
        self.assertEqual(result, "123 anzac parade, kensington nsw 2033")

    def test_expands_street_abbreviation(self):
        from features.scanning.dedup_blocking import normalize_address
        result = normalize_address("45 Main St")
        self.assertEqual(result, "45 main street")

    def test_expands_road_abbreviation(self):
        from features.scanning.dedup_blocking import normalize_address
        result = normalize_address("10 Pacific Rd")
        self.assertEqual(result, "10 pacific road")

    def test_expands_avenue_abbreviation(self):
        from features.scanning.dedup_blocking import normalize_address
        result = normalize_address("7 Collins Ave")
        self.assertEqual(result, "7 collins avenue")

    def test_expands_drive_abbreviation(self):
        from features.scanning.dedup_blocking import normalize_address
        result = normalize_address("99 Ocean Dr")
        self.assertEqual(result, "99 ocean drive")

    def test_expands_terrace_abbreviation(self):
        from features.scanning.dedup_blocking import normalize_address
        result = normalize_address("5 Bondi Tce")
        self.assertEqual(result, "5 bondi terrace")

    def test_case_insensitive(self):
        from features.scanning.dedup_blocking import normalize_address
        result = normalize_address("123 MAIN STREET")
        self.assertEqual(result, "123 main street")

    def test_strips_whitespace(self):
        from features.scanning.dedup_blocking import normalize_address
        result = normalize_address("  123  Main   Street  ")
        self.assertEqual(result, "123 main street")

    def test_empty_string(self):
        from features.scanning.dedup_blocking import normalize_address
        self.assertEqual(normalize_address(""), "")

    def test_none_returns_empty(self):
        from features.scanning.dedup_blocking import normalize_address
        self.assertEqual(normalize_address(None), "")

    def test_no_abbreviation_passthrough(self):
        from features.scanning.dedup_blocking import normalize_address
        result = normalize_address("123 Main Street")
        self.assertEqual(result, "123 main street")

    def test_expands_multiple_abbreviations(self):
        from features.scanning.dedup_blocking import normalize_address
        # Only the road type abbreviation should expand, not "St" in "St Kilda"
        result = normalize_address("10 St Kilda Rd")
        self.assertEqual(result, "10 st kilda road")


class TestComputeFieldCompleteness(unittest.TestCase):
    """Tests for compute_field_completeness() — counts non-null, non-empty fields."""

    def test_full_listing(self):
        from features.scanning.dedup_blocking import compute_field_completeness
        listing = {
            "id": "uuid-1",
            "name": "Test Business",
            "address": "123 Main St",
            "city": "SYDNEY",
            "categories": ["RESTAURANT"],
            "phone": "0412345678",
            "website": "https://test.com",
            "email": "test@test.com",
            "description": "A test business",
            "facebookUrl": "https://facebook.com/test",
        }
        self.assertEqual(compute_field_completeness(listing), 10)

    def test_sparse_listing(self):
        from features.scanning.dedup_blocking import compute_field_completeness
        listing = {
            "id": "uuid-1",
            "name": "Test Business",
            "address": "123 Main St",
            "city": "SYDNEY",
            "phone": None,
            "website": "",
        }
        self.assertEqual(compute_field_completeness(listing), 4)

    def test_empty_list_not_counted(self):
        from features.scanning.dedup_blocking import compute_field_completeness
        listing = {"categories": [], "name": "Test"}
        self.assertEqual(compute_field_completeness(listing), 1)


class TestBuildBlockingPairs(unittest.TestCase):
    """Tests for build_blocking_pairs() — deterministic candidate pair generation."""

    def _make_listing(self, **overrides):
        base = {
            "id": "uuid-default",
            "name": "Default Business",
            "address": "123 Main St",
            "city": "SYDNEY",
            "categories": ["RESTAURANT"],
            "sourceUrl": None,
            "createdAt": "2026-01-01T00:00:00Z",
        }
        base.update(overrides)
        return base

    def test_exact_name_match_creates_pair(self):
        from features.scanning.dedup_blocking import build_blocking_pairs
        listings = [
            self._make_listing(id="a", name="CJ Migration"),
            self._make_listing(id="b", name="CJ Migration"),
        ]
        pairs = build_blocking_pairs(listings)
        self.assertEqual(len(pairs), 1)
        ids = {pairs[0][0]["id"], pairs[0][1]["id"]}
        self.assertEqual(ids, {"a", "b"})

    def test_exact_name_match_case_insensitive(self):
        from features.scanning.dedup_blocking import build_blocking_pairs
        listings = [
            self._make_listing(id="a", name="Manila Grill"),
            self._make_listing(id="b", name="manila grill"),
        ]
        pairs = build_blocking_pairs(listings)
        self.assertEqual(len(pairs), 1)

    def test_fuzzy_name_match_creates_pair(self):
        from features.scanning.dedup_blocking import build_blocking_pairs
        listings = [
            self._make_listing(id="a", name="CJMigration"),
            self._make_listing(id="b", name="CJ Migration"),
        ]
        pairs = build_blocking_pairs(listings)
        self.assertEqual(len(pairs), 1)
        self.assertIn("fuzzy_name_match", pairs[0][2])

    def test_no_false_blocking_different_names(self):
        from features.scanning.dedup_blocking import build_blocking_pairs
        listings = [
            self._make_listing(id="a", name="Manila Grill"),
            self._make_listing(id="b", name="Tindahan Filipino"),
        ]
        pairs = build_blocking_pairs(listings)
        self.assertEqual(len(pairs), 0)

    def test_source_url_match_creates_pair(self):
        from features.scanning.dedup_blocking import build_blocking_pairs
        listings = [
            self._make_listing(id="a", name="Business A", sourceUrl="https://facebook.com/biz"),
            self._make_listing(id="b", name="Business B", sourceUrl="https://facebook.com/biz"),
        ]
        pairs = build_blocking_pairs(listings)
        self.assertEqual(len(pairs), 1)
        self.assertIn("shared_source_url", pairs[0][2])

    def test_no_pair_for_different_urls(self):
        from features.scanning.dedup_blocking import build_blocking_pairs
        listings = [
            self._make_listing(id="a", name="Manila Grill Restaurant", sourceUrl="https://facebook.com/a"),
            self._make_listing(id="b", name="Tindahan Filipino Store", sourceUrl="https://facebook.com/b"),
        ]
        pairs = build_blocking_pairs(listings)
        self.assertEqual(len(pairs), 0)


class TestGroupPairsUnionFind(unittest.TestCase):
    """Tests for group_pairs_union_find() — transitive grouping via Union-Find."""

    def _make_listing(self, id_val):
        return {"id": id_val, "name": f"Listing {id_val}"}

    def test_single_pair_single_group(self):
        from features.scanning.dedup_blocking import group_pairs_union_find
        a = self._make_listing("a")
        b = self._make_listing("b")
        pairs = [(a, b, "exact_name_match")]
        groups = group_pairs_union_find(pairs)
        self.assertEqual(len(groups), 1)
        ids = {l["id"] for l in groups[0]}
        self.assertEqual(ids, {"a", "b"})

    def test_transitive_closure(self):
        from features.scanning.dedup_blocking import group_pairs_union_find
        a = self._make_listing("a")
        b = self._make_listing("b")
        c = self._make_listing("c")
        pairs = [(a, b, "exact_name_match"), (b, c, "fuzzy_name_match")]
        groups = group_pairs_union_find(pairs)
        self.assertEqual(len(groups), 1)
        ids = {l["id"] for l in groups[0]}
        self.assertEqual(ids, {"a", "b", "c"})

    def test_two_separate_groups(self):
        from features.scanning.dedup_blocking import group_pairs_union_find
        a = self._make_listing("a")
        b = self._make_listing("b")
        c = self._make_listing("c")
        d = self._make_listing("d")
        pairs = [(a, b, "exact_name_match"), (c, d, "exact_name_match")]
        groups = group_pairs_union_find(pairs)
        self.assertEqual(len(groups), 2)

    def test_empty_pairs(self):
        from features.scanning.dedup_blocking import group_pairs_union_find
        groups = group_pairs_union_find([])
        self.assertEqual(len(groups), 0)


class TestSelectSurvivor(unittest.TestCase):
    """Tests for select_survivor() — picks oldest createdAt, tiebreaks by completeness."""

    def test_oldest_survives(self):
        from features.scanning.dedup_blocking import select_survivor
        group = [
            {"id": "new", "name": "Biz", "createdAt": "2026-06-01T00:00:00Z", "phone": "123"},
            {"id": "old", "name": "Biz", "createdAt": "2026-01-01T00:00:00Z", "phone": None},
        ]
        survivor, duplicates = select_survivor(group)
        self.assertEqual(survivor["id"], "old")
        self.assertEqual(len(duplicates), 1)
        self.assertEqual(duplicates[0]["id"], "new")

    def test_tiebreak_by_completeness(self):
        from features.scanning.dedup_blocking import select_survivor, compute_field_completeness
        group = [
            {"id": "sparse", "name": "Biz", "createdAt": "2026-01-01T00:00:00Z"},
            {"id": "rich", "name": "Biz", "createdAt": "2026-01-01T00:00:00Z",
             "phone": "123", "website": "https://test.com", "email": "a@b.com"},
        ]
        survivor, duplicates = select_survivor(group)
        self.assertEqual(survivor["id"], "rich")

    def test_single_item_group(self):
        from features.scanning.dedup_blocking import select_survivor
        group = [{"id": "only", "name": "Solo", "createdAt": "2026-01-01T00:00:00Z"}]
        survivor, duplicates = select_survivor(group)
        self.assertEqual(survivor["id"], "only")
        self.assertEqual(len(duplicates), 0)


class TestComputeMergeFields(unittest.TestCase):
    """Tests for compute_merge_fields() — fields to copy from duplicate to survivor."""

    def test_fills_missing_phone(self):
        from features.scanning.dedup_blocking import compute_merge_fields
        survivor = {"id": "s", "name": "Biz", "phone": None}
        duplicate = {"id": "d", "name": "Biz", "phone": "0412345678"}
        merge = compute_merge_fields(survivor, duplicate)
        self.assertEqual(merge["phone"], "0412345678")

    def test_no_overwrite_existing_fields(self):
        from features.scanning.dedup_blocking import compute_merge_fields
        survivor = {"id": "s", "name": "Biz", "phone": "111"}
        duplicate = {"id": "d", "name": "Biz", "phone": "222"}
        merge = compute_merge_fields(survivor, duplicate)
        self.assertNotIn("phone", merge)

    def test_skips_protected_fields(self):
        from features.scanning.dedup_blocking import compute_merge_fields
        survivor = {"id": "s", "createdAt": None}
        duplicate = {"id": "d", "createdAt": "2026-01-01T00:00:00Z"}
        merge = compute_merge_fields(survivor, duplicate)
        self.assertNotIn("id", merge)
        self.assertNotIn("createdAt", merge)

    def test_fills_missing_website_and_email(self):
        from features.scanning.dedup_blocking import compute_merge_fields
        survivor = {"id": "s", "website": None, "email": ""}
        duplicate = {"id": "d", "website": "https://biz.com", "email": "biz@biz.com"}
        merge = compute_merge_fields(survivor, duplicate)
        self.assertEqual(merge["website"], "https://biz.com")
        self.assertEqual(merge["email"], "biz@biz.com")

    def test_empty_duplicate_returns_empty_merge(self):
        from features.scanning.dedup_blocking import compute_merge_fields
        survivor = {"id": "s", "phone": "111", "website": "https://biz.com"}
        duplicate = {"id": "d", "phone": None, "website": ""}
        merge = compute_merge_fields(survivor, duplicate)
        self.assertEqual(merge, {})


class TestGenerateCandidateGroups(unittest.TestCase):
    """Integration test for generate_candidate_groups() — full pipeline."""

    def _make_listing(self, **overrides):
        base = {
            "id": "uuid-default",
            "name": "Default Business",
            "address": "123 Main St",
            "city": "SYDNEY",
            "categories": ["RESTAURANT"],
            "verificationStatus": "VERIFIED",
            "status": "OPERATIONAL",
            "sourceUrl": None,
            "createdAt": "2026-01-01T00:00:00Z",
            "lastEnrichedAt": None,
            "phone": None,
            "website": None,
            "email": None,
            "facebookUrl": None,
            "instagramUrl": None,
            "tiktokUrl": None,
            "description": None,
            "operatingHours": None,
            "imageUrl": None,
            "tags": None,
        }
        base.update(overrides)
        return base

    def test_two_duplicate_pairs_produce_two_groups(self):
        from features.scanning.dedup_blocking import generate_candidate_groups
        listings = [
            self._make_listing(id="a1", name="CJ Migration", createdAt="2026-01-01T00:00:00Z"),
            self._make_listing(id="a2", name="CJMigration", createdAt="2026-03-01T00:00:00Z"),
            self._make_listing(id="b1", name="Manila Grill", createdAt="2026-02-01T00:00:00Z"),
            self._make_listing(id="b2", name="Manila Grill", createdAt="2026-04-01T00:00:00Z"),
            self._make_listing(id="c1", name="Unique Business"),
        ]
        groups = generate_candidate_groups(listings)
        self.assertEqual(len(groups), 2)

    def test_group_structure_has_required_keys(self):
        from features.scanning.dedup_blocking import generate_candidate_groups
        listings = [
            self._make_listing(id="a1", name="CJ Migration", createdAt="2026-01-01T00:00:00Z"),
            self._make_listing(id="a2", name="CJ Migration", createdAt="2026-03-01T00:00:00Z"),
        ]
        groups = generate_candidate_groups(listings)
        self.assertEqual(len(groups), 1)
        group = groups[0]
        self.assertIn("groupId", group)
        self.assertIn("candidates", group)
        self.assertIn("blockingReasons", group)
        self.assertIn("suggestedSurvivorId", group)
        self.assertIn("suggestedDuplicateIds", group)
        self.assertIn("verdict", group)
        self.assertIsNone(group["verdict"])

    def test_suggested_survivor_is_oldest(self):
        from features.scanning.dedup_blocking import generate_candidate_groups
        listings = [
            self._make_listing(id="newer", name="Test Biz", createdAt="2026-06-01T00:00:00Z"),
            self._make_listing(id="older", name="Test Biz", createdAt="2026-01-01T00:00:00Z"),
        ]
        groups = generate_candidate_groups(listings)
        self.assertEqual(groups[0]["suggestedSurvivorId"], "older")
        self.assertEqual(groups[0]["suggestedDuplicateIds"], ["newer"])

    def test_no_duplicates_returns_empty(self):
        from features.scanning.dedup_blocking import generate_candidate_groups
        listings = [
            self._make_listing(id="a", name="Manila Grill Restaurant"),
            self._make_listing(id="b", name="Tindahan Filipino Store"),
            self._make_listing(id="c", name="Barrio Fiesta Catering"),
        ]
        groups = generate_candidate_groups(listings)
        self.assertEqual(len(groups), 0)


if __name__ == "__main__":
    unittest.main()
