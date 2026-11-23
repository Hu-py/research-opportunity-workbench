from pathlib import Path


def test_business_oauth_audience_hook_sql_has_valid_function_delimiters():
    sql_path = Path(__file__).parents[1] / "docs" / "sql" / "business_agent_oauth_audience_hook.sql"
    sql = sql_path.read_text(encoding="utf-8")

    assert "create or replace function public.business_agent_oauth_access_token_hook(event jsonb)" in sql
    assert "set search_path = ''" in sql
    assert "end;\n$$;" in sql
    assert "\n$;\n" not in sql
    assert "claims->>'client_id'" in sql
    assert "jsonb_build_array(resource_audience, 'authenticated')" in sql
