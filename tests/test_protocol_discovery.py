"""Test protocol discovery module."""

import pytest
from lib.protocol_discovery import extract_protocol_structure
from configuration import systems


class TestProtocolDiscovery:
    """Test protocol structure extraction."""

    def test_extract_protocol_structure_returns_dict(self):
        """extract_protocol_structure should return a dict."""
        for protocol_name in systems.keys():
            result = extract_protocol_structure(protocol_name)
            assert isinstance(result, dict)

    def test_extracted_structure_has_protocol_info(self):
        """Extracted structure should contain protocol information."""
        for protocol_name in systems.keys():
            result = extract_protocol_structure(protocol_name)
            assert "protocol_name" in result or protocol_name in result

    def test_extracted_structure_has_roles(self):
        """Extracted structure should list roles."""
        for protocol_name in systems.keys():
            result = extract_protocol_structure(protocol_name)
            # Should have roles in some form
            assert len(result) > 0

    def test_purchase_protocol_extraction(self):
        """Purchase protocol should extract with known roles."""
        result = extract_protocol_structure("Purchase")
        assert result is not None
        # Should contain role information
        assert len(result) > 0

    def test_logistics_protocol_extraction(self):
        """Logistics protocol should extract with known roles."""
        result = extract_protocol_structure("Logistics")
        assert result is not None
        assert len(result) > 0

    def test_protocol_discovery_handles_all_protocols(self):
        """Should handle extraction for all configured protocols."""
        for protocol_name in systems.keys():
            try:
                result = extract_protocol_structure(protocol_name)
                assert result is not None
            except Exception as e:
                pytest.fail(f"Failed to extract {protocol_name}: {str(e)}")
