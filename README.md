# Document Management & Secure File Sharing System

A modular REST API built with FastAPI, Python, PostgreSQL, SQLAlchemy, JWT authentication, and Argon2 password hashing.

## Features — Day 1

- User registration with validation
- Secure Argon2 password hashing
- JWT access token generation and validation
- Protected current-user profile endpoint
- PostgreSQL database integration
- SQLAlchemy ORM
- Pydantic request and response schemas
- Automated authentication tests using Pytest

## Technology Stack

- Python
- FastAPI
- Mysql
- SQLAlchemy
- Pydantic
- Argon2
- PyJWT
- Pytest

## Setup

1. Create and activate a virtual environment.
2. Install dependencies using `pip install -r requirements.txt`.
3. Create the `document_management_db` PostgreSQL database.
4. Configure the `.env` file with your database URL and JWT secret.
5. Start the application:

```bash
uvicorn app.main:app --reload
```

## API Documentation

Open `http://127.0.0.1:8000/docs` to explore and test the API.

## Authentication Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/auth/register` | Register a user |
| POST | `/api/v1/auth/login` | Obtain a JWT access token |
| GET | `/api/v1/auth/me` | Get the authenticated user's profile |
| GET | `/health` | Check application health |

## Run Tests

```bash
pytest -v
```

## Security Notes

- Passwords are stored as Argon2 hashes.
- Protected endpoints require a valid bearer token.
- Secrets and database credentials belong in `.env`, not source control.
- Never commit real credentials or production user data.

## Day 2 — File Upload & Document Management

### Features

- Single and multiple document uploads
- File extension, MIME type, content signature, and size validation
- UUID-generated storage filenames
- Document metadata stored in MySQL
- Authenticated document listing and retrieval
- Secure document downloads
- Owner-only document deletion
- Pagination, filename search, content-type filtering, and sorting
- Pytest coverage for document APIs

### Document API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/documents/upload` | Upload one document |
| POST | `/api/v1/documents/upload-multiple` | Upload multiple documents |
| GET | `/api/v1/documents/` | List and filter documents |
| GET | `/api/v1/documents/{document_id}` | Retrieve document metadata |
| GET | `/api/v1/documents/{document_id}/download` | Download a document |
| DELETE | `/api/v1/documents/{document_id}` | Delete an owned document |

### Storage and Security

- Document metadata is stored in MySQL.
- Uploaded file contents are stored in `storage/documents/`.
- Document endpoints require JWT bearer authentication.
- Users can access only their own documents.
- Uploads are limited to five files per request and 10 MB per file by default.
- Uploaded files are excluded from Git using `.gitignore`.

### Run Tests

```bash
python -m pytest -v
```

### Run the Application

```bash
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` to test the APIs.

# Day 3: Role-Based Access Control (RBAC) & Document Sharing

## Overview

Day 3 of the **Document Management & Secure File Sharing System** focuses on implementing Role-Based Access Control (RBAC), secure document sharing, and permission-based document access using FastAPI, Python, SQLAlchemy, and MySQL.

## Technologies Used

- Python
- FastAPI
- MySQL
- SQLAlchemy
- JWT Authentication
- Pydantic
- Pytest
- Swagger UI

## Features Implemented

### 1. Role-Based Access Control (RBAC)

Implemented four user roles:

| Role | Permissions |
|---|---|
| Admin | Full access to documents and user-role management |
| Manager | Read and download documents; share and delete owned documents |
| User | Manage owned documents and share them with other users |
| Viewer | Read and download permitted documents only |

Reusable role-validation dependencies are used to restrict API access according to user roles.

### 2. Document Sharing

Users can share documents with other registered users using their email addresses.

Sharing permissions:

- **Read:** Allows the recipient to view document information but not download the file.
- **Download:** Allows the recipient to view document information and download the file.

Implemented functionality:

- Share documents with registered users.
- Assign read or download permissions.
- View received shared documents.
- Update permissions when sharing the same document again.
- Revoke document-sharing permissions.

