/// <reference types="@sveltejs/kit" />

declare global {
  namespace App {
    interface Error {
      message: string;
    }
    interface Locals {
      user?: { sub: string; username: string; wallet_id: string };
    }
    interface PageData {
      user?: { sub: string; username: string; wallet_id: string } | null;
    }
    interface PageState {}
    interface Platform {}
  }
}

export {};
