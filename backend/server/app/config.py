from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "WFM x Finance Integration"
    app_version: str = "0.1.0"
    database_url: str = "sqlite:///./wfm_finance.db"

    # Java frontend origins (Spring Boot, Vaadin, JSP, etc.)
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:4200",
        "http://localhost:8080",
        "http://localhost:8081",
        "http://127.0.0.1:8080",
    ]

    # Reconciliation thresholds (section 6.4)
    coverage_variance_threshold_pct: float = 10.0
    leave_drift_threshold_days: float = 0.5

    # Rate card staleness (section 10 - Risks & Mitigations)
    rate_card_preview_ttl_hours: int = 24

    # Holiday / overtime stacking (section 5.1 step 3)
    holiday_overtime_stack: bool = False

    # Night shift window (section 4.1 / 5.1)
    night_start_hour: int = 22
    night_end_hour: int = 6

    # Default WFM extract for the streaming ingest pipeline. Override with
    # the WFM_CSV_PATH env var or per-request ?path= query string.
    wfm_csv_path: str = "../Agent_Breakdown_140426.csv"


settings = Settings()
