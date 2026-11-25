from pathlib import Path

import pytest
from google.adk.evaluation.agent_evaluator import AgentEvaluator
from google.adk.evaluation.eval_config import get_evaluation_criteria_or_default
from google.adk.evaluation.eval_set import EvalSet

EVALS_DIR = Path(__file__).resolve().parent.parent / "expense_approval_agent" / "evals"


@pytest.mark.asyncio
async def test_expense_approval_evalset():
    """CI/CD regression gate binding eval_config.json via ADK's AgentEvaluator."""
    eval_file = EVALS_DIR / "expense_approval.evalset.json"
    config_file = EVALS_DIR / "eval_config.json"

    eval_set = EvalSet.model_validate_json(eval_file.read_text(encoding="utf-8"))
    eval_config = get_evaluation_criteria_or_default(str(config_file))

    # AgentEvaluator.evaluate_eval_set lanza AssertionError si algún criterio falla
    await AgentEvaluator.evaluate_eval_set(
        agent_module="expense_approval_agent",
        eval_set=eval_set,
        eval_config=eval_config,
        num_runs=1,
        print_detailed_results=True,
    )
