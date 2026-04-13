# Sports Team Management Backend

This project is a Django backend for managing sports clubs, teams, players, coaches, and parent-linked child accounts.

The current codebase focuses on role-aware team management:

- user registration and login
- club creation
- team creation and team updates
- adding and removing team members
- captain assignment
- player-specific team data updates
- parent-to-player association and parent-managed child access settings


## Core Concepts

The backend is built around a few main entities:

- `User`
  Custom auth model using email instead of username.
- `Club`
  A sports club managed by a club director.
- `Team`
  A team that belongs to a club.
- `ClubMembership`
  Club-level role assignments. Right now this is used for club directors.
- `TeamMembership`
  Team-level role assignments for players and coaches.
- `PlayerProfile`
  Player-specific data such as jersey number, primary position, and notes.
- `ParentPlayerRelation`
  Links a parent account to a player account.
- `PlayerAccessPolicy`
  Controls whether a player account is parent-managed and which self-service actions the player can perform.

## Current Permission Model

The backend currently supports these high-level behaviors:

- Club directors can manage clubs and teams in their club.
- Club directors can add coaches and players to teams.
- Club directors can remove coaches and players from teams.
- Coaches can manage their own team.
- Coaches can add players to their team.
- Coaches can remove players from their team.
- Coaches and directors can assign or remove captains.
- Players can edit their own emergency contact.
- Parents can be linked to players.
- Parents can manage parent-controlled access settings for linked players under 18.
- If a player is parent-managed, some self-service actions can be restricted.
- Once a player is 18 or older, parent-managed restrictions are ignored for that player.

## Implemented API Endpoints

All backend routes are mounted under `/api/`.

### Authentication

- `POST /api/register/`
- `POST /api/auth/login/`
- `GET /api/auth/me/`

### Clubs and Teams

- `POST /api/clubs/create/`
- `POST /api/clubs/<club_id>/teams/create/`
- `PATCH /api/teams/<team_id>/update/`

### Team Members

- `GET /api/teams/<team_id>/members/`
- `POST /api/teams/<team_id>/members/add/`
- `DELETE /api/teams/<team_id>/members/<target_user_id>/remove/`
- `PATCH /api/teams/<team_id>/members/<target_user_id>/team-data/`

### Captains

- `POST /api/teams/<team_id>/captains/<player_id>/`
- `DELETE /api/teams/<team_id>/captains/<player_id>/remove/`

### Parent Associations and Parent Management

- `POST /api/players/<player_id>/parents/`
- `DELETE /api/players/<player_id>/parents/<parent_id>/`
- `GET /api/players/<player_id>/parent-management/`
- `PATCH /api/players/<player_id>/parent-management/`

## `/auth/me/` Response

The `/api/auth/me/` endpoint returns:

- the authenticated user
- clubs they own as a director
- teams they coach
- teams they play on
- children linked through active parent associations

This is useful for frontend bootstrapping, dashboard loading, and team switching.

## Project Structure

```text
backend/
  apps/
    core/
      admin.py
      permissions.py
      tests.py
      urls.py
      views.py
      models/
        club.py
        membership.py
        parent_player_relation.py
        player_access_policy.py
        player_profile.py
        team.py
        user.py
      migrations/
  config/
    settings/
    urls.py
  manage.py
README.md
venv/
```

## Tech Stack

- Python
- Django 6.0.4
- MySQL
- PyMySQL

See [backend/requirements.txt].

## Local Setup

### 1. Create and activate the virtual environment

If you are using the repo-local virtual environment:

```bash
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r backend/requirements.txt
```

### 3. Configure environment variables

Create a `.env` file at the project root and set values for:

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `MYSQL_DATABASE`
- `MYSQL_USER`
- `MYSQL_PASSWORD`
- `MYSQL_HOST`
- `MYSQL_PORT`

The settings loader reads `.env` from the project root in [base.py](/Users/ronniesaba/Documents/EECE%20430L/430Course/Project/backend/config/settings/base.py).

### 4. Create the MySQL database and user

Create a schema matching `MYSQL_DATABASE`, and a MySQL user whose name and password match `MYSQL_USER` and `MYSQL_PASSWORD` in `.env`.

Example (adjust names/passwords; run in MySQL as an admin user):

```sql
CREATE DATABASE IF NOT EXISTS project_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'project_user'@'localhost' IDENTIFIED BY 'your_secure_password';
GRANT ALL PRIVILEGES ON project_db.* TO 'project_user'@'localhost';
FLUSH PRIVILEGES;
```

Then set `MYSQL_USER`, `MYSQL_PASSWORD`, and `MYSQL_DATABASE` in `.env` to those values. Alternatively, for local development only, you can use `MYSQL_USER=root` and your MySQL root password.

If you see **`OperationalError (1045) Access denied`**, the user or password in `.env` does not match MySQL—fix the credentials or create the user as above.

### 5. Run migrations

```bash
cd backend
python manage.py migrate
```

### 6. Start the server

```bash
python manage.py runserver
```

The API will then be available at something like:

```text
http://127.0.0.1:8000/api/
```

## Tests

The project includes Django tests in [tests.py](/Users/ronniesaba/Documents/EECE%20430L/430Course/Project/backend/apps/core/tests.py).

Run them with:

```bash
cd backend
python manage.py test
```

Note: the tests use the configured MySQL-backed Django database settings, so your local database needs to be available.

## Current Scope

This repository currently implements backend foundations for:

- authentication
- club and team management
- role-aware team membership
- captain assignment
- parent linkage
- parent-managed player restrictions

Features like announcements, payments, attendance confirmation, schedule approval, and richer parent-facing workflows are not fully implemented yet, though the permission structure has started to prepare for them.
