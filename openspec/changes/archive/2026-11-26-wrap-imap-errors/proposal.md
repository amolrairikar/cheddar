## Why

The `refresh-api` spec requires HTTP 502 when searching the mailbox or moving emails fails, but some mail server and network errors are not converted into loader errors. Searching and fetching convert no raised errors, and selecting and moving miss network errors, so these surface as an unhandled 500.

## What Changes

- Mail protocol errors and network errors raised while selecting a folder, searching or moving are reported as loader errors, so the refresh responds 502.
- A mail protocol or network error raised while fetching a message fails only that message, and the fetch continues with the next one.
- Unchanged: a fetch that the server answers with a non-OK status, or a message that cannot be decoded or parsed, still fails only that message.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `email-loader`: adds how server and network errors are handled after login.
- `refresh-api`: adds the 502 response for those errors while selecting, searching or moving, and the outcome of a refresh when fetching raises them.

## Impact

- `api/email_parser/loading/imap.py`: `_select_pending`, `fetch_raw` and `move`.
- `tests/loading/` and `tests/api/test_main.py`: new error cases.
- No new dependencies, configuration or response body fields.
