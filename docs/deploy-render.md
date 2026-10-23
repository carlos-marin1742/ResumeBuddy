# Deploying ResumeBuddy on Render

This runbook deploys the `render.yaml` Blueprint: one Docker web service (`resumebuddy`) and one managed Postgres
database (`resumebuddy-db`), both in `ohio`. Registration stays closed (`REGISTRATION_MODE` unset), so you create users
by hand and no email service is needed.

Statements marked **(unverified)** were not confirmed against Render's documentation or a live deploy. Check them
before relying on them; the last section collects them.

## 1. Prerequisites

- A Render account with a payment method (the `0.5c-512mb` web plan and `0.1c-256mb` database are paid plans).
- The repository pushed to a Git provider Render can read. The Blueprint reads `render.yaml` from the repo root.
- Keys on hand: an Anthropic API key, a Groq API key.
- A generated pepper of at least 32 characters. Example: `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
  Store it in a password manager; you need the same value if you ever rebuild the service.
- Locally: the [Render CLI](https://render.com/docs/cli), and `pg_dump`, `pg_restore` and Docker for the backup drill.
- Check the Blueprint before creating it. **Unverified, check with Render's Blueprint validation.** `fromDatabase`
  with `name:` and `property: connectionString` under an `envVars` entry was written from the field list in the spec,
  not from a published example. The Render CLI documents this command (not run here):

  ```bash
  render blueprints validate render.yaml
  ```

  The CLI docs list `blueprints validate [BLUEPRINT_FILE]` with `./render.yaml` as the default and no flags. Whether
  your installed CLI version has it is **not verified**; the dashboard also validates the file when you create the
  Blueprint.

## 2. Create the Blueprint

1. Dashboard: **New > Blueprint**, pick the repository and branch.
2. Render reads `render.yaml` and lists the web service and the database. Both are in `ohio`; the web service uses
   `autoDeployTrigger: "off"`, so pushes never deploy by themselves. Deploy manually from the dashboard.
3. Render prompts for the four `sync: false` variables. Fill them in as described next. Render prompts **only at
   initial Blueprint creation**; later changes go through the service's **Environment** page.
4. Apply. The first build installs Chromium and builds the frontend, so it takes several minutes.

## 3. Set the four secret values

<!-- set-by-hand:start -->
Entered in the dashboard prompt, never committed:

- `AUTH_TOKEN_PEPPER` (at least 32 characters; startup refuses anything shorter)
- `ANTHROPIC_API_KEY`
- `GROQ_API_KEY`
- `ALLOWED_ORIGINS` (see below)
<!-- set-by-hand:end -->

Everything else the app needs in production is already in `render.yaml`: `DATABASE_URL` (the database's internal
connection string), `APP_ENV=production`, `REQUIRE_HTTPS=true`, `PDF_MAX_CONCURRENCY=1`. `REGISTRATION_MODE`,
`STATIC_PROFILES_ENABLED` and `FORWARDED_ALLOW_IPS` are deliberately not set (closed registration, no static
profiles, and the value in section 7 is decided from evidence).

## 4. `ALLOWED_ORIGINS`

Set it to the service's exact public origin: `https://<service>.onrender.com`

- `https` scheme, the exact hostname shown on the service page, **no trailing slash**, no path, no wildcard.
- Any browser POST/PUT/PATCH/DELETE to `/api/*` (other than `/api/auth/*`) that carries an `Origin` header not in this
  list gets `403 Untrusted request origin.`
- Startup refuses an invalid value, so a typo shows up as a failed deploy rather than silent rejections.
- The hostname is only final after the service exists. If Render appends a suffix to the name, correct the variable
  on the **Environment** page and redeploy.
- Add a custom domain later as a second comma-separated origin. That is out of scope here.

## 5. First-deploy checks

Replace `$URL` with `https://<service>.onrender.com`.

1. **Deploy finished.** The deploy log shows `alembic upgrade head` running, then uvicorn listening on
   `0.0.0.0:10000` (**the port is unverified**; the app binds whatever `PORT` Render injects).
2. **Liveness.** `curl -i $URL/health` returns `200 {"status":"ok"}`.
3. **Readiness.** `curl -i $URL/health/ready` returns `200`. A generic `503` means the database, the
   `chrome-headless-shell` binary, or a prerequisite check failed; read the service logs.
4. **Login.** Create a user (section 6), open `$URL`, sign in. A wrong password must not reveal whether the account
   exists.
