# Deploying the frontend (tritone.cards)

## Build

```bash
npm ci
npm run build
```

Output is in **`build/`**: `index.html`, `_app/` (JS/CSS), `favicon.png`, `manifest.webmanifest`, etc.

## Why you get a white screen / "MIME type text/html" for .js

If the browser requests `/_app/immutable/entry/start.XXXX.js` and the server returns **HTML** (your SPA `index.html`) instead of the real JavaScript file, you see:

- **"Expected a JavaScript-or-Wasm module script but the server responded with a MIME type of text/html"**
- Blank white screen

That means the server is sending the SPA fallback for **every** request instead of serving static files first.

## Fix: serve static files first, then fallback to index.html

The server must:

1. **Use the full `build/` output as the document root** (so that `/_app/` exists as a directory).
2. **Serve existing files with correct MIME types** (e.g. `.js` → `application/javascript`).
3. **Only** serve `index.html` for requests that do **not** match a file or directory.

### Nginx

```nginx
root /path/to/build;
index index.html;
location / {
    try_files $uri $uri/ /index.html;
}
# Optional: ensure .js MIME type
location ~* \.js$ {
    add_header Content-Type "application/javascript; charset=utf-8";
}
```

### Apache

```apache
DocumentRoot /path/to/build
<Directory /path/to/build>
    Options -Indexes +FollowSymLinks
    AllowOverride None
    Require all granted
    RewriteEngine On
    RewriteBase /
    RewriteRule ^index\.html$ - [L]
    RewriteCond %{REQUEST_FILENAME} !-f
    RewriteCond %{REQUEST_FILENAME} !-d
    RewriteRule . /index.html [L]
</Directory>
```

### Node / Express (e.g. serve or custom server)

- Serve the `build/` directory as static first (e.g. `express.static('build')`).
- Then add a catch-all that sends `index.html` only for GET requests that didn’t match a file.

### Vercel / Netlify

- Use the repo’s `vercel.json` / `netlify.toml` so the app is built with `npm run build` and the **publish directory is `build`**.
- Both platforms serve static files first; the SPA fallback only applies when no file is found.

## AdGuard / extension errors

`GET https://local.adguard.org/... net::ERR_CONNECTION_REFUSED` is from the AdGuard browser extension. It does not affect your app. Users can disable AdGuard for your site or ignore the error.
