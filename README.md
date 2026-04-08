# Full-Stack Project

This repository is set up for a Django backend and a future frontend.

## Current structure

- `backend/`: Django project and apps
- `venv/`: local virtual environment

## Backend quick start

1. Copy `.env.example` to `.env`
2. Update the MySQL credentials in `.env`
3. Create the MySQL schema in MySQL Workbench
4. Install backend dependencies if needed
5. Run migrations from the `backend/` directory
6. Start the server

## MySQL Workbench notes

- Create a database that matches `MYSQL_DATABASE` in `.env`
- Make sure the username, password, host, and port in Workbench match the values in `.env`
- The backend is configured for MySQL through Django using the `PyMySQL` driver
