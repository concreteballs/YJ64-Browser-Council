import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker, ValidationError


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "browser-council-v1.schema.json"
V1_FIXTURE_PATH = ROOT / "tests" / "fixtures" / "yj64-council-api-v1-contract.json"


class ContractSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.validator = Draft202012Validator(
            cls.schema, format_checker=FormatChecker()
        )
        cls.external_v1 = json.loads(V1_FIXTURE_PATH.read_text(encoding="utf-8"))

    def assert_definition_valid(self, name, value):
        validator = Draft202012Validator(
            {"$schema": self.schema["$schema"], "$ref": f"#/$defs/{name}",
             "$defs": self.schema["$defs"]},
            format_checker=FormatChecker(),
        )
        validator.validate(value)

    def test_schema_is_valid_draft_2020_12(self):
        Draft202012Validator.check_schema(self.schema)

    def test_event_envelope_accepts_valid_event(self):
        self.assert_definition_valid("event", {
            "protocol_version": "browser-council.internal.v1",
            "event_id": "evt-001",
            "workspace_id": "ws-001",
            "sequence": 1,
            "type": "run.queued",
            "occurred_at": "2026-11-19T12:00:00Z",
            "resource": {"workspace_id": "ws-001", "run_id": "run-001"},
            "payload": {"status": "queued"},
        })

    def test_completed_run_requires_analytical_outcome(self):
        valid = {
            "run_id": "run-001", "status": "completed",
            "outcome": "insufficient_evidence",
            "created_at": "2026-11-19T12:00:00Z",
            "updated_at": "2026-11-19T12:01:00Z",
        }
        self.assert_definition_valid("run_status", valid)
        invalid = dict(valid)
        invalid["outcome"] = None
        with self.assertRaises(ValidationError):
            self.assert_definition_valid("run_status", invalid)

    def test_non_completed_run_cannot_claim_final_outcome(self):
        value = {
            "run_id": "run-002", "status": "failed", "outcome": None,
            "created_at": "2026-11-19T12:00:00Z",
            "updated_at": "2026-11-19T12:01:00Z",
        }
        self.assert_definition_valid("run_status", value)
        value["outcome"] = "consensus"
        with self.assertRaises(ValidationError):
            self.assert_definition_valid("run_status", value)

    def test_api_and_browser_connections_have_distinct_requirements(self):
        api = {
            "provider_connection_id": "pc-001", "workspace_id": "ws-001",
            "connection_type": "api", "provider_key": "openai",
            "display_name": "OpenAI API", "status": "ready",
        }
        self.assert_definition_valid("provider_connection", api)
        browser = dict(api, connection_type="browser_session",
                       browser_profile_id="bp-001")
        self.assert_definition_valid("provider_connection", browser)
        invalid_browser = dict(api, connection_type="browser_session")
        with self.assertRaises(ValidationError):
            self.assert_definition_valid("provider_connection", invalid_browser)
        invalid_api = dict(api, browser_profile_id="bp-001")
        with self.assertRaises(ValidationError):
            self.assert_definition_valid("provider_connection", invalid_api)


    def test_external_yj64_v1_compatibility_fixture_is_explicit(self):
        contract = self.external_v1
        self.assertEqual(contract["contract"], "yj64.council-api.v1")
        self.assertEqual(
            contract["request"]["protocol_version"], "yj64.council-api.v1"
        )
        self.assertEqual(
            contract["status"]["status"],
            ["accepted", "running", "completed", "blocked", "failed", "cancelled"],
        )
        self.assertEqual(
            contract["result"]["outcome"],
            ["consensus", "qualified_consensus", "unresolved_disagreement",
             "insufficient_evidence"],
        )
        self.assertEqual(contract["request"]["limits"]["max_rounds"]["maximum"], 10)
        self.assertEqual(contract["request"]["limits"]["timeout_seconds"]["minimum"], 30)
        self.assertEqual(contract["request"]["limits"]["max_output_tokens"]["minimum"], 256)

    def test_external_v1_claim_and_evidence_types_are_not_silently_collapsed(self):
        external_claim_types = set(self.external_v1["result"]["claim_epistemic_type"])
        internal_claim_types = {
            "observation", "source_fact", "inference", "hypothesis",
            "test_result", "model_assertion",
        }
        self.assertNotEqual(external_claim_types, internal_claim_types)
        self.assertIn("evidence", self.external_v1["result"]["required"])
        self.assertIn("evidence_refs", self.schema["$defs"]["council_result"]["required"])

    def test_create_run_rejects_duplicate_participants_and_unsafe_limits(self):
        valid = {
            "council_id": "council-001", "prompt": "Assess this proposal.",
            "participant_ids": ["p-001", "p-002"],
            "idempotency_key": "request-key-001",
            "limits": {"timeout_seconds": 120, "max_rounds": 3,
                       "max_output_tokens": 4000},
        }
        self.assert_definition_valid("create_run", valid)
        invalid = dict(valid, participant_ids=["p-001", "p-001"])
        with self.assertRaises(ValidationError):
            self.assert_definition_valid("create_run", invalid)
        invalid = dict(valid, limits={"timeout_seconds": 1, "max_rounds": 3,
                                      "max_output_tokens": 4000})
        with self.assertRaises(ValidationError):
            self.assert_definition_valid("create_run", invalid)


if __name__ == "__main__":
    unittest.main()