5. **A POST past the Origin guard.** The guard runs before authentication, so this needs no session:

   ```bash
   # Rejected by the guard (expect 403 and an untrusted_origin_rejected log event)
   curl -i -X POST -H 'Origin: https://evil.example' $URL/api/resumes/parse
   # Passes the guard, then stops at authentication (expect 401, not 403)
   curl -i -X POST -H "Origin: $URL" $URL/api/resumes/parse
   ```

   Then, signed in, run the keyword-extraction step in the UI. It makes one POST with the browser's real `Origin`
   and shows that `ALLOWED_ORIGINS` matches. A `403` here means `ALLOWED_ORIGINS` is wrong.
6. **Cookie flags.** After login, in browser dev tools (Application > Cookies) or `curl -i -X POST $URL/api/auth/login ...`,
   confirm the cookie is named `__Host-resumebuddy_session` with `HttpOnly`, `Secure`, `Path=/`, **no** `Domain`, and
   `SameSite=Lax`. The code sets these; the check confirms nothing between the app and the browser changed them.
7. **Security headers.** `curl -I $URL/health` shows `X-Content-Type-Options`, `X-Frame-Options` and `Referrer-Policy`.
8. **PDF.** Generate one resume and download it, to prove Chromium launches on a 512 MB instance. If the process is
   killed or the request fails, see the unverified assumptions about memory and request timeout.

## 6. Create users, reset a password

Registration is closed, so users are created with the admin script. `render ssh <service> --ephemeral` opens an
ephemeral, isolated shell instance. The CLI docs say Render does not run the service's start command there, so the
script does not depend on a running app. Whether the ephemeral shell receives the service's environment variables
(`DATABASE_URL` and `AUTH_TOKEN_PEPPER`) is **unverified**. Check first:

```bash
render ssh <service> --ephemeral
# inside the shell
cd /app/backend           # the image WORKDIR; the CLI docs list the argument as [SERVICE_ID], so use the ID if the name is rejected
python -c "import os; print(bool(os.environ.get('DATABASE_URL')))"   # must print True
python -m scripts.manage_users create you@example.com    # prompts twice for a 12-128 character password
python -m scripts.manage_users list
```

If the variable is missing, the script fails with "Database configuration is required"; in that case connect with
`render ssh <service>` (without `--ephemeral`) instead, and say so in your notes.

**Reset a password:** `python -m scripts.manage_users reset you@example.com`. It sets the new password, clears the
failed-login lock and revokes the user's active sessions. There is no password-reset UI.

Passwords are only read from the prompt and are never printed or placed in shell history.

## 7. Decide `FORWARDED_ALLOW_IPS` from evidence

The start command passes `--forwarded-allow-ips=${FORWARDED_ALLOW_IPS:-127.0.0.1}`. With the default, uvicorn trusts
`X-Forwarded-*` only from loopback, so behind Render's proxy `request.client.host` is probably the proxy's address
and every user shares one rate-limit bucket. **This runbook does not pick a value.** Collect this evidence first.

1. From a machine whose public IP you know (`curl -s https://api.ipify.org`), send a request with a forged header:

   ```bash
   curl -s -o /dev/null -H 'X-Forwarded-For: 203.0.113.77' $URL/api/resumes
   ```

   (`/api/resumes` answers 401, which is still logged as an `api_request` event.)
2. In the service logs, find that request's `api_request` line (`path=/api/resumes`) and record its `client_ip`:
   - the proxy's internal address (a private range such as `10.x`): the header is not being trusted yet;
   - your real public IP: Render's proxy already overwrites or sanitises the header and uvicorn applied it;
   - `203.0.113.77`: **stop**. The forged value is trusted, so the setting is unsafe as it stands.
3. Repeat from a second network (phone hotspot) and confirm the logged `client_ip` differs between the two.
4. Record the proxy address(es) you saw (a few requests, a few minutes apart) in your notes. Then decide the value
   from that evidence: a value that includes only the proxy addresses is safe, while `*` is only safe if Render's
   proxy always replaces client-supplied `X-Forwarded-For`, which step 2 tests. Set it on the **Environment** page and
   run steps 1 and 2 again to confirm the logged IP is now your real one and the forged value is not.

Until this is done, per-IP rate limits and logs are keyed to one shared address.

## 8. Backups: export and a local restore test

Render's own backup features depend on the plan and are **unverified** for `0.1c-256mb`. Take your own export.

1. Get the **External** database URL from the database's **Info** page. External access is TLS-only; add
   `?sslmode=require` if the URL lacks it. The Blueprint sets no `ipAllowList`, so whether your IP can connect by
   default is **unverified**; if the connection times out, add your IP on the database's access-control settings.
2. Export (custom format, no ownership):

   ```bash
   pg_dump --format=custom --no-owner --no-privileges --file=resumebuddy-$(date +%F).dump "$EXTERNAL_DATABASE_URL"
   ```

