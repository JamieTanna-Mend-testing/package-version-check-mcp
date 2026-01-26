# package-version-check-mcp
A MCP server that returns the current, up-to-date version of packages you use as dependencies in a variety of ecosystems, such as Python, NPM, Go, or GitHub Actions

## Features

Currently supported ecosystems:
- **npm** - Node.js packages from the npm registry
- **pypi** - Python packages from PyPI
- **GitHub Actions** - Actions hosted on GitHub

## Usage

### Running the Server

To run the MCP server:

```bash
.poetry/bin/poetry run python -m package_version_check_mcp.main
```

Or if you have the `.venv` activated:

```bash
python src/package_version_check_mcp/main.py
```

### Available Tools

#### `get_latest_versions`

Fetches the latest versions of packages from various ecosystems.

**Input:**
- `packages`: Array of package specifications, where each item contains:
  - `ecosystem` (required): Either "npm" or "pypi"
  - `package_name` (required): The name of the package (e.g., "express", "requests")
  - `version` (optional): Version constraint (not currently used for filtering)

**Output:**
- `result`: Array of successful lookups with:
  - `ecosystem`: The package ecosystem (as provided)
  - `package_name`: The package name (as provided)
  - `latest_version`: The latest version number (e.g., "1.2.4")
  - `digest`: (optional) Package digest/hash if available
  - `published_on`: (optional) Publication date if available
- `lookup_errors`: Array of errors with:
  - `ecosystem`: The package ecosystem (as provided)
  - `package_name`: The package name (as provided)
  - `error`: Description of the error

**Example:**
```json
{
  "packages": [
    {"ecosystem": "npm", "package_name": "express"},
    {"ecosystem": "pypi", "package_name": "requests"}
  ]
}
```

#### `get_github_action_versions_and_args`

Fetches the latest versions and metadata for GitHub Actions hosted on github.com.

**Input:**
- `action_names` (required): Array of action names in "owner/repo" format (e.g., ["actions/checkout", "docker/login-action"])
- `include_readme` (optional): Boolean (default: false), whether to include the action's README.md with usage instructions

**Output:**
- `result`: Array of successful lookups with:
  - `name`: The action name (as provided)
  - `latest_version`: The most recent Git tag (e.g., "v3.2.4")
  - `metadata`: The action.yml metadata as an object with fields:
    - `inputs`: Action input parameters
    - `outputs`: Action outputs
    - `runs`: Execution configuration
  - `readme`: (optional) The action's README content if `include_readme` was true
- `lookup_errors`: Array of errors with:
  - `name`: The action name (as provided)
  - `error`: Description of the error

**Example:**
```json
{
  "action_names": ["actions/checkout", "actions/setup-python"],
  "include_readme": false
}
```

## Development

### Package management with Poetry

#### Setup

On a new machine, create a venv for Poetry (in path `<project-root>/.poetry`), and one for the project itself (in path `<project-root>/.venv`), e.g. via `C:\Users\USER\AppData\Local\Programs\Python\Python312\python.exe -m venv <path>`.
This separation is necessary to avoid dependency _conflicts_ between the project and Poetry.

Using the `pip` of the Poetry venv, install Poetry via `pip install -r requirements-poetry.txt`

Then, run `poetry sync --all-extras`, but make sure that either no venv is active, or the `.venv` one, but **not** the `.poetry` one (otherwise Poetry would stupidly install the dependencies into that one, unless you previously ran `poetry config virtualenvs.in-project true`). The `--all-extras` flag is required to install development dependencies like pytest.

#### Updating dependencies

- When dependencies changed **from the outside**, e.g. because Renovate updated the `pyproject.toml` and `poetry.lock` file, run `poetry sync --all-extras` to update the local environment. This removes any obsolete dependencies from the `.venv` venv.
- If **you** updated a dependency in `pyproject.toml`, run `poetry update && poetry sync --all-extras` to update the lock file and install the updated dependencies including extras.
- To only update the **transitive** dependencies (keeping the ones in `pyproject.toml` the same), run `poetry update && poetry sync --all-extras`, which updates the lock file and installs the updates into the active venv.

Make sure that either no venv is active (or the `.venv` venv is active) while running any of the above `poetry` commands.
