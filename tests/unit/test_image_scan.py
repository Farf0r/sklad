"""Какие уязвимости образа запрещают публикацию (make image-scan)."""

from tools.image_scan import blocking, vulnerabilities

REPORT = {
    "Results": [
        {
            "Target": "debian",
            "Vulnerabilities": [
                {"VulnerabilityID": "CVE-1", "Severity": "CRITICAL", "FixedVersion": "1.2"},
                {"VulnerabilityID": "CVE-2", "Severity": "HIGH", "FixedVersion": ""},
                {"VulnerabilityID": "CVE-3", "Severity": "MEDIUM", "FixedVersion": "2.0"},
            ],
        },
        {"Target": "python-pkg", "Vulnerabilities": None},
        {
            "Target": "python-pkg",
            "Vulnerabilities": [
                {"VulnerabilityID": "CVE-4", "Severity": "HIGH", "FixedVersion": "3.1.6"}
            ],
        },
    ]
}


def ids(vulns):
    return [v["VulnerabilityID"] for v in vulns]


def test_all_vulnerabilities_are_collected():
    assert ids(vulnerabilities(REPORT)) == ["CVE-1", "CVE-2", "CVE-3", "CVE-4"]


def test_only_high_and_critical_with_fix_block_publication():
    assert ids(blocking(vulnerabilities(REPORT))) == ["CVE-1", "CVE-4"]


def test_clean_image_passes():
    assert blocking(vulnerabilities({"Results": [{"Target": "debian"}]})) == []
    assert vulnerabilities({}) == []
