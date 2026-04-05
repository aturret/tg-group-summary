import pytest


@pytest.fixture(autouse=True)
def _reset_llm_clients():
    """Reset the lazy singleton clients in gemini.py and gpt.py between tests."""
    import tg_summary_core.report.gemini as gemini_mod
    import tg_summary_core.report.gpt as gpt_mod

    gemini_mod._client = None
    gpt_mod._client = None
    gemini_mod.remove_file_path_list.clear()
    gpt_mod._remove_file_path_list.clear()
    yield