3. Restore into a throwaway local Postgres and look at the data:

   ```bash
   docker run -d --name rb-restore -e POSTGRES_PASSWORD=restore-test -p 55432:5432 postgres:16
   # wait a few seconds, then
   PGPASSWORD=restore-test createdb -h localhost -p 55432 -U postgres resumebuddy_restore
   PGPASSWORD=restore-test pg_restore -h localhost -p 55432 -U postgres -d resumebuddy_restore --no-owner resumebuddy-YYYY-MM-DD.dump
   PGPASSWORD=restore-test psql -h localhost -p 55432 -U postgres -d resumebuddy_restore \
     -c "select count(*) from users" -c "select count(*) from master_resumes" -c "select count(*) from tailored_resumes" \
     -c "select version_num from alembic_version"
   docker rm -f rb-restore
   ```

   Row counts match production and `alembic_version` equals the repo's head revision. A dump you have never restored
   is not a backup. Delete the `.dump` afterwards: it contains personal resume data.

## 9. Roll back

- **Code:** dashboard > the service > **Events/Deploys**, pick the previous successful deploy and redeploy or roll
  back to it (exact button names **unverified**). Because auto-deploy is off, only deploys you started are involved.
- **Schema:** the start command runs `alembic upgrade head` on every boot. Rolling the image back does **not** undo a
  migration, and an older image may run against a newer schema. Before deploying a release that adds a migration,
  take the section 8 export. Never edit an applied revision; to reverse a migration, write a new one, or restore from
  the export into a new database and repoint `DATABASE_URL`.
- After a rollback, repeat the section 5 checks.

## 10. Rotate secrets

| Secret | Procedure | Effect |
|---|---|---|
| `AUTH_TOKEN_PEPPER` | Set the new value (at least 32 characters) in **Environment**, redeploy. | The pepper keys the SHA-256 of session and email tokens, so every existing session and outstanding token stops working. Users sign in again. Passwords are bcrypt hashes without the pepper and are unaffected. |
| `ANTHROPIC_API_KEY` | Create a new key in the Anthropic console, update **Environment**, redeploy, check one generation, then revoke the old key. | No user-visible effect. |
| `GROQ_API_KEY` | Same as above in the Groq console, verify keyword extraction, then revoke the old key. | None. |
| `ALLOWED_ORIGINS` | Edit the value (exact origins, no trailing slash) and redeploy. | A wrong value rejects every browser write with 403. |
| Database password | **Unverified.** Render manages it. Confirm in the database settings whether it can be regenerated, and whether `fromDatabase` follows the change, before attempting it. | The app will not connect until `DATABASE_URL` is current. |

Changing an environment variable on Render normally triggers a redeploy (**unverified**); with auto-deploy off,
confirm in the dashboard that the new deploy actually ran.

## 11. Unverified assumptions

- **Request timeout.** Render's maximum time for one HTTP request is not confirmed. Resume generation chains Groq,
  Claude and a Chromium render (up to `PDF_RENDER_TIMEOUT_SECONDS`, default 45, plus the queue wait). Time a real
  generation from the public URL.
- **Ephemeral instances and env vars.** The CLI docs say the start command is not run in `--ephemeral`; they do not say
  whether the service's environment variables are present. Section 6 checks it.
- **Proxy header behavior.** Whether Render's proxy appends to or replaces a client-supplied `X-Forwarded-For`, which
  addresses it connects from, and whether it sets `X-Forwarded-Proto: https` are not confirmed. The app rejects
  non-HTTPS requests with 400 when `X-Forwarded-Proto` is not `https`, so a missing header would make every request
  fail. Sections 5 and 7 test this.
- **Build and runtime memory.** Whether a 512 MB instance builds the image (`npm ci`, Vite, `playwright install
  chromium`) and renders PDFs without being OOM-killed is not confirmed. `PDF_MAX_CONCURRENCY=1` limits renders to one
  at a time. Build limits are separate from runtime limits and are not documented here.
- **Blueprint fields.** The `fromDatabase` `name` and `property` sub-keys and a shared `ohio` region for the internal
  connection string were not seen in a published example. Run `render blueprints validate render.yaml`
  (**not verified** to exist in your CLI version) or let the dashboard validate it.
- **Internal TLS.** Render documents internal Postgres connections as optionally TLS; the Blueprint does not add
  `sslmode`, so the private connection is unencrypted unless Render enforces it. `?sslmode=require` is preserved by
  the app's URL normalization and is tested; self-signed certificates mean `verify-ca` and `verify-full` will not work.
- **Database access control and backups** on the `0.1c-256mb` plan (section 8), and the **dashboard wording** of
  rollback and secret-rotation steps.
- **Ephemeral disk.** Nothing needs a persistent disk: generated PDFs in `outputs/` are re-rendered from the database on
  download after a redeploy, at the cost of one extra render.
