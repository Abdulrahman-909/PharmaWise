# PharmaWise

PharmaWise is a management system in development for retail pharmacies and pharmaceutical distributors. Its goal is to help a business trace medicine batches from purchase to sale and connect each stock movement to its financial records.

## Current status

Milestone 0 is in progress.

| Status | Work |
| --- | --- |
| Implemented | Backend dependency files for Django, Django REST Framework, PostgreSQL connectivity, and testing |
| Verified locally | Python 3.12 environment, Django installation, pytest installation, and PostgreSQL accepting connections |
| In progress | Django project setup, database configuration, and React frontend setup |
| Planned | Medicine catalog, batch and expiry tracking, purchases, point of sale, accounting, and wholesale distribution |

## Development setup

The project is being developed on Windows with PowerShell and PyCharm.
From the repository root, create the backend environment and install the development dependencies.

```powershell
py -3.12 -m venv backend\.venv
.\backend\.venv\Scripts\python.exe -m pip install -r .\backend\requirements\dev.txt
