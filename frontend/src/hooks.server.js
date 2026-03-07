/** @type {import('@sveltejs/kit').Handle} */
export async function handle({ event, resolve }) {
  if (event.url.pathname === '/favicon.ico') {
    return Response.redirect(new URL('/favicon.png', event.url), 302);
  }
  return resolve(event);
}
