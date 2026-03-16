import type { HandleServerError } from '@sveltejs/kit';

export const handleError: HandleServerError = ({ error, status, message }) => {
  if (status >= 500) {
    console.error(`[${status}]`, error);
  }
  // Return a safe message for 500 so we don't leak internal details to the client
  if (status >= 500) {
    return { message: 'Something went wrong. Please try again later.' };
  }
  return { message };
};
