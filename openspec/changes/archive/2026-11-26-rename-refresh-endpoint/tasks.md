## 1. Rename the endpoint

- [x] 1.1 In `api/main.py`, change the route to `POST /refresh` and rename the handler to `refresh`; verify `/refresh` appears and `/refresh_transactions` does not in `app.openapi()["paths"]`
- [x] 1.2 Update the requested paths in `tests/api/test_main.py` to `/refresh`; verify the existing tests pass
- [x] 1.3 Add a test that `POST /refresh_transactions` returns 404 without opening a mail session; verify it passes

## 2. Verification

- [x] 2.1 Run the full test suite and the pre-commit hooks; verify both pass
- [x] 2.2 Search outside `openspec/` for `refresh_transactions`; verify the only match is the 404 test
- [x] 2.3 When syncing specs, also change "transaction refresh" in the `refresh-api` Purpose to "refresh"; verify the Purpose reads correctly