### 3. Document Access Control

- Validate document ownership before restricted operations.
- Prevent viewers from uploading documents.
- Allow document access based on assigned roles.
- Check sharing permissions before downloading files.
- Return appropriate HTTP status codes for unauthorized or forbidden operations.
- Restrict user-role changes to administrators.

### 4. Admin Role Management

Administrators can change user roles through a protected API endpoint.

The initial administrator role is assigned directly in the database. New users receive the default `user` role, and users cannot assign themselves administrator privileges through registration.

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/shares/documents/{document_id}` | Share a document |
| GET | `/api/v1/shares/received` | View received shared documents |
| DELETE | `/api/v1/shares/documents/{document_id}/users/{recipient_id}` | Revoke document sharing |
| PATCH | `/api/v1/admin/users/{user_id}/role` | Update a user's role |
| GET | `/api/v1/documents/{document_id}/download` | Download a document with permission checks |

Existing authentication and document-management endpoints remain available.

## Testing

Automated tests were executed using Pytest.

```bash
pytest -v
```

**Test result: 15 passed**

The tests cover:

- User registration and login
- Protected user profile
- Document upload and download
- Unsupported file extension validation
- Multiple document uploads
- User role defaults
- Unauthorized role changes
- Viewer upload restrictions
- Document sharing and read-only download restrictions

## Security Considerations

- JWT authentication protects user-specific endpoints.
- Role-based dependencies restrict access to protected operations.
- Document ownership and sharing permissions are checked on the server.
- Read-only shares do not grant file-download permission.
- Users cannot change their own role through the public registration process.

## Day 3 Status

**Completed successfully.**

Implemented RBAC, document sharing, and permission-based download restrictions. All 15 automated tests passed.

## Project Progress

- Day 1: Authentication & User Management — Completed
- Day 2: File Upload & Document Management — Completed
- Day 3: RBAC & Secure Document Sharing — Completed
- Day 4: Audit Logs & Activity Tracking — Pending
- Day 5: Testing, Security Improvements & Docker — Pending


# Day 4: Advanced Features & Performance Optimization

## Project Overview

Day 4 focuses on improving the Document Management & Secure File Sharing System built using **FastAPI, Python, MySQL, and Redis**. This phase introduces dependency injection, database transaction management, background tasks, caching, rate limiting, exception handling, request logging, and database migrations.

## Technologies Used

- Python
- FastAPI
- MySQL
- SQLAlchemy
- Redis
- Alembic
- SlowAPI
- Pytest
- JWT Authentication

## Features Implemented

### 1. Dependency Injection
- Used FastAPI dependencies for database sessions and authenticated users.
- Improved code reusability and separation of concerns.

### 2. Database Transactions
- Implemented transaction handling for database operations.
- Added commit and rollback handling to maintain data consistency.
- Coordinated document metadata and audit-log operations.

### 3. Background Tasks
- Implemented background tasks for document upload notifications.
- Kept notification processing separate from the main request flow.

### 4. Redis Caching
- Implemented caching for document listing operations.
- Added cache invalidation after document changes.
- Configured graceful handling when Redis is unavailable.

### 5. Login Rate Limiting
- Added rate limiting to the login endpoint using SlowAPI.
- Configured limits to reduce repeated login attempts.

### 6. Standardized Exception Handling
- Implemented centralized exception handlers.
- Standardized API error responses for HTTP errors, validation errors, rate-limit errors, and unexpected exceptions.

### 7. Request Logging
- Added middleware to log HTTP methods, request paths, response status codes, and request processing time.

### 8. Audit Logging
- Added audit-log records for relevant user and document operations.
- Created an administrator endpoint to retrieve audit logs.

### 9. Database Migrations
- Configured Alembic for database schema migrations.
- Prepared migration support for tracking database schema changes.

## API Endpoint

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/admin/audit-logs` | Retrieve audit logs for administrators |

## Testing

Automated tests were executed using Pytest.

```bash
python -m pytest -v
```

