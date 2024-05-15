# python-interface

A high performance Python interface for communicating with RLBot v5.

## Dev setup

- Ensure Python 3.11+ is installed
- Create a virtual Python environment
  - `python3 -m venv venv`
- Activate the virtual environment
  - Windows: `venv\Scripts\activate.bat`
  - Linux: `source venv/bin/activate`
- Install the package
  - `pip install --editable .`
  - This will install the package in editable mode,
  meaning you can make changes to the code and they
  will be reflected in the installed package without
  having to run the command again

This project is formatted using Black.

## Testing

- You can test launching a match with `python tests/runner.py`

## Building

- You can build the package with `python -m build`
  - Note: You might have to `pip install -U build` first
  - `rlbot-5.0.0-py3-none-any.whl` and `rlbot-5.0.0.tar.gz`
  will be created in the `dist` folder
