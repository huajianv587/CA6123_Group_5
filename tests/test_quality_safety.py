from quality_safety import PIIRedactor, QualitySafetyAgent


def test_pii_redaction():
    text = PIIRedactor().redact("我的手机是13812345678，订单202404250001")
    assert "138****5678" in text
    assert "202404****" in text


def test_guardrail_replaces_unsafe_commitment():
    result = QualitySafetyAgent().review("我们一定赔偿，并且立刻到账")
    assert "一定赔偿" not in result.text
    assert "立刻到账" not in result.text
