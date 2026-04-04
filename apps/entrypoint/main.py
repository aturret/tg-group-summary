from tg_summary_core.config import settings
from tg_summary_core.report.report_generate import test_get_daily_report_multimodal

if __name__ == "__main__":
    test_get_daily_report_multimodal('gemini', model=settings.summary_model, num_calls=5)
