# Shiny Bot

This is a Python project, likely a web application built with Shiny for Python.

## Project Structure

- `app.py`: The main application file.
- `app_utils.py`: Utility functions for the application.
- `shared.py`: Shared configurations or variables.
- `requirements.txt`: Python dependencies.
- `tips.csv`: Data file.
- `shiny_bookmarks/`: Directory for Shiny application bookmarks, containing `input.json` and `values.json` for each bookmark.
- `.env`: Environment variables.
- `.venv/`: Python virtual environment.

## Setup

1.  **Create a virtual environment** (if not already present):
    ```bash
    python -m venv .venv
    ```

2.  **Activate the virtual environment**:
    -   On Windows:
        ```bash
        .venv\Scripts\activate
        ```
    -   On macOS/Linux:
        ```bash
        source .venv/bin/activate
        ```

3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## Running the Application

To run the Shiny application, execute:

```bash
shiny run app.py
```

This will typically start a web server, and you can access the application in your browser.