**Test Results:**
- Total tests passed: 15
- Failed tests: 0

All 15 tests passed during the Day 4 test run.

## Day 4 Outcome

Successfully implemented and tested the Day 4 advanced features, including caching, rate limiting, transaction handling, background tasks, centralized exception handling, request logging, and audit logging.

The application is ready for the next development phase, subject to final verification of database migrations and deployment configuration.

# Day 5 – Final Testing, Dockerization & Deployment Preparation

## Overview

Day 5 focused on finalizing the Document Management & Secure File Sharing System by performing application testing, reviewing API documentation, configuring Docker, managing environment variables, and preparing the project for GitHub deployment.

## Tasks Completed

### 1. Unit Testing and Integration Testing
- Implemented and executed automated tests using Pytest.
- Tested authentication and authorization.
- Tested document upload and management APIs.
- Verified Role-Based Access Control (RBAC).
- Tested invalid requests and unauthorized access.
- Verified API error responses.

**Test Result:** 22 tests passed successfully.

### 2. Swagger and OpenAPI Documentation
- Reviewed FastAPI Swagger UI.
- Verified OpenAPI JSON schema.
- Checked API endpoints and request/response documentation.
- Verified multiple file upload documentation.

Swagger UI:

`http://localhost:8000/docs`

OpenAPI JSON:

`http://localhost:8000/openapi.json`

### 3. Docker Configuration

Created a Dockerfile to containerize the FastAPI application.

Configured Docker Compose with three services:

| Service | Technology | Purpose |
|---|---|---|
| Web | FastAPI | Backend application |
| Database | MySQL 8.4 | Data storage |
| Cache | Redis 7 | Caching |

### 4. Environment Variables and Secrets
- Configured environment variables using `.env`.
- Stored database credentials separately from application code.
- Configured Docker Compose environment variables.
- Excluded `.env` from Git using `.gitignore`.

### 5. Database Migration and Startup Verification
- Configured Alembic database migrations.
- Executed migrations during Docker application startup.
- Verified MySQL container health.
- Verified Redis container health.
- Verified FastAPI container startup.

### 6. Docker Commands

**Build Docker images:**

```bash
docker compose build
```

**Start all services:**

```bash
docker compose up -d
```

**Stop all services:**

```bash
docker compose stop
```

**Start stopped services:**

```bash
docker compose start
```

**Check container status:**

```bash
docker compose ps
```

**View application logs:**

```bash
docker compose logs web --tail 100
```

### 7. API Verification
- Started the application using Docker Compose.
- Accessed Swagger UI through the browser.
- Verified the OpenAPI endpoint.
- Confirmed the application was accessible through port 8000.

## Final Deliverables

- Automated test suite with 22 passing tests.
- FastAPI Swagger and OpenAPI documentation.
- Dockerfile.
- Docker Compose configuration.
- MySQL and Redis container configuration.
- Environment variable configuration.
- Alembic migration integration.
- GitHub-ready project structure.

## Conclusion

Successfully completed Day 5 activities for the Document Management & Secure File Sharing System. The project has been tested with 22 passing tests, containerized using Docker, and prepared for deployment.

**Project Status:** Day 5 implementation and Docker setup completed. GitHub publication and production deployment should be verified separately.


## Project Progress

- Day 1: Authentication & User Management — Completed
- Day 2: File Upload & Document Management — Completed
- Day 3: RBAC & Secure Document Sharing — Completed
- Day 4: Audit Logs & Activity Tracking — Completed
- Day 5: Testing, Security Improvements & Docker — Completed



## Project Roadmap

- Day 1: Authentication and user management
- Day 2: File upload and document management
- Day 3: Role-based access control and document sharing
- Day 4: Advanced dependencies, Redis, rate limiting, logging, and migrations
- Day 5: Testing, Docker, and final integration

## Author

**S. Gaviprawin**

Python Full-Stack Developer

- GitHub: https://github.com/Gaviprawin
- LinkedIn: https://www.linkedin.com/in/gaviprawin/
