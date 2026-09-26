import pytest

from app.ai.tools import ToolRisk
from app.ai.command_risk import CommandRiskClassifier


@pytest.fixture
def classifier():
    return CommandRiskClassifier()


def test_classifies_read_only_commands(classifier):
    assert classifier.classify("git status") == ToolRisk.READ
    assert classifier.classify("git diff") == ToolRisk.READ
    assert classifier.classify("pytest .\\tests") == ToolRisk.READ


def test_classifies_low_risk_write_commands(classifier):
    assert classifier.classify("git add .") == ToolRisk.LOW_RISK_WRITE


def test_classifies_system_change_commands(classifier):
    assert classifier.classify("pip install pandas") == ToolRisk.SYSTEM_CHANGE


def test_classifies_destructive_commands(classifier):
    assert classifier.classify("git reset --hard") == ToolRisk.DESTRUCTIVE


def test_unknown_commands_use_conservative_fallback(classifier):
    assert classifier.classify("some_unknown_command") == ToolRisk.COMMAND

def test_similar_commands_do_not_inherit_a_more_permissive_risk(classifier):
    assert classifier.classify("git reset") == ToolRisk.COMMAND
    assert classifier.classify("git reset --soft HEAD") == ToolRisk.COMMAND
    assert classifier.classify("git clean -fd") == ToolRisk.COMMAND
    assert classifier.classify("git add important.py") == ToolRisk.COMMAND

def test_command_classification_normalizes_whitespace_and_case(classifier):
    assert classifier.classify("  GIT STATUS  ") == ToolRisk.READ
    assert classifier.classify("  git diff  ") == ToolRisk.READ
    assert classifier.classify("  GIT ADD .  ") == ToolRisk.LOW_RISK_WRITE
    assert classifier.classify("  PIP INSTALL pandas  ") == ToolRisk.SYSTEM_CHANGE
    assert classifier.classify("  GIT RESET --HARD  ") == ToolRisk.DESTRUCTIVE        

def test_empty_commands_are_rejected(classifier):
    with pytest.raises(ValueError, match="Command cannot be empty"):
        classifier.classify("")

    with pytest.raises(ValueError, match="Command cannot be empty"):
        classifier.classify("   ")    

def test_classifies_additional_read_only_development_commands(classifier):
    assert classifier.classify("python -m pytest .\\tests") == ToolRisk.READ
    assert classifier.classify("git log") == ToolRisk.READ
    assert classifier.classify("git show") == ToolRisk.READ        

def test_read_only_classification_requires_exact_supported_commands(classifier):
    assert classifier.classify("git reset") == ToolRisk.COMMAND
    assert classifier.classify("git reset --soft HEAD") == ToolRisk.COMMAND
    assert classifier.classify("git clean -fd") == ToolRisk.COMMAND
    assert classifier.classify("git add important.py") == ToolRisk.COMMAND
    assert classifier.classify("git checkout feature") == ToolRisk.COMMAND
    assert classifier.classify("npm install") == ToolRisk.COMMAND

def test_classifies_supported_read_only_command_variants(classifier):
    assert classifier.classify("git status --short") == ToolRisk.READ
    assert classifier.classify("git diff --cached") == ToolRisk.READ
    assert classifier.classify("git diff --stat") == ToolRisk.READ
    assert classifier.classify("git log --oneline") == ToolRisk.READ
    assert classifier.classify("git show HEAD") == ToolRisk.READ
    assert classifier.classify("git branch --show-current") == ToolRisk.READ
    assert classifier.classify("git rev-parse --show-toplevel") == ToolRisk.READ

    assert classifier.classify("pytest") == ToolRisk.READ
    assert classifier.classify("pytest .\\tests -q") == ToolRisk.READ
    assert classifier.classify(
        "python -m pytest .\\tests -q"
    ) == ToolRisk.READ
    assert classifier.classify("python --version") == ToolRisk.READ