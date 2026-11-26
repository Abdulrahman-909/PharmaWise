# PharmaWise

Django and PostgreSQL manage the medicine catalog, batches, supplier receipts, sales, delivery costs, payments, payment corrections, returns, and daily reports. The React register supports organization login, cash or customer credit, package pricing, line discounts, and on-screen receipts.

Existing accounts and business records from the single-pharmacy source are assigned to Default Pharmacy by the organization migrations. Branch and warehouse records exist; stock quantities are still organization-wide. Posting a return records the quantity. Refunds and restocking are separate work.

## Windows development setup

Use a separate folder for this merged source. Back up the existing database before applying the multi-organization migrations; preferably rehearse on a restored development copy. The archive contains source and an example environment file. Keep real credentials private.

1. Make a virtual environment with Python 3.12 in the root (or use your existing PharmaWise interpreter).
2. Install backend requirements: `.\.venv\Scripts\python.exe -m pip install -r backend\requirements\base.txt`.
3. Configure `backend\.env` with your own Django secret and PostgreSQL settings. Enable `DJANGO_DEBUG=True` for local HTTP development and allow `127.0.0.1,localhost`. On a machine using the approved PostgreSQL 18 system driver, set `$env:Path = "C:\Program Files\PostgreSQL\18\bin;$env:Path"` and `$env:PSYCOPG_IMPL = "python"` in the backend terminal.
4. From the root run `.\.venv\Scripts\python.exe backend\manage.py migrate --plan`, review the database and plan, then run `.\.venv\Scripts\python.exe backend\manage.py migrate`.
5. Start Django with `.\.venv\Scripts\python.exe backend\manage.py runserver`. In a second terminal enter `frontend`, run `npm ci` and `npm run dev`, and open http://127.0.0.1:5173.
6. Sign in with a pharmacy-linked account and choose Checkout. A new platform superuser needs an organization to use the register. Checkout supports AFN organizations and roles with sales creation permission. Customer credit uses an existing customer record.

## Verification

From the backend directory, run the virtual environment's Python with `manage.py test`. In the frontend directory run `npm run build` and `npm run lint`. The test suite uses a temporary database. The consolidated source includes the migration chain and server entry points from the earlier repository.
