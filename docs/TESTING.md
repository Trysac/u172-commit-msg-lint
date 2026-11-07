# Testing

## Running

```sh
uv run pytest --cov=commit_msg_lint
```

## Test Coverage

The repository includes `tests/test_commit_msg_lint.py` which contains tests covering:

- All acceptance criteria defined in the project specification.
- Individual validation of rules C001 through C010.
- Correctness of the `parse` function for header, body, and footer extraction.
- The safe correction logic in `suggest`.
- Error handling for invalid inputs and oversized files.
- The `main` CLI entrypoint, covering success, finding, and error exit codes.
