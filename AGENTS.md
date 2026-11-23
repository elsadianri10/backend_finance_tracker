# Project preferences

- Use relational tables and typed columns for new features. Do not use JSON/JSONB for application data (user preference, 9 October 2026).
- Preserve existing financial data during migrations. Test upgrades and baseline/reset in isolated synthetic schemas; never reset the application database for verification.
- Register FastAPI endpoints with `@router.get`, `@router.post`, `@router.patch`, `@router.delete`, and other method decorators. Keep routes thin: forward validated parameters to controllers, and keep business logic in services.

## Anti-slop for Finance Tracker

Adapted from the [upstream anti-slop rulebook](https://github.com/miqdadbadjuber/anti-slop/blob/main/antislop.md). Apply these checks to the backend code, API responses, and documentation touched by the task.

- Reuse existing route, controller, and service patterns. Add a helper or layer only when it removes real duplication or clarifies a business rule.
- Keep comments focused on reasons the code cannot express, such as why two financial records must update together or why a date uses WIB.
- Use precise errors and documentation. Keep sample financial data clearly marked as synthetic. Base claims about security, performance, and verification on evidence.
- Verify the affected behavior before delivery. For changes that move or count money, check the relevant ownership, duplicate-recording, and consistency cases. Report the checks actually run and any gaps.
