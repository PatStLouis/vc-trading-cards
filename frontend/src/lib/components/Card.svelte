<script lang="ts">
  import { spring } from 'svelte/motion';
  import { onMount } from 'svelte';
  import { activeCard } from '$lib/stores/activeCard';

  export let id = '';
  export let name = '';
  export let number = '';
  export let set = '';
  export let types: string | string[] = 'fighting';
  export let subtypes = 'trading-cards';
  export let supertype = 'trading-card';
  export let rarity = 'common';
  export let img = '';
  export let back = '/card-back.svg';

  const clamp = (v: number, min: number, max: number) => Math.min(Math.max(v, min), max);
  const round = (v: number) => Math.round(v);
  const adjust = (v: number, fromMin: number, fromMax: number, toMin: number, toMax: number) =>
    round(toMin + ((toMax - toMin) * (v - fromMin)) / (fromMax - fromMin));

  let thisCard: HTMLDivElement;
  let active = false;
  let interacting = false;
  let firstPop = true;
  let isVisible = true;

  const springOpts = { stiffness: 0.066, damping: 0.25 };
  const springPop = { stiffness: 0.033, damping: 0.45 };
  const springRotate = spring({ x: 0, y: 0 }, springOpts);
  const springGlare = spring({ x: 50, y: 50, o: 0 }, springOpts);
  const springBackground = spring({ x: 50, y: 50 }, springOpts);
  const springRotateDelta = spring({ x: 0, y: 0 }, springPop);
  const springTranslate = spring({ x: 0, y: 0 }, springPop);
  const springScale = spring(1, springPop);

  function updateSprings(background: { x: number; y: number }, rotate: { x: number; y: number }, glare: { x: number; y: number; o: number }) {
    springBackground.stiffness = springOpts.stiffness;
    springBackground.damping = springOpts.damping;
    springRotate.stiffness = springOpts.stiffness;
    springRotate.damping = springOpts.damping;
    springGlare.stiffness = springOpts.stiffness;
    springGlare.damping = springOpts.damping;
    springBackground.set(background);
    springRotate.set(rotate);
    springGlare.set(glare);
  }

  function interact(e: MouseEvent | TouchEvent) {
    if (!isVisible) return (interacting = false);
    if ($activeCard && $activeCard !== thisCard) return (interacting = false);
    interacting = true;
    const ev = e.type === 'touchmove' ? (e as TouchEvent).touches[0] : (e as MouseEvent);
    const rect = (e.target as HTMLElement).getBoundingClientRect();
    const absolute = { x: ev.clientX - rect.left, y: ev.clientY - rect.top };
    const percent = { x: clamp(round((100 / rect.width) * absolute.x), 0, 100), y: clamp(round((100 / rect.height) * absolute.y), 0, 100) };
    const center = { x: percent.x - 50, y: percent.y - 50 };
    updateSprings(
      { x: adjust(percent.x, 0, 100, 37, 63), y: adjust(percent.y, 0, 100, 33, 67) },
      { x: round(-(center.x / 3.5)), y: round(center.y / 2) },
      { x: round(percent.x), y: round(percent.y), o: 1 }
    );
  }

  function interactEnd(delay = 500) {
    setTimeout(() => {
      interacting = false;
      const s = 0.01, d = 0.06;
      springRotate.stiffness = s; springRotate.damping = d; springRotate.set({ x: 0, y: 0 }, { soft: true });
      springGlare.stiffness = s; springGlare.damping = d; springGlare.set({ x: 50, y: 50, o: 0 }, { soft: true });
      springBackground.stiffness = s; springBackground.damping = d; springBackground.set({ x: 50, y: 50 }, { soft: true });
    }, delay);
  }

  function setCenter() {
    if (!thisCard) return;
    const rect = thisCard.getBoundingClientRect();
    const view = document.documentElement;
    springTranslate.set({ x: round(view.clientWidth / 2 - rect.x - rect.width / 2), y: round(view.clientHeight / 2 - rect.y - rect.height / 2) });
  }

  function activate() {
    if ($activeCard === thisCard) {
      activeCard.set(null);
      retreat();
      return;
    }
    activeCard.set(thisCard);
    active = true;
    setCenter();
    const rect = thisCard.getBoundingClientRect();
    const scaleW = (window.innerWidth / rect.width) * 0.9;
    const scaleH = (window.innerHeight / rect.height) * 0.9;
    if (firstPop) {
      springRotateDelta.set({ x: 360, y: 0 });
      firstPop = false;
    }
    springScale.set(Math.min(scaleW, scaleH, 1.75));
    interactEnd(100);
  }

  function retreat() {
    active = false;
    springScale.set(1, { soft: true });
    springTranslate.set({ x: 0, y: 0 }, { soft: true });
    springRotateDelta.set({ x: 0, y: 0 }, { soft: true });
    interactEnd(100);
  }

  export { retreat };

  $: if ($activeCard === thisCard) {
    if (!active) {
      active = true;
      setCenter();
      const rect = thisCard?.getBoundingClientRect();
      if (rect) {
        const scaleW = (window.innerWidth / rect.width) * 0.9;
        const scaleH = (window.innerHeight / rect.height) * 0.9;
        springScale.set(Math.min(scaleW, scaleH, 1.75));
      }
      interactEnd(100);
    }
  } else if (active) {
    retreat();
  }

  $: dynamicStyles = `
    --pointer-x: ${$springGlare.x}%;
    --pointer-y: ${$springGlare.y}%;
    --pointer-from-center: ${$springGlare ? clamp(Math.sqrt(($springGlare.x - 50) ** 2 + ($springGlare.y - 50) ** 2) / 50, 0, 1) : 0};
    --pointer-from-top: ${$springGlare.y / 100};
    --pointer-from-left: ${$springGlare.x / 100};
    --card-opacity: ${$springGlare.o};
    --rotate-x: ${$springRotate.x + $springRotateDelta.x}deg;
    --rotate-y: ${$springRotate.y + $springRotateDelta.y}deg;
    --background-x: ${$springBackground.x}%;
    --background-y: ${$springBackground.y}%;
    --card-scale: ${$springScale};
    --translate-x: ${$springTranslate.x}px;
    --translate-y: ${$springTranslate.y}px;
  `;

  onMount(() => { isVisible = document.visibilityState === 'visible'; });
