"""Test-case structured-output schema (Pydantic)."""
import pytest
from pydantic import ValidationError

from server.agent.core_tools import TestCase, TestCaseList


def test_valid_test_case():
    tc = TestCase(
        id="TC-1",
        title="正常登录",
        steps=["输入账号密码", "点击登录"],
        expected_result="登录成功",
        priority="P1",
        source_basis=["01_login_prd.md#概述"],
        basis_type="documented",
    )
    assert tc.id == "TC-1"
    assert tc.basis_type == "documented"


def test_invalid_basis_type_rejected():
    with pytest.raises(ValidationError):
        TestCase(
            id="TC-1", title="x", steps=["s"], expected_result="ok",
            priority="P1", basis_type="made_up",
        )


def test_missing_id_rejected():
    with pytest.raises(ValidationError):
        TestCase(
            title="x", steps=["s"], expected_result="ok",
            priority="P1", basis_type="documented",
        )


def test_testcase_list():
    tcs = TestCaseList(test_cases=[
        TestCase(id="TC-1", title="x", steps=["s"], expected_result="ok",
                 priority="P1", basis_type="documented"),
    ])
    assert len(tcs.test_cases) == 1
