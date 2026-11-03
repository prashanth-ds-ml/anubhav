---
name: debug-sql
description: When run_query returns an error or an implausible result, find the cause from the error and the schema and fix one thing at a time.
---
# Debug a query

1. **Read the error text.** "no such column" or "no such table": check the exact name in `describe_tables` (a column
   may live in a joined table). "ambiguous column": qualify it with its table. A syntax error: simplify, then add back.
2. **Zero rows is a result to question.** Check the filter values exist (case, spelling, the date range the records
   cover) with a small SELECT DISTINCT on that column.
3. **Too many rows or raw rows:** add the GROUP BY or the aggregate the brief asked for.
4. **Change one thing per retry** and say what you changed. A tool fails at most 3 times per request; after that, report
   what failed and why instead of trying again.
