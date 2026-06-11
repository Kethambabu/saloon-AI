import re

def clean_sql(sql_query: str) -> str:
    sql_clean = sql_query.strip()
    sql_clean = re.sub(
        r"\bINTERVAL\s+'([^'\)]+)\)'",
        r"INTERVAL '\1')",
        sql_clean,
        flags=re.IGNORECASE
    )
    return sql_clean

query = "SELECT SUM(revenue) FROM appointments WHERE start_time::date = (CURRENT_DATE - INTERVAL '2 day)'"
repaired = clean_sql(query)
print("Original:", query)
print("Repaired:", repaired)
assert repaired == "SELECT SUM(revenue) FROM appointments WHERE start_time::date = (CURRENT_DATE - INTERVAL '2 day')"
print("Success!")
