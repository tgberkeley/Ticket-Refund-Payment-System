# Customer Support Dashboard with AI Chat — Databricks Apps + Reflex

### Main Dashboard
![](./assets/crud_app_dashboard.png)

### Refunds Page
![](./assets/crud_app_refunds.png)

### Chat LLM Interface
![](./assets/crud_app_chat.png)

This repository demonstrates how to build a custom [Databricks Apps](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/) application using [Reflex](https://reflex.dev/). It integrates [Databricks Lakebase](https://www.databricks.com/product/lakebase) as an OLTP database and queries LLM APIs via [Foundation Model Serving](https://www.databricks.com/product/model-serving). Users can securely create, read, update, and delete support tickets, refund requests, and payment records, and use an AI chat assistant to query business data.

## Prerequisites

- A Databricks workspace with a [Lakebase database instance](https://docs.databricks.com/aws/en/oltp/instances/about)
- [Databricks CLI](https://docs.databricks.com/aws/en/dev-tools/cli/install) installed and authenticated
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (recommended) or pip
- Python 3.11+

## Local Development

1. Authenticate with your Databricks workspace using OAuth U2M via the CLI:

   ```bash
   databricks auth login --host https://<your-workspace>.cloud.databricks.com
   ```

2. Copy the example environment file and fill in your values:

   ```bash
   cp .env.example .env
   ```

   Edit `.env` with the connection details for your Lakebase instance. See `.env.example` for a description of each variable. `PGUSER` is resolved automatically from your Databricks identity. If you have multiple Databricks CLI profiles, set `DATABRICKS_CONFIG_PROFILE` to the profile name you want to use. The `.env` file is loaded at startup and is already included in `.gitignore`.

3. Start the app:

   ```bash
   uv run --python 3.11 --with-requirements requirements.txt reflex run
   ```

   This installs dependencies and starts the app in one step. The required database tables (`help_ticket`, `refund_requests`, `stripe_payments`) are created automatically on first startup if they don't already exist, and sample seed data is inserted into empty tables so the dashboard is populated immediately.

## Deploy to Databricks Apps

This app is designed to be deployed to [Databricks Apps](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/) directly from a Git repository. You can point your Databricks App to this repository directly, or fork it to customize the app and deploy from your own repo.

1. **(Optional) Create a Lakebase instance** — if you don't have one yet, create a Lakebase database instance in your workspace:
   - Via UI: click **Apps > Lakebase Postgres > Provisioned > Create database instance**
   - Or via CLI: `databricks database create-database-instance <instance-name> --capacity CU_1`
   - See [Create and manage a database instance](https://docs.databricks.com/aws/en/oltp/instances/create)

2. **Create the app and add a Lakebase database resource**:
   - Via UI: go to **Compute > Apps > Create app**. During app creation, add a Lakebase database resource under **App resources > Add resource > Database**. Select your database instance and database.
   - Or via CLI: `databricks apps create <your-app-name>`
   - For an existing app, go to **Compute > Apps > your app** and click **Edit** to add the database resource.
   - Adding a Lakebase resource automatically sets the PG* environment variables (`PGHOST`, `PGDATABASE`, `PGPORT`, `PGUSER`, `PGSSLMODE`) and grants the app's service principal `CONNECT` and `CREATE` privileges on the database.
   - See [Add a Lakebase resource to a Databricks app](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/lakebase)

3. **Configure the Git repository**:
   - In the app configuration, enter the Git repository URL and select your Git provider
   - For private repositories, configure a Git credential for the app's service principal
   - See [Deploy a Databricks app](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/deploy)

4. **Deploy**:
   - Click **Deploy > From Git**, then select the branch, tag, or commit to deploy
   - The app runs using the command defined in `app.yaml`

   Databricks authentication and PG* environment variables are handled automatically by the platform. Database tables are created on first startup. By default, the app uses `PGAPPNAME` (the app name) as the Lakebase instance name. If your instance name differs, add `LAKEBASE_INSTANCE_NAME` to the `env` section in `app.yaml`.

## Project Structure

```
app/
  app.py            # Reflex app definition and page routes
  db.py             # Database connection pool and schema initialization
  components/       # UI components (sidebar, views, charts)
  states/           # Reflex state classes (dashboard, tickets, refunds, payments, chat)
assets/             # Images and static files
app.yaml            # Databricks Apps deployment configuration
rxconfig.py         # Reflex framework configuration
requirements.txt    # Python dependencies
```
