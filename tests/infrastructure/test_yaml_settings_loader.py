from index_analysis.config.loader import load_settings


def test_load_settings_reads_yaml_file(tmp_path):
    settings_path = tmp_path / "setting.yml"
    settings_path.write_text(
        """
default_ticker: "^N225"
trend_lookbacks:
  - 20
  - 60
risk_free_rate: 0.04
""",
        encoding="utf-8",
    )

    settings = load_settings(settings_path)

    assert settings["default_ticker"] == "^N225"
    assert settings["trend_lookbacks"] == [20, 60]
    assert settings["risk_free_rate"] == 0.04
