# Deploy the Research Opportunity Workbench

## 1. Safety and persistence

The repository is currently public. The workbench's researcher profiles and idea feedback are **private research records**, so do not deploy without access control.

Streamlit Community Cloud instances do not provide durable local SQLite storage. Use a PostgreSQL service for any real long-term workflow. Configure database TLS and restricted roles on the DB service. Do not paste credentials into Git files.

## 2. Deploy in Streamlit Community Cloud

1. Open https://share.streamlit.io/ and sign in with GitHub.
2. Click **Create app** → **Yup, I have an app**.
3. Repository: `Hu-py/research-opportunity-workbench`
4. Branch: `feat/research-mvp` (switch to `main` after merging PR).
5. Main file path: `app.py`.
6. Under **Advanced settings → Secrets**, set the following (replace placeholders):

```toml
WORKBENCH_REQUIRE_AUTH = "true"
APP_PASSWORD = "replace-with-long-random-password"
DATABASE_URL = "postgresql+psycopg://USER:PASSWORD@HOST:5432/DB?sslmode=require"
```

7. Deploy. Only the successful deployment will issue a real URL.

**Do not put the above example values into the actual secrets.** Do not share the deployed URL/password broadly. The current simple password is a **prototype**, not enterprise-grade user identity management or per-user isolation.

## 3. Initialization

The database schema is created automatically when opening the page. Open **研究者画像** and replace the example profile with your real research directions. Then open **科研总览** and select **更新文献与选题**. The first sync requires working OpenAlex network/API access.

Optional keys can be configured as environment secrets according to your OpenAlex account.

## 4. Weekly briefing automation

The GitHub Actions scheduler is separate from the frontend. To enable recurring summaries, put the **same** `DATABASE_URL` in GitHub Actions Secrets, and set the Actions variable `ENABLE_WEEKLY=true`. Configure SMTP secrets to send email. Do not enable weekly jobs until testing the database connection.

## 5. Local development

```bash
pip install -r requirements.txt
streamlit run app.py
```

For local use, the SQLite default is available and does not require access protection as long as the dashboard is not published to the internet.

## Known MVP limits

- The current app is a personal workbench, **not a public multi-user service**.
- No full-text RAG, LLM autonomous peer review, or verified novelty detection.
- Search scoring is heuristic; users must inspect original paper evidence.
- Password in a simple app session is for private prototype use only.
