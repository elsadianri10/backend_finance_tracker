# Project preferences

- Use relational tables and typed columns for new features. Do not use JSON/JSONB for application data (user preference, 9 October 2026).
- Preserve existing financial data during migrations. Test upgrades and baseline/reset in isolated synthetic schemas; never reset the application database for verification.
