<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';

  let error = $state('');

  onMount(() => {
    const params = new URLSearchParams(window.location.search);
    error = params.get('error') || '';
  });

  function login() {
    window.location.href = '/auth/discord';
  }
</script>

<main class="landing">
  <header class="hero">
    <h1>VC Trading Cards</h1>
    <p class="tagline">Your verifiable credential trading cards in one place. Log in with Discord to browse your wallet.</p>
    {#if error}
      <p class="error">Login failed. Please try again.</p>
    {/if}
    <button class="btn btn-primary" onclick={login}>Log in with Discord</button>
  </header>
  <footer class="landing-footer">
    <p>Uses ACA-Py multitenancy. Each user gets their own wallet.</p>
  </footer>
</main>

<style>
  .landing {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 2rem;
  }
  .hero h1 {
    font-size: clamp(2rem, 5vw, 3rem);
    margin: 0 0 1rem;
    font-weight: 700;
  }
  .tagline {
    font-size: 1.1rem;
    color: var(--text-light);
    opacity: 0.9;
    max-width: 480px;
    margin: 0 auto 1.5rem;
    line-height: 1.5;
  }
  .error {
    color: #f44336;
    margin-bottom: 1rem;
  }
  .btn {
    padding: 0.75rem 1.5rem;
    font-size: 1rem;
    border-radius: 8px;
    border: none;
    cursor: pointer;
    font-weight: 600;
    transition: transform 0.2s, box-shadow 0.2s;
  }
  .btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
  }
  .btn-primary {
    background: #5865F2;
    color: white;
  }
  .btn-primary:hover {
    background: #4752c4;
  }
  .landing-footer {
    margin-top: auto;
    padding-top: 3rem;
    font-size: 0.875rem;
    opacity: 0.7;
  }
</style>