</script>

<div
  class="card {typesStr} interactive"
  class:active
  class:interacting
  data-id={id}
  data-number={numberStr}
  data-set={setStr}
  data-subtypes={subtypesStr}
  data-supertype={supertypeStr}
  data-rarity={rarityStr}
  data-trainer-gallery={false}
  style={dynamicStyles}
  bind:this={thisCard}
>
  <div class="card__translater">
    <button
      class="card__rotator"
      on:click={activate}
      on:pointermove={interact}
      on:mouseout={() => interactEnd()}
      on:blur={() => { if ($activeCard === thisCard) activeCard.set(null); interactEnd(); }}
      aria-label="Expand card: {name}"
      tabindex="0"
    >
      <img class="card__back" src={back} alt="Card back" loading="lazy" width="660" height="921" />
      <div class="card__front">
        {#if img}
          <img src={img} alt="{name}" loading="lazy" width="660" height="921" />
        {:else}
          <div class="card__placeholder"><span>{name}</span></div>
        {/if}
        <div class="card__shine"></div>
        <div class="card__glare"></div>
      </div>
    </button>
  </div>
</div>

<style>
  .card__placeholder {
    width: 100%;
    height: 100%;
    display: grid;
    place-items: center;
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    color: rgba(255,255,255,0.7);
    font-size: 0.9rem;
    padding: 1rem;
    text-align: center;
  }
</style>